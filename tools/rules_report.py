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

from core.action_rules import FLAGS, PRIORITY, QUALCO, REASONS, REPLIES, RULES  # noqa: E402

ACTION_NAMES = {
    "request": "Αίτημα Qualco", "portal_referral": "Παραπομπή στο Portal", "ask_identification": "Need more Info",
    "manual": "Χειρισμός από το προσωπικό", "forward": "Προώθηση", "reply": "Απάντηση", "bank_referral": "Παραπομπή σε Eurobank",
    "activity": "Activity Qualco", "no_action": "Καμία ενέργεια", "outlook_folder": "Φάκελος Outlook",
}
ACCOUNT_MODES = {
    "per_spv": ("Ανά SPV", "Ένα αίτημα σε κάθε χαρτοφυλάκιο (SPV) του πελάτη, σε έναν λογαριασμό του. Αν το email αναφέρει λογαριασμό, σε αυτόν."),
    "account": ("Ο λογαριασμός", "Πρέπει να ταυτοποιηθεί ο λογαριασμός: από το email, ή ο μοναδικός του πελάτη, ή όλοι όταν ζητά για όλες τις οφειλές. Αλλιώς Need more Info."),
    "spv": ("Το SPV", "Ένα αίτημα σε έναν λογαριασμό του SPV που ταυτοποιείται: από λογαριασμό του email, ή το μοναδικό SPV, ή κάθε SPV για όλες τις οφειλές. Αλλιώς Need more Info."),
}

# Choices made where the spreadsheet is silent or ambiguous: for the business to confirm.
OPEN_QUESTIONS = [
    ("Ανοιχτή / κλειστή υπόθεση",
     "Μέχρι να υπάρξει η ένδειξη στο μητρώο, κάθε αίτημα ανοίγει με τον κωδικό ανοιχτής υπόθεσης (χωρίς _Cust). "
     "Χρειαζόμαστε το όνομα της στήλης και τις τιμές που σημαίνουν «κλειστή»· τότε ο κωδικός _Cust επιλέγεται αυτόματα ανά λογαριασμό."),
    ("«Τυχαίος» λογαριασμός",
     "Για να δίνει το ίδιο email πάντα το ίδιο αποτέλεσμα, ο λογαριασμός επιλέγεται με σειρά: ανοιχτή υπόθεση πρώτα, "
     "λογαριασμός Ν.3869 για αιτήματα Ν.3869, μετά ο μικρότερος αριθμός λογαριασμού."),
    ("Κατηγορίες χωρίς κανόνα λογαριασμού",
     "Αντιλογισμοί, Ηχογραφημένες κλήσεις, Πλειστηριασμοί και Πόθεν έσχες δεν έχουν τιμή στη στήλη «REQ ανά SPV / λογαριασμό». "
     "Εφαρμόζεται «ανά SPV». Ο αντιλογισμός ίσως πρέπει να απαιτεί τον λογαριασμό."),
    ("Πελάτης χωρίς ΑΦΜ/λογαριασμό σε κατηγορία Portal",
     "Συνεχίζεται ο προηγούμενος κανόνας: απάντηση με το πρότυπο Portal (μπορεί να εξυπηρετηθεί μόνος του). Εναλλακτικά: Need more Info."),
    ("Need more Info: αυτόματα ή με έλεγχο;",
     "Σήμερα κάθε email που χρειάζεται στοιχεία πηγαίνει σε έλεγχο, ώστε ένας άνθρωπος να εγκρίνει την απάντηση. Μπορεί να γίνει αυτόματο αργότερα."),
    ("Όνομα που διαφέρει από τον κάτοχο",
     "Εμφανίζεται στον ελεγκτή, αλλά δεν στέλνει το email σε έλεγχο, αφού το όνομα είναι συμπληρωματικό στοιχείο."),
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
        return f'<span class="act act-request">{name}</span> {detail} {"".join(flags)}'
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
            f'<td>{"Ναι" if spec.get("portal") else "—"}</td><td>{escape(mode)}</td><td><ul class="rules">{rules}</ul></td></tr>')
    return "\n".join(rows)


def templates_html() -> str:
    from core.action_rules import render_reply

    out = []
    for key, spec in REPLIES["templates"].items():
        text = render_reply(key, ["afm", "account"])
        out.append(f'<details class="tpl"><summary><b>{escape(spec["label"])}</b> <span class="muted">{escape(spec["name"])}</span>'
                   f'</summary><pre>{escape(text)}</pre></details>')
    return "\n".join(out)


