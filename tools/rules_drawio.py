"""Build docs/decision_rules.drawio: the decision rules as an editable draw.io file (diagrams.net).

    python tools/rules_drawio.py            # writes docs/decision_rules.drawio
    python tools/rules_drawio.py --check    # exit 1 if the file is out of date (also a unit test)

Same content as docs/decision_rules.html (tools/rules_report.py), on five pages: the flow of an email
(shapes joined by real connectors, so boxes can be moved and the arrows follow), the criteria and the
account rules, every category, the reply templates, and the points for the business to confirm.
"""

from __future__ import annotations

import math
import sys
from html import escape
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "decision_rules.drawio"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rules_report import (  # noqa: E402
    ACCOUNT_MODES, ACTION_NAMES, OPEN_QUESTIONS, PRIORITY, QUALCO, REPLIES, REVIEW_REASONS, RULES, condition,
)

INK, INK2, LINE = "#18212B", "#4A5663", "#9AA6B2"
ACCENT, ACCENT_WASH = "#155E8F", "#E6F0F7"
TPL, TPL_WASH = "#6A4FB0", "#F1EDFA"
OK, WARN = "#1D7A4C", "#A14D0E"
FONT = "fontFamily=Helvetica;fontColor=" + INK + ";"

BOX = f"rounded=1;arcSize=8;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={INK2};{FONT}fontSize=13;"
DECIDE = f"rhombus;whiteSpace=wrap;html=1;fillColor={ACCENT_WASH};strokeColor={ACCENT};{FONT}fontSize=13;"
TEMPLATE = f"rounded=1;arcSize=8;whiteSpace=wrap;html=1;fillColor={TPL_WASH};strokeColor={TPL};{FONT}fontSize=13;"
SIDE = f"rounded=1;arcSize=8;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={INK2};dashed=1;{FONT}fontSize=13;"
PILL = "rounded=1;arcSize=50;whiteSpace=wrap;html=1;fontFamily=Helvetica;fontColor=#FFFFFF;fontStyle=1;fontSize=14;"
EDGE = f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeColor={INK2};fontColor={INK2};fontSize=12;labelBackgroundColor=#FFFFFF;"
FEED = f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;dashed=1;strokeColor={TPL};fontColor={TPL};fontSize=12;labelBackgroundColor=#FFFFFF;"
TEXT = f"text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;{FONT}fontSize=13;spacing=4;"
CARD = (f"rounded=1;arcSize=3;whiteSpace=wrap;html=1;align=left;verticalAlign=top;spacing=12;fillColor=#FFFFFF;"
        f"strokeColor={LINE};{FONT}fontSize=12;")


