"""Build a self-contained, offline HTML review app (Greek UI): each email beside its assessment.

    python evaluation/evaluate.py probabilities probs_v1     # one probability per category
    python evaluation/extract_and_act.py facts facts_v3      # what the email asks
    python evaluation/review_app.py probs_v1

Writes OUT_DIR/review_app.html. It embeds client emails, so it stays local:
open it from disk, never publish or upload it. Reviewers rank up to three
categories and confirm or correct the actions. Their work stays in the browser
and is exported per reviewer as business_review_<name>.csv; drop those files in
OUT_DIR and `evaluate.py score` merges them, using the first-ranked category.
"""

from __future__ import annotations

import json
import re
import sys

import openpyxl

from common import (
    NO_MATCH,
    OUT_DIR,
    build_cases,
    categories_without_wizard,
    load_categories,
    spec_path,
)
from core.action_rules import decide, explain
from email_chain import message_key, split_chain
from evaluate import _load, ranked_scores
import extract_and_act as ea

BODY_LIMIT = 20_000
ACTION_FACTS, ACTION_FIELDS = "facts_v3", "fields_v2"
# A high second score means "could also be this", not "also asks for this": on the 720 test
# emails it matched the further requests found by the facts step about 5% of the time.
# So it is only labelled for reviewers; actions follow the top category plus those requests.
ALSO_LIKELY = 50
# The stated numbers are not calibrated: at 90+ the top category agrees with the reference
# 87% of the time, below 90 about 36%. So this line separates sure from unsure in the filter.
HIGH_CERTAINTY = 90


def _records(case: dict) -> list[dict]:
    return [
        {
            "file": r.get("filename"),
            "type": r.get("document_type"),
            "relevance": r.get("relevance"),
            "summary": r.get("summary"),
            "asks": r.get("requested_actions") or [],
            "evidence": r.get("evidence_phrases") or [],
        }
        for r in (case["attachment_context"] or {}).get("records") or []
        if r.get("status") == "ANALYZED"
    ]


def _chain(case: dict) -> list[dict]:
    """The whole conversation, newest first, each message once."""
    older = sorted(
        case["thread_context"].get("Previous_Messages") or [],
        key=lambda m: m.get("Sent_At") or "",
        reverse=True,
    )
    sources = [(case["body"][:BODY_LIMIT], {})] + [
        (
            (m.get("Body") or "")[:4000],
            {
                "who": m.get("Sender_Type"),
                "when": m.get("Sent_At"),
                "subject": m.get("Subject"),
            },
        )
        for m in older
    ]
    messages, seen = [], set()
    for body, known in sources:
        for position, part in enumerate(split_chain(body)):
            key = message_key(part["body"])
            if messages and (not key or key in seen):
                continue
            seen.add(key)
            if position == 0:
                part = {k: v or known.get(k) or "" for k, v in part.items()}
            messages.append(part)
    return messages


def _ranked(prediction: dict) -> list[str]:
    return ranked_scores(prediction["scores"], prediction["reasons"])[:3]


def _top3(prediction: dict) -> list[dict]:
    return [
        {
            "cat": name,
            "p": prediction["scores"][name],
            "why": (prediction["reasons"].get(name) or {}).get("why", ""),
        }
        for name in _ranked(prediction)
    ]


def _code_names() -> dict[str, str]:
    """Request code -> its readable name in the business spec (Qualco_Requests)."""
    sheet = openpyxl.load_workbook(spec_path(), read_only=True, data_only=True)[
        "Qualco_Requests"
    ]
    names = {}
    for row in sheet.iter_rows(values_only=True):
        text = " ".join(str(row[0] or "").split())
        match = re.match(r"(\d+)\s+\S", text)
        if match:
            # "( open case Qs)" is said in words by the page.
            names[match[1]] = (
                re.sub(r"\s*\([^)]*case[^)]*\)", "", text).replace("_", " ").strip()
            )
    return names


def _spec_text() -> dict[str, str]:
    """What the business spec says about each category, shown to reviewers word for word."""
    return {
        c["Categories"].strip(): "\n\n".join(
            filter(
                None,
                ((c.get("Actions") or "").strip(), (c.get("comments") or "").strip()),
            )
        )
        for c in categories_without_wizard()
    }


def _actions(
    cases: list[dict], predictions: dict, spec: dict[str, str]
) -> dict[str, dict]:
    """Proposed actions per email, each with the reasons it was chosen."""

    def rows(file: str) -> dict[str, dict]:
        path = OUT_DIR / f"{file}.jsonl"
        return {r["id"]: r for r in map(json.loads, path.open(encoding="utf-8"))}

    facts, fields = rows(ACTION_FACTS), rows(ACTION_FIELDS)
    registry = ea.Registry(ea._registry(ea._digits_only(fields)))
    names = _code_names()

    def code(value: str | None) -> str | None:
        return names.get(value, value) if value else None

    result = {}
    for case in cases:
        i = case["id"]
        if i not in facts or i not in fields:
            continue
        resolved = ea.resolve(fields[i], registry)
        actions = decide(
            [_ranked(predictions[i])[0], *facts[i]["other_requests"]],
            facts[i],
            resolved["customer"],
            ea.has_contract_number(resolved),
            best_guess=True,  # reviewers judge the likely request, caveats shown with it
        )
        result[i] = {
            "items": [
                {
                    "do": a["do"],
                    "caveat": a.get("caveat"),
                    "cat": a["category"],
                    "open": code(a.get("open")),
                    "closed": code(a.get("closed")),
                    "codes": [code(c) for c in a.get("codes") or []],
                    "to": a.get("to")
                    or (
                        re.findall(
                            r"[\w.+-]+@[\w.-]+\.\w+", spec.get(a["category"], "")
                        )
                        if a["do"] == "forward"
                        else []
                    ),
                    "why": explain(a),
                }
                for a in actions
            ],
            "customer": {**resolved["customer"], "via": resolved["via"]},
            "fields": _extracted(case, resolved["assigned"]),
        }
    return result


# What the side panel lists, in this order. CID is left out: staff add it during
# review, so a new email cannot have one.
EXTRACTED = {
    "afm": "ΑΦΜ",
    "adt": "ΑΔΤ",
    "email": "Email",
    "account": "Δανειακός λογαριασμός",
    "payment_code": "Κωδικός πληρωμής",
    "contract": "Αριθμός σύμβασης",
    "iban": "IBAN",
    "phone": "Τηλέφωνο",
}
_ADT_FORMAT = re.compile(r"^[Α-ΩA-Z]{1,2}\d{6}$")  # AA123456 or A123456
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_OWN_DOMAINS = ("dovalue",)


def _extracted(case: dict, assigned: list[dict]) -> list[dict]:
    """Each field's values with whose they are; values = None when nothing was found."""
    found: dict[str, list[dict]] = {key: [] for key in EXTRACTED}
    # Values that identify the case first, then the rest.
    for a in sorted(assigned, key=lambda a: not a.get("identifies_case")):
        field, role = a.get("field"), a.get("role")
        if field not in found or role == "dovalue_or_bank":
            continue
        value = a["value"]
        if field == "adt":
            value = re.sub(r"[\s\-]", "", value).upper()
            if not _ADT_FORMAT.match(value):
                continue
        if all(v["value"] != value for v in found[field]):
            found[field].append(
                {
                    "value": value,
                    "who": ea.REVIEW_ROLES.get(role, ""),
                    "case": bool(a.get("identifies_case")),
                }
            )
    sender = case["sender"].strip().lower()
    texts = [case["subject"], case["body"]]
    texts += [
        m.get("Body") or ""
        for m in case["thread_context"].get("Previous_Messages") or []
    ]
    emails = [(sender, "Αποστολέας")] + [
        (e.lower(), "Στο κείμενο") for t in texts for e in _EMAIL.findall(t)
    ]
    for address, who in emails:
        domain = address.rsplit("@", 1)[-1]
        if (
            address
            and not any(d in domain for d in _OWN_DOMAINS)
            and all(v["value"] != address for v in found["email"])
        ):
            found["email"].append({"value": address, "who": who, "case": False})
    return [
        {"key": key, "label": label, "values": found[key] or None}
        for key, label in EXTRACTED.items()
    ]