FLOW_SVG = """
<svg viewBox="0 0 820 1010" role="img" aria-label="Η διαδρομή ενός email: ταξινόμηση, σειρά αιτημάτων, κανόνες κατηγορίας, Portal, ταυτοποίηση με ΑΦΜ ή λογαριασμό, επιλογή λογαριασμού, κωδικός Qualco, μία απάντηση και δρομολόγηση σε αυτόματα ή έλεγχο.">
  <defs>
    <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="currentColor"/>
    </marker>
  </defs>
  <g class="spine" fill="none" stroke="currentColor" stroke-width="1.5" marker-end="url(#arr)">
    <line x1="230" y1="58" x2="230" y2="84"/>
    <line x1="230" y1="144" x2="230" y2="164"/>
    <line x1="230" y1="224" x2="230" y2="244"/>
    <line x1="230" y1="304" x2="230" y2="328"/>
    <line x1="230" y1="412" x2="230" y2="436"/>
    <line x1="230" y1="520" x2="230" y2="544"/>
    <line x1="230" y1="628" x2="230" y2="652"/>
    <line x1="230" y1="712" x2="230" y2="736"/>
    <line x1="230" y1="796" x2="230" y2="824"/>
  </g>
  <!-- nodes -->
  <g class="node start"><rect x="130" y="14" width="200" height="44" rx="22"/><text x="230" y="41">Νέο email</text></g>
  <g class="node"><rect x="80" y="84" width="300" height="60" rx="8"/>
    <text x="230" y="108" class="h">1 · Ταξινόμηση</text><text x="230" y="128" class="s">κύριο αίτημα + λοιπά αιτήματα</text></g>
  <g class="node"><rect x="80" y="164" width="300" height="60" rx="8"/>
    <text x="230" y="188" class="h">2 · Σειρά αιτημάτων</text><text x="230" y="208" class="s">προτεραιότητα 1 → 3 · παράπονο τελευταίο</text></g>
  <g class="node"><rect x="80" y="244" width="300" height="60" rx="8"/>
    <text x="230" y="268" class="h">3 · Κανόνες κατηγορίας</text><text x="230" y="288" class="s">ό,τι λέει το email → ενέργεια</text></g>
  <g class="node decide"><path d="M230,328 L410,370 L230,412 L50,370 z"/>
    <text x="230" y="366" class="h">4 · Portal;</text><text x="230" y="384" class="s">κατηγορία και πελάτης με Portal</text></g>
  <g class="node decide"><path d="M230,436 L410,478 L230,520 L50,478 z"/>
    <text x="230" y="474" class="h">5 · Ταυτοποίηση;</text><text x="230" y="492" class="s">ΑΦΜ ή λογαριασμός</text></g>
  <g class="node decide"><path d="M230,544 L410,586 L230,628 L50,586 z"/>
    <text x="230" y="582" class="h">6 · Λογαριασμός;</text><text x="230" y="600" class="s">βρέθηκε λογαριασμός / SPV</text></g>
  <g class="node"><rect x="80" y="652" width="300" height="60" rx="8"/>
    <text x="230" y="676" class="h">7 · Κωδικός Qualco</text><text x="230" y="696" class="s">ανοιχτή: χωρίς _Cust · κλειστή: _Cust</text></g>
  <g class="node"><rect x="80" y="736" width="300" height="60" rx="8"/>
    <text x="230" y="760" class="h">8 · Μία απάντηση ανά email</text><text x="230" y="780" class="s">από τα πρότυπα (δεξιά)</text></g>
  <g class="node decide"><path d="M230,824 L410,866 L230,908 L50,866 z"/>
    <text x="230" y="862" class="h">9 · Αυτόματα;</text><text x="230" y="880" class="s">κανένας λόγος ελέγχου</text></g>
  <g class="node end auto"><rect x="130" y="944" width="200" height="44" rx="22"/><text x="230" y="971">Αυτόματα</text></g>
  <g class="node end review"><rect x="560" y="844" width="200" height="44" rx="22"/><text x="660" y="871">Προς έλεγχο</text></g>
  <!-- exits -->
  <g fill="none" stroke="currentColor" stroke-width="1.5" marker-end="url(#arr)">
    <line x1="230" y1="908" x2="230" y2="938"/>
    <line x1="410" y1="866" x2="554" y2="866"/>
    <line x1="380" y1="274" x2="554" y2="274"/>
    <line x1="410" y1="370" x2="554" y2="370"/>
    <line x1="410" y1="478" x2="554" y2="478"/>
    <line x1="410" y1="586" x2="554" y2="586"/>
  </g>
  <g class="lbl">
    <text x="244" y="928">ναι</text><text x="476" y="858">όχι</text>
    <text x="244" y="322">αίτημα Qualco</text><text x="468" y="266">άλλη ενέργεια</text>
    <text x="476" y="362">ναι</text><text x="244" y="430">όχι, ή τεχνικό πρόβλημα</text>
    <text x="476" y="470">όχι</text><text x="244" y="538">ναι</text>
    <text x="476" y="578">όχι</text><text x="244" y="646">ναι</text>
  </g>
  <g class="node side"><rect x="560" y="240" width="240" height="68" rx="8"/>
    <text x="680" y="264" class="h">Χωρίς πελάτη</text><text x="680" y="284" class="s">προώθηση · φάκελος Outlook</text><text x="680" y="300" class="s">activity · τράπεζα · προσωπικό</text></g>
  <g class="node tpl"><rect x="560" y="344" width="240" height="52" rx="8"/>
    <text x="680" y="366" class="h">Πρότυπο Portal</text><text x="680" y="384" class="s">αντί για αίτημα</text></g>
  <g class="node tpl"><rect x="560" y="452" width="240" height="52" rx="8"/>
    <text x="680" y="474" class="h">Need more Info</text><text x="680" y="492" class="s">ζητάμε ΑΦΜ</text></g>
  <g class="node tpl"><rect x="560" y="560" width="240" height="52" rx="8"/>
    <text x="680" y="582" class="h">Need more Info</text><text x="680" y="600" class="s">ζητάμε αριθμό λογαριασμού</text></g>
  <g class="node tpl"><rect x="560" y="660" width="240" height="96" rx="8"/>
    <text x="680" y="682" class="h">Πρότυπα απάντησης</text>
    <text x="680" y="702" class="s">1 Need more Info</text><text x="680" y="718" class="s">2 Portal · 3 Eurobank</text>
    <text x="680" y="734" class="s">4 Received / In Progress</text><text x="680" y="750" class="s">της κατηγορίας</text></g>
  <g fill="none" stroke="currentColor" stroke-width="1.2" stroke-dasharray="4 4" class="feed">
    <polyline points="800,308 812,308 812,706 800,706"/>
    <polyline points="800,396 812,396"/>
    <polyline points="800,504 812,504"/>
    <polyline points="800,612 812,612"/>
    <line x1="560" y1="760" x2="386" y2="766" marker-end="url(#arr)"/>
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
    <figcaption>Τα βήματα 4–7 ισχύουν για κάθε αίτημα Qualco του email, με τη σειρά του βήματος 2. Οι μωβ θέσεις είναι πρότυπα απάντησης· κάθε email παίρνει ένα, με αυτή τη σειρά: Need more Info, Portal, Eurobank, και αλλιώς το Received ή In Progress της κατηγορίας. Το Portal παρακάμπτεται όταν ο πελάτης αναφέρει τεχνικό πρόβλημα ή όταν το ίδιο email έχει αίτημα που δεν γίνεται στο Portal.</figcaption>
  </figure></div>

  <h2>Τα βασικά κριτήρια</h2>
  <div class="grid3">
    <div class="panel card"><div class="k">Ταυτοποίηση</div><h3>Μόνο ΑΦΜ ή λογαριασμός</h3>
      <p>Ο πελάτης ταυτοποιείται μόνο με ΑΦΜ (με σωστό ψηφίο ελέγχου) ή αριθμό λογαριασμού που υπάρχουν στο μητρώο. Όνομα και email είναι συμπληρωματικά: εμφανίζονται ως «πιθανός» πελάτης, αλλά δεν αρκούν για αυτόματη επεξεργασία.</p></div>
    <div class="panel card"><div class="k">Προτεραιότητα</div><h3>Το πιο σημαντικό αίτημα πρώτο</h3>
      <p>Όταν ένα email έχει πολλά αιτήματα, κύριο είναι αυτό με τη μικρότερη προτεραιότητα (1 = πιο σημαντικό). Το «Παράπονα» είναι κύριο μόνο όταν το email δεν ζητά τίποτε άλλο και η δυσαρέσκεια είναι έντονη.</p></div>
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

  <h2>Πρότυπα απάντησης</h2>
  <div class="panel">__TEMPLATES__</div>

  <h2>Προς επιβεβαίωση από την επιχείρηση</h2>
  <p>Σημεία όπου το φύλλο δεν ήταν σαφές και επιλέχθηκε μια λύση. Παρακαλούμε επιβεβαιώστε ή διορθώστε.</p>
  <ol class="questions">__QUESTIONS__</ol>
</div>
<script>
(function () {
  var q = document.getElementById("q"), rows = Array.prototype.slice.call(document.querySelectorAll("#rows tr"));
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
