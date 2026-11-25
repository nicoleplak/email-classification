"""Turn what an email asks plus who the customer is into actions, using inputs/action_rules.json.

Rule of thumb: the model answers questions about the email (FLAGS), the registry answers questions
about the customer (customer). This module only combines them, in this order (business rules, Nov 2026):

1. Requests: the principal request first, then the others by category Priority (1 = most important).
   A complaint ("Παράπονα") is never first when the email also asks for something else
   (``order_requests``).
2. Rules: every rule of the category whose ``when`` holds fires; a rule without ``when`` always fires;
   ``else`` fires when none of the others did.
3. Portal: for a Portal category (Παραπομπές portal = YES) the customer with the Portal flag gets the
   Portal reply instead of a request, unless they report a technical problem with the Portal.
4. Identification: only a tax ID or an account number identifies the customer (core.customer_lookup).
5. Account: the category says how the Qualco account is chosen (``select_accounts``):
   - per_spv  one request per portfolio (SPV) of the customer, on one of its accounts, unless the
              email names specific accounts;
   - account  the account must be identified: named in the email, the customer's only account, or
              every account when the email concerns all debts; otherwise "Need more Info";
   - spv      one request on one account of the identified SPV: from a named account, the only SPV,
              or every SPV when the email concerns all debts; otherwise "Need more Info".
6. Code: the open-case request (without _cust); the closed-case _cust request only for an account the
   registry marks closed (that column is not delivered yet, see core.customer_lookup.account_state).
   Each request is followed by its Qualco activity on the same account (``with_activities``, sheet
   'Activities'). A category whose Portal column names requests ('YES for Request 113') sends only those
   to the Portal (``portal_eligible``).
7. Reply: one template per email (inputs/reply_templates.json): Need more Info, Portal, ERB branch, or
   the category's Received / In Progress template once something was done.

Further requests: a second or third category the classifier finds with 80% certainty or more
(``extra_categories``) is added on its own, with its actions, like a request the reader found.

Each action records why it was chosen in ``because``; ``explain`` turns that into Greek.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

INPUTS = Path(__file__).resolve().parents[1] / "inputs"


def _load(name: str) -> dict:
    return json.loads((INPUTS / name).read_text(encoding="utf-8"))


RULES = {k: v for k, v in _load("action_rules.json").items() if not k.startswith("_")}
QUALCO = _load("qualco_requests.json")
REPLIES = _load("reply_templates.json")
PRIORITY = {
    c["Categories"].strip(): float(c["Priority"]) if c.get("Priority") not in (None, "") else 3.0
    for c in _load("categories.json")
}
COMPLAINTS = ("Παράπονα",)  # never the principal request when the email asks for something else
REPLY_KINDS = ("reply", "portal_referral", "bank_referral", "ask_identification")

# What the model reports about the email. Definitions live next to the values so
# the prompt and the rule table cannot drift apart.
FLAGS = {
    "cannot_use_online": "Reports a technical problem with the Portal: cannot log in, cannot submit or download there, or returns saying the Portal referral did not work",
    "is_heir": "Writes as heir of a deceased debtor",
    "wants_breakdown": "Asks for a debt certificate WITH an analysis/breakdown of the debt",
    "decision_3869_attached": "Sends the court decision of law 3869",
    "asks_instalment": "Asks what instalment they must pay",
    "asks_payment_history": "Asks for a certificate of payments made / compliance with the court settlement",
    "asks_debt_certificate": "Asks for a debt certificate",
    "asks_reversal": "Asks for a reversal of a payment (αντιλογισμός)",
    "disputes_debt": "Disputes the debt or the charges",
    "areios_pagos_decision": "Concerns a decision of the Supreme Court (Άρειος Πάγος)",
    "asks_source_of_funds": "Asks for a certificate for 'πόθεν έσχες'",
    "asks_schedule": "Asks for the instalment schedule (δοσολόγιο) of law 4738",
    "insurance_replacement": "Submits a replacement insurance policy (not a renewal)",
    "insurance_info": "Asks for information about a fire/earthquake policy",
    "insurance_compensation": "Concerns an insurance compensation",
    "release_partial": "Asks for a PARTIAL release of a pre-notation (μερική άρση)",
    "auction_imminent": "An auction is imminent: today, tomorrow or within a week",
    "asks_negotiation": "Asks doValue to contact them to negotiate",
    "auction_cancel_4738": "Asks to cancel an auction because of law 4738",
    "health_data": "The request relies on health data",
    "health_doc_attached": "A signed solemn declaration (Υ/Δ) accompanies the health data",
    "reversal_form_attached": "The completed reversal form is attached",
    "call_preservation": "Asks to PRESERVE recorded calls older than a year (not to receive copies)",
    "all_debts": "The request concerns ALL of the customer's loans or debts (όλες τις οφειλές / όλα τα δάνεια), not one account",
    "distress_or_threat": "Mentions self-harm or suicide (αυτοχειρία, αυτοκτονία), or threatens legal action against doValue (μήνυση)",
}

# Why an action fired, in words a reviewer can check against the email.
# Conditions read "<fact>=true" or "<fact>=false"; the rest are decision steps.
REASONS = {
    "decision_3869_attached=true": "Το email επισυνάπτει την απόφαση του Ν.3869.",
    "asks_instalment=true": "Ο αποστολέας ρωτά ποια δόση πρέπει να πληρώσει.",
    "asks_payment_history=true": "Ζητά βεβαίωση καταβολών ή τήρησης της δικαστικής ρύθμισης.",
    "asks_debt_certificate=true": "Ζητά βεβαίωση οφειλής.",
    "asks_reversal=true": "Ζητά αντιλογισμό πληρωμής.",
    "disputes_debt=true": "Αμφισβητεί την οφειλή ή τις χρεώσεις.",
    "areios_pagos_decision=true": "Αφορά απόφαση του Αρείου Πάγου.",
    "asks_source_of_funds=true": "Ζητά βεβαίωση για το πόθεν έσχες.",
    "asks_schedule=true": "Ζητά το δοσολόγιο του Ν.4738.",
    "registry_3869=true": "Στο μητρώο ο πελάτης είναι στον Ν.3869.",
    "registry_3869=false": "Στο μητρώο ο πελάτης δεν είναι στον Ν.3869.",
    "reversal_form_attached=true": "Έχει επισυνάψει τη φόρμα αντιλογισμού.",
    "reversal_form_attached=false": "Δεν έχει επισυνάψει τη φόρμα αντιλογισμού, οπότε του τη στέλνουμε για συμπλήρωση.",
    "insurance_replacement=true": "Στέλνει ασφαλιστήριο αντικατάστασης, όχι ανανέωση.",
    "insurance_info=true": "Ζητά πληροφορίες για ασφαλιστήριο πυρός ή σεισμού.",
    "insurance_compensation=true": "Αφορά ασφαλιστική αποζημίωση.",
    "is_heir=true": "Γράφει ως κληρονόμος αποβιώσαντος οφειλέτη.",
    "is_heir=false": "Δεν γράφει ως κληρονόμος.",
    "wants_breakdown=true": "Ζητά και ανάλυση της οφειλής.",
    "wants_breakdown=false": "Δεν ζητά ανάλυση της οφειλής.",
    "release_partial=true": "Ζητά μερική άρση προσημείωσης.",
    "erb=true": "Η υπόθεση ανήκει στην ERB, οπότε το χειρίζεται η τράπεζα.",
    "erb=false": "Η υπόθεση δεν ανήκει στην ERB.",
    "call_preservation=true": "Ζητά να διατηρηθούν κλήσεις παλαιότερες του ενός έτους.",
    "asks_negotiation=true": "Ζητά να επικοινωνήσουμε μαζί του για διαπραγμάτευση.",
    "auction_imminent=true": "Ο πλειστηριασμός είναι επικείμενος, μέσα στην εβδομάδα.",
    "auction_cancel_4738=true": "Ζητά ακύρωση πλειστηριασμού λόγω Ν.4738.",
    "health_data=true": "Το αίτημα στηρίζεται σε δεδομένα υγείας.",
    "health_data=false": "Το αίτημα δεν στηρίζεται σε δεδομένα υγείας.",
    "health_doc_attached=true": "Συνοδεύεται από υπογεγραμμένη υπεύθυνη δήλωση.",
    "health_doc_attached=false": "Δεν συνοδεύεται από υπογεγραμμένη υπεύθυνη δήλωση, οπότε ζητούμε να τη στείλει.",
    "else": "Δεν ισχύει καμία από τις ειδικές περιπτώσεις της κατηγορίας, οπότε εφαρμόζεται ο γενικός κανόνας.",
    "category_rule": "Για αυτή την κατηγορία η προδιαγραφή ορίζει πάντα αυτή την ενέργεια.",
    "has_portal": "Ο πελάτης έχει πρόσβαση στο Portal και αυτό το αίτημα γίνεται εκεί, οπότε του απαντάμε να το κάνει από το Portal.",
    "no_portal": "Ο πελάτης δεν έχει πρόσβαση στο Portal, οπότε το αίτημα το καταχωρούμε εμείς.",
    "unidentified_online": "Το email δεν ταυτοποιεί τον πελάτη, αλλά το αίτημα γίνεται online, οπότε τον παραπέμπουμε στο Portal.",
    "cannot_use_online": "Ο αποστολέας αναφέρει τεχνικό πρόβλημα με το Portal, οπότε το αίτημα το καταχωρούμε εμείς.",
    "other_request_offline": "Το ίδιο email έχει κι άλλο αίτημα που δεν γίνεται στο Portal, οπότε δεν κάνουμε παραπομπή για κανένα.",
    "not_identified": "Το email δεν έχει ΑΦΜ ή αριθμό λογαριασμού, οπότε πρώτα ζητάμε στοιχεία ταυτοποίησης.",
    "not_in_registry": "Ο ΑΦΜ ή ο λογαριασμός του email δεν υπάρχει στο μητρώο, οπότε το εξετάζει το προσωπικό.",
    "guess_not_identified": "Το email δεν έχει ΑΦΜ ή αριθμό λογαριασμού. Η ενέργεια είναι η καλύτερη εκτίμηση: πριν την καταχώρηση χρειάζεται ταυτοποίηση.",
    "guess_not_in_registry": "Ο ΑΦΜ ή ο λογαριασμός του email δεν βρέθηκε στο μητρώο. Η ενέργεια είναι η καλύτερη εκτίμηση: πριν την καταχώρηση πρέπει να βρεθεί ο πελάτης.",
    "named_account": "Το email αναφέρει συγκεκριμένο δανειακό λογαριασμό, οπότε το αίτημα καταχωρείται σε αυτόν.",
    "per_spv": "Για αυτή την κατηγορία καταχωρείται ένα αίτημα ανά χαρτοφυλάκιο (SPV) του πελάτη, σε έναν από τους λογαριασμούς του.",
    "all_debts_accounts": "Το αίτημα αφορά όλες τις οφειλές, οπότε καταχωρείται σε κάθε λογαριασμό του πελάτη.",
    "all_debts_spv": "Το αίτημα αφορά όλες τις οφειλές, οπότε καταχωρείται ένα αίτημα σε κάθε χαρτοφυλάκιο (SPV).",
    "single_account": "Ο πελάτης έχει έναν μόνο λογαριασμό, οπότε το αίτημα καταχωρείται σε αυτόν.",
    "single_spv": "Ο πελάτης έχει λογαριασμούς σε ένα μόνο χαρτοφυλάκιο (SPV), οπότε το αίτημα καταχωρείται σε έναν από αυτούς.",
    "account_not_identified": "Η κατηγορία απαιτεί ταυτοποίηση λογαριασμού, αλλά το email δεν αναφέρει λογαριασμό και ο πελάτης έχει περισσότερους, οπότε ζητάμε τον αριθμό λογαριασμού.",
    "spv_not_identified": "Η κατηγορία απαιτεί ταυτοποίηση χαρτοφυλακίου (SPV), αλλά το email δεν αναφέρει λογαριασμό και ο πελάτης έχει λογαριασμούς σε περισσότερα, οπότε ζητάμε τον αριθμό λογαριασμού.",
    "guess_account_not_identified": "Ο λογαριασμός δεν ταυτοποιείται από το email. Πριν την καταχώρηση χρειάζεται ο αριθμός λογαριασμού.",
    "no_accounts": "Δεν βρέθηκαν λογαριασμοί του πελάτη στο μητρώο.",
    "account_open": "Ο λογαριασμός είναι ανοιχτή υπόθεση στο Qualco, οπότε χρησιμοποιείται ο κωδικός ανοιχτής υπόθεσης.",
    "account_closed": "Ο λογαριασμός είναι κλειστή υπόθεση στο Qualco, οπότε χρησιμοποιείται ο κωδικός _Cust.",
    "account_state_unknown": "Δεν υπάρχει ακόμη η ένδειξη ανοιχτής/κλειστής υπόθεσης, οπότε χρησιμοποιείται ο κωδικός ανοιχτής υπόθεσης (χωρίς _Cust).",
    "category_reply": "Η κατηγορία ορίζει αυτό το πρότυπο απάντησης.",
    "request_activity": "Κάθε αίτημα Qualco καταγράφεται και με τη δραστηριότητά του (φύλλο Activities).",
}


def explain(action: dict) -> list[str]:
    """The action's reasons as Greek sentences, in the order they were applied."""
    return [REASONS[key] for key in action["because"]]