def payload(name: str, unclassified: bool = False) -> dict:
    """Every email with its assessment. With `unclassified`, emails the run has no
    prediction for are included too, with cat None (the review server queues them)."""
    predictions = _load(name)
    every = build_cases()
    cases = [c for c in every if c["id"] in predictions]
    spec = _spec_text()
    actions = _actions(cases, predictions, spec)
    categories = [c["Categories"].strip() for c in load_categories()] + [NO_MATCH]
    rows = []
    for case in every:
        p = predictions.get(case["id"])
        if not p and not unclassified:
            continue
        current = case["thread_context"]["Current_Message"]
        rows.append(
            {
                "id": case["id"],
                "dataset": case.get("dataset", ""),
                "received": (current.get("Sent_At") or "")[:16],
                "sender": case["sender"],
                "subject": case["subject"],
                "chain": _chain(case),
                "attachments": _records(case),
                "cat": _ranked(p)[0] if p else None,
                "scores": [p["scores"].get(c, 0) for c in categories] if p else [],
                "top3": _top3(p) if p else [],
                "quotes": sorted(
                    {q for r in p["reasons"].values() for q in r.get("quotes") or []}
                )
                if p
                else [],
                "action": actions.get(case["id"]),
            }
        )
    return {
        "emails": rows,
        "categories": categories,
        "spec": spec,
        "high": HIGH_CERTAINTY,
        "also": ALSO_LIKELY,
    }


def build(name: str) -> None:
    data = payload(name)
    rows = data["emails"]
    payload_json = json.dumps(data, ensure_ascii=False)
    # Email text must not be able to end or derail the <script> block that holds it.
    safe = payload_json.replace("</", "<\\/").replace("<!--", "<\\u0021--")
    html = TEMPLATE.replace("__DATA__", safe)
    path = OUT_DIR / "review_app.html"
    path.write_text(html, encoding="utf-8")
    book = openpyxl.load_workbook(spec_path(), read_only=True)
    print(f"spec: {spec_path().name}, saved {book.properties.modified}")
    print(f"wrote {len(rows)} emails to {path}")


