"""Build docs/decision_rules.html: the email decision rules as the business reviews them.

    python tools/rules_report.py            # writes docs/decision_rules.html
    python tools/rules_report.py --check    # exit 1 if the file is out of date (also a unit test)

Everything category-specific is read from the files the code runs on (inputs/action_rules.json,
categories.json, qualco_requests.json, reply_templates.json and core/action_rules.py), so the page
cannot drift from the system. The flow diagram and the open questions are written here.
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "AI_email_classifier"
OUT = ROOT / "docs" / "decision_rules.html"
sys.path.insert(0, str(APP))

from core.action_rules import FLAGS, PRIORITY, QUALCO, REASONS, REPLIES, RULES, request_activities  # noqa: E402

ACTION_NAMES = {
    "request": "Αίτημα Qualco", "portal_referral": "Παραπομπή στο Portal", "ask_identification": "Need more Info",
    "manual": "Χειρισμός από το προσωπικό", "forward": "Προώθηση", "reply": "Απάντηση", "bank_referral": "Παραπομπή σε Eurobank",
    "activity": "Activity Qualco", "no_action": "Καμία ενέργεια", "outlook_folder": "Φάκελος Outlook",
}
ACCOUNT_MODES = {
    "per_spv": ("Ανά SPV", "Ένα αίτημα σε κάθε χαρτοφυλάκιο (SPV) του πελάτη, σε έναν λογαριασμό του. Αν το email αναφέρει λογαριασμό, σε αυτόν· αν αναφέρει την τράπεζα ή το SPV του δανείου, μόνο σε αυτό το SPV."),
    "account": ("Ο λογαριασμός", "Πρέπει να ταυτοποιηθεί ο λογαριασμός: από το email, ή ο μοναδικός του πελάτη (ή του SPV που αναφέρει το email), ή όλοι όταν ζητά για όλες τις οφειλές. Αλλιώς Need more Info."),
    "spv": ("Το SPV", "Ένα αίτημα σε έναν λογαριασμό του SPV που ταυτοποιείται: από λογαριασμό του email, από την τράπεζα ή το SPV που αναφέρει το email ή συνημμένο, ή το μοναδικό SPV, ή κάθε SPV για όλες τις οφειλές. Αν το SPV δεν βρεθεί, ένα αίτημα σε κάθε SPV (όχι ένα στην τύχη)."),
}

# Choices made where the spreadsheet is silent or ambiguous: for the business to confirm.
OPEN_QUESTIONS = [
    ("Ανοιχτή / κλειστή υπόθεση",
     "Μέχρι να υπάρξει η ένδειξη στο μητρώο, κάθε αίτημα ανοίγει με τον κωδικό ανοιχτής υπόθεσης (χωρίς _Cust). "
     "Χρειαζόμαστε το όνομα της στήλης και τις τιμές που σημαίνουν «κλειστή»· τότε ο κωδικός _Cust επιλέγεται αυτόματα ανά λογαριασμό."),
    ("«Τυχαίος» λογαριασμός",
     "Για να δίνει το ίδιο email πάντα το ίδιο αποτέλεσμα, ο λογαριασμός επιλέγεται με σειρά: ανοιχτή υπόθεση πρώτα, "
     "λογαριασμός Ν.3869 για αιτήματα Ν.3869, μετά ο μικρότερος αριθμός λογαριασμού."),
    ("Τράπεζα → SPV",
     "Η τράπεζα ή το χαρτοφυλάκιο που αναφέρει το email ή συνημμένο δείχνει το SPV του αιτήματος. Το αρχείο inputs/banks.json "
     "χρειάζεται, για κάθε τράπεζα, τα ονόματα των SPV (PRTFL_NM) που προήλθαν από αυτή· μέχρι τότε ταιριάζει μόνο όνομα SPV γραμμένο στο κείμενο."),
    ("Follow-up υπάρχοντος αιτήματος",
     "Αίτημα του ίδιου τύπου σε «Καταχώρηση αιτήματος» στο αρχείο αιτημάτων Qualco: δεν ανοίγει νέο, καταχωρείται μόνο η δραστηριότητά του. "
     "Τα αιτήματα 96 και 111 δεν έχουν δραστηριότητα στο φύλλο Activities· για αυτά χρησιμοποιείται η 2090. Σωστό; Άλλες καταστάσεις που μετρούν ως «ανοιχτό»;"),
    ("Σήμανση ERB",
     "Email ή συνημμένο που αναφέρει τη Eurobank σημαίνεται ERB, με φίλτρο στην εφαρμογή ελέγχου. Δεν αλλάζει την ενέργεια ούτε στέλνει σε έλεγχο· "
     "η παραπομπή σε Eurobank γίνεται, όπως πριν, για πελάτη που το μητρώο δείχνει ERB. Να στέλνεται σε έλεγχο;"),
    ("Κατηγορίες χωρίς κανόνα λογαριασμού",
     "Αντιλογισμοί, Ηχογραφημένες κλήσεις, Πλειστηριασμοί και Πόθεν έσχες δεν έχουν τιμή στη στήλη «REQ ανά SPV / λογαριασμό». "
     "Εφαρμόζεται «ανά SPV». Ο αντιλογισμός ίσως πρέπει να απαιτεί τον λογαριασμό."),
    ("Πελάτης χωρίς ΑΦΜ/λογαριασμό σε κατηγορία Portal",
     "Συνεχίζεται ο προηγούμενος κανόνας: απάντηση με το πρότυπο Portal (μπορεί να εξυπηρετηθεί μόνος του). Εναλλακτικά: Need more Info."),
    ("Need more Info: αυτόματα ή με έλεγχο;",
     "Σήμερα κάθε email που χρειάζεται στοιχεία πηγαίνει σε έλεγχο, ώστε ένας άνθρωπος να εγκρίνει την απάντηση. Μπορεί να γίνει αυτόματο αργότερα."),
    ("Όνομα που διαφέρει από τον κάτοχο",
     "Εμφανίζεται στον ελεγκτή, αλλά δεν στέλνει το email σε έλεγχο, αφού το όνομα είναι συμπληρωματικό στοιχείο."),
    ("Ταυτοποίηση μόνο από κληρονόμο",
     "Όταν ο αποβιώσας οφειλέτης δεν βρίσκεται στο μητρώο και ο πελάτης βρίσκεται μόνο από ΑΦΜ ή λογαριασμό κληρονόμου, το email πηγαίνει σε έλεγχο. Σωστό;"),
    ("Αυτοτραυματισμός ή απειλή μήνυσης",
     "Το email πηγαίνει πάντα σε έλεγχο, όποια κατηγορία κι αν πάρει."),
    ("Παράπονο μαζί με άλλο αίτημα",
     "Το άλλο αίτημα γίνεται κύριο και το email πηγαίνει σε έλεγχο, ώστε να καταγραφεί και το παράπονο."),
    ("Αποδείξεις πληρωμών",
     "Το φύλλο έχει Portal = YES αλλά ενέργεια «φάκελος ΦΟΡΕΙΣ». Πελάτης με Portal παίρνει το πρότυπο Portal, αλλιώς φάκελος ΦΟΡΕΙΣ. Σωστός ο φάκελος;"),
    ("Ρύθμιση",
     "Η προώθηση στο support_special_cases γίνεται σε κάθε email ρύθμισης, μαζί με το αίτημα 40/142."),
    ("Βεβαιώσεις εξόφλησης",
     "Αφαιρέθηκε ο παλιός κανόνας «χρειάζεται αριθμός σύμβασης»· ισχύει ο κανόνας «ανά SPV» του φύλλου."),
    ("Κείμενα απαντήσεων και διεύθυνση Portal",
     f"Τα κείμενα είναι προσχέδια. Η διεύθυνση Portal είναι {REPLIES['settings']['portal_url']}: χρειάζεται επιβεβαίωση."),
    ("Φόρμες επικοινωνίας επενδυτή",
     "Το φύλλο δεν ορίζει ενέργεια· πηγαίνει στο προσωπικό."),
    ("96 Εκτύπωση_Αναλυτικής_Κίνησης_Int",
     "Ο εσωτερικός κωδικός δεν χρησιμοποιείται αυτόματα· ο ελεγκτής μπορεί να τον προσθέσει."),
    ("Εσωτερικοί αποστολείς",
     "Κάθε email από @dovaluegreece.gr, εκτός από τις διευθύνσεις Retail Support, παίρνει την κατηγορία 38 από τη διεύθυνση, "
     "χωρίς κλήση στο μοντέλο, και πάει αυτόματα στον φάκελο doValueGreece-noreply, χωρίς απάντηση."),
    ("Λίστα Retail Support",
     "Η λίστα (inputs/retail_support_emails.txt) είναι ακόμη κενή. Όταν συμπληρωθεί, αυτά τα email ταξινομούνται κανονικά "
     "και σημαίνονται «Προώθηση Retail Support»."),
    ("111 Ειδική βεβαίωση_int",
     "Δεν υπάρχει στο φύλλο Activities, οπότε δεν καταγράφεται δραστηριότητα. Σωστό;"),
    ("Νομιμοποίηση κληρονόμων",
     "Το φύλλο Activities δίνει 6598 + 5005 + 5007 για τα 44 / 123: καταγράφονται και οι τρεις σε κάθε αίτημα "
     "(παλιότερα 5005 μόνο για πιστοποιητικό εγγυτέρων ή ληξιαρχική πράξη, 5007 για τα άλλα έγγραφα)."),
    ("Κίνηση λογαριασμού στο Portal",
     "«YES for Request 119»: μόνο οι κλειστές υποθέσεις (119 _Cust) πάνε στο Portal, οι ανοιχτές (95) καταχωρούνται. "
     "Μέχρι να υπάρξει η ένδειξη ανοιχτού/κλειστού, ισχύει πάντα το 95."),
    ("Διατήρηση ηχογραφημένων κλήσεων",
     "Το αίτημα είναι πλέον 86 (κλειστή: 150) από το φύλλο Activities, στη θέση του «REQ ΔΙΑΤΗΡΗΣΗ ΚΛΗΣΕΩΝ»."),
]

REVIEW_REASONS = [
    "Βεβαιότητα κάτω από το όριο (σήμερα 90%)",
    "Καμία κατηγορία δεν ταιριάζει, ή η ταξινόμηση απέτυχε",
    "Χρειάζεται πελάτης (αίτημα Qualco) αλλά δεν βρέθηκε με ΑΦΜ ή λογαριασμό",
    "Δεν ταυτοποιήθηκε ο λογαριασμός ή το SPV του αιτήματος",
    "Παράπονο μαζί με άλλο αίτημα",
    "Αυτοτραυματισμός ή απειλή νομικών μέτρων",
    "Οι ΑΦΜ του email οδηγούν σε διαφορετικές κατηγορίες",
    "Ένα συνημμένο δεν διαβάστηκε",
]


def code_html(code: str | None) -> str:
    if not code:
        return ""
    name = QUALCO["requests"].get(code) or QUALCO["activities"].get(code) or ""
    return f'<span class="code"><b>{escape(code)}</b> {escape(name)}</span>'


def condition(rule: dict) -> str:
    if rule.get("else"):
        return "Σε κάθε άλλη περίπτωση"
    when = rule.get("when") or {}
    if not when:
        return "Πάντα"
    parts = []
    for key, value in when.items():
        text = REASONS.get(f"{key}={str(value).lower()}")
        if text is None:  # a flag without its own false sentence
            text = ("Όχι: " if not value else "") + FLAGS.get(key, key)
        parts.append(text.rstrip("."))
    return " · ".join(parts)


def action(rule: dict) -> str:
    do = rule["do"]
    name = escape(ACTION_NAMES.get(do, do))
    if do == "request":
        if rule.get("codes"):
            detail = code_html(rule["codes"][0])
        else:
            detail = f'{code_html(rule["open"])}<span class="cust">κλειστή: {code_html(rule.get("closed"))}</span>'
        flags = []
        if rule.get("bypass_online"):
            flags.append('<span class="tag">και με Portal</span>')
        acts = request_activities((rule.get("codes") or [rule.get("open")])[0])
        activity = f'<span class="actv">activity {escape(" + ".join(acts))}</span>' if acts else '<span class="actv">χωρίς activity</span>'
        return f'<span class="act act-request">{name}</span> {detail} {activity} {"".join(flags)}'
    if do == "forward":
        return f'<span class="act">{name}</span> <span class="mono">{escape(", ".join(rule.get("to") or ["—"]))}</span>'
    if do == "outlook_folder":
        gated = ' <span class="tag">ή Portal</span>' if rule.get("online_gated") else ""
        return f'<span class="act">{name}</span> «{escape(rule["folder"])}»{gated}'
    if do == "activity":
        codes = " ".join(code_html(c) for c in rule.get("codes") or []) or "—"
        return f'<span class="act">{name}</span> {codes}'
    if do == "reply":
        return f'<span class="act">{name}</span> «{escape(REPLIES["templates"][rule["template"]]["label"])}»'
    return f'<span class="act">{name}</span>'


def category_rows() -> str:
    names = sorted((c for c in RULES if c != "No Match Found"), key=lambda c: (PRIORITY.get(c, 3), c))
    rows = []
    for category in names:
        spec = RULES[category]
        reply = REPLIES["templates"][spec["reply"]]["label"] if spec.get("reply") else "—"
        mode = ACCOUNT_MODES[spec["accounts"]][0] if spec.get("accounts") else "—"
        rules = "".join(f"<li><span class=\"when\">{escape(condition(r))}</span><span class=\"arrow\" aria-hidden=\"true\">→</span>"
                        f"<span class=\"then\">{action(r)}</span></li>" for r in spec["rules"])
        p = PRIORITY.get(category)
        rows.append(
            f'<tr data-search="{escape(category.lower())}"><th scope="row">{escape(category)}</th>'
            f'<td class="num">{"" if p is None else int(p)}</td><td>{escape(reply)}</td>'
            f'<td>{portal_text(spec)}</td><td>{escape(mode)}</td><td><ul class="rules">{rules}</ul></td></tr>')
    return "\n".join(rows)


def portal_text(spec: dict) -> str:
    if not spec.get("portal"):
        return "—"
    return "μόνο " + ", ".join(spec["portal_codes"]) if spec.get("portal_codes") else "Ναι"


def code_table() -> list[dict]:
    """Every Qualco request the rules can open: open code, _Cust code, activity, Portal, categories."""
    rows: dict[str, dict] = {}
    for category, spec in RULES.items():
        for rule in spec["rules"]:
            if rule["do"] != "request":
                continue
            code = (rule.get("codes") or [rule.get("open")])[0]
            row = rows.setdefault(code, {"code": code, "closed": rule.get("closed"), "categories": [], "portal": False})
            row["categories"].append(category)
            portal_codes = spec.get("portal_codes")
            if spec.get("portal") and not rule.get("bypass_online"):
                row["portal"] = row["portal"] or not portal_codes or code in portal_codes
                if rule.get("closed") and portal_codes and rule["closed"] in portal_codes:
                    row["portalClosed"] = True
    for row in rows.values():
        row["name"] = QUALCO["requests"].get(row["code"], "")
        row["activities"] = request_activities(row["code"])
        row["closedActivities"] = request_activities(row["closed"]) if row["closed"] else []
        row["categories"] = list(dict.fromkeys(row["categories"]))
    return sorted(rows.values(), key=lambda r: (not r["code"].isdigit(), int(r["code"]) if r["code"].isdigit() else 0))


def code_rows() -> str:
    out = []
    for r in code_table():
        portal = "Ναι" if r["portal"] else ("μόνο κλειστή" if r.get("portalClosed") else "—")
        closed = code_html(r["closed"]) if r["closed"] else "—"
        acts = " + ".join(r["activities"]) or "—"
        if r["closedActivities"] and r["closedActivities"] != r["activities"]:
            acts += f" (κλειστή: {' + '.join(r['closedActivities'])})"
        out.append(f'<tr data-search="{escape(r["code"])}"><th scope="row">{code_html(r["code"])}</th><td>{closed}</td>'
                   f'<td class="mono">{escape(acts)}</td><td>{portal}</td><td>{escape(", ".join(r["categories"]))}</td></tr>')
    return "\n".join(out)


def templates_html() -> str:
    from core.action_rules import render_reply

    out = []
    for key, spec in REPLIES["templates"].items():
        text = render_reply(key, ["afm", "account"])
        out.append(f'<details class="tpl"><summary><b>{escape(spec["label"])}</b> <span class="muted">{escape(spec["name"])}</span>'
                   f'</summary><pre>{escape(text)}</pre></details>')
    return "\n".join(out)


FLOW_SVG = """
<svg viewBox="0 0 820 1200" role="img" aria-label="Η διαδρομή ενός email: έλεγχος αποστολέα (εσωτερικοί: κατηγορία 38 χωρίς μοντέλο), ταξινόμηση, σειρά αιτημάτων, κανόνες κατηγορίας, Portal, ταυτοποίηση με ΑΦΜ ή λογαριασμό, λογαριασμός, κωδικός Qualco, activity, μία απάντηση και δρομολόγηση.">
  <defs>
    <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="currentColor"/>
    </marker>
  </defs>
  <g class="spine" fill="none" stroke="currentColor" stroke-width="1.5" marker-end="url(#arr)">
    <line x1="230" y1="58" x2="230" y2="80"/>
    <line x1="230" y1="164" x2="230" y2="190"/>
    <line x1="230" y1="250" x2="230" y2="270"/>
    <line x1="230" y1="330" x2="230" y2="350"/>
    <line x1="230" y1="410" x2="230" y2="434"/>
    <line x1="230" y1="518" x2="230" y2="542"/>
    <line x1="230" y1="626" x2="230" y2="650"/>
    <line x1="230" y1="734" x2="230" y2="758"/>
    <line x1="230" y1="818" x2="230" y2="838"/>
    <line x1="230" y1="898" x2="230" y2="918"/>
    <line x1="230" y1="978" x2="230" y2="1002"/>
    <line x1="230" y1="1086" x2="230" y2="1116"/>
  </g>
  <g class="node start"><rect x="130" y="14" width="200" height="44" rx="22"/><text x="230" y="41">Νέο email</text></g>
  <g class="node decide"><path d="M230,80 L410,122 L230,164 L50,122 z"/>
    <text x="230" y="118" class="h">0 · Εσωτερικός αποστολέας;</text><text x="230" y="136" class="s">@dovaluegreece.gr, όχι Retail Support</text></g>
  <g class="node"><rect x="80" y="190" width="300" height="60" rx="8"/>
    <text x="230" y="214" class="h">1 · Ταξινόμηση</text><text x="230" y="234" class="s">κύριο αίτημα + λοιπά (από 80% αυτόματα)</text></g>
  <g class="node"><rect x="80" y="270" width="300" height="60" rx="8"/>
    <text x="230" y="294" class="h">2 · Σειρά αιτημάτων</text><text x="230" y="314" class="s">προτεραιότητα 1 → 3 · παράπονο τελευταίο</text></g>
  <g class="node"><rect x="80" y="350" width="300" height="60" rx="8"/>
    <text x="230" y="374" class="h">3 · Κανόνες κατηγορίας</text><text x="230" y="394" class="s">ό,τι λέει το email → ενέργεια</text></g>
  <g class="node decide"><path d="M230,434 L410,476 L230,518 L50,476 z"/>
    <text x="230" y="472" class="h">4 · Portal;</text><text x="230" y="490" class="s">αίτημα Portal + πελάτης με Portal</text></g>
  <g class="node decide"><path d="M230,542 L410,584 L230,626 L50,584 z"/>
    <text x="230" y="580" class="h">5 · Ταυτοποίηση;</text><text x="230" y="598" class="s">ΑΦΜ ή λογαριασμός</text></g>
  <g class="node decide"><path d="M230,650 L410,692 L230,734 L50,692 z"/>
    <text x="230" y="688" class="h">6 · Λογαριασμός;</text><text x="230" y="706" class="s">βρέθηκε λογαριασμός / SPV</text></g>
  <g class="node"><rect x="80" y="758" width="300" height="60" rx="8"/>
    <text x="230" y="782" class="h">7 · Κωδικός αιτήματος Qualco</text><text x="230" y="802" class="s">ανοιχτή: χωρίς _Cust · κλειστή: _Cust</text></g>
  <g class="node act"><rect x="80" y="838" width="300" height="60" rx="8"/>
    <text x="230" y="862" class="h">8 · Activity Qualco</text><text x="230" y="882" class="s">μόνο αυτή, αν το αίτημα υπάρχει ήδη</text></g>
  <g class="node"><rect x="80" y="918" width="300" height="60" rx="8"/>
    <text x="230" y="942" class="h">9 · Μία απάντηση ανά email</text><text x="230" y="962" class="s">από τα πρότυπα (δεξιά)</text></g>
  <g class="node decide"><path d="M230,1002 L410,1044 L230,1086 L50,1044 z"/>
    <text x="230" y="1040" class="h">10 · Αυτόματα;</text><text x="230" y="1058" class="s">κανένας λόγος ελέγχου</text></g>
  <g class="node end auto"><rect x="130" y="1122" width="200" height="44" rx="22"/><text x="230" y="1149">Αυτόματα</text></g>
  <g class="node end review"><rect x="560" y="1022" width="200" height="44" rx="22"/><text x="660" y="1049">Προς έλεγχο</text></g>
  <g fill="none" stroke="currentColor" stroke-width="1.5" marker-end="url(#arr)">
    <line x1="410" y1="122" x2="554" y2="122"/>
    <line x1="380" y1="380" x2="554" y2="380"/>
    <line x1="410" y1="476" x2="554" y2="476"/>
    <line x1="410" y1="584" x2="554" y2="584"/>
    <line x1="410" y1="692" x2="554" y2="692"/>
    <line x1="410" y1="1044" x2="554" y2="1044"/>
  </g>
  <g class="lbl">
    <text x="476" y="114">ναι</text><text x="244" y="182">όχι (Retail Support: σήμανση)</text>
    <text x="244" y="428">αίτημα Qualco</text><text x="468" y="372">άλλη ενέργεια</text>
    <text x="476" y="468">ναι</text><text x="244" y="536">όχι, ή τεχνικό πρόβλημα</text>
    <text x="476" y="576">όχι</text><text x="244" y="644">ναι</text>
    <text x="476" y="684">όχι</text><text x="244" y="752">ναι</text>
    <text x="476" y="1036">όχι</text><text x="244" y="1106">ναι</text>
  </g>
  <g class="node internal"><rect x="560" y="88" width="240" height="68" rx="8"/>
    <text x="680" y="112" class="h">Κατηγορία 38 · αυτόματα</text><text x="680" y="132" class="s">χωρίς μοντέλο · φάκελος</text><text x="680" y="148" class="s">doValueGreece-noreply</text></g>
  <g class="node side"><rect x="560" y="346" width="240" height="68" rx="8"/>
    <text x="680" y="370" class="h">Χωρίς πελάτη</text><text x="680" y="390" class="s">προώθηση · φάκελος Outlook</text><text x="680" y="406" class="s">τράπεζα · προσωπικό</text></g>
  <g class="node tpl"><rect x="560" y="450" width="240" height="52" rx="8"/>
    <text x="680" y="472" class="h">Πρότυπο Portal</text><text x="680" y="490" class="s">αντί για το αίτημα</text></g>
  <g class="node tpl"><rect x="560" y="558" width="240" height="52" rx="8"/>
    <text x="680" y="580" class="h">Need more Info</text><text x="680" y="598" class="s">ζητάμε ΑΦΜ</text></g>
  <g class="node tpl"><rect x="560" y="666" width="240" height="52" rx="8"/>
    <text x="680" y="688" class="h">Need more Info</text><text x="680" y="706" class="s">ζητάμε αριθμό λογαριασμού</text></g>
  <g class="node tpl"><rect x="560" y="840" width="240" height="96" rx="8"/>
    <text x="680" y="862" class="h">Πρότυπα απάντησης</text>
    <text x="680" y="882" class="s">1 Need more Info</text><text x="680" y="898" class="s">2 Portal · 3 Eurobank</text>
    <text x="680" y="914" class="s">4 Received / In Progress</text><text x="680" y="930" class="s">της κατηγορίας</text></g>
  <g fill="none" stroke="currentColor" stroke-width="1.2" stroke-dasharray="4 4" class="feed">
    <polyline points="800,414 812,414 812,886 800,886"/>
    <polyline points="800,502 812,502"/>
    <polyline points="800,610 812,610"/>
    <polyline points="800,718 812,718"/>
    <line x1="560" y1="930" x2="386" y2="946" marker-end="url(#arr)"/>
  </g>