def priority(category: str) -> float:
    return PRIORITY.get(category, 3.0)


def order_requests(principal: str | None, others: list[str]) -> tuple[list[str], bool]:
    """The email's requests, principal first, the rest by Priority. Returns (ordered, complaint_demoted).

    A complaint is the principal request only when nothing else is asked; otherwise the most important
    other request takes its place and the complaint follows.
    """
    found = list(dict.fromkeys(c for c in [principal, *others] if c))
    if not found:
        return [], False
    first, rest = found[0], sorted(found[1:], key=priority)
    if first in COMPLAINTS and rest:
        return [rest[0], *rest[1:], first], True
    return [first, *rest], False


def extra_threshold() -> float:
    """Certainty from which a further request is added on its own (EXTRA_CATEGORY_THRESHOLD, default 0.80)."""
    try:
        return float(os.getenv("EXTRA_CATEGORY_THRESHOLD", "0.80"))
    except ValueError:
        return 0.80


def extra_categories(confidence: dict, principal: str | None, threshold: float | None = None) -> list[dict]:
    """The second and third categories the classifier is sure enough of: at most two, most certain first.

    confidence: {category: share of classifier samples that found that request in the email}.
    """
    limit = extra_threshold() if threshold is None else threshold
    found = [(c, float(v)) for c, v in (confidence or {}).items()
             if c and c != principal and c in RULES and c != "No Match Found" and float(v) >= limit]
    found.sort(key=lambda cv: (-cv[1], priority(cv[0])))
    return [{"category": c, "confidence": round(v, 4)} for c, v in found[:2]]


