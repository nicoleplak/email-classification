"""Turn what an email asks plus who the customer is into actions, using inputs/action_rules.json.

Rule of thumb: the model answers questions about the email (FLAGS), the registry
answers questions about the customer (customer). This module only combines them.
Every rule whose `when` holds fires; `else` fires when none of the others did.
Each action records why it was chosen in `because`; `explain` turns that into Greek.
"""

from __future__ import annotations

import json
from pathlib import Path

RULES = json.loads(
    (Path(__file__).resolve().parents[1] / "inputs" / "action_rules.json").read_text(
        encoding="utf-8"
    )
)

# What the model reports about the email. Definitions live next to the values so
# the prompt and the rule table cannot drift apart.
FLAGS = {
    "cannot_use_online": "States they cannot log in to or submit via the portal, reports a technical problem there, or returns saying the referral did not work",
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
    "authorization_attached": "Sends an authorization/power of attorney together with the request",
    "auction_cancel_4738": "Asks to cancel an auction because of law 4738",
    "health_data": "The request relies on health data",
    "health_doc_attached": "A signed solemn declaration (Υ/Δ) accompanies the health data",
    "reversal_form_attached": "The completed reversal form is attached",
    "call_preservation": "Asks to PRESERVE recorded calls older than a year (not to receive copies)",
}

# Why an action fired, in words a reviewer can check against the email.
# Conditions read "<fact>=true" or "<fact>=false"; the rest are routing steps.
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
    "authorization_attached=true": "Στέλνει μαζί και εξουσιοδότηση.",
    "auction_imminent=true": "Ο πλειστηριασμός είναι επικείμενος, μέσα στην εβδομάδα.",
    "auction_cancel_4738=true": "Ζητά ακύρωση πλειστηριασμού λόγω Ν.4738.",
    "health_data=true": "Το αίτημα στηρίζεται σε δεδομένα υγείας.",
    "health_data=false": "Το αίτημα δεν στηρίζεται σε δεδομένα υγείας.",
    "health_doc_attached=true": "Συνοδεύεται από υπογεγραμμένη υπεύθυνη δήλωση.",
    "health_doc_attached=false": "Δεν συνοδεύεται από υπογεγραμμένη υπεύθυνη δήλωση, οπότε ζητούμε να τη στείλει.",
    "else": "Δεν ισχύει καμία από τις ειδικές περιπτώσεις της κατηγορίας, οπότε εφαρμόζεται ο γενικός κανόνας.",
    "category_rule": "Για αυτή την κατηγορία η προδιαγραφή ορίζει πάντα αυτή την ενέργεια.",
    "has_portal": "Ο πελάτης έχει πρόσβαση στο Portal και αυτό το αίτημα γίνεται εκεί.",
    "no_portal": "Ο πελάτης δεν έχει πρόσβαση στο Portal, οπότε το αίτημα το καταχωρούμε εμείς.",
    "unidentified_online": "Το email δεν ταυτοποιεί τον πελάτη, αλλά το αίτημα γίνεται online, οπότε τον παραπέμπουμε στο Portal.",
    "cannot_use_online": "Ο αποστολέας αναφέρει ότι δεν μπορεί να χρησιμοποιήσει το Portal, οπότε το αίτημα το καταχωρούμε εμείς.",
    "other_request_offline": "Το ίδιο email έχει κι άλλο αίτημα που δεν γίνεται στο Portal, οπότε δεν κάνουμε παραπομπή για κανένα.",
    "not_identified": "Το email δεν έχει στοιχεία που να ταυτοποιούν τον πελάτη, οπότε πρέπει πρώτα να τα ζητήσουμε.",
    "not_in_registry": "Τα στοιχεία του email δεν αντιστοιχούν σε πελάτη του μητρώου, οπότε το εξετάζει το προσωπικό.",
    "missing_contract": "Λείπει ο αριθμός σύμβασης, που είναι υποχρεωτικός για αυτό το αίτημα.",
    "open_or_closed": "Δεν φαίνεται ακόμη αν η υπόθεση είναι ανοιχτή ή κλειστή, γι' αυτό δείχνουμε και τους δύο κωδικούς.",
    "guess_not_identified": "Το email δεν ταυτοποιεί τον πελάτη. Η ενέργεια είναι η καλύτερη εκτίμηση: πριν την καταχώρηση χρειάζεται ταυτοποίηση.",
    "guess_not_in_registry": "Τα στοιχεία του email δεν βρέθηκαν στο μητρώο. Η ενέργεια είναι η καλύτερη εκτίμηση: πριν την καταχώρηση πρέπει να βρεθεί ο πελάτης.",
}