</svg>
"""

PAGE = """<title>Κανόνες αποφάσεων email</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Commissioner:wght@500;600;700&family=Noto+Sans:wght@400;600&family=JetBrains+Mono:wght@500&display=swap">
<style>
/* Layout: one reading column; the flow figure and the category table may scroll sideways in their own boxes. */
:root {
  --bg: #f6f7f9; --surface: #ffffff; --ink: #18212b; --ink-2: #4a5663; --muted: #6c7783; --line: #dbe1e8;
  --accent: #155e8f; --accent-wash: #e6f0f7; --tpl: #6a4fb0; --tpl-wash: #f1edfa; --ok: #1d7a4c; --warn: #a14d0e;
  --display: "Commissioner", "Noto Sans", system-ui, sans-serif; --body: "Noto Sans", system-ui, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #12171d; --surface: #1a2129; --ink: #e8edf2; --ink-2: #b7c2cd; --muted: #8b97a3; --line: #2e3842;
  --accent: #6cb4e4; --accent-wash: #1c3344; --tpl: #b39cf0; --tpl-wash: #2a2340; --ok: #5cc78f; --warn: #f0a36a; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #12171d; --surface: #1a2129; --ink: #e8edf2; --ink-2: #b7c2cd; --muted: #8b97a3; --line: #2e3842;
  --accent: #6cb4e4; --accent-wash: #1c3344; --tpl: #b39cf0; --tpl-wash: #2a2340; --ok: #5cc78f; --warn: #f0a36a; color-scheme: dark }
body { background: var(--bg); color: var(--ink); font: 15px/1.6 var(--body); }
.wrap { max-width: 1180px; margin: 0 auto; padding-block: 32px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
h1, h2, h3 { font-family: var(--display); text-wrap: balance; line-height: 1.25; }
h1 { font-size: 30px; margin: 0 0 6px; }
h2 { font-size: 21px; margin: 44px 0 10px; }
h3 { font-size: 16px; margin: 0 0 6px; }
p { max-width: 70ch; }
.lede { color: var(--ink-2); margin: 0; }
.meta { color: var(--muted); font-size: 13px; margin-top: 8px; }
.eyebrow { font: 600 12px/1 var(--display); letter-spacing: .08em; text-transform: uppercase; color: var(--accent); margin-bottom: 10px; }
.muted { color: var(--muted); }
.mono, code, .code b { font-family: var(--mono); font-size: 12.5px; }
.mono { overflow-wrap: anywhere; }
.panel { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
figure { margin: 0; padding: 18px; overflow-x: auto; }
figure svg { display: block; width: 100%; min-width: 640px; max-width: 860px; height: auto; margin: 0 auto; color: var(--ink-2); }
figcaption { color: var(--ink-2); font-size: 14px; margin-top: 12px; max-width: 80ch; }
.node rect, .node path { fill: var(--surface); stroke: var(--ink-2); stroke-width: 1.4; }
.node text { fill: var(--ink); font: 600 14px var(--display); text-anchor: middle; }
.node text.h { font: 600 14px var(--display); }
.node text.s { font: 400 12px var(--body); fill: var(--ink-2); }
.node.decide path { fill: var(--accent-wash); stroke: var(--accent); }
.node.start rect { fill: var(--ink); stroke: var(--ink); } .node.start text { fill: var(--bg); }
.node.tpl rect { fill: var(--tpl-wash); stroke: var(--tpl); }
.node.side rect { stroke-dasharray: 5 4; }
.node.act rect { fill: var(--surface); stroke: var(--ok); stroke-width: 2; }
.node.internal rect { fill: var(--surface); stroke: var(--ok); stroke-dasharray: 5 4; }
.node.end.auto rect { fill: var(--ok); stroke: var(--ok); } .node.end.review rect { fill: var(--warn); stroke: var(--warn); }
.node.end text { fill: #fff; }
.lbl text { fill: var(--muted); font: 500 12px var(--body); }
.feed { color: var(--tpl); }
.grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }
.card { padding: 16px 18px; min-width: 0; }
.card .k { font: 600 12px var(--display); color: var(--muted); letter-spacing: .06em; text-transform: uppercase; }
.two { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }
ul.plain { margin: 0; padding-left: 18px; } ul.plain li { margin: 4px 0; }
.tools { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 6px 0 10px; }
.tools input { font: inherit; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--ink); min-width: 0; flex: 1 1 260px; max-width: 420px; }
.tools input:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.table-box { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 900px; font-size: 13.5px; }
th, td { text-align: left; vertical-align: top; padding: 10px 12px; border-bottom: 1px solid var(--line); }
thead th { font: 600 12px var(--display); color: var(--muted); letter-spacing: .04em; text-transform: uppercase; position: sticky; top: 0; background: var(--surface); }
tbody th { font: 600 14px var(--display); width: 220px; }
td.num { font-variant-numeric: tabular-nums; text-align: center; }
ul.rules { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
ul.rules li > * { min-width: 0; }
ul.rules li { display: grid; grid-template-columns: minmax(150px, 1fr) 16px minmax(220px, 1.4fr); gap: 6px; }
.when { color: var(--ink-2); } .arrow { color: var(--muted); }
.act { font-weight: 600; } .act-request { color: var(--accent); }
.code { display: inline; margin-right: 6px; } .code b { background: var(--accent-wash); padding: 1px 5px; border-radius: 4px; }
.cust { display: block; color: var(--muted); font-size: 12.5px; margin-top: 2px; } .cust .code b { background: transparent; border: 1px solid var(--line); }
.actv { display: inline-block; font-size: 12px; color: var(--ok); border: 1px solid var(--ok); border-radius: 999px; padding: 0 7px; margin-left: 4px; white-space: nowrap; }
.codes-table { min-width: 860px; }
.codes-table tbody th { width: 300px; }
.codes-table td.mono { white-space: nowrap; }
.tag { font-size: 11.5px; color: var(--tpl); border: 1px solid var(--tpl); border-radius: 999px; padding: 0 7px; margin-left: 4px; white-space: nowrap; }
details.tpl { padding: 10px 14px; border-bottom: 1px solid var(--line); } details.tpl:last-child { border-bottom: 0; }
details.tpl summary { cursor: pointer; } details.tpl pre { white-space: pre-wrap; font: 13.5px/1.6 var(--body); background: var(--tpl-wash); border-radius: 8px; padding: 12px 14px; margin: 10px 0 2px; }
ol.questions { margin: 0; padding: 0; list-style: none; counter-reset: q; display: grid; gap: 10px; }
ol.questions li { counter-increment: q; padding: 12px 16px 12px 52px; position: relative; }
ol.questions li::before { content: counter(q); position: absolute; left: 16px; top: 12px; width: 24px; height: 24px; border-radius: 50%;
  background: var(--accent-wash); color: var(--accent); font: 600 12px/24px var(--display); text-align: center; }
ol.questions b { font-family: var(--display); }
.none { padding: 14px; color: var(--muted); }
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
</style>

<div class="wrap">
  <header>
    <div class="eyebrow">doValue Greece · Email classification</div>
    <h1>Κανόνες αποφάσεων email</h1>
    <p class="lede">Πώς το σύστημα αποφασίζει για κάθε email: ποιο είναι το κύριο αίτημα, ποιος είναι ο πελάτης, ποιο αίτημα Qualco ανοίγει και σε ποιον λογαριασμό, ποια απάντηση στέλνεται, και πότε το email πηγαίνει σε έλεγχο.</p>
    <p class="meta">Πηγή: rules_for_prompt.xlsx (Νοέμβριος 2026). Ο πίνακας κατηγοριών δημιουργείται από τα αρχεία κανόνων που χρησιμοποιεί το σύστημα.</p>
  </header>

  <h2>Η διαδρομή ενός email</h2>
  <div class="panel"><figure>
    __FLOW__
    <figcaption>Τα βήματα 4–8 ισχύουν για κάθε αίτημα Qualco του email, με τη σειρά του βήματος 2. Οι κωδικοί και οι δραστηριότητες κάθε αιτήματος είναι στον πίνακα «Κωδικοί αιτημάτων Qualco». Οι μωβ θέσεις είναι πρότυπα απάντησης· κάθε email παίρνει ένα, με αυτή τη σειρά: Need more Info, Portal, Eurobank, και αλλιώς το Received ή In Progress της κατηγορίας. Το Portal παρακάμπτεται όταν ο πελάτης αναφέρει τεχνικό πρόβλημα ή όταν το ίδιο email έχει αίτημα που δεν γίνεται στο Portal.</figcaption>
  </figure></div>

  <h2>Τα βασικά κριτήρια</h2>
  <div class="grid3">
    <div class="panel card"><div class="k">Ταυτοποίηση</div><h3>Μόνο ΑΦΜ ή λογαριασμός</h3>
      <p>Ο πελάτης ταυτοποιείται μόνο με ΑΦΜ (με σωστό ψηφίο ελέγχου) ή αριθμό λογαριασμού που υπάρχουν στο μητρώο. Όνομα και email είναι συμπληρωματικά: εμφανίζονται ως «πιθανός» πελάτης, αλλά δεν αρκούν για αυτόματη επεξεργασία. Σε κληρονομιά ο πελάτης αναζητείται πρώτα με ΑΦΜ ή λογαριασμό του αποβιώσαντος οφειλέτη· του κληρονόμου είναι δεύτερη προτεραιότητα, μόνο αν ο αποβιώσας δεν βρεθεί, και τότε το email πηγαίνει σε έλεγχο.</p></div>
    <div class="panel card"><div class="k">Προτεραιότητα</div><h3>Το πιο σημαντικό αίτημα πρώτο</h3>
      <p>Όταν ένα email έχει πολλά αιτήματα, κύριο είναι αυτό με τη μικρότερη προτεραιότητα (1 = πιο σημαντικό). Το «Παράπονα» είναι κύριο μόνο όταν το email δεν ζητά τίποτε άλλο και η δυσαρέσκεια είναι έντονη.</p></div>
    <div class="panel card"><div class="k">Αποστολέας</div><h3>Εσωτερικά email: κατηγορία 38 χωρίς μοντέλο</h3>
      <p>Email από @dovaluegreece.gr παίρνει την κατηγορία 38 από τη διεύθυνση, χωρίς κλήση στο μοντέλο, και πάει αυτόματα στον φάκελο doValueGreece-noreply. Εξαίρεση οι διευθύνσεις Retail Support: ταξινομούνται κανονικά και σημαίνονται «Προώθηση Retail Support» (φίλτρο «Αποστολέας»).</p></div>
    <div class="panel card"><div class="k">Activity</div><h3>Κάθε αίτημα με τη δραστηριότητά του</h3>
      <p>Κάθε αίτημα Qualco καταγράφεται και με τη δραστηριότητα του φύλλου Activities, στον ίδιο λογαριασμό (π.χ. 62 → 6572, 44 → 6598 + 5005 + 5007). Αν το Qualco έχει ήδη αίτημα του ίδιου τύπου σε «Καταχώρηση αιτήματος» για τον λογαριασμό (αρχείο αιτημάτων request_output), δεν ανοίγει νέο αίτημα: καταχωρείται μόνο η δραστηριότητα ως follow-up και η απάντηση είναι «σε εξέλιξη».</p></div>
    <div class="panel card"><div class="k">Επιπλέον αιτήματα</div><h3>Δεύτερη και τρίτη κατηγορία από 80%</h3>
      <p>Όταν το email ζητά και κάτι άλλο και ο ταξινομητής το βρίσκει με βεβαιότητα 80% ή περισσότερο (τουλάχιστον 4 στα 5 δείγματα), η κατηγορία προστίθεται αυτόματα, έως δύο, μαζί με τις ενέργειές της. Κάτω από 80% εμφανίζεται μόνο ως πρόταση στον ελεγκτή.</p></div>
    <div class="panel card"><div class="k">Portal</div><h3>Portal πρώτα</h3>
      <p>Σε κατηγορίες με Portal = YES, ο πελάτης με Portal flag παίρνει απάντηση να το κάνει από το Portal, εκτός αν αναφέρει τεχνικό πρόβλημα. Τότε ανοίγει κανονικά το αίτημα Qualco.</p></div>
  </div>

  <h2>Σε ποιον λογαριασμό ανοίγει το αίτημα</h2>
  <div class="grid3">__MODES__</div>
  <p class="muted">Αίτημα για ανοιχτή υπόθεση: ο κωδικός χωρίς _Cust. Ο κωδικός _Cust (κλειστή υπόθεση) θα επιλέγεται ανά λογαριασμό μόλις το μητρώο έχει την ένδειξη ανοιχτού/κλειστού· μέχρι τότε χρησιμοποιείται πάντα ο κωδικός ανοιχτής υπόθεσης.</p>

  <h2>Αυτόματα ή προς έλεγχο</h2>
  <div class="two">
    <div class="panel card"><div class="k">Αυτόματα</div><h3>Όταν δεν ισχύει κανένας λόγος ελέγχου</h3>
      <p>Βεβαιότητα 90% ή περισσότερο, ο πελάτης ταυτοποιήθηκε με ΑΦΜ ή λογαριασμό (ή καμία ενέργεια δεν χρειάζεται πελάτη, π.χ. προώθηση ή φάκελος Outlook), και ο λογαριασμός βρέθηκε.</p></div>
    <div class="panel card"><div class="k">Προς έλεγχο</div><h3>Αν ισχύει έστω ένα</h3><ul class="plain">__REVIEW__</ul></div>
  </div>

  <h2>Ανά κατηγορία</h2>
  <div class="tools"><label for="q" class="muted">Αναζήτηση</label><input id="q" type="search" placeholder="π.χ. οφειλής, 3869, Portal…" autocomplete="off"><span id="count" class="muted"></span></div>
  <div class="panel table-box">
    <table>
      <thead><tr><th>Κατηγορία</th><th>Προτ.</th><th>Απάντηση</th><th>Portal</th><th>Λογαριασμός</th><th>Αν … → ενέργεια</th></tr></thead>
      <tbody id="rows">
__ROWS__
      </tbody>
    </table>
    <div id="none" class="none" hidden>Καμία κατηγορία δεν ταιριάζει με την αναζήτηση.</div>
  </div>

  <h2>Κωδικοί αιτημάτων Qualco</h2>
  <p class="muted">Κάθε αίτημα που μπορούν να ανοίξουν οι κανόνες: κωδικός ανοιχτής υπόθεσης, κωδικός _Cust για κλειστή, η δραστηριότητα που καταγράφεται μαζί του (φύλλο Activities), αν το Portal το αντικαθιστά, και οι κατηγορίες που το χρησιμοποιούν.</p>
  <div class="panel table-box">
    <table class="codes-table">
      <thead><tr><th>Αίτημα (ανοιχτή)</th><th>Κλειστή (_Cust)</th><th>Activity</th><th>Portal</th><th>Κατηγορίες</th></tr></thead>
      <tbody>
__CODES__
      </tbody>
    </table>
  </div>

  <h2>Πρότυπα απάντησης</h2>
  <div class="panel">__TEMPLATES__</div>

  <h2>Προς επιβεβαίωση από την επιχείρηση</h2>
  <p>Σημεία όπου το φύλλο δεν ήταν σαφές και επιλέχθηκε μια λύση. Παρακαλούμε επιβεβαιώστε ή διορθώστε.</p>
  <ol class="questions">__QUESTIONS__</ol>
</div>
<script>
(function () {
  var q = document.getElementById("q"), rows = Array.prototype.slice.call(document.querySelectorAll("#rows tr"));  // categories only
  var count = document.getElementById("count"), none = document.getElementById("none");
  function norm(s) { return s.normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toLowerCase(); }
  rows.forEach(function (r) { r.dataset.text = norm(r.textContent); });
  function paint() {
    var v = norm(q.value.trim()), shown = 0;
    rows.forEach(function (r) { var on = !v || r.dataset.text.indexOf(v) >= 0; r.hidden = !on; if (on) shown++; });
    count.textContent = shown + " / " + rows.length;
    none.hidden = shown > 0;
  }
  q.addEventListener("input", paint);
  paint();
})();
</script>
"""


def render() -> str:
    modes = "".join(f'<div class="panel card"><h3>{escape(title)}</h3><p>{escape(text)}</p>'
                    f'<p class="muted">{escape(", ".join(c for c, s in RULES.items() if s.get("accounts") == key))}</p></div>'
                    for key, (title, text) in ACCOUNT_MODES.items())
    return (PAGE.replace("__FLOW__", FLOW_SVG.strip())
            .replace("__MODES__", modes)
            .replace("__REVIEW__", "".join(f"<li>{escape(r)}</li>" for r in REVIEW_REASONS))
            .replace("__ROWS__", category_rows())
            .replace("__CODES__", code_rows())
            .replace("__TEMPLATES__", templates_html())
            .replace("__QUESTIONS__", "".join(f"<li><b>{escape(t)}.</b> {escape(d)}</li>" for t, d in OPEN_QUESTIONS)))


if __name__ == "__main__":
    page = render()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        sys.exit(0 if current == page else "docs/decision_rules.html is out of date: run python tools/rules_report.py")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(page) // 1024} KB, {len(RULES) - 1} categories)")