def code_name(code: str) -> str:
    return QUALCO["requests"].get(code) or QUALCO["activities"].get(code) or ""


def render_reply(template: str, missing: list[str] | None = None) -> str:
    settings = REPLIES["settings"]
    lines = "\n".join(REPLIES["missing"][m] for m in missing or [] if m in REPLIES["missing"])
    return REPLIES["templates"][template]["text"].format(
        signature=settings["signature"], portal_url=settings["portal_url"], missing=lines)


def _holds(when: dict, facts: dict) -> bool:
    return all(bool(facts.get(key)) == value for key, value in when.items())


def _fired(category: str, facts: dict) -> list[dict]:
    rules = RULES.get(category, RULES["No Match Found"])["rules"]
    fired = [r for r in rules if not r.get("else") and _holds(r.get("when", {}), facts)]
    return fired or [r for r in rules if r.get("else")]


def _rule_reasons(rule: dict) -> list[str]:
    if rule.get("else"):
        return ["else"]
    conditions = rule.get("when", {})
    return [f"{key}={str(value).lower()}" for key, value in conditions.items()] or ["category_rule"]


def select_accounts(
    mode: str | None, accounts: list[dict], named: list[str], all_debts: bool, prefer_3869: bool = False
) -> tuple[list[dict] | None, list[str], str | None]:
    """Which accounts get the request. Returns (accounts or None, reasons, what to ask for when None).

    "One of its accounts" is not random: open cases first, then Ν.3869 accounts for Ν.3869 requests,
    then the lowest account number, so the same email always gives the same account.
    """
    mode = mode or "per_spv"
    if not accounts:
        return None, ["no_accounts"], "account"
    ordered = sorted(accounts, key=lambda a: (a["state"] == "closed", not (prefer_3869 and a["is3869"]), a["account"]))
    by_spv: dict[str, list[dict]] = {}
    for account in ordered:
        by_spv.setdefault(account["spv"], []).append(account)
    one_per_spv = [group[0] for group in by_spv.values()]
    chosen = [a for a in ordered if a["account"] in set(named)]
    if chosen:
        if mode == "spv":
            return list({a["spv"]: a for a in reversed(chosen)}.values())[::-1], ["named_account"], None
        return chosen, ["named_account"], None
    if mode == "per_spv":
        return one_per_spv, ["per_spv"], None
    if mode == "account":
        if all_debts:
            return ordered, ["all_debts_accounts"], None
        if len(ordered) == 1:
            return ordered, ["single_account"], None
        return None, ["account_not_identified"], "account"
    if all_debts:  # spv
        return one_per_spv, ["all_debts_spv"], None
    if len(by_spv) == 1:
        return one_per_spv, ["single_spv"], None
    return None, ["spv_not_identified"], "spv"