class Page:
    def __init__(self, name: str, width: int, height: int):
        self.name, self.width, self.height = name, width, height
        self.cells: list[str] = []
        self.n = 0

    def _id(self) -> str:
        self.n += 1
        return f"{self.name[:3]}-{self.n}"

    def box(self, x: float, y: float, w: float, h: float, label: str, style: str) -> str:
        cid = self._id()
        self.cells.append(f'<mxCell id="{cid}" value={quoteattr(label)} style={quoteattr(style)} vertex="1" parent="1">'
                          f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" as="geometry"/></mxCell>')
        return cid

    def edge(self, source: str, target: str, label: str = "", style: str = EDGE, extra: str = "") -> str:
        cid = self._id()
        self.cells.append(f'<mxCell id="{cid}" value={quoteattr(label)} style={quoteattr(style + extra)} edge="1" parent="1" '
                          f'source="{source}" target="{target}"><mxGeometry relative="1" as="geometry"/></mxCell>')
        return cid

    def xml(self) -> str:
        return (f'<diagram id="{escape(self.name)}" name={quoteattr(self.name)}>'
                f'<mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
                f'fold="1" page="1" pageScale="1" pageWidth="{self.width}" pageHeight="{self.height}" math="0" shadow="0">'
                f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{"".join(self.cells)}</root></mxGraphModel></diagram>')


def two_lines(title: str, sub: str) -> str:
    return f"<b>{escape(title)}</b><br><font style=\"font-size:12px\" color=\"{INK2}\">{escape(sub)}</font>"


def flow_page() -> Page:
    p = Page("1 Διαδρομή email", 900, 1300)
    p.box(40, 10, 820, 40, f"<b style=\"font-size:20px\">Κανόνες αποφάσεων email</b><br>"
          f"<font color=\"{INK2}\">Η διαδρομή ενός email · πηγή: rules_for_prompt.xlsx (Νοέμβριος 2026)</font>", TEXT)
    start = p.box(150, 80, 200, 44, "Νέο email", PILL + f"fillColor={INK};strokeColor={INK};")
    s1 = p.box(100, 160, 300, 60, two_lines("1 · Ταξινόμηση", "κύριο αίτημα + λοιπά (από 80% αυτόματα)"), BOX)
    s2 = p.box(100, 250, 300, 60, two_lines("2 · Σειρά αιτημάτων", "προτεραιότητα 1 → 3 · παράπονο τελευταίο"), BOX)
    s3 = p.box(100, 340, 300, 60, two_lines("3 · Κανόνες κατηγορίας", "ό,τι λέει το email → ενέργεια"), BOX)
    d4 = p.box(80, 440, 340, 100, two_lines("4 · Portal;", "κατηγορία και πελάτης με Portal"), DECIDE)
    d5 = p.box(80, 580, 340, 100, two_lines("5 · Ταυτοποίηση;", "ΑΦΜ ή λογαριασμός στο μητρώο"), DECIDE)
    d6 = p.box(80, 720, 340, 100, two_lines("6 · Λογαριασμός;", "βρέθηκε λογαριασμός / SPV"), DECIDE)
    s7 = p.box(100, 860, 300, 60, two_lines("7 · Κωδικός Qualco", "ανοιχτή: χωρίς _Cust · κλειστή: _Cust"), BOX)
    s8 = p.box(100, 950, 300, 60, two_lines("8 · Μία απάντηση ανά email", "από τα πρότυπα (δεξιά)"), BOX)
    d9 = p.box(80, 1050, 340, 100, two_lines("9 · Αυτόματα;", "κανένας λόγος ελέγχου"), DECIDE)
    auto = p.box(150, 1190, 200, 44, "Αυτόματα", PILL + f"fillColor={OK};strokeColor={OK};")
    review = p.box(600, 1075, 200, 50, "Προς έλεγχο", PILL + f"fillColor={WARN};strokeColor={WARN};")
    other = p.box(560, 330, 280, 80, two_lines("Χωρίς πελάτη", "προώθηση · φάκελος Outlook · activity · τράπεζα · προσωπικό"), SIDE)
    portal = p.box(560, 465, 280, 50, two_lines("Πρότυπο Portal", "αντί για αίτημα Qualco"), TEMPLATE)
    nmi_afm = p.box(560, 605, 280, 50, two_lines("Need more Info", "ζητάμε ΑΦΜ"), TEMPLATE)
    nmi_acc = p.box(560, 745, 280, 50, two_lines("Need more Info", "ζητάμε αριθμό λογαριασμού"), TEMPLATE)
    tpl = p.box(560, 900, 280, 110, "<b>Πρότυπα απάντησης</b><br><font style=\"font-size:12px\">1 Need more Info<br>2 Portal · 3 Eurobank"
                "<br>4 Received / In Progress της κατηγορίας</font>", TEMPLATE)
    for a, b in ((start, s1), (s1, s2), (s2, s3), (s7, s8), (s8, d9)):
        p.edge(a, b)
    p.edge(s3, d4, "αίτημα Qualco")
    p.edge(s3, other, "άλλη ενέργεια")
    p.edge(d4, portal, "ναι")
    p.edge(d4, d5, "όχι, ή τεχνικό πρόβλημα")
    p.edge(d5, nmi_afm, "όχι")
    p.edge(d5, d6, "ναι")
    p.edge(d6, nmi_acc, "όχι")
    p.edge(d6, s7, "ναι")
    p.edge(d9, auto, "ναι")
    p.edge(d9, review, "όχι")
    for side in (other, portal, nmi_afm, nmi_acc):
        p.edge(side, tpl, "", FEED, "exitX=1;exitY=0.5;entryX=1;entryY=0.5;")
    p.edge(tpl, s8, "μία απάντηση", FEED)
    p.box(40, 1250, 820, 50, f"<font color=\"{INK2}\">Τα βήματα 4–7 ισχύουν για κάθε αίτημα Qualco του email, με τη σειρά του βήματος 2. "
          "Το Portal παρακάμπτεται όταν ο πελάτης αναφέρει τεχνικό πρόβλημα ή όταν το ίδιο email έχει αίτημα που δεν γίνεται στο Portal.</font>", TEXT)
    return p


def criteria_page() -> Page:
    p = Page("2 Κριτήρια και λογαριασμός", 1200, 1060)
    p.box(40, 10, 1100, 40, "<b style=\"font-size:20px\">Τα βασικά κριτήρια</b>", TEXT)
    cards = [
        ("Ταυτοποίηση: μόνο ΑΦΜ ή λογαριασμός",
         "Ο πελάτης ταυτοποιείται μόνο με ΑΦΜ (με σωστό ψηφίο ελέγχου) ή αριθμό λογαριασμού που υπάρχουν στο μητρώο. "
         "Όνομα και email είναι συμπληρωματικά: «πιθανός» πελάτης, ποτέ αυτόματη επεξεργασία."),
        ("Προτεραιότητα: το πιο σημαντικό αίτημα πρώτο",
         "Με πολλά αιτήματα, κύριο είναι αυτό με τη μικρότερη προτεραιότητα (1 = πιο σημαντικό). Το «Παράπονα» είναι κύριο "
         "μόνο όταν το email δεν ζητά τίποτε άλλο και η δυσαρέσκεια είναι έντονη."),
        ("Δεύτερη και τρίτη κατηγορία από 80%",
         "Όταν ο ταξινομητής βρίσκει και άλλο αίτημα με βεβαιότητα 80% ή περισσότερο (τουλάχιστον 4 στα 5 δείγματα), η κατηγορία "
         "προστίθεται αυτόματα, έως δύο, μαζί με τις ενέργειές της. Κάτω από 80% είναι μόνο πρόταση στον ελεγκτή."),
        ("Portal πρώτα",
         "Σε κατηγορίες με Portal = YES, ο πελάτης με Portal flag παίρνει απάντηση να το κάνει από το Portal, εκτός αν "
         "αναφέρει τεχνικό πρόβλημα. Τότε ανοίγει κανονικά το αίτημα Qualco."),
    ]
    for i, (title, text) in enumerate(cards):
        p.box(40 + i * 280, 70, 265, 200, f"<b>{escape(title)}</b><br><br>{escape(text)}", CARD + "fontSize=13;")
    p.box(40, 280, 1100, 40, "<b style=\"font-size:20px\">Σε ποιον λογαριασμό ανοίγει το αίτημα</b>", TEXT)
    for i, (key, (title, text)) in enumerate(ACCOUNT_MODES.items()):
        cats = [c for c, s in RULES.items() if s.get("accounts") == key]
        p.box(40 + i * 370, 340, 350, 330,
              f"<b>{escape(title)}</b><br><br>{escape(text)}<br><br><font color=\"{INK2}\">"
              + "<br>".join("• " + escape(c) for c in cats) + "</font>", CARD + "fontSize=13;")
    p.box(40, 685, 1100, 40, f"<font color=\"{INK2}\">Αίτημα για ανοιχτή υπόθεση: κωδικός χωρίς _Cust. Ο κωδικός _Cust επιλέγεται ανά "
          "λογαριασμό μόλις το μητρώο έχει την ένδειξη ανοιχτού/κλειστού· μέχρι τότε ισχύει πάντα ο κωδικός ανοιχτής υπόθεσης.</font>", TEXT)
    p.box(40, 745, 1100, 40, "<b style=\"font-size:20px\">Αυτόματα ή προς έλεγχο</b>", TEXT)
    p.box(40, 800, 540, 180, "<b>Αυτόματα</b>, όταν δεν ισχύει κανένας λόγος ελέγχου:<br><br>Βεβαιότητα 90% ή περισσότερο, ο πελάτης "
          "ταυτοποιήθηκε με ΑΦΜ ή λογαριασμό (ή καμία ενέργεια δεν χρειάζεται πελάτη, π.χ. προώθηση ή φάκελος Outlook), "
          "και ο λογαριασμός βρέθηκε.", CARD + f"fontSize=13;strokeColor={OK};")
    p.box(600, 800, 540, 230, "<b>Προς έλεγχο</b>, αν ισχύει έστω ένα:<br><br>" + "<br>".join("• " + escape(r) for r in REVIEW_REASONS),
          CARD + f"fontSize=13;strokeColor={WARN};")
    return p


def _action_text(rule: dict) -> str:
    do = rule["do"]
    name = f"<b>{escape(ACTION_NAMES.get(do, do))}</b>"

    def code(c):
        return f"<b>{escape(c)}</b> {escape(QUALCO['requests'].get(c) or QUALCO['activities'].get(c) or '')}" if c else ""

    if do == "request":
        if rule.get("codes"):
            text = f"{name} {code(rule['codes'][0])}"
        else:
            text = f"{name} {code(rule['open'])} <font color=\"{INK2}\">(κλειστή: {code(rule.get('closed'))})</font>"
        return text + (" <i>(και με Portal)</i>" if rule.get("bypass_online") else "")
    if do == "forward":
        return f"{name} {escape(', '.join(rule.get('to') or ['—']))}"
    if do == "outlook_folder":
        return f"{name} «{escape(rule['folder'])}»" + (" <i>(ή Portal)</i>" if rule.get("online_gated") else "")
    if do == "activity":
        return f"{name} " + (", ".join(code(c) for c in rule.get("codes") or []) or "—")
    if do == "reply":
        return f"{name} «{escape(REPLIES['templates'][rule['template']]['label'])}»"
    return name


def _lines(text: str, chars: int = 72) -> int:
    plain = text.replace("<br>", "\n")
    for tag in ("<b>", "</b>", "<i>", "</i>", "</font>"):
        plain = plain.replace(tag, "")
    while "<font" in plain:
        start = plain.index("<font")
        plain = plain[:start] + plain[plain.index(">", start) + 1:]
    return sum(max(1, math.ceil(len(line) / chars)) for line in plain.split("\n"))


def categories_page() -> Page:
    names = sorted((c for c in RULES if c != "No Match Found"), key=lambda c: (PRIORITY.get(c, 3), c))
    columns, width, gap, top = 3, 520, 20, 70
    heights = [top] * columns
    cards = []
    for category in names:
        spec = RULES[category]
        reply = REPLIES["templates"][spec["reply"]]["label"] if spec.get("reply") else "—"
        mode = ACCOUNT_MODES[spec["accounts"]][0] if spec.get("accounts") else "—"
        p_ = PRIORITY.get(category)
        meta = (f"Προτ. {'' if p_ is None else int(p_)} · Απάντηση: {escape(reply)} · Portal: {'Ναι' if spec.get('portal') else '—'}"
                f" · Λογαριασμός: {escape(mode)}")
        rules = "<br>".join(f"• <font color=\"{INK2}\">{escape(condition(r))}</font> → {_action_text(r)}" for r in spec["rules"])
        label = f"<b style=\"font-size:14px\">{escape(category)}</b><br><font color=\"{INK2}\">{meta}</font><br><br>{rules}"
        height = 34 + 17 * (_lines(label) + 1)
        column = heights.index(min(heights))
        cards.append((40 + column * (width + gap), heights[column], height, label))
        heights[column] += height + gap
    p = Page("3 Κατηγορίες", 40 * 2 + columns * width + (columns - 1) * gap, max(heights) + 40)
    p.box(40, 10, 1500, 40, "<b style=\"font-size:20px\">Ανά κατηγορία</b> "
          f"<font color=\"{INK2}\">· ταξινομημένες κατά προτεραιότητα · αν … → ενέργεια</font>", TEXT)
    for x, y, h, label in cards:
        p.box(x, y, width, h, label, CARD)
    return p


def templates_page() -> Page:
    from core.action_rules import render_reply

    p = Page("4 Πρότυπα απάντησης", 1200, 100 + 290 * math.ceil(len(REPLIES["templates"]) / 2))
    p.box(40, 10, 1100, 40, "<b style=\"font-size:20px\">Πρότυπα απάντησης</b> "
          f"<font color=\"{INK2}\">· προσχέδια, προς έγκριση</font>", TEXT)
    for i, (key, spec) in enumerate(REPLIES["templates"].items()):
        text = escape(render_reply(key, ["afm", "account"])).replace("\n", "<br>")
        x, y = 40 + (i % 2) * 560, 70 + (i // 2) * 290
        p.box(x, y, 540, 270, f"<b>{escape(spec['label'])}</b> <font color=\"{INK2}\">({escape(spec['name'])})</font><br><br>{text}",
              CARD + f"fontSize=12;fillColor={TPL_WASH};strokeColor={TPL};")
    return p


def questions_page() -> Page:
    p = Page("5 Προς επιβεβαίωση", 1200, 160 + 110 * math.ceil(len(OPEN_QUESTIONS) / 2))
    p.box(40, 10, 1100, 50, "<b style=\"font-size:20px\">Προς επιβεβαίωση από την επιχείρηση</b><br>"
          f"<font color=\"{INK2}\">Σημεία όπου το φύλλο δεν ήταν σαφές και επιλέχθηκε μια λύση.</font>", TEXT)
    for i, (title, text) in enumerate(OPEN_QUESTIONS):
        x, y = 40 + (i % 2) * 560, 80 + (i // 2) * 110
        p.box(x, y, 540, 95, f"<b>{i + 1}. {escape(title)}</b><br>{escape(text)}", CARD + "fontSize=12;")
    return p


def render() -> str:
    pages = [flow_page(), criteria_page(), categories_page(), templates_page(), questions_page()]
    return ('<mxfile host="app.diagrams.net" agent="tools/rules_drawio.py" version="24.7.17">'
            + "".join(p.xml() for p in pages) + "</mxfile>\n")


if __name__ == "__main__":
    xml = render()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        sys.exit(0 if current == xml else "docs/decision_rules.drawio is out of date: run python tools/rules_drawio.py")
    OUT.write_text(xml, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(xml) // 1024} KB, 5 pages)")