TEMPLATE = r"""<!doctype html>
<html lang="el"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Έλεγχος email</title>
<style>
:root{--ground:#eef3f9;--paper:#fff;--paper-2:#f5f8fc;--ink:#12263f;--soft:#52657d;--line:#d3deea;--blue:#1a5fb4;--on-blue:#fff;--blue-2:#3b76c4;--blue-soft:#dde9f8;--imp:#0f8a7e;
--red:#a8322a;--red-soft:#f8e4e1;--mark:#bcd8fb;--list-w:300px;--side-w:max(440px,40%);--bar-h:60px;--dock-h:60px;--gap:16px;--speed:.26s;--ease:cubic-bezier(.4,0,.2,1);
--ui:Arial,Helvetica,sans-serif;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--ground:#0f1722;--paper:#172230;--paper-2:#131d29;--ink:#e6edf5;--soft:#a0b1c4;--line:#2c3b4d;--blue:#7fb2f0;--on-blue:#0b1a2b;--blue-2:#5d93d6;--blue-soft:#1d3350;--imp:#4fc4b6;
--red:#ff9c92;--red-soft:#3a1c1a;--mark:#2e5689;color-scheme:dark}}
/* Shorter, not removed: managed PCs often force this setting on. */
@media (prefers-reduced-motion:reduce){:root{--speed:.16s}}
*{box-sizing:border-box}[hidden]{display:none!important}
html{scroll-padding-top:calc(var(--bar-h) + 12px);scrollbar-gutter:stable}
html:has(dialog[open]){overflow:hidden}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.5 var(--ui);min-height:100vh;display:flex;flex-direction:column}
h1,h2,h3,p{margin:0}
:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
button,input{font:inherit;color:inherit}
button{cursor:pointer;background:var(--paper);border:1px solid var(--line);border-radius:9px;padding:7px 14px;line-height:1.3}
button:hover:not(:disabled){border-color:var(--blue)}button:disabled{opacity:.45;cursor:default}
button.primary{background:var(--blue);border-color:var(--blue);color:var(--on-blue);font-weight:600}
button.quiet{border-color:transparent;background:none;color:var(--blue);padding:4px 8px}
button.icon{padding:5px 11px;font-size:17px;line-height:1.1}
input{background:var(--paper);border:1px solid var(--line);border-radius:9px;padding:7px 12px;width:100%}
/* Top bar */
.bar{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px 14px;flex-wrap:wrap;padding:10px 18px}
.brand{font:600 18px/1.2 var(--ui);white-space:nowrap}
.progress{display:flex;flex-direction:column;gap:3px;min-width:170px;font-size:13px;color:var(--soft)}
.progress b{color:var(--ink);font-weight:600}
.progress i{display:block;height:5px;border-radius:3px;background:var(--blue-soft);overflow:hidden}.progress i::after{content:"";display:block;height:100%;width:var(--done,0%);background:linear-gradient(to right,var(--blue) var(--own,100%),var(--imp) 0)}
.grow{flex:1 1 0}.msg{font-size:13.5px;color:var(--red)}
#reviewer{width:170px}
button.on{background:var(--blue-soft);border-color:var(--blue);color:var(--blue);font-weight:600}
/* Page */
main{flex:1;display:flex;align-items:flex-start;min-width:0}
#list{flex:0 0 var(--list-w);position:sticky;top:var(--bar-h);height:calc(100vh - var(--bar-h) - var(--dock-h));overflow:hidden;background:var(--paper);border-right:1px solid var(--line)}
#listInner{width:var(--list-w);height:100%;display:flex;flex-direction:column}
#split{flex:0 0 6px;align-self:stretch;cursor:col-resize}#split:hover,#split.drag{background:var(--blue)}
main.nolist #list,main.nolist #split{flex-basis:0px;visibility:hidden;border-right-width:0}main.nolist #listInner{opacity:0}
main.anim #list{transition:flex-basis var(--speed) var(--ease),visibility 0s}
main.anim #split{transition:flex-basis var(--speed) var(--ease),background .15s,visibility 0s}
main.anim #listInner{transition:opacity var(--speed) var(--ease)}
main.anim.nolist #list,main.anim.nolist #split{transition:flex-basis var(--speed) var(--ease),visibility 0s var(--speed)}
.list-head{flex:none;padding:12px 14px 10px;border-bottom:1px solid var(--line)}
.list-count{display:flex;justify-content:space-between;align-items:center;margin-top:6px;font-size:13px;color:var(--soft);min-height:28px}
#items{flex:1;overflow:hidden auto;position:relative}
.item{display:block;width:100%;text-align:left;background:none;border:0;border-bottom:1px solid var(--line);border-radius:0;padding:11px 14px}
.item:hover{background:var(--paper-2)}.item.sel{background:var(--blue-soft);box-shadow:inset 4px 0 var(--blue)}
.item .s{display:flex;gap:6px;font-weight:600;font-size:14px}.item .s span{min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.item .tick{flex:none;color:var(--blue);font-style:normal}.item .tick.imp{color:var(--imp)}
.item .m{font-size:12.5px;color:var(--soft);display:flex;justify-content:space-between;gap:8px;margin-top:2px}.item .m span:first-child{min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.item .m span:last-child{flex:none}
.item .c{font-size:12.5px;color:var(--ink);margin-top:3px;display:flex;justify-content:space-between;gap:8px}.item .c span:first-child{min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.item .c b{flex:none;font-weight:600;font-variant-numeric:tabular-nums}
#detail{flex:1 1 0;min-width:0;padding:22px 24px 28px}
.subject{font:600 22px/1.3 var(--ui);max-width:40em;overflow-wrap:anywhere}
.meta{display:flex;flex-wrap:wrap;gap:2px 18px;margin:6px 0 18px;font-size:13.5px;color:var(--soft)}.meta span{overflow-wrap:anywhere;min-width:0}
.layout{display:grid;grid-template-columns:minmax(0,1fr) var(--gap) minmax(360px,min(var(--side-w),calc(100% - 340px - var(--gap))));align-items:start}
.reading,.assess{display:flex;flex-direction:column;gap:var(--gap);min-width:0}
.vbar{align-self:stretch;min-height:100%;position:relative;cursor:col-resize}
.vbar::before{content:"";position:absolute;top:0;bottom:0;left:50%;width:2px;margin-left:-1px;border-radius:2px;background:transparent}
.vbar:hover::before,.vbar.drag::before,.vbar:focus-visible::before{background:var(--blue);width:4px;margin-left:-2px}
/* The email, as letters on a desk */
.sheet{background:var(--paper);border:1px solid var(--line);border-radius:14px}
.fold-head{display:flex;width:100%;justify-content:space-between;align-items:center;gap:12px;text-align:left;background:none;border:0;border-radius:13px;padding:11px 22px}
.fold-head:hover{background:var(--paper-2)}
.fold-title{min-width:0;font-weight:600;font-size:14px;overflow-wrap:anywhere}.fold-title small{display:block;font-weight:400;font-size:13px;color:var(--soft)}
.chev{flex:none;font-size:16px;line-height:1;color:var(--soft);transition:transform var(--speed) var(--ease)}.fold-head[aria-expanded="false"] .chev{transform:rotate(-90deg)}
.fold{display:grid;grid-template-rows:1fr;transition:grid-template-rows var(--speed) var(--ease)}.fold.closed{grid-template-rows:0fr}
.fold-in{min-height:0;overflow:hidden;transition:visibility 0s}.fold.closed .fold-in{visibility:hidden;transition:visibility 0s var(--speed)}
.fold-pad{padding:0 22px 18px}
.sheet.old{background:var(--paper-2);margin-left:calc(var(--depth,1)*14px)}
.body{font:15px/1.55 var(--ui);white-space:pre-wrap;overflow-wrap:anywhere;max-width:68ch}
mark{background:var(--mark);color:inherit;border-radius:3px;padding:0 2px}
.seam{display:flex;align-items:center;gap:12px;margin:2px 0}
.seam::before,.seam::after{content:"";flex:1 1 24px;min-width:24px;height:6px;background:radial-gradient(circle at center,var(--soft) 1.7px,transparent 2.2px) center/12px 6px repeat-x}
.seam-card{flex:0 1 auto;min-width:0;background:var(--blue-soft);color:var(--ink);border-radius:12px;padding:6px 16px;text-align:center;font-size:13px;line-height:1.35;overflow-wrap:anywhere}
.seam-card b{display:block;color:var(--blue);font-weight:600}
.panel h2{font-size:17px;font-weight:600;line-height:1.3}
.att{border-top:1px solid var(--line)}.att .fold-head{padding:9px 0;border-radius:0}.att .fold-pad{padding:0 0 12px}.att .fold-head:hover{background:none}
.att .f{font-weight:600;overflow-wrap:anywhere}.sub{font-size:13.5px;color:var(--soft);margin-top:4px;overflow-wrap:anywhere}
/* Assessment panels */
.panel{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px 20px;display:flex;flex-direction:column;gap:14px}
.hint{font-size:13.5px;color:var(--soft)}
.slots{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
.slot{display:flex;align-items:center;gap:8px;min-height:38px;padding:4px 6px 4px 5px;border:1px solid var(--line);border-radius:11px}
.slot.empty{border-style:dashed;color:var(--soft)}
.rank{flex:none;width:28px;height:28px;border-radius:7px;display:grid;place-items:center;font:600 13px/1 var(--ui)}
.r1 .rank{background:var(--blue);color:var(--on-blue)}.r2 .rank{background:var(--blue-2);color:var(--on-blue)}.r3 .rank{border:2px solid var(--blue);color:var(--blue)}
.slot.empty .rank{background:none;border:2px dashed var(--line);color:var(--soft)}
.slot-name{flex:1;min-width:0;font-weight:600;font-size:13.5px;line-height:1.3;overflow-wrap:anywhere}.slot.empty .slot-name{font-weight:400}
.slot button{padding:1px 8px}
.cand{border-top:1px solid var(--line);padding-top:12px;display:flex;flex-direction:column;gap:6px}
.cand-top{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.cand-name{font-weight:600;line-height:1.3;overflow-wrap:anywhere}.cand-pct{font:600 19px/1 var(--ui);font-variant-numeric:tabular-nums;white-space:nowrap}
.meter{height:7px;border-radius:4px;background:var(--blue-soft);overflow:hidden}.meter i{display:block;height:100%;border-radius:4px;background:var(--blue)}
.cand.low .meter i{background:var(--soft)}.cand.low .cand-pct{color:var(--soft)}
.why{font-size:14px;line-height:1.5;overflow-wrap:anywhere}
.cand-foot{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.tag{font-size:12.5px;font-weight:600;color:var(--blue);background:var(--blue-soft);padding:2px 10px;border-radius:999px}
.tag.soft{background:none;border:1px solid var(--line);color:var(--soft)}
.tag.bad{color:var(--red);background:var(--red-soft);border-radius:10px;overflow-wrap:anywhere}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.act{border-top:1px solid var(--line);padding-top:12px;display:flex;flex-direction:column;gap:6px}.act:first-of-type{border-top:0;padding-top:0}
.act h3{font-size:16px;font-weight:600;line-height:1.3}
.codes{margin:0;padding:10px 12px;background:var(--paper-2);border-radius:9px;font-size:14px;display:grid;gap:4px}
.codes div{overflow-wrap:anywhere}.codes b{font-weight:600}
.reasons{margin:0;padding-left:18px;font-size:14px;display:grid;gap:3px}
.lead{font-size:13.5px;font-weight:600;margin-top:4px}
details{font-size:13.5px;color:var(--soft)}summary{cursor:pointer;color:var(--blue);width:fit-content}details div{white-space:pre-wrap;overflow-wrap:anywhere;margin-top:6px;padding:10px 12px;background:var(--paper-2);border-radius:9px}
.who dd{min-width:0;overflow-wrap:anywhere}.fv-value{font-variant-numeric:tabular-nums}
.who{margin:0;display:grid;grid-template-columns:auto 1fr;gap:3px 14px;font-size:13.5px;padding-top:12px;border-top:1px solid var(--line)}.who dt{color:var(--soft)}.who dd{margin:0;font-weight:600}
.blank{color:var(--soft);padding:48px 16px;text-align:center}
/* Bottom bar */
.dock{position:sticky;bottom:0;z-index:5;background:var(--paper);border-top:1px solid var(--line);display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px;padding:10px 18px}
.dock .nav{display:flex;align-items:center;gap:6px;font-size:14px;color:var(--soft);font-variant-numeric:tabular-nums;white-space:nowrap}
.state{font-size:14px;min-width:0;overflow-wrap:anywhere}
.state.ok{color:var(--blue);font-weight:600}
/* Panels that open over the page */
dialog{border:0;border-radius:16px;background:var(--paper);color:var(--ink);padding:16px 22px;width:min(1240px,calc(100vw - 32px));max-width:none;max-height:calc(100vh - 32px);box-shadow:0 18px 60px rgba(10,25,50,.35);overflow:auto}
dialog::backdrop{background:rgba(10,25,50,.5)}
dialog.narrow{width:min(860px,calc(100vw - 32px))}
.dlg-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:10px}
.dlg-head h2{font:600 20px/1.25 var(--ui)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));grid-auto-rows:1fr;gap:6px}
.tiles.wide{grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.tile{position:relative;display:flex;flex-direction:column;justify-content:space-between;gap:4px;text-align:left;min-height:56px;padding:7px 11px;font-size:var(--tile,13px);line-height:1.25;overflow-wrap:anywhere;border-radius:11px}
#filterBody .tile{height:76px}#filterBody #filterCat{grid-column:1/-1}
.tile b{font-weight:600}.tile small{color:var(--soft);font-size:.92em;font-variant-numeric:tabular-nums}.tile small.long{line-height:1.3}
.tile[aria-pressed="true"]{background:var(--blue-soft);border-color:var(--blue)}
#catTiles .tile{flex-direction:row;justify-content:space-between;align-items:flex-start;gap:6px}
.tile-side{flex:none;width:30px;display:flex;flex-direction:column;align-items:flex-end;gap:3px}
.badge{width:24px;height:20px;border-radius:6px;display:grid;place-items:center;font:600 11px/1 var(--ui)}
.tile.r1 .badge{background:var(--blue);color:var(--on-blue)}.tile.r2 .badge{background:var(--blue-2);color:var(--on-blue)}.tile.r3 .badge{border:2px solid var(--blue);color:var(--blue);background:var(--paper)}
fieldset{border:0;padding:0;margin:0 0 16px}legend{padding:0 0 8px;font-weight:600}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin:0 0 16px}
.tabs button{border:0;border-bottom:2px solid transparent;border-radius:0;background:none;padding:8px 12px;color:var(--soft);font-weight:600}
.tabs button[aria-selected="true"]{color:var(--blue);border-bottom-color:var(--blue)}
#helpDlg{width:min(680px,calc(100vw - 32px))}#helpDlg ol,#helpDlg ul{padding-left:20px;margin:0 0 14px}#helpDlg li{margin-bottom:8px}#helpDlg p{margin:0 0 12px;color:var(--soft);font-size:14px}#helpDlg h4{margin:16px 0 8px}#helpDlg h4:first-child{margin-top:0}#helpDlg code{background:var(--paper-2);padding:1px 6px;border-radius:4px;font-size:13px}
@media (max-width:1100px){.layout{display:block}.vbar{display:none}.assess{margin-top:var(--gap)}}
@media (max-width:760px){main{display:block}#split{display:none}#list{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}#listInner{width:100%;height:auto}#items{max-height:40vh}main.nolist #list{display:none}#detail{padding:16px}.fold-head{padding:10px 14px}.fold-pad{padding:0 14px 14px}.sheet.old{margin-left:0}.subject{font-size:20px}.brand{display:none}#reviewer{width:130px}}
</style></head><body>
<header class="bar" id="bar">
<button class="icon on" id="tList" title="Εμφάνιση ή απόκρυψη της λίστας" aria-label="Εμφάνιση ή απόκρυψη της λίστας">☰</button>
<span class="brand">Έλεγχος email</span>
<div class="progress"><span id="kpi"></span><i id="meter"></i></div>
<span class="grow"></span><span class="msg" id="msg" role="status"></span>
<input id="reviewer" placeholder="Το όνομά σας" aria-label="Το όνομά σας">
<button id="filters">Φίλτρα</button>
<button id="import">Εισαγωγή</button>
<button id="export" class="primary">Εξαγωγή</button>
<button id="help">Οδηγίες</button>
<input type="file" id="file" accept=".csv" hidden>
</header>
<main id="main">
<aside id="list"><div id="listInner">
<div class="list-head"><input id="fText" type="search" placeholder="Αναζήτηση σε θέμα ή αποστολέα" aria-label="Αναζήτηση σε θέμα ή αποστολέα">
<div class="list-count"><span id="count"></span><button class="quiet" id="clearFilters" hidden>Καθαρισμός φίλτρων</button></div></div>
<div id="items"></div></div></aside>
<div id="split" title="Σύρετε για αλλαγή πλάτους"></div>
<section id="detail"><div class="blank">Επιλέξτε ένα email από τη λίστα.</div></section>
</main>
<footer class="dock" id="dock">
<div class="nav"><button class="icon" id="prev" title="Προηγούμενο (k)" aria-label="Προηγούμενο email">‹</button><span id="pos">–</span><button class="icon" id="next" title="Επόμενο (j)" aria-label="Επόμενο email">›</button></div>
<span class="state" id="state" role="status"></span><span class="grow"></span>
<button id="clear">Καθαρισμός ελέγχου</button>
<button class="primary" id="nextBig">Επόμενο email</button>
</footer>

<dialog id="catDlg" aria-labelledby="catTitle"><div class="dlg-head"><div><h2 id="catTitle"></h2><p class="hint" id="catHint"></p></div><button class="primary" id="catDone">Τέλος</button></div><div class="tiles" id="catTiles"></div></dialog>
<dialog id="actDlg" class="narrow" aria-labelledby="actTitle"><div class="dlg-head"><div><h2 id="actTitle">Ποιες ενέργειες είναι σωστές για αυτό το email;</h2><p class="hint">Επιλέξτε όσες ισχύουν. Με δεύτερο πάτημα αφαιρείται.</p></div><button class="primary" id="actDone">Τέλος</button></div><div class="tiles wide" id="actTiles"></div></dialog>
<dialog id="filterDlg" class="narrow" aria-labelledby="filterTitle"><div class="dlg-head"><h2 id="filterTitle">Φίλτρα</h2><div class="row"><button id="filterReset">Καθαρισμός</button><button class="primary" id="filterDone">Τέλος</button></div></div><div id="filterBody"></div></dialog>

<dialog id="helpDlg" aria-labelledby="helpTitle">
<div class="dlg-head"><h2 id="helpTitle">Οδηγίες</h2><button class="primary" id="helpClose">Κλείσιμο</button></div>
<div class="tabs" role="tablist">
<button role="tab" id="tabReview" aria-controls="panReview" aria-selected="true">Έλεγχος</button>
<button role="tab" id="tabFiles" aria-controls="panFiles" aria-selected="false">Εξαγωγή και εισαγωγή</button>
</div>
<div role="tabpanel" id="panReview" aria-labelledby="tabReview">
<ol>
<li>Ανοίξτε το αρχείο αποθηκευμένο στον υπολογιστή σας, σε Edge ή Chrome (όχι μέσα από το SharePoint ή το email), και γράψτε το όνομά σας πάνω δεξιά.</li>
<li>Διαβάστε το email. Όταν μια αλληλογραφία περιέχει παλαιότερα μηνύματα, τα χωρίζει μια διάτρητη γραμμή. Πατώντας την επικεφαλίδα ενός μηνύματος ή συνημμένου το κρύβετε ή το εμφανίζετε.</li>
<li><b>Κατηγορίες.</b> Το μοντέλο εκτιμά για κάθε κατηγορία χωριστά πόσο πιθανό είναι να ταιριάζει, γι' αυτό τα ποσοστά δεν αθροίζουν στο 100%. Βλέπετε τις τρεις πιθανότερες και γιατί.</li>
<li>Επιλέξτε έως τρεις κατηγορίες με σειρά σημασίας: 1η η κύρια, 2η και 3η μόνο αν το email ζητά κι άλλα. Με «Αποδοχή πρότασης» κρατάτε την πρώτη πρόταση του μοντέλου, με «Άλλη κατηγορία» βλέπετε όλες.</li>
<li><b>Ενέργειες.</b> Βλέπετε τι προτείνεται να γίνει και γιατί. Πατήστε «Σωστή πρόταση» ή «Άλλη ενέργεια» για να τη διορθώσετε. Οι ενέργειες προκύπτουν από τους κανόνες της προδιαγραφής.</li>
<li>Με «Επόμενο email» κάτω δεξιά, ή τα πλήκτρα j και k, συνεχίζετε. Με τα «Φίλτρα» βλέπετε μόνο όσα σας ενδιαφέρουν. Ο έλεγχος αποθηκεύεται μόνος του σε αυτόν τον browser.</li>
</ol>
<p>Το αρχείο περιέχει προσωπικά δεδομένα πελατών και δεν προωθείται εκτός της ομάδας ελέγχου. Το ☰ κρύβει τη λίστα. Το πλάτος της λίστας και της στήλης αξιολόγησης αλλάζει σύροντας το όριό τους.</p>
</div>
<div role="tabpanel" id="panFiles" aria-labelledby="tabFiles" hidden>
<h4>Εξαγωγή: αποστολή του ελέγχου σας</h4>
<ol>
<li>Βεβαιωθείτε ότι έχετε γράψει το όνομά σας πάνω δεξιά. Χωρίς όνομα η εξαγωγή δεν γίνεται.</li>
<li>Πατήστε «Εξαγωγή». Ο αριθμός δείχνει πόσα email θα περιληφθούν.</li>
<li>Ο browser αποθηκεύει το αρχείο <code>business_review_&lt;όνομα&gt;.csv</code>, συνήθως στις «Λήψεις».</li>
<li>Ανεβάστε το στον κοινόχρηστο φάκελο ελέγχου. Αν υπάρχει παλαιότερο δικό σας αρχείο, αντικαταστήστε το.</li>
</ol>
<p>Κάθε εξαγωγή περιέχει όλο τον έλεγχό σας μέχρι εκείνη τη στιγμή, και μετράει πάντα η πιο πρόσφατη.</p>
<h4>Πότε να κάνετε εξαγωγή</h4>
<ul>
<li>Στο τέλος κάθε συνεδρίας και πριν κλείσετε τον browser για μεγάλο διάστημα.</li>
<li>Ο έλεγχος φυλάσσεται μόνο σε αυτόν τον browser, σε αυτόν τον υπολογιστή. Χάνεται ό,τι δεν έχει εξαχθεί αν διαγραφούν τα δεδομένα περιήγησης, αν χρησιμοποιήσετε ιδιωτικό παράθυρο ή αν αλλάξετε υπολογιστή.</li>
</ul>
<h4>Εισαγωγή: συνέχεια από προηγούμενο αρχείο</h4>
<ol>
<li>Πατήστε «Εισαγωγή» και επιλέξτε ένα αρχείο CSV που έχετε εξαγάγει εσείς. Γίνονται δεκτά και τα παλαιότερα αρχεία.</li>
<li>Ό,τι περιέχει προστίθεται στον έλεγχο που υπάρχει ήδη. Για το ίδιο email ισχύει αυτό του αρχείου.</li>
</ol>
<p>Μην εισάγετε αρχεία άλλων: στην επόμενη εξαγωγή θα εμφανίζονταν με το δικό σας όνομα.</p>
</div>
</dialog>

<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent), E = D.emails, CATS = D.categories;
const KEY = 'classifier-review-verdicts', UIKEY = 'classifier-review-ui', NAMEKEY = 'classifier-review-name';
const INDEX = new Map(CATS.map((c, i) => [c, i]));
const SORTED = [...CATS].sort(new Intl.Collator('el', { sensitivity: 'base' }).compare);
const ORD = ['1η', '2η', '3η'], SLOT_HINT = ['Η κύρια κατηγορία', 'Δεύτερη, αν το email ζητά κι άλλο', 'Τρίτη, αν το email ζητά κι άλλο'];
const WHO = { Customer: 'Πελάτης', Agent: 'Εκπρόσωπος', Internal: 'Εσωτερικός', Unknown: 'Άγνωστος' };
const REL = { relevant: 'σχετικό', possibly_relevant: 'πιθανώς σχετικό', irrelevant: 'μη σχετικό' };
const VIA = { afm: 'με ΑΦΜ', account: 'με αριθμό λογαριασμού', contract: 'με αριθμό σύμβασης', payment_code: 'με κωδικό πληρωμής' };
const ACTIONS = {
  request: ['Καταχώρηση αιτήματος στο Qualco', 'Το προσωπικό ανοίγει αίτημα στο Qualco με τον κωδικό που φαίνεται.'],
  portal_referral: ['Παραπομπή στο Portal', 'Απαντάμε ότι το αίτημα γίνεται από το Portal και καταχωρούμε activity «Παραπομπή Portal».'],
  forward: ['Προώθηση σε άλλο τμήμα', 'Το email προωθείται στους παραλήπτες που ορίζει η προδιαγραφή.'],
  manual: ['Χειρισμός από το προσωπικό', 'Δεν γίνεται αυτόματη ενέργεια. Το email το εξετάζει το προσωπικό στο Outlook.'],
  activity: ['Καταχώρηση activity', 'Η αλληλογραφία επισυνάπτεται στο αίτημα που είναι ήδη ανοιχτό.'],
  reply: ['Απαντητικό email', 'Απαντάμε στον αποστολέα και ζητάμε ό,τι λείπει.'],
  bank_referral: ['Παραπομπή στην τράπεζα', 'Ενημερώνουμε τον αποστολέα να απευθυνθεί στην τράπεζα.'],
  no_action: ['Καμία ενέργεια', 'Το email δεν χρειάζεται χειρισμό.'],
  ask_identification: ['Αίτημα ταυτοποίησης', 'Απαντάμε και ζητάμε τα στοιχεία που χρειάζονται για να βρούμε την υπόθεση.'],
};

const CAVEATS = { not_identified: 'Εκτίμηση · χρειάζεται πρώτα ταυτοποίηση', not_in_registry: 'Εκτίμηση · ο πελάτης δεν βρέθηκε στο μητρώο' };

const $ = id => document.getElementById(id);
function h(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') n.className = v;
    else if (k === 'key') n.dataset.key = v;
    else if (k.startsWith('on')) n[k] = v;
    else n.setAttribute(k, v === true ? '' : v);
  }
  n.append(...kids.flat(2).filter(x => x != null && x !== false && x !== ''));
  return n;
}
const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) || d } catch (e) { return d } };
const store = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)) } catch (e) {} };
const date = s => { const m = /^(\d{4})-(\d\d)-(\d\d)[T ](\d\d:\d\d)/.exec(s || ''); return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}` : (s || '') };
const focusedKey = () => { const a = document.activeElement; return a && a.dataset ? a.dataset.key : null };
const refocus = (box, key) => { if (!key) return; const again = box.querySelector(`[data-key="${CSS.escape(key)}"]`); if (again && !again.disabled) again.focus() };

// Reviewer's work. Files and browsers from the earlier version hold a single `cat`.
const V = load(KEY, {});
for (const r of Object.values(V)) if (!r.cats) { r.cats = r.cat ? [r.cat] : []; delete r.cat }
const rec = e => V[e.id] || { cats: [], actions: null, comment: '', at: '' };
const done = e => rec(e).cats.length > 0;
const proposedDos = e => e.action ? [...new Set(e.action.items.map(x => x.do))] : [];
const sameSet = (a, b) => a.length === b.length && a.every(x => b.includes(x));
const sameOrder = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);
function put(e, change) {
  const r = { ...rec(e), ...change, at: new Date().toISOString() }; delete r.by;
  if (!r.cats.length && !r.actions && !r.comment) delete V[e.id]; else V[e.id] = r;
  store(KEY, V); kpi(); renderList(); if (cur && cur.id === e.id) renderAssess(e); renderDock();
}

const UI = load(UIKEY, { list: true, w: 300 });
const F = { status: 'all', level: 'all', batch: '', action: '', cat: '' };
const FILTERS = {
  status: { all: () => true, todo: e => !done(e), done, wrong: e => done(e) && rec(e).cats[0] !== e.cat },
  level: { all: () => true, high: e => e.top3[0].p >= D.high, low: e => e.top3[0].p < D.high, second: e => e.top3[1].p >= D.also },
};
let cur = null, shown = [], items = new Map(), msgTimer = null;

function say(t) { $('msg').textContent = t; clearTimeout(msgTimer); msgTimer = setTimeout(() => $('msg').textContent = '', 5000) }
function applyUI() {
  $('main').classList.toggle('nolist', !UI.list); $('tList').classList.toggle('on', UI.list);
  const css = document.documentElement.style;
  css.setProperty('--list-w', Math.max(220, Math.min(640, UI.w || 300)) + 'px');
  if (UI.side) css.setProperty('--side-w', UI.side + 'px'); else css.removeProperty('--side-w');
  store(UIKEY, UI);
}
new ResizeObserver(() => {
  const css = document.documentElement.style;
  css.setProperty('--bar-h', $('bar').offsetHeight + 'px'); css.setProperty('--dock-h', $('dock').offsetHeight + 'px');
}).observe(document.body);

function kpi() {
  const n = E.length, rev = E.filter(done), agree = rev.filter(e => rec(e).cats[0] === e.cat).length, k = $('kpi');
  const imp = rev.filter(e => rec(e).by).length;
  k.replaceChildren(h('b', null, `Ελέγχθηκαν ${rev.length} από ${n}`), imp ? h('span', { style: 'color:var(--imp)' }, ` (${imp} από εισαγωγή)`) : '', rev.length ? `, συμφωνία ${Math.round(100 * agree / rev.length)}%` : '');
  $('meter').style.setProperty('--done', (100 * rev.length / n) + '%');
  $('meter').style.setProperty('--own', rev.length ? (100 * (rev.length - imp) / rev.length) + '%' : '100%');
  $('export').textContent = `Εξαγωγή (${Object.keys(V).length})`;
}
function match(e) {
  const t = $('fText').value.toLowerCase();
  return FILTERS.status[F.status](e) && FILTERS.level[F.level](e) && (!F.batch || e.dataset === F.batch)
    && (!F.action || proposedDos(e).includes(F.action)) && (!F.cat || e.cat === F.cat)
    && (!t || ((e.subject || '') + ' ' + e.sender).toLowerCase().includes(t));
}
const activeFilters = () => [F.status !== 'all', F.level !== 'all', F.batch, F.action, F.cat].filter(Boolean).length;
function renderList() {
  shown = E.filter(match); items = new Map();
  $('count').textContent = `${shown.length} από ${E.length} email`;
  const n = activeFilters(); $('filters').textContent = n ? `Φίλτρα (${n})` : 'Φίλτρα'; $('filters').classList.toggle('on', !!n); $('clearFilters').hidden = !n;
  const L = $('items'), top = L.scrollTop;
  L.replaceChildren(...(shown.length ? shown.map(listItem) : [h('div', { class: 'blank' }, 'Κανένα email δεν ταιριάζει στα φίλτρα.')]));
  L.scrollTop = top; renderDock();
}
function listItem(e) {
  const it = h('button', { class: 'item' + (cur && cur.id === e.id ? ' sel' : ''), onclick: () => show(e) },
    h('div', { class: 's' }, done(e) && (rec(e).by ? h('i', { class: 'tick imp', title: 'Ελέγχθηκε από ' + rec(e).by, 'aria-label': 'Ελέγχθηκε από ' + rec(e).by }, '✓') : h('i', { class: 'tick', 'aria-label': 'Ελέγχθηκε' }, '✓')), h('span', null, e.subject || '(χωρίς θέμα)')),
    h('div', { class: 'm' }, h('span', null, e.sender), h('span', null, date(e.received).slice(0, 10))),
    h('div', { class: 'c' }, h('span', null, e.cat), h('b', null, e.top3[0].p + '%')));
  items.set(e.id, it); return it;
}
function renderDock() {
  const i = cur ? shown.findIndex(x => x.id === cur.id) : -1, s = $('state');
  $('pos').textContent = (i < 0 ? '–' : i + 1) + ' / ' + shown.length;
  $('prev').disabled = i <= 0; $('next').disabled = $('nextBig').disabled = !shown.length || i >= shown.length - 1;
  $('clear').disabled = !cur || !V[cur.id];
  if (!cur) { s.textContent = ''; return }
  const r = rec(cur), parts = [];
  if (r.cats.length) parts.push(r.cats.length === 1 ? '1 κατηγορία' : `${r.cats.length} κατηγορίες με σειρά`);
  if (r.actions) parts.push(sameSet(r.actions, proposedDos(cur)) ? 'σωστή ενέργεια' : 'διορθωμένη ενέργεια');
  s.className = 'state' + (parts.length ? ' ok' : '');
  s.textContent = parts.length ? '✓ Αποθηκεύτηκε: ' + parts.join(', ') : 'Δεν έχει ελεγχθεί ακόμη';
}
function go(d) { if (!shown.length) return; const i = cur ? shown.findIndex(x => x.id === cur.id) : -1; show(shown[Math.max(0, Math.min(shown.length - 1, i + d))]) }

function mark(text, quotes, cls) {
  const box = h('div', { class: cls }), qs = (quotes || []).filter(q => q && q.length > 2 && text.includes(q));
  if (!qs.length) { box.textContent = text; return box }
  const re = new RegExp(qs.map(q => q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g');
  let last = 0;
  text.replace(re, (m, i) => { box.append(text.slice(last, i), h('mark', null, m)); last = i + m.length });
  box.append(text.slice(last)); return box;
}

// A heading that hides or shows what is under it. Remembered until the page is closed.
const FOLDED = new Set();
function fold(e, key, head, content) {
  const id = `${e.id}:${key}`, closed = FOLDED.has(id);
  const box = h('div', { class: 'fold' + (closed ? ' closed' : '') }, h('div', { class: 'fold-in' }, h('div', { class: 'fold-pad' }, content)));
  const label = shut => shut ? 'Εμφάνιση' : 'Απόκρυψη';
  const btn = h('button', { class: 'fold-head', title: label(closed), 'aria-expanded': String(!closed), onclick: () => {
    const shut = box.classList.toggle('closed');
    if (shut) FOLDED.add(id); else FOLDED.delete(id);
    btn.setAttribute('aria-expanded', String(!shut)); btn.title = label(shut);
  } }, h('span', { class: 'fold-title' }, head), h('span', { class: 'chev', 'aria-hidden': 'true' }, '▾'));
  return [btn, box];
}
function renderReading(e) {
  const out = [], older = e.chain.length - 1;
  e.chain.forEach((m, i) => {
    if (i) out.push(h('div', { class: 'seam', role: 'separator', 'aria-label': `Προηγούμενο μήνυμα ${i} από ${older}` },
      h('div', { class: 'seam-card' }, h('b', null, `Προηγούμενο μήνυμα ${i} από ${older}`))));
    const from = [WHO[m.who] || m.who, date(m.when)].filter(Boolean).join(', ');
    const head = i ? [from || 'Αποστολέας άγνωστος', m.subject && h('small', null, m.subject)] : [older ? 'Τελευταίο μήνυμα' : 'Μήνυμα', from && h('small', null, from)];
    out.push(h('article', { class: 'sheet' + (i ? ' old' : ''), style: i ? `--depth:${Math.min(i, 3)}` : null },
      fold(e, `m${i}`, head, mark(m.body || '(κενό μήνυμα)', e.quotes, 'body'))));
  });
  if (e.attachments.length) out.push(h('section', { class: 'sheet attach' },
    fold(e, 'att', [`Συνημμένα (${e.attachments.length})`, h('small', null, 'Όπως τα διάβασε το μοντέλο')],
      e.attachments.map((x, i) => h('div', { class: 'att' },
        fold(e, `att${i}`, [x.file, h('small', null, [x.type, REL[x.relevance] || x.relevance].filter(Boolean).join(', '))], [
          mark(x.summary || '', e.quotes, 'why'),
          x.asks.length ? mark('Ζητά: ' + x.asks.join('; '), e.quotes, 'sub') : null,
          (x.evidence || []).length ? mark('Αποσπάσματα: ' + x.evidence.join('; '), e.quotes, 'sub') : null,
        ]))))));
  return out;
}

function pickToggle(e, c) {
  const cats = rec(e).cats;
  if (cats.includes(c)) put(e, { cats: cats.filter(x => x !== c) });
  else if (cats.length < 3) put(e, { cats: [...cats, c] });
}
function pickUp(e, i) { const c = [...rec(e).cats]; [c[i - 1], c[i]] = [c[i], c[i - 1]]; put(e, { cats: c }) }

function categoriesPanel(e) {
  const picks = rec(e).cats, accepted = sameOrder(picks, [e.cat]);
  return h('section', { class: 'panel', id: 'catPanel' },
    h('div', null, h('h2', null, 'Τι αφορά το email'),
      h('p', { class: 'hint' }, 'Η σειρά σας, από την πιο σημαντική κατηγορία. Η 2η και η 3η είναι προαιρετικές.')),
    h('ol', { class: 'slots' }, [0, 1, 2].map(i => {
      const c = picks[i];
      return h('li', { class: `slot r${i + 1}${c ? '' : ' empty'}` }, h('span', { class: 'rank' }, ORD[i]), h('span', { class: 'slot-name' }, c || SLOT_HINT[i]),
        c && i > 0 && h('button', { key: `up${i}`, title: 'Μία θέση πιο πάνω', 'aria-label': `Μεταφορά της ${ORD[i]} μία θέση πιο πάνω`, onclick: () => pickUp(e, i) }, '↑'),
        c && h('button', { key: `rm${i}`, title: 'Αφαίρεση', 'aria-label': `Αφαίρεση της ${ORD[i]}`, onclick: () => pickToggle(e, c) }, '×'));
    })),
    h('div', { class: 'row' },
      h('button', { class: accepted ? 'on' : 'primary', key: 'accept', id: 'accept', onclick: () => put(e, { cats: [e.cat] }) }, accepted ? '✓ Αποδεκτή πρόταση' : 'Αποδοχή πρότασης'),
      h('button', { key: 'other', id: 'other', onclick: () => openCats('rank') }, 'Άλλη κατηγορία…')),
    h('div', null, h('h3', { class: 'lead' }, 'Οι τρεις πιθανότερες κατά το μοντέλο'),
      h('p', { class: 'hint' }, "Το ποσοστό εκτιμάται για κάθε κατηγορία χωριστά, γι' αυτό δεν αθροίζουν στο 100%.")),
    e.top3.map((t, n) => {
      const at = picks.indexOf(t.cat), likely = n === 0 || t.p >= D.also;
      return h('div', { class: 'cand' + (likely ? '' : ' low') },
        h('div', { class: 'cand-top' }, h('span', { class: 'cand-name' }, t.cat), h('span', { class: 'cand-pct' }, t.p + '%')),
        h('div', { class: 'meter', 'aria-hidden': 'true' }, h('i', { style: `width:${t.p}%` })),
        t.why && h('p', { class: 'why' }, t.why),
        h('div', { class: 'cand-foot' }, n === 0 ? h('span', { class: 'tag' }, 'Πρόταση μοντέλου') : likely ? h('span', { class: 'tag soft' }, 'Επίσης πιθανή') : h('span', { class: 'hint' }, 'Χαμηλότερη πιθανότητα'),
          h('button', { key: `cand${n}`, disabled: at < 0 && picks.length >= 3, onclick: () => pickToggle(e, t.cat) },
            at >= 0 ? `✓ ${ORD[at]} επιλογή, αφαίρεση` : `Επιλογή ως ${ORD[picks.length] || '–'}`)));
    }));
}

function actionsPanel(e) {
  const A = e.action, mine = rec(e).actions;
  if (!A) return h('section', { class: 'panel', id: 'actPanel' }, h('h2', null, 'Τι πρέπει να γίνει'), h('p', { class: 'hint' }, 'Δεν υπάρχει πρόταση ενέργειας για αυτό το email.'));
  const dos = proposedDos(e), right = mine && sameSet(mine, dos), C = A.customer;
  return h('section', { class: 'panel', id: 'actPanel' },
    h('div', null, h('h2', null, 'Τι πρέπει να γίνει'), h('p', { class: 'hint' }, 'Πρόταση από τους κανόνες της προδιαγραφής, με βάση την πρόταση του μοντέλου και ό,τι άλλο ζητά το email.')),
    A.items.map(x => h('div', { class: 'act' },
      h('h3', null, ACTIONS[x.do][0]),
      x.caveat && h('span', { class: 'tag soft' }, CAVEATS[x.caveat]),
      h('p', { class: 'hint' }, 'Για την κατηγορία: ' + x.cat),
      h('p', { class: 'why' }, ACTIONS[x.do][1]),
      (x.open || x.closed || x.codes.length) ? h('div', { class: 'codes' },
        x.open && h('div', null, h('b', null, x.open), ', αν η υπόθεση είναι ανοιχτή'),
        x.closed && h('div', null, h('b', null, x.closed), ', αν η υπόθεση είναι κλειστή'),
        x.codes.map(c => h('div', null, h('b', null, c)))) : null,
      x.to.length ? h('p', { class: 'why' }, 'Παραλήπτες: ' + x.to.join(', ')) : null,
      x.why.length ? [h('div', { class: 'lead' }, 'Γιατί αυτή η ενέργεια'), h('ul', { class: 'reasons' }, x.why.map(w => h('li', null, w)))] : null,
      D.spec[x.cat] && h('details', null, h('summary', null, 'Τι ορίζει η προδιαγραφή'), h('div', null, D.spec[x.cat])))),
    h('dl', { class: 'who' },
      h('dt', null, 'Πελάτης'), h('dd', null, C.identified ? 'Ταυτοποιήθηκε ' + (VIA[C.via] || '') : 'Δεν ταυτοποιήθηκε'),
      C.identified && [h('dt', null, 'Μητρώο'), h('dd', null, C.known ? 'Βρέθηκε' : 'Δεν βρέθηκε')],
      C.known && [h('dt', null, 'Portal'), h('dd', null, C.portal ? 'Έχει πρόσβαση' : 'Δεν έχει πρόσβαση')],
      C.is_3869 && [h('dt', null, 'Ν.3869'), h('dd', null, 'Ναι')], C.erb && [h('dt', null, 'ERB'), h('dd', null, 'Ναι')]),
    h('div', { class: 'row' },
      h('button', { class: right ? 'on' : 'primary', key: 'actOk', id: 'actOk', onclick: () => put(e, { actions: dos }) }, right ? '✓ Σωστή πρόταση' : 'Σωστή πρόταση'),
      h('button', { key: 'actOther', id: 'actOther', onclick: openActions }, 'Άλλη ενέργεια…'),
      mine && !right && h('span', { class: 'tag bad' }, 'Διόρθωση: ' + (mine.map(d => ACTIONS[d][0]).join(', ') || 'καμία ενέργεια'))));
}
function fieldsPanel(e) {
  const F = e.action && e.action.fields;
  if (!F) return null;
  return h('section', { class: 'panel', id: 'fieldsPanel' },
    h('div', null, h('h2', null, 'Στοιχεία που εντοπίστηκαν'),
      h('p', { class: 'hint' }, 'Από το email και τα συνημμένα. Πρώτα όσα ταυτοποιούν την υπόθεση.')),
    h('dl', { class: 'who fields' }, F.map(f => [
      h('dt', null, f.label),
      h('dd', null, f.values
        ? f.values.map(v => h('div', { class: 'fv' }, h('span', { class: 'fv-value' }, v.value),
            (v.who || v.case) && h('span', { class: 'hint' }, ' · ' + [v.who, v.case && 'ταυτοποιεί την υπόθεση'].filter(Boolean).join(', '))))
        : h('span', { class: 'hint' }, 'Δεν βρέθηκε'))])));
}
function renderAssess(e) {
  const box = document.querySelector('.assess'); if (!box) return;
  const key = focusedKey();
  box.replaceChildren(categoriesPanel(e), actionsPanel(e), fieldsPanel(e),
    h('section', { class: 'panel' }, h('label', { for: 'comment', class: 'lead' }, 'Σχόλιο'),
      h('input', { id: 'comment', placeholder: 'Προαιρετικό', value: rec(e).comment || '', onchange: ev => put(e, { comment: ev.target.value.trim() }) })));
  refocus(box, key);
}

const SIDE_MIN = 360, EMAIL_MIN = 340, SIDE_STEP = 24;
function columnBar(lay) {
  const b = h('div', { class: 'vbar', tabindex: 0, title: 'Σύρετε για αλλαγή πλάτους, διπλό κλικ για επαναφορά', role: 'separator', 'aria-orientation': 'vertical', 'aria-label': 'Πλάτος στήλης αξιολόγησης', 'aria-valuemin': SIDE_MIN });
  const width = () => Math.round(lay.querySelector('.assess').getBoundingClientRect().width);
  const sync = () => { b.setAttribute('aria-valuenow', width()); b.setAttribute('aria-valuemax', Math.round(lay.getBoundingClientRect().width - b.offsetWidth - EMAIL_MIN)) };
  const set = px => { UI.side = Math.max(SIDE_MIN, Math.min(lay.getBoundingClientRect().width - b.offsetWidth - EMAIL_MIN, Math.round(px))); applyUI(); sync() };
  b.addEventListener('mousedown', ev => {
    ev.preventDefault(); b.focus(); b.classList.add('drag');
    const right = lay.getBoundingClientRect().right, move = m => set(right - m.clientX);
    const up = () => { b.classList.remove('drag'); document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up) };
    document.addEventListener('mousemove', move); document.addEventListener('mouseup', up);
  });
  b.addEventListener('dblclick', () => { delete UI.side; applyUI(); sync() });
  b.addEventListener('keydown', ev => { const d = { ArrowLeft: SIDE_STEP, ArrowRight: -SIDE_STEP }[ev.key]; if (d) { ev.preventDefault(); set(width() + d) } });
  queueMicrotask(sync); return b;
}

function show(e) {
  const was = cur && items.get(cur.id); if (was) was.classList.remove('sel');
  const moved = !cur || cur.id !== e.id; cur = e;
  const now = items.get(e.id); if (now) now.classList.add('sel');
  const lay = h('div', { class: 'layout' }, h('div', { class: 'reading', id: 'reading' }, renderReading(e)));
  $('detail').replaceChildren(
    h('h1', { class: 'subject' }, e.subject || '(χωρίς θέμα)'),
    h('div', { class: 'meta' }, h('span', null, e.sender), h('span', null, date(e.received)), h('span', null, 'Παρτίδα ' + e.dataset)),
    lay);
  lay.append(h('div', { class: 'assess' })); lay.insertBefore(columnBar(lay), lay.lastChild);
  renderAssess(e); renderDock();
  if (moved) window.scrollTo(0, 0);
  if (now) { const L = $('items'), a = now.offsetTop, z = a + now.offsetHeight; if (a < L.scrollTop) L.scrollTop = a; else if (z > L.scrollTop + L.clientHeight) L.scrollTop = z - L.clientHeight }
}

// Panels
// Shrink the text to avoid scrolling; if even the smallest won't fit, stay readable and scroll.
function fitTiles(dlg) {
  for (let s = 13; s >= 10; s -= .5) { dlg.style.setProperty('--tile', s + 'px'); if (dlg.scrollHeight <= dlg.clientHeight) return }
  dlg.style.setProperty('--tile', '13px');
}
let catMode = 'rank';
function renderCats() {
  const e = cur, picks = catMode === 'rank' && e ? rec(e).cats : [];
  $('catTitle').textContent = catMode === 'rank' ? 'Επιλέξτε έως τρεις κατηγορίες, με σειρά σημασίας' : 'Φίλτρο κατηγορίας';
  $('catHint').textContent = catMode === 'rank' ? `Η πρώτη που πατάτε γίνεται 1η, η επόμενη 2η. Επιλέχθηκαν ${picks.length} από 3. Το ποσοστό είναι η εκτίμηση του μοντέλου.` : 'Δείχνει τα email όπου αυτή είναι η πιθανότερη κατηγορία.';
  const pickFilter = c => { F.cat = c; $('catDlg').close(); renderList(); renderFilters() };
  const tiles = SORTED.map(c => {
    const at = picks.indexOf(c), full = catMode === 'rank' && at < 0 && picks.length >= 3;
    const on = catMode === 'rank' ? at >= 0 : F.cat === c;
    return h('button', { class: `tile${at >= 0 ? ` r${at + 1}` : ''}`, key: 'cat' + c, 'aria-pressed': String(on), disabled: full, onclick: () => { if (catMode === 'rank') { pickToggle(e, c); renderCats() } else pickFilter(c) } },
      h('b', null, c), catMode === 'rank' && e && h('span', { class: 'tile-side' }, at >= 0 && h('span', { class: 'badge' }, ORD[at]), h('small', null, (e.scores[INDEX.get(c)] || 0) + '%')));
  });
  if (catMode === 'filter') tiles.unshift(h('button', { class: 'tile', 'aria-pressed': String(!F.cat), onclick: () => pickFilter('') }, h('b', null, 'Όλες οι κατηγορίες')));
  const key = focusedKey();
  $('catTiles').replaceChildren(...tiles);
  refocus($('catTiles'), key);
}
function openCats(mode) { catMode = mode; renderCats(); $('catDlg').showModal(); fitTiles($('catDlg')) }
function renderActs() {
  const e = cur, mine = rec(e).actions || proposedDos(e), key = focusedKey();
  $('actTiles').replaceChildren(...Object.entries(ACTIONS).map(([d, [name, what]]) => h('button', { class: 'tile', key: 'act' + d, 'aria-pressed': String(mine.includes(d)), onclick: () => {
    const now = rec(e).actions || proposedDos(e);
    put(e, { actions: now.includes(d) ? now.filter(x => x !== d) : [...now, d] }); renderActs();
  } }, h('b', null, name), h('small', { class: 'long' }, what))));
  refocus($('actTiles'), key);
}
function openActions() { renderActs(); $('actDlg').showModal() }
function renderFilters() {
  const count = fn => E.filter(fn).length;
  const group = (title, name, options) => h('fieldset', null, h('legend', null, title), h('div', { class: 'tiles' }, options.map(([value, label, n]) => h('button', { class: 'tile', 'aria-pressed': String(F[name] === value), onclick: () => { F[name] = value; renderList(); renderFilters() } }, h('b', null, label), h('small', null, n + ' email')))));
  const batches = [...new Set(E.map(e => e.dataset))].sort();
  $('filterBody').replaceChildren(
    group('Έλεγχος', 'status', [['all', 'Όλα', E.length], ['todo', 'Χωρίς έλεγχο', count(FILTERS.status.todo)], ['done', 'Ελεγμένα', count(FILTERS.status.done)], ['wrong', 'Με διαφορετική 1η κατηγορία', count(FILTERS.status.wrong)]]),
    group('Εκτίμηση μοντέλου', 'level', [['all', 'Όλα', E.length], ['high', `Βέβαιο, ${D.high}% και πάνω`, count(FILTERS.level.high)], ['low', `Λιγότερο βέβαιο, κάτω από ${D.high}%`, count(FILTERS.level.low)], ['second', 'Με δεύτερη πιθανή κατηγορία', count(FILTERS.level.second)]]),
    group('Παρτίδα', 'batch', [['', 'Όλες', E.length], ...batches.map(b => [b, b, count(e => e.dataset === b)])]),
    group('Προτεινόμενη ενέργεια', 'action', [['', 'Όλες', E.length], ...Object.entries(ACTIONS).map(([d, [name]]) => [d, name, count(e => proposedDos(e).includes(d))])]),
    h('fieldset', null, h('legend', null, 'Κατηγορία'), h('div', { class: 'tiles' }, h('button', { class: 'tile', id: 'filterCat', 'aria-pressed': String(!!F.cat), onclick: () => openCats('filter') }, h('b', null, F.cat || 'Όλες οι κατηγορίες'), h('small', null, 'Αλλαγή…')))));
}
function resetFilters() { Object.assign(F, { status: 'all', level: 'all', batch: '', action: '', cat: '' }); renderList(); renderFilters() }
$('filters').onclick = () => { renderFilters(); $('filterDlg').showModal() };
$('filterReset').onclick = $('clearFilters').onclick = resetFilters;
$('filterDone').onclick = () => $('filterDlg').close();
$('catDone').onclick = () => $('catDlg').close(); $('actDone').onclick = () => $('actDlg').close();
document.querySelectorAll('dialog').forEach(d => d.addEventListener('click', ev => { if (ev.target === d) d.close() }));
window.addEventListener('resize', () => { if ($('catDlg').open) fitTiles($('catDlg')) });

// Chrome
$('tList').onclick = () => { UI.list = !UI.list; applyUI() };
$('split').addEventListener('mousedown', ev => {
  ev.preventDefault(); const left = $('list').getBoundingClientRect().left; $('split').classList.add('drag'); $('main').classList.remove('anim');
  const move = m => { UI.w = Math.round(m.clientX - left); applyUI() };
  const up = () => { $('split').classList.remove('drag'); $('main').classList.add('anim'); document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up) };
  document.addEventListener('mousemove', move); document.addEventListener('mouseup', up);
});
$('reviewer').value = load(NAMEKEY, ''); $('reviewer').oninput = () => store(NAMEKEY, $('reviewer').value.trim());
function tab(name) { [['tabReview', 'panReview'], ['tabFiles', 'panFiles']].forEach(([t, p]) => { const on = t === name; $(t).setAttribute('aria-selected', on); $(t).tabIndex = on ? 0 : -1; $(p).hidden = !on }) }
$('tabReview').onclick = () => tab('tabReview'); $('tabFiles').onclick = () => tab('tabFiles');
document.querySelector('.tabs').addEventListener('keydown', ev => { if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') { const next = $('tabReview').getAttribute('aria-selected') === 'true' ? 'tabFiles' : 'tabReview'; tab(next); $(next).focus() } });
$('help').onclick = () => $('helpDlg').showModal(); $('helpClose').onclick = () => $('helpDlg').close();
$('prev').onclick = () => go(-1); $('next').onclick = $('nextBig').onclick = () => go(1);
$('clear').onclick = () => { if (cur) { delete V[cur.id]; store(KEY, V); kpi(); renderList(); renderAssess(cur); renderDock() } };
$('fText').oninput = renderList;
document.addEventListener('keydown', ev => { if (document.querySelector('dialog[open]') || /INPUT|TEXTAREA|SELECT/.test(ev.target.tagName)) return; if (ev.key === 'j') go(1); if (ev.key === 'k') go(-1) });

// Files
const COLUMNS = ['id', 'business_category', 'business_comment', 'reviewer', 'reviewed_at', 'business_category_2', 'business_category_3', 'business_actions'];
const q = s => '"' + String(s).replace(/"/g, '""') + '"';
$('export').onclick = () => {
  const name = $('reviewer').value.trim();
  if (!name) { say('Γράψτε πρώτα το όνομά σας.'); $('reviewer').focus(); return }
  if (!Object.keys(V).length) { say('Δεν υπάρχει έλεγχος για εξαγωγή.'); return }
  const lines = [COLUMNS.join(',')].concat(Object.entries(V).map(([id, x]) =>
    [id, x.cats[0] || '', x.comment || '', x.by || name, x.at || '', x.cats[1] || '', x.cats[2] || '', (x.actions || []).join('; ')].map(q).join(',')));
  const a = h('a'); a.href = URL.createObjectURL(new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv' }));
  a.download = 'business_review_' + name.replace(/[^\p{L}\p{N}]+/gu, '_') + '.csv'; a.click();
};
// CSV with quoted commas, quotes and line breaks (comments can hold all three).
function readCsv(t) {
  let lines = t.replace(/^﻿/, '').split(/\r?\n/);
  // Excel in a Greek locale opens the file as one column and saves each row as one quoted cell plus ';'.
  // ponytail: unwrapped line by line, so a hand-edited stray quote costs one cell, not the rest of the file
  if (/,.*;$/.test(lines[0])) lines = lines.map(l => { l = l.replace(/;+$/, ''); return /^".*"$/.test(l) ? l.slice(1, -1).replace(/""/g, '"') : l });
  const s = lines.join('\n'), d = lines[0].includes(',') ? ',' : ';', rows = [[]]; let f = '', q = false;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (q) { if (ch !== '"') f += ch; else if (s[i + 1] === '"') { f += '"'; i++ } else q = false }
    else if (ch === '"') q = true;
    else if (ch === d) { rows.at(-1).push(f); f = '' }
    else if (ch === '\n') { rows.at(-1).push(f); f = ''; rows.push([]) }
    else f += ch;
  }
  rows.at(-1).push(f);
  return rows.filter(r => r.some(c => c.trim()));
}
$('import').onclick = () => $('file').click();
$('file').onchange = ev => {
  const f = ev.target.files[0]; if (!f) return;
  f.text().then(t => {
    const rows = readCsv(t);
    const head = (rows.shift() || []).map(s => s.trim()), at = n => head.indexOf(n), here = new Set(E.map(e => e.id)); let count = 0, elsewhere = 0;
    rows.forEach(c => {
      const id = (c[at('id')] || '').trim(); if (!id) return;
      const cats = [c[at('business_category')], c[at('business_category_2')], c[at('business_category_3')]].filter(Boolean);
      const actions = (c[at('business_actions')] || '').split('; ').filter(d => ACTIONS[d]);
      // Kept even when the email is not in this page, so the next export does not drop it.
      V[id] = { cats, actions: actions.length ? actions : null, comment: c[at('business_comment')] || '', at: c[at('reviewed_at')] || '', by: c[at('reviewer')] || 'εισαγωγή' };
      here.has(id) ? count++ : elsewhere++;
    });
    store(KEY, V); kpi(); renderList(); if (cur) renderAssess(cur); $('file').value = '';
    say(`Φορτώθηκε ο έλεγχος για ${count} email.` + (elsewhere ? ` ${elsewhere} ακόμη αφορούν email που δεν υπάρχουν σε αυτή τη σελίδα.` : ''));
  });
};

applyUI(); kpi(); renderList(); if (shown.length) show(shown[0]);
if (!load(NAMEKEY, '')) $('helpDlg').showModal();
setTimeout(() => $('main').classList.add('anim'), 50);
</script></body></html>
"""


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build(sys.argv[1] if len(sys.argv) > 1 else "probs_v1")