def _code_for(rule: dict, account: dict | None) -> tuple[str, list[str]]:
    """The request code for one account: the open-case code, or _cust for a closed case."""
    if rule.get("codes"):
        return rule["codes"][0], []
    if account is None:
        return rule["open"], []
    if account["state"] == "closed" and rule.get("closed"):
        return rule["closed"], ["account_closed"]
    return rule["open"], ["account_open" if account["state"] == "open" else "account_state_unknown"]


def portal_eligible(category: str, rule: dict, code: str | None) -> bool:
    """The Portal can replace this request: the category is a Portal one and, when the sheet names
    requests ('YES for Request 113'), the request's code is one of them."""
    spec = RULES.get(category, {})
    if not spec.get("portal"):
        return False
    return not spec.get("portal_codes") or code in spec["portal_codes"]


def request_activities(code: str | None) -> list[str]:
    """The Qualco activities a request is logged with (sheet 'Activities')."""
    return list(QUALCO.get("request_activities", {}).get(str(code), [])) if code else []


def with_activities(actions: list[dict]) -> list[dict]:
    """After each Qualco request, its activities on the same account (the request's caveat, if any, too)."""
    out = []
    for action in actions:
        out.append(action)
        if action["do"] != "request":
            continue
        for activity in request_activities(action.get("code")):
            out.append({key: action[key] for key in ("category", "account", "spv", "accountState", "caveat") if action.get(key)}
                       | {"do": "activity", "code": activity, "codes": [activity], "forRequest": action["code"],
                          "because": ["request_activity"]})
    return out


