from __future__ import annotations
import inspect
from datetime import datetime, timezone
from typing import Any
from tqdm.auto import tqdm
from utils.afm_utils import extract_afms
from utils.builders import (
    build_cid_spv_list,
    build_spv_account_map_and_requests,
)
from utils.registry_utils import get_category_metadata
from utils.routing_engine import pick_account_for_category
from data.saver import DataSaver


class ThreadProcessingError(ValueError):
    """Raised when a supplied email thread cannot be processed safely."""


class EmailProcessor:
    CONTINUITY_RELATIONS = {
        "continuation",
        "clarification",
        "confirmation",
        "follow_up",
        "same_request",
    }

    def __init__(
        self,
        registry_df,
        classifier,
        categories_data,
        reply_templates,
        forward_rules,
        default_reply,
        max_prior_messages: int = 8,
        max_context_characters: int = 24_000,
        max_characters_per_message: int = 6_000,
        sender_mailbox: str = "dovaluegreece@dovaluegreece.gr",
        attachment_processor=None,
    ):
        if max_prior_messages < 0:
            raise ValueError("max_prior_messages cannot be negative.")
        if max_context_characters < 0:
            raise ValueError("max_context_characters cannot be negative.")
        if max_characters_per_message < 0:
            raise ValueError("max_characters_per_message cannot be negative.")
        self.registry_df = registry_df
        self.classifier = classifier
        self.categories_data = categories_data
        self.reply_templates = reply_templates
        self.forward_rules = forward_rules
        self.default_reply = default_reply
        self.max_prior_messages = max_prior_messages
        self.max_context_characters = max_context_characters
        self.max_characters_per_message = max_characters_per_message
        self.sender_mailbox = sender_mailbox
        self.attachment_processor = attachment_processor

    # -----------------------------------------------------------
    # PROCESS SINGLE EMAIL or THREAD
    # -----------------------------------------------------------
    def process_email(self, email: dict[str, Any]) -> list[dict[str, Any]]:
        """
        If the email contains a 'conversation_thread' with more than one message,
        process as a thread. Otherwise, process as standalone.
        """
        self._validate_email(email)
        thread = self._get_thread_for_email(email)
        if thread is not None:
            return self.process_thread(messages=thread, target_message_id=email["id"])
        return self._process_target_email(
            target_email=email,
            prior_messages=[],
            thread_warnings=[],
            allow_context_afm=False,
            previous_thread_classification=None,
        )

    def _get_thread_for_email(
        self, email: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        """
        Returns the conversation thread messages if present and >1, else None.
        """
        thread = email.get("conversation_thread")
        if isinstance(thread, list) and len(thread) > 1:
            return thread
        return None

    # -----------------------------------------------------------
    # PROCESS EMAIL WITH THREAD CONTEXT
    # -----------------------------------------------------------
    def process_thread(
        self,
        messages: list[dict[str, Any]],
        target_message_id: str,
        previous_thread_classification: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        target_email, prior_messages, warnings = self._prepare_thread(
            messages=messages,
            target_message_id=target_message_id,
        )
        selected_context, context_warnings = self._select_context_messages(
            prior_messages
        )
        warnings.extend(context_warnings)
        return self._process_target_email(
            target_email=target_email,
            prior_messages=selected_context,
            thread_warnings=warnings,
            allow_context_afm=True,
            previous_thread_classification=previous_thread_classification,
        )

    # -----------------------------------------------------------
    # PROCESS MULTIPLE EMAILS (BATCH)
    # -----------------------------------------------------------
    def process_batch(
        self,
        emails: list[dict[str, Any]],
        export: bool = True,
        use_thread_context: bool = True,
    ) -> list[dict[str, Any]]:
        """
        For each email, if it has conversation_thread, process as thread.
        Otherwise, batch logic as before.
        """
        if not isinstance(emails, list):
            raise TypeError("emails must be a list of email dictionaries.")
        all_results: list[dict[str, Any]] = []
        processed_ids = set()

        for email in tqdm(
            emails,
            desc="Processing emails",
            unit="email",
            dynamic_ncols=True,
        ):
            self._validate_email(email)
            if email["id"] in processed_ids:
                continue  # Avoid duplicate processing
            thread = self._get_thread_for_email(email)
            if thread is not None and use_thread_context:
                # Use the thread, mark all ids as processed
                results = self.process_thread(
                    messages=thread, target_message_id=email["id"]
                )
                all_results.extend(results)
                for msg in thread:
                    if "id" in msg:
                        processed_ids.add(msg["id"])
            else:
                if not use_thread_context:
                    results = self.process_email(email)
                    all_results.extend(results)
                    processed_ids.add(email["id"])
                else:
                    # Fallback: group by conversationId
                    conversation_id = email.get("conversationId")
                    if conversation_id:
                        group = [
                            e
                            for e in emails
                            if e.get("conversationId") == conversation_id
                        ]
                        if len(group) > 1:
                            results = self.process_thread(
                                messages=group, target_message_id=email["id"]
                            )
                            all_results.extend(results)
                            for msg in group:
                                if "id" in msg:
                                    processed_ids.add(msg["id"])
                        else:
                            results = self.process_email(email)
                            all_results.extend(results)
                            processed_ids.add(email["id"])
                    else:
                        results = self.process_email(email)
                        all_results.extend(results)
                        processed_ids.add(email["id"])
        if export:
            DataSaver.save_json(all_results)
            DataSaver.save_excel(all_results)
        return all_results

    # -----------------------------------------------------------
    # CORE TARGET PROCESSING
    # -----------------------------------------------------------
    def _process_target_email(
        self,
        target_email: dict[str, Any],
        prior_messages: list[dict[str, Any]],
        thread_warnings: list[str],
        allow_context_afm: bool,
        previous_thread_classification: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        mail_id = target_email.get("id")
        conversation_id = target_email.get("conversationId")
        sender = self._get_sender_address(target_email)
        subject = target_email.get("subject") or ""
        body = self._get_message_body(target_email)
        received = target_email.get("receivedDateTime") or ""
        attachment_bundle = self._process_attachments(target_email)
        body_afms = list(dict.fromkeys(extract_afms(f"{subject} {body}")))
        attachment_afms = list(
            dict.fromkeys(attachment_bundle.get("extracted_afms", []) or [])
        )
        target_afms = list(dict.fromkeys([*body_afms, *attachment_afms]))
        thread_warnings.extend(attachment_bundle.get("warnings", []))

        # Always classify so attachment summaries can support the category,
        # including when neither the email body nor attachments contain an AFM.
        classification, context_applied = self._classify_target(
            target_email=target_email,
            prior_messages=prior_messages,
            previous_thread_classification=previous_thread_classification,
            attachment_bundle=attachment_bundle,
        )
        base_category = (
            classification.get("Category")
            or classification.get("category")
            or "UNKNOWN"
        )
        base_confidence = (
            classification.get("Confidence")
            if "Confidence" in classification
            else classification.get("confidence", 0)
        )
        base_matched_rules = (
            classification.get("Matched_Rules")
            if "Matched_Rules" in classification
            else classification.get("matched_rules", [])
        ) or []
        base_reasoning = (
            classification.get("Reasoning") or classification.get("reasoning") or ""
        )
        thread_relation = self._extract_thread_relation(
            classification=classification,
            has_context=bool(prior_messages),
        )
        context_message_ids = [
            message.get("Message_ID") or message.get("id")
            for message in prior_messages
            if message.get("Message_ID") or message.get("id")
        ]

        if not target_afms and not prior_messages:
            return self._with_model_signals([
                self._build_no_afm_record(
                    mail_id=mail_id,
                    conversation_id=conversation_id,
                    sender=sender,
                    received=received,
                    subject=subject,
                    classification=classification,
                    thread_relation=thread_relation,
                    context_message_ids=context_message_ids,
                    context_applied=context_applied,
                    thread_warnings=thread_warnings,
                    attachment_bundle=attachment_bundle,
                )
            ], classification)

        afms = list(target_afms)
        afm_source = None
        afm_source_message_id = mail_id if afms else None

        if (
            not afms
            and allow_context_afm
            and thread_relation in self.CONTINUITY_RELATIONS
        ):
            afms, afm_source_message_id = self._find_nearest_context_afms(
                prior_messages
            )
            if afms:
                afm_source = "thread_context"
                thread_warnings.append(
                    "The target contained no AFM. AFM information was "
                    "inherited from the nearest applicable prior message."
                )
        results: list[dict[str, Any]] = []
        for afm in afms:
            if afm in attachment_afms:
                current_afm_source = "target_attachment"
            elif afm in body_afms:
                current_afm_source = "target_body"
            else:
                current_afm_source = afm_source

            results.extend(
                self._process_afm_record(
                    afm=afm,
                    mail_id=mail_id,
                    conversation_id=conversation_id,
                    sender=sender,
                    received=received,
                    subject=subject,
                    body=body,
                    base_category=base_category,
                    base_confidence=base_confidence,
                    base_matched_rules=base_matched_rules,
                    base_reasoning=base_reasoning,
                    thread_relation=thread_relation,
                    context_message_ids=context_message_ids,
                    context_applied=context_applied,
                    thread_warnings=thread_warnings,
                    afm_source=current_afm_source,
                    afm_source_message_id=afm_source_message_id,
                    attachment_bundle=attachment_bundle,
                )
            )
        return self._with_model_signals(results, classification)

    @staticmethod
    def _with_model_signals(
        records: list[dict[str, Any]], classification: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Carry the vote split and the model's own review flag onto every record."""
        votes = dict(classification.get("Category_Votes") or {})
        others = dict(classification.get("Other_Category_Confidence") or {})
        needs_review = bool(classification.get("Needs_Review", False))
        for record in records:
            record["model_votes"] = votes
            record["model_other_categories"] = others
            record["model_needs_review"] = needs_review
        return records

    # -----------------------------------------------------------
    # THREAD PREPARATION
    # -----------------------------------------------------------
    def _prepare_thread(
        self,
        messages: list[dict[str, Any]],
        target_message_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[str],
    ]:
        if not target_message_id:
            raise ThreadProcessingError("target_message_id must be provided.")
        if not isinstance(messages, list) or not messages:
            raise ThreadProcessingError("Thread messages must be a non-empty list.")
        invalid_positions = [
            index
            for index, message in enumerate(messages)
            if not isinstance(message, dict)
        ]
        if invalid_positions:
            raise ThreadProcessingError(
                "Every thread item must be an email dictionary. "
                f"Invalid positions: {invalid_positions}"
            )
        target_matches = [
            (index, message)
            for index, message in enumerate(messages)
            if message.get("id") == target_message_id
        ]
        if not target_matches:
            raise ThreadProcessingError(
                f"Target message {target_message_id!r} was not found "
                "in the supplied thread."
            )
        if len(target_matches) > 1:
            raise ThreadProcessingError(
                f"Target message {target_message_id!r} appears more "
                "than once in the supplied thread."
            )
        target_original_index, target_email = target_matches[0]
        self._validate_email(target_email)
        target_conversation_id = target_email.get("conversationId")
        warnings: list[str] = []
        eligible_messages: list[tuple[int, dict[str, Any]]] = []
        excluded_conversation_count = 0
        for original_index, message in enumerate(messages):
            message_conversation_id = message.get("conversationId")
            if (
                target_conversation_id
                and message_conversation_id
                and message_conversation_id != target_conversation_id
            ):
                excluded_conversation_count += 1
                continue
            eligible_messages.append((original_index, message))
        if excluded_conversation_count:
            warnings.append(
                f"{excluded_conversation_count} message(s) with a different "
                "conversationId were excluded from thread context."
            )
        ordered_messages = sorted(
            eligible_messages,
            key=lambda item: self._thread_sort_key(
                message=item[1],
                original_index=item[0],
            ),
        )
        target_position = next(
            index
            for index, (original_index, _) in enumerate(ordered_messages)
            if original_index == target_original_index
        )
        prior_messages = [message for _, message in ordered_messages[:target_position]]
        later_messages = ordered_messages[target_position + 1 :]
        if later_messages:
            warnings.append(
                f"{len(later_messages)} message(s) occurring after the "
                "target were excluded to prevent future-context leakage."
            )
        return target_email, prior_messages, warnings

    def _select_context_messages(
        self,
        prior_messages: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        if not prior_messages or self.max_prior_messages == 0:
            return [], warnings
        meaningful_messages = [
            message
            for message in prior_messages
            if (
                (message.get("subject") or "").strip()
                or self._get_message_body(message).strip()
            )
        ]
        if not meaningful_messages:
            warnings.append(
                "Prior messages were present, but none contained a "
                "meaningful subject or body."
            )
            return [], warnings
        first_message = meaningful_messages[0]
        recent_messages = meaningful_messages[-self.max_prior_messages :]
        candidates: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for message in [first_message, *recent_messages]:
            message_id = message.get("id")
            uniqueness_key = message_id or f"object:{id(message)}"
            if uniqueness_key in seen_ids:
                continue
            seen_ids.add(uniqueness_key)
            candidates.append(message)
        candidates.sort(
            key=lambda message: self._thread_sort_key(
                message=message,
                original_index=prior_messages.index(message),
            )
        )
        selected: list[dict[str, Any]] = []
        remaining_characters = self.max_context_characters
        origin = candidates[0]
        prepared_origin = self._prepare_context_message(
            origin,
            remaining_characters,
        )
        if prepared_origin is not None:
            selected.append(prepared_origin)
            remaining_characters -= self._context_message_size(prepared_origin)
        recent_candidates = [message for message in candidates[1:]]
        selected_recent: list[dict[str, Any]] = []
        for message in reversed(recent_candidates):
            prepared_message = self._prepare_context_message(
                message,
                remaining_characters,
            )
            if prepared_message is None:
                warnings.append(
                    "Part of the older thread was omitted because the "
                    "historical context budget was reached."
                )
                continue
            selected_recent.append(prepared_message)
            remaining_characters -= self._context_message_size(prepared_message)
        selected_recent.reverse()
        selected.extend(selected_recent)
        if len(meaningful_messages) > len(selected):
            warnings.append(
                "Not all prior messages were included in classifier context."
            )
        return selected, self._deduplicate_strings(warnings)

    def _prepare_current_message(
        self,
        message: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "Message_ID": message.get("id"),
            "Sender_Type": self._resolve_sender_type(message),
            "Sender_Address": self._get_sender_address(message),
            "Sent_At": (
                message.get("sentDateTime") or message.get("receivedDateTime") or ""
            ),
            "Subject": message.get("subject") or "",
            "Body": self._get_message_body(message),
            "Has_Attachments": bool(message.get("hasAttachments", False)),
        }

    def _prepare_context_message(
        self,
        message: dict[str, Any],
        available_characters: int,
    ) -> dict[str, Any] | None:
        if available_characters <= 0:
            return None
        sender_type = self._resolve_sender_type(message)
        subject = message.get("subject") or ""
        body = self._get_message_body(message)
        remaining = max(0, available_characters - len(sender_type))
        bounded_subject = subject[:remaining]
        remaining -= len(bounded_subject)
        body_limit = min(self.max_characters_per_message, remaining)
        bounded_body = body[:body_limit]
        prepared_message = {
            "Message_ID": message.get("id"),
            "Sender_Type": sender_type,
            "Sent_At": (
                message.get("sentDateTime") or message.get("receivedDateTime") or ""
            ),
            "Subject": bounded_subject,
            "Body": bounded_body,
            "Has_Attachments": bool(message.get("hasAttachments", False)),
        }
        if not prepared_message["Subject"] and not prepared_message["Body"]:
            return None
        return prepared_message

    # -----------------------------------------------------------
    # CLASSIFIER INVOCATION
    # -----------------------------------------------------------
    def _classify_target(
        self,
        target_email: dict[str, Any],
        prior_messages: list[dict[str, Any]],
        previous_thread_classification: dict[str, Any] | None,
        attachment_bundle: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        subject = target_email.get("subject") or ""
        body = self._get_message_body(target_email)
        classify_method = self.classifier.classify
        signature = inspect.signature(classify_method)
        parameters = signature.parameters
        supports_thread_context = "thread_context" in parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        if supports_thread_context:
            thread_context = {
                "Thread_ID": target_email.get("conversationId") or "",
                "Thread_Subject": self._resolve_thread_subject(
                    target_email=target_email,
                    prior_messages=prior_messages,
                ),
                "Current_Message": self._prepare_current_message(target_email),
                "Previous_Messages": prior_messages,
                "Previous_Thread_Classification": (previous_thread_classification),
            }
            result = classify_method(
                subject,
                body,
                self.categories_data,
                thread_context=thread_context,
                attachment_context=attachment_bundle,
            )
            context_applied = bool(prior_messages or previous_thread_classification)
        else:
            result = classify_method(
                subject,
                body,
                self.categories_data,
                attachment_context=attachment_bundle,
            )
            context_applied = False
        if not isinstance(result, dict):
            raise TypeError("classifier.classify() must return a dictionary.")
        return result, context_applied

    # -----------------------------------------------------------
    # AFM RESOLUTION
    # -----------------------------------------------------------
    def _find_nearest_context_afms(
        self,
        prior_messages: list[dict[str, Any]],
    ) -> tuple[list[str], str | None]:
        for message in reversed(prior_messages):
            subject = message.get("Subject") or message.get("subject") or ""
            body = message.get("Body") or message.get("body") or ""
            afms = extract_afms(f"{subject} {body}")
            if afms:
                message_id = message.get("Message_ID") or message.get("id")
                return list(afms), message_id
        return [], None

    # -----------------------------------------------------------
    # RECORD BUILDERS
    # -----------------------------------------------------------
    def _build_no_afm_record(
        self,
        mail_id,
        conversation_id,
        sender,
        received,
        subject,
        classification,
        thread_relation,
        context_message_ids,
        context_applied,
        thread_warnings,
        attachment_bundle=None,
    ) -> dict[str, Any]:
        classification = classification or {}
        category = (
            classification.get("Category")
            or classification.get("category")
            or "No Match Found"
        )

        confidence = (
            classification.get("Confidence")
            if "Confidence" in classification
            else classification.get("confidence", 0)
        )
        matched_rules = (
            classification.get("Matched_Rules")
            if "Matched_Rules" in classification
            else classification.get("matched_rules", [])
        ) or []
        reasoning = (
            classification.get("Reasoning") or classification.get("reasoning") or ""
        )
        provisional_routing_mode = self._resolve_routing_mode(category)
        return {
            "id": mail_id,
            "conversationId": conversation_id,
            "from": self.sender_mailbox,
            "to": sender,
            "received": received,
            "subject": subject,
            "afm": None,
            "afm_source": None,
            "afm_source_message_id": None,
            "tax_id_found_in_attachment": False,
            "identification_verified": False,
            "identification_verification_source": None,
            "status": "needs_identification",
            "category": category,
            "confidence": self._format_confidence(confidence),
            "matched_rules": matched_rules,
            "reasoning": reasoning,
            "CID_SPV_LIST": None,
            "SPV_ACCOUNT_MAP": None,
            "request_codes": [],
            "reply_text": self.reply_templates.get(
                "NEEDS_IDENTIFICATION",
                self.default_reply,
            ),
            "routing_mode": "NONE",
            "provisional_routing_mode": provisional_routing_mode,
            "routing_ready": False,
            "thread_relation": thread_relation,
            "context_message_ids": context_message_ids,
            "thread_context_applied": context_applied,
            "thread_warnings": self._deduplicate_strings(thread_warnings),
            "model_category": (
                classification.get("Category")
                or classification.get("category")
                or "No Match Found"
            ),
            "model_confidence": self._normalize_confidence(confidence),
            "model_matched_rules": matched_rules,
            "model_reasoning": reasoning,
            **self._attachment_output_fields(attachment_bundle),
        }

    def _process_afm_record(
        self,
        afm,
        mail_id,
        conversation_id,
        sender,
        received,
        subject,
        body,
        base_category,
        base_confidence,
        base_matched_rules,
        base_reasoning,
        thread_relation,
        context_message_ids,
        context_applied,
        thread_warnings,
        afm_source,
        afm_source_message_id,
        attachment_bundle=None,
    ) -> list[dict[str, Any]]:
        del body  # Retained in the interface for future rule requirements.
        rows_for_afm = self.registry_df[self.registry_df["TAX_ID_NO"] == afm]
        common_metadata = {
            "id": mail_id,
            "conversationId": conversation_id,
            "from": self.sender_mailbox,
            "to": sender,
            "received": received,
            "subject": subject,
            "afm": afm,
            "afm_source": afm_source,
            "afm_source_message_id": afm_source_message_id,
            "tax_id_found_in_attachment": afm_source == "target_attachment",
            "identification_verified": afm_source
            in {"target_body", "target_attachment", "thread_context"},
            "identification_verification_source": afm_source,
            "thread_relation": thread_relation,
            "context_message_ids": context_message_ids,
            "thread_context_applied": context_applied,
            "thread_warnings": self._deduplicate_strings(thread_warnings),
            "model_category": base_category,
            "model_confidence": self._normalize_confidence(base_confidence),
            "model_matched_rules": list(base_matched_rules),
            "model_reasoning": base_reasoning,
            **self._attachment_output_fields(attachment_bundle),
        }
        # Rule 1: Datamart -> ERB
        if not rows_for_afm.empty and (rows_for_afm["SOURCE"] == "Datamart").any():
            return [
                {
                    **common_metadata,
                    "status": "erb_datamart",
                    "category": "ERB",
                    "confidence": "100%",
                    "matched_rules": ["DATAMART_ERB"],
                    "reasoning": (
                        "The AFM has at least one registry row whose "
                        "SOURCE is Datamart."
                    ),
                    "CID_SPV_LIST": build_cid_spv_list(rows_for_afm),
                    "SPV_ACCOUNT_MAP": None,
                    "request_codes": [],
                    "reply_text": self.reply_templates.get(
                        "ERB",
                        self.default_reply,
                    ),
                    "routing_mode": "ERB",
                    "provisional_routing_mode": "ERB",
                    "routing_ready": True,
                }
            ]
        # Rule 2: Special handling for 3869
        priority_categories = {
            "Νομιμοποίηση κληρονόμων με επισύναψη εγγράφων",
            "Εξουσιοδοτήσεις",
            "Ασφαλιστήρια",
        }
        is_3869 = (
            not rows_for_afm.empty
            and rows_for_afm["CST_STS_NM"]
            .str.contains("3869", case=False, na=False)
            .any()
        )
        if is_3869 and base_category not in priority_categories:
            category = "Αιτήματα Ν.3869"
            confidence = 1.0
            matched_rules = ["FORCED_3869"]
            reasoning = "Detected 3869 from registry."
        else:
            category = base_category
            confidence = base_confidence
            matched_rules = base_matched_rules
            reasoning = base_reasoning
        # Rule 3: Forwarding
        if category in self.forward_rules:
            rule = self.forward_rules[category]
            forward_to = list(rule.get("forward_to", []))
            return [
                {
                    **common_metadata,
                    "status": "forwarded",
                    "category": category,
                    "confidence": self._format_confidence(confidence),
                    "matched_rules": matched_rules,
                    "reasoning": reasoning,
                    "CID_SPV_LIST": None,
                    "SPV_ACCOUNT_MAP": None,
                    "request_codes": [],
                    "reply_text": None,
                    "routing_mode": rule.get(
                        "routing_mode",
                        "FORWARD",
                    ),
                    "provisional_routing_mode": rule.get(
                        "routing_mode",
                        "FORWARD",
                    ),
                    "routing_ready": True,
                    "forward_to": forward_to,
                }
            ]
        # Rule 4: Routing

        get_category_metadata(
            category,
            self.categories_data,
        )

        routing_mode = self._resolve_routing_mode(category)
        status = "verified" if not rows_for_afm.empty else "needs_review"
        cid_spv_list = build_cid_spv_list(rows_for_afm)
        (
            spv_account_map,
            request_codes,
        ) = build_spv_account_map_and_requests(
            rows_for_afm,
            category,
            pick_account_for_category,
        )
        return [
            {
                **common_metadata,
                "status": status,
                "category": category,
                "confidence": self._format_confidence(confidence),
                "matched_rules": matched_rules,
                "reasoning": reasoning,
                "CID_SPV_LIST": cid_spv_list,
                "SPV_ACCOUNT_MAP": spv_account_map,
                "request_codes": request_codes,
                "reply_text": self.reply_templates.get(
                    category,
                    self.default_reply,
                ),
                "routing_mode": routing_mode,
                "provisional_routing_mode": routing_mode,
                "routing_ready": status == "verified",
            }
        ]

    # -----------------------------------------------------------
    # ATTACHMENT PROCESSING
    # -----------------------------------------------------------
    def _process_attachments(self, email: dict[str, Any]) -> dict[str, Any]:
        if self.attachment_processor is None:
            return {
                "total": 0,
                "processed": 0,
                "relevant": 0,
                "failed_or_unsupported": 0,
                "ignored_inline": 0,
                "requires_review": False,
                "warnings": [],
                "extracted_afms": [],
                "evidence_text": "",
                "records": [],
            }
        return self.attachment_processor.process_email_attachments(
            email, self.categories_data
        )

    @staticmethod
    def _attachment_output_fields(bundle) -> dict[str, Any]:
        bundle = bundle or {}
        return {
            "attachment_count": bundle.get("total", 0),
            "attachment_processed_count": bundle.get("processed", 0),
            "attachment_relevant_count": bundle.get("relevant", 0),
            "attachment_failed_count": bundle.get("failed_or_unsupported", 0),
            "attachment_requires_review": bool(bundle.get("requires_review", False)),
            "attachment_warnings": bundle.get("warnings", []),
            "attachment_extracted_afms": bundle.get("extracted_afms", []),
            "attachment_evidence_text": bundle.get("evidence_text", ""),
            "attachment_summaries": [
                {
                    "filename": record.get("filename"),
                    "document_type": record.get("document_type"),
                    "relevance": record.get("relevance"),
                    "summary": record.get("summary", ""),
                }
                for record in bundle.get("records", [])
                if record.get("status") == "ANALYZED"
            ],
            "attachment_records": bundle.get("records", []),
        }

    # -----------------------------------------------------------
    # GENERAL HELPERS
    # -----------------------------------------------------------
    def _resolve_routing_mode(self, category: str) -> str:
        category_meta = (
            get_category_metadata(
                category,
                self.categories_data,
            )
            or {}
        )
        routing_hint = (
            (category_meta.get("Παραπομπές wizard/portal") or "").strip().upper()
        )
        # The e-wizard is discontinued: its categories are handled internally.
        if routing_hint == "PORTAL":
            return "PORTAL"
        return "INTERNAL"

    @staticmethod
    def _validate_email(email: dict[str, Any]) -> None:
        if not isinstance(email, dict):
            raise TypeError("Email must be supplied as a dictionary.")
        if not email.get("id"):
            raise ValueError("Email is missing its required 'id' field.")

    @staticmethod
    def _get_sender_address(email: dict[str, Any]) -> str:
        sender = email.get("from") or {}
        email_address = sender.get("emailAddress") or {}
        return email_address.get("address") or ""

    @staticmethod
    def _get_message_body(email: dict[str, Any]) -> str:
        body = email.get("body") or {}
        if not isinstance(body, dict):
            return str(body or "")
        return body.get("body_clean") or body.get("content") or ""

    @staticmethod
    def _parse_received_datetime(value: Any) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None

    def _resolve_sender_type(
        self,
        message: dict[str, Any],
    ) -> str:
        sender = self._get_sender_address(message).strip().lower()
        if not sender:
            return "Unknown"
        monitored_mailbox = self.sender_mailbox.strip().lower()
        if sender == monitored_mailbox:
            return "Agent"
        if sender.endswith("@dovaluegreece.gr"):
            return "Internal"
        return "Customer"

    def _resolve_thread_subject(
        self,
        target_email: dict[str, Any],
        prior_messages: list[dict[str, Any]],
    ) -> str:
        target_subject = (target_email.get("subject") or "").strip()
        if target_subject:
            return target_subject
        for message in reversed(prior_messages):
            previous_subject = (message.get("subject") or "").strip()
            if previous_subject:
                return previous_subject
        return ""

    def _thread_sort_key(
        self,
        message: dict[str, Any],
        original_index: int,
    ) -> tuple[int, datetime, int]:
        parsed_datetime = self._parse_received_datetime(
            message.get("sentDateTime") or message.get("receivedDateTime")
        )
        if parsed_datetime is None:
            return (
                1,
                datetime.max.replace(tzinfo=timezone.utc),
                original_index,
            )
        return 0, parsed_datetime, original_index

    @staticmethod
    def _extract_thread_relation(
        classification: dict[str, Any],
        has_context: bool,
    ) -> str:
        raw_relation = classification.get("Thread_Relation") or classification.get(
            "thread_relation"
        )
        if raw_relation is None:
            return "unknown" if has_context else "standalone"
        normalized = str(raw_relation).strip().lower()
        normalized = normalized.replace("-", "_").replace(" ", "_")
        return normalized or ("unknown" if has_context else "standalone")

    @staticmethod
    def _classification_state_from_results(
        results: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Build the previous valid thread state from processed records."""
        if not results:
            return None
        record = results[0]
        category = record.get("model_category")
        if not category:
            return None
        return {
            "Category": category,
            "Confidence": record.get("model_confidence", 0.0),
            "Matched_Rules": record.get("model_matched_rules", []) or [],
            "Reasoning": record.get("model_reasoning", "") or "",
            "Thread_Relation": record.get(
                "thread_relation",
                "unknown",
            ),
        }

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.endswith("%"):
                normalized = normalized[:-1].strip()
                try:
                    percentage = float(normalized)
                except ValueError:
                    return 0.0
                return max(0.0, min(1.0, percentage / 100.0))
            try:
                numeric_value = float(normalized)
            except ValueError:
                return 0.0
        else:
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                return 0.0
        if numeric_value > 1:
            numeric_value /= 100.0
        return max(0.0, min(1.0, numeric_value))

    @classmethod
    def _format_confidence(cls, value: Any) -> str:
        normalized = cls._normalize_confidence(value)
        return f"{round(normalized * 100)}%"

    @staticmethod
    def _context_message_size(
        message: dict[str, Any],
    ) -> int:
        return (
            len(message.get("Sender_Type") or "")
            + len(message.get("Subject") or "")
            + len(message.get("Body") or "")
        )

    @staticmethod
    def _deduplicate_strings(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))