def explain(action: dict) -> list[str]:
    """The action's reasons as Greek sentences, in the order they were applied."""
    return [REASONS[key] for key in action["because"]]


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
    return [f"{key}={str(value).lower()}" for key, value in conditions.items()] or [
        "category_rule"
    ]


def decide(
    categories: list[str],
    flags: dict,
    customer: dict,
    has_contract: bool = False,
    best_guess: bool = False,
) -> list[dict]:
    """Actions for an email. categories: every request found, principal one first.

    customer: {identified, known, portal, erb, is_3869}.
    best_guess: for review, keep the request and its codes when the customer is not
    identified or not in the registry, and record that as a caveat, instead of
    switching to identification or manual handling.
    Open-or-closed case is not resolved: no registry column is confirmed to mean it,
    so request actions carry both codes.
    """
    facts = {
        **flags,
        "registry_3869": customer.get("is_3869", False),
        "erb": customer.get("erb", False),
    }
    fired = [
        (category, rule)
        for category in dict.fromkeys(categories)
        for rule in _fired(category, facts)
    ]
    cannot_use_online = bool(flags.get("cannot_use_online"))
    # Spec: one request that cannot be done online means no referral for any of them.
    other_request_offline = any(
        rule["do"] == "request"
        and not RULES.get(category, {}).get("online")
        and not rule.get("bypass_online")
        for category, rule in fired
    )
    actions = []
    for category, rule in fired:
        action = {
            "category": category,
            "do": rule["do"],
            "because": _rule_reasons(rule),
        }
        because = action["because"]
        if (
            RULES.get(category, {}).get("online")
            and (rule["do"] == "request" or rule.get("online_gated"))
            and not rule.get("bypass_online")
        ):
            if cannot_use_online:
                because.append("cannot_use_online")
            elif other_request_offline:
                because.append("other_request_offline")
            elif not customer.get("identified"):
                # Spec: unidentified + online-eligible + no stated inability -> website.
                action["do"] = "portal_referral"
                because.append("unidentified_online")
            elif customer.get("portal"):
                action["do"] = "portal_referral"
                because.append("has_portal")
            else:
                because.append("no_portal")
        if action["do"] == "request":
            if not customer.get("identified"):
                if best_guess:
                    action["caveat"] = "not_identified"
                    because.append("guess_not_identified")
                else:
                    action["do"] = "ask_identification"
                    because.append("not_identified")
            elif not customer.get("known"):
                if best_guess:
                    action["caveat"] = "not_in_registry"
                    because.append("guess_not_in_registry")
                else:
                    action["do"] = "manual"
                    action["note"] = "not in registry"
                    because.append("not_in_registry")
        if action["do"] == "request":
            action["open"] = rule.get("open")
            action["closed"] = rule.get("closed")
            action["codes"] = rule.get("codes", [])
            if action["open"] and action["closed"]:
                because.append("open_or_closed")
            if rule.get("requires_contract") and not has_contract:
                action["missing"] = "contract number"
                because.append("missing_contract")
        if rule.get("to"):
            action["to"] = rule["to"]
        actions.append(action)
    return actions