def decide(
    categories: list[str],
    flags: dict,
    customer: dict,
    has_contract: bool = False,
    best_guess: bool = False,
) -> list[dict]:
    """Actions for an email. categories: every request found, in order (``order_requests``).

    customer: {identified, known, portal, erb, is_3869, accounts, named_accounts} (core.customer_lookup).
    best_guess: for review, keep the request and its code when the customer or the account is not
    identified, with a caveat and a "Need more Info" reply, instead of only asking for the details.
    has_contract is kept for callers; no rule needs it any more.
    """
    facts = {**flags, "registry_3869": customer.get("is_3869", False), "erb": customer.get("erb", False)}
    fired = [(category, rule) for category in dict.fromkeys(categories) for rule in _fired(category, facts)]
    cannot_use_online = bool(flags.get("cannot_use_online"))
    # Spec: one request that cannot be done online means no referral for any of them.
    # A request counts as one the Portal can take when any of its codes can (Κίνηση: only its _Cust 119).
    other_request_offline = any(
        rule["do"] == "request" and not rule.get("bypass_online")
        and not any(portal_eligible(category, rule, c) for c in (rule.get("codes") or [rule.get("open"), rule.get("closed")]))
        for category, rule in fired
    )
    actions: list[dict] = []
    missing: list[str] = []
    for category, rule in fired:
        spec = RULES.get(category, {})
        action: dict[str, Any] = {"category": category, "do": rule["do"], "because": _rule_reasons(rule)}
        because = action["because"]
        default_code = _code_for(rule, None)[0] if rule["do"] == "request" else None
        if ((rule["do"] == "request" and portal_eligible(category, rule, default_code))
                or (rule.get("online_gated") and spec.get("portal") and not spec.get("portal_codes"))) \
                and not rule.get("bypass_online"):
            if cannot_use_online:
                because.append("cannot_use_online")
            elif other_request_offline:
                because.append("other_request_offline")
            elif not customer.get("identified"):
                action["do"] = "portal_referral"
                because.append("unidentified_online")
            elif customer.get("portal"):
                action["do"] = "portal_referral"
                because.append("has_portal")
            else:
                because.append("no_portal")
        for key in ("to", "folder", "template"):
            if rule.get(key):
                action[key] = rule[key]
        if action["do"] == "activity" and rule.get("codes"):
            action["codes"] = list(rule["codes"])
        if action["do"] != "request":
            actions.append(action)
            continue
        # A Qualco request: who, which account, which code.
        code, _ = _code_for(rule, None)
        action.update(codes=[code], code=code, openCode=code, closedCode=rule.get("closed"))
        if not customer.get("identified"):
            missing.append("afm")
            if best_guess:
                action["caveat"] = "not_identified"
                because.append("guess_not_identified")
            else:
                action = {"category": category, "do": "ask_identification", "because": [*because, "not_identified"]}
            actions.append(action)
            continue
        if not customer.get("known"):
            if best_guess:
                action["caveat"] = "not_in_registry"
                because.append("guess_not_in_registry")
            else:
                action = {"category": category, "do": "manual", "note": "not in registry",
                          "because": [*because, "not_in_registry"]}
            actions.append(action)
            continue
        targets, why, ask = select_accounts(spec.get("accounts"), customer.get("accounts") or [],
                                            customer.get("named_accounts") or [], bool(flags.get("all_debts")),
                                            bool(spec.get("prefer_3869")))
        if targets is None:
            missing.append(ask)
            if best_guess:
                action["caveat"] = "account_not_identified"
                because.extend([*why, "guess_account_not_identified"])
            else:
                action = {"category": category, "do": "ask_identification", "because": [*because, *why]}
            actions.append(action)
            continue
        for account in targets:
            code, code_why = _code_for(rule, account)
            if (code != default_code and portal_eligible(category, rule, code) and not rule.get("bypass_online")
                    and not cannot_use_online and not other_request_offline and customer.get("portal")):
                actions.append({"category": category, "do": "portal_referral", "because": [*because, *code_why, "has_portal"],
                                "account": account["account"], "spv": account["spv"]})
                continue
            actions.append({
                **action, "because": [*because, *why, *code_why], "code": code, "codes": [code],
                "account": account["account"], "spv": account["spv"], "accountState": account["state"],
            })

    actions = with_activities(actions)

    # One reply per email.
    asks = [a for a in actions if a["do"] == "ask_identification"]
    if missing or asks:
        actions = [a for a in actions if a["do"] != "ask_identification"]
        why = [k for a in [*asks, *actions] for k in a["because"]
               if k in ("not_identified", "account_not_identified", "spv_not_identified", "guess_not_identified")]
        why = [{"guess_not_identified": "not_identified"}.get(k, k) for k in why]
        actions.append({"category": (asks or actions or [{"category": None}])[0]["category"], "do": "ask_identification",
                        "template": "need_more_info", "missing": list(dict.fromkeys(missing or ["afm"])),
                        "because": list(dict.fromkeys(why or ["not_identified"]))})
    elif not any(a["do"] in REPLY_KINDS for a in actions) or any(a["do"] not in REPLY_KINDS for a in actions):
        done = [a for a in actions if a["do"] not in REPLY_KINDS and a["do"] != "no_action"]
        reply_category = next((c for c in dict.fromkeys(categories) if RULES.get(c, {}).get("reply")), None)
        if done and reply_category:
            actions.append({"category": reply_category, "do": "reply", "template": RULES[reply_category]["reply"],
                            "because": ["category_reply"]})
    for action in actions:
        if action["do"] == "portal_referral":
            action["template"] = "portal"
        elif action["do"] == "bank_referral":
            action["template"] = "erb_branch"
        if action.get("template"):
            action["text"] = render_reply(action["template"], action.get("missing"))
        if action.get("code"):
            action["codeName"] = code_name(action["code"])
    return actions
