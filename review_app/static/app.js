"use strict";
/* Review app page. Plain JS, no build. Data from /api/*; text is always set with textContent. */

// ------------------------------------------------------------------ words
const T = {
  el: {
    appName: "Έλεγχος email", signIn: "Είσοδος", signOut: "Έξοδος", yourName: "Ονοματεπώνυμο",
    yourEmail: "Email εργασίας (doValue)", accessCode: "Κωδικός πρόσβασης",
    signinIntro: "Συνδεθείτε για να ελέγξετε τα email που ταξινόμησε το σύστημα.",
    signinNote: "Προσωρινή σύνδεση έως ότου ενεργοποιηθεί η σύνδεση Microsoft. Το πρόγραμμα περιήγησης θα σας θυμάται.",
    errName: "Συμπληρώστε όνομα και έγκυρο email.", errCode: "Λάθος κωδικός πρόσβασης.",
    errMany: "Πολλές προσπάθειες. Δοκιμάστε ξανά σε λίγα λεπτά.",
    qReview: "Προς έλεγχο", qAuto: "Αυτόματα", qReviewed: "Ελεγμένα", qAll: "Όλα",
    search: "Αναζήτηση: θέμα, αποστολέας, κατηγορία…", day: "Ημέρα", by: "Βάσει", order: "Σειρά",
    allDays: "Όλες οι μέρες", byArrival: "Άφιξης", byReview: "Ελέγχου", newest: "Νεότερα πρώτα", oldest: "Παλαιότερα πρώτα",
    wholeDay: "Όλη η μέρα", stillArriving: "συνεχίζεται", noItems: "Δεν υπάρχουν email εδώ.",
    noReviewTime: "Μόνο τα ελεγμένα email έχουν ώρα ελέγχου.",
    pickOne: "Επιλέξτε ένα email από τη λίστα.",
    stClassifying: "Ταξινομείται…", clfPreparing: "Ο ταξινομητής ξεκινά…", clfRunning: "Ταξινόμηση {done} από {total}",
    stReceived: "Δεν έχει ταξινομηθεί", stReview: "Χρειάζεται έλεγχο", stAuto: "Αυτόματη ταξινόμηση",
    stException: "Σφάλμα — έλεγχος", stReviewed: "Ελέγχθηκε",
    openBy: "Ανοιχτό: {n}", attachments: "{n} συνημμένα",
    lockedBy: "Το email το έχει ανοιχτό ο/η {n}. Μπορείτε να το δείτε· αποφύγετε να το ελέγξετε ταυτόχρονα.",
    leftMailbox: "Το email δεν βρίσκεται πια στο γραμματοκιβώτιο.",
    decision: "Ταξινόμηση", suggestion: "Πρόταση συστήματος", noSuggestion: "Δεν υπάρχει ακόμη πρόταση συστήματος.",
    certainty: "Βεβαιότητα", whyReview: "Γιατί χρειάζεται έλεγχο", alsoConsidered: "Εξετάστηκαν επίσης",
    accept: "Η πρόταση είναι σωστή", other: "Άλλη κατηγορία", noneFits: "Καμία κατηγορία δεν ταιριάζει",
    chooseCat: "Γράψτε ή επιλέξτε κατηγορία", extra: "Επιπλέον αίτημα στο ίδιο email (προαιρετικό)",
    comment: "Σχόλιο (προαιρετικό)", save: "Αποθήκευση", saved: "Αποθηκεύτηκε", next: "Επόμενο μετά την αποθήκευση",
    reviewedBy: "Ελέγχθηκε από {n}, {d}", change: "Αλλαγή", final: "Τελική κατηγορία",
    badCat: "Επιλέξτε κατηγορία από τη λίστα.", changed: "Κάποιος άλλος αποθήκευσε αυτό το email στο μεταξύ. Φορτώθηκε η νέα εκδοχή· ελέγξτε την και αποθηκεύστε ξανά.",
    actions: "Τι πρέπει να γίνει", noActions: "Δεν προέκυψαν ενέργειες.",
    customer: "Πελάτης", customerFrom: "από το μητρώο {f}",
    aboutPerson: "Το email αφορά", people: "Πρόσωπα στο email",
    confirmed: "Επιβεβαιωμένος", possible: "Πιθανός", matchedOn: "Ταίριαξε με",
    sameName: "{n} πελάτες έχουν το ίδιο όνομα — κανένας δεν επιλέχθηκε αυτόματα.",
    nameMismatch: "Το όνομα στο email δεν ταιριάζει με τον κάτοχο στο μητρώο.",
    noCustomer: "Δεν βρέθηκε πελάτης στο μητρώο.", unmatched: "Δεν υπάρχουν στο μητρώο",
    tooMany: "Το όνομα «{v}» ταιριάζει σε {n} πελάτες· χρειάζεται ΑΦΜ ή λογαριασμός.",
    taxId: "ΑΦΜ", custCode: "Κωδ. πελάτη", portfolio: "Χαρτοφυλάκιο", status: "Κατάσταση", source: "Πηγή",
    portal: "Portal", yes: "Ναι", no: "Όχι", accounts: "Λογαριασμοί ({n})", recent: "Πρόσφατα αιτήματα Qualco",
    account: "Λογαριασμός", type: "Τύπος", settlement: "Ρύθμιση", created: "Δημιουργία",
    found: "Στοιχεία που βρέθηκαν", foundNone: "Δεν βρέθηκαν αναγνωριστικά.", value: "Τιμή", belongs: "Ανήκει σε",
    where: "Πού βρέθηκε", checked: "έλεγχος ψηφίου", history: "Ιστορικό", readError: "Τα στοιχεία πελάτη δεν διαβάστηκαν: {e}",
    email: "Email", showImages: "Εμφάνιση εικόνων", hideImages: "Απόκρυψη εικόνων", download: "Λήψη",
    downloadEmail: "Λήψη email ({x})", downloadAll: "Λήψη όλων (.zip)", openTab: "Άνοιγμα σε νέα καρτέλα",
    noPreview: "Αυτός ο τύπος αρχείου δεν προβάλλεται στον browser.", page: "σελ. {n}",
    evRegistered: "Παραλήφθηκε", evClassified: "Ταξινομήθηκε από το σύστημα", evReviewed: "Ελέγχθηκε",
    evLeft: "Έφυγε από το γραμματοκιβώτιο", system: "σύστημα",
    analysis: "Σημείωση μοντέλου",
    suggestedCats: "Προτάσεις συστήματος", greekCats: "Ελληνικά", englishCats: "Αγγλικά",
    noMatchCats: "Καμία κατηγορία δεν ταιριάζει με την αναζήτηση.", findCat: "Αναζήτηση κατηγορίας…", clear: "Καθαρισμός",
    activity: "Ιστορικό ενεργειών", close: "Κλείσιμο", onlyReviews: "Μόνο έλεγχοι", noEvents: "Δεν υπάρχουν ενέργειες ακόμη.",
    evClassifiedAs: "Πρόταση: {c} ({p}) → {r}", evChanged: "{a} → {b}", evFirst: "Ορίστηκε: {b}",
    routeAUTO: "αυτόματο", routeREVIEW: "προς έλεγχο", routeEXCEPTION: "σφάλμα",
    evRerouted: "Νέο όριο αυτόματης ταξινόμησης",
    signingIn: "Σύνδεση…", saving: "Αποθήκευση…", loading: "Φόρτωση…", loadingEmail: "Φόρτωση email…",
    resetReview: "Επαναφορά σε «Προς έλεγχο»", resetConfirm: "Ναι, επαναφορά", cancel: "Άκυρο",
    resetQuestion: "Ο έλεγχος θα αναιρεθεί και το email θα επιστρέψει στα «Προς έλεγχο». Το ιστορικό τον κρατά.",
    resetDone: "Επέστρεψε στα «Προς έλεγχο»", evReset: "Ο έλεγχος αναιρέθηκε", evResetDetail: "Ήταν: {b}",
    ingestTitle: "Παραλαβή email", ingestManual: "Τα email παραλαμβάνονται χειροκίνητα, όταν κάποιος ξεκινήσει τη λήψη.",
    ingestSchedule: "Τα email παραλαμβάνονται αυτόματα, με πρόγραμμα.", ingestNext: "Επόμενη παραλαβή",
    ingestLast: "Τελευταία παραλαβή", ingestCount: "{n} email", ingestImported: "εισαγωγή αρχείων",
    ingestNone: "Δεν έχει γίνει ακόμη παραλαβή.", ingestDelay: "Ένα νέο email εμφανίζεται εδώ μετά την επόμενη παραλαβή.",
    error: "Κάτι πήγε στραβά. Δοκιμάστε ξανά.",
    highlights: "Επισημάνσεις", lgClass: "Κατηγορία", lgAction: "Ενέργεια", lgId: "Στοιχεία πελάτη",
    viewOriginal: "Πρωτότυπο", viewText: "Κείμενο με επισημάνσεις", evidence: "Τεκμήρια από το email",
    noTextView: "Δεν υπάρχει κείμενο για επισημάνσεις σε αυτό το αρχείο.",
    stepCategory: "1 · Κατηγορία", stepActions: "2 · Ενέργειες", stepSave: "3 · Αποθήκευση",
    tickActions: "Τσεκάρετε όσες θα γίνουν", chosenActions: "Επιλέχθηκαν στον έλεγχο",
    proposedOnly: "Προτάσεις συστήματος — δεν έχουν επιλεγεί ακόμη",
    actionsForOther: "Οι προτεινόμενες ενέργειες αφορούν την αρχική κατηγορία «{c}». Ελέγξτε αν ισχύουν ή προσθέστε άλλες.",
    noActionsChosen: "Δεν έχει επιλεγεί καμία ενέργεια.", addAction: "Προσθήκη ενέργειας", findAction: "Αναζήτηση ενέργειας ή κωδικού…",
    generalActions: "Γενικές ενέργειες", addedByYou: "προστέθηκε", remove: "Αφαίρεση", actionsCount: "{n} ενέργειες",
  },
  en: {
    appName: "Email review", signIn: "Sign in", signOut: "Sign out", yourName: "Full name",
    yourEmail: "Work email (doValue)", accessCode: "Access code",
    signinIntro: "Sign in to review the emails the system classified.",
    signinNote: "Temporary sign-in until Microsoft sign-in is switched on. This browser will remember you.",
    errName: "Enter your name and a valid email.", errCode: "Wrong access code.",
    errMany: "Too many attempts. Try again in a few minutes.",
    qReview: "To review", qAuto: "Automatic", qReviewed: "Reviewed", qAll: "All",
    search: "Search: subject, sender, category…", day: "Day", by: "By", order: "Order",
    allDays: "All days", byArrival: "Arrival", byReview: "Review", newest: "Newest first", oldest: "Oldest first",
    wholeDay: "Whole day", stillArriving: "ongoing", noItems: "No emails here.",
    noReviewTime: "Only reviewed emails have a review time.",
    pickOne: "Pick an email from the list.",
    stClassifying: "Classifying…", clfPreparing: "Classifier starting…", clfRunning: "Classifying {done} of {total}",
    stReceived: "Not classified yet", stReview: "Needs review", stAuto: "Classified automatically",
    stException: "Error — review", stReviewed: "Reviewed",
    openBy: "Open: {n}", attachments: "{n} attachments",
    lockedBy: "{n} has this email open. You can look; avoid reviewing it at the same time.",
    leftMailbox: "This email is no longer in the mailbox.",
    decision: "Classification", suggestion: "System suggestion", noSuggestion: "No system suggestion yet.",
    certainty: "Certainty", whyReview: "Why it needs review", alsoConsidered: "Also considered",
    accept: "The suggestion is right", other: "Another category", noneFits: "No category fits",
    chooseCat: "Type or pick a category", extra: "Further request in the same email (optional)",
    comment: "Comment (optional)", save: "Save", saved: "Saved", next: "Open the next one after saving",
    reviewedBy: "Reviewed by {n}, {d}", change: "Change", final: "Final category",
    badCat: "Pick a category from the list.", changed: "Someone else saved this email meanwhile. The new version is loaded; check it and save again.",
    actions: "What needs to happen", noActions: "No actions.",
    customer: "Customer", customerFrom: "from registry {f}",
    aboutPerson: "The email is about", people: "People in the email",
    confirmed: "Confirmed", possible: "Possible", matchedOn: "Matched on",
    sameName: "{n} customers share this name — none was picked automatically.",
    nameMismatch: "The name in the email does not match the registry owner.",
    noCustomer: "No customer found in the registry.", unmatched: "Not in the registry",
    tooMany: "The name “{v}” matches {n} customers; a tax ID or account is needed.",
    taxId: "Tax ID", custCode: "Customer code", portfolio: "Portfolio", status: "Status", source: "Source",
    portal: "Portal", yes: "Yes", no: "No", accounts: "Accounts ({n})", recent: "Recent Qualco requests",
    account: "Account", type: "Type", settlement: "Settlement", created: "Created",
    found: "Details found", foundNone: "No identifiers found.", value: "Value", belongs: "Belongs to",
    where: "Found in", checked: "check digit", history: "History", readError: "Customer details could not be read: {e}",
    email: "Email", showImages: "Show images", hideImages: "Hide images", download: "Download",
    downloadEmail: "Download email ({x})", downloadAll: "Download all (.zip)", openTab: "Open in new tab",
    noPreview: "This file type cannot be shown in the browser.", page: "p. {n}",
    evRegistered: "Received", evClassified: "Classified by the system", evReviewed: "Reviewed",
    evLeft: "Left the mailbox", system: "system",
    analysis: "Model note",
    suggestedCats: "System suggestions", greekCats: "Greek", englishCats: "English",
    noMatchCats: "No category matches the search.", findCat: "Search categories…", clear: "Clear",
    activity: "Activity log", close: "Close", onlyReviews: "Reviews only", noEvents: "No activity yet.",
    evClassifiedAs: "Suggested: {c} ({p}) → {r}", evChanged: "{a} → {b}", evFirst: "Set to: {b}",
    routeAUTO: "automatic", routeREVIEW: "to review", routeEXCEPTION: "error",
    evRerouted: "New automatic threshold",
    signingIn: "Signing in…", saving: "Saving…", loading: "Loading…", loadingEmail: "Loading email…",
    resetReview: "Reset to “To review”", resetConfirm: "Yes, reset", cancel: "Cancel",
    resetQuestion: "The review will be undone and the email goes back to “To review”. The history keeps it.",
    resetDone: "Back in “To review”", evReset: "Review reset", evResetDetail: "Was: {b}",
    ingestTitle: "Email intake", ingestManual: "Emails are fetched by hand, when someone starts a fetch.",
    ingestSchedule: "Emails are fetched automatically, on a schedule.", ingestNext: "Next fetch",
    ingestLast: "Last fetch", ingestCount: "{n} emails", ingestImported: "file import",
    ingestNone: "No fetch has run yet.", ingestDelay: "A new email shows up here after the next fetch.",
    error: "Something went wrong. Please try again.",
    highlights: "Highlights", lgClass: "Category", lgAction: "Action", lgId: "Customer details",
    viewOriginal: "Original", viewText: "Text with highlights", evidence: "Evidence from the email",
    noTextView: "No text with highlights for this file.",
    stepCategory: "1 · Category", stepActions: "2 · Actions", stepSave: "3 · Save",
    tickActions: "Tick the ones to carry out", chosenActions: "Chosen in the review",
    proposedOnly: "System proposals — none chosen yet",
    actionsForOther: "The proposed actions were made for the original category “{c}”. Check they still apply or add others.",
    noActionsChosen: "No action chosen.", addAction: "Add an action", findAction: "Search actions or codes…",
    generalActions: "General actions", addedByYou: "added", remove: "Remove", actionsCount: "{n} actions",
  },
};
const FIELD = {
  el: { afm: "ΑΦΜ", case_ref: "Αρ. υπόθεσης/φακέλου", account: "Δανειακός λογαριασμός", contract: "Αρ. σύμβασης",
        iban: "IBAN", payment_code: "Κωδικός πληρωμής", phone: "Τηλέφωνο", adt: "Αρ. ταυτότητας", email: "Email" },
  en: { afm: "Tax ID", case_ref: "Case/file ref.", account: "Loan account", contract: "Contract no.",
        iban: "IBAN", payment_code: "Payment code", phone: "Phone", adt: "ID card", email: "Email" },
};
const ROLE = {
  el: { debtor: "Οφειλέτης", co_debtor: "Συνοφειλέτης / εγγυητής", deceased_debtor: "Αποβιώσας οφειλέτης",
        heir: "Κληρονόμος", representative: "Εκπρόσωπος", authority: "Αρχή", dovalue_or_bank: "doValue / τράπεζα",
        other_party: "Άλλος", none: "—" },
  en: { debtor: "Debtor", co_debtor: "Co-debtor / guarantor", deceased_debtor: "Deceased debtor", heir: "Heir",
        representative: "Representative", authority: "Authority", dovalue_or_bank: "doValue / bank",
        other_party: "Other party", none: "—" },
};
const ACTION = {
  el: { request: "Καταχώρηση αιτήματος στο Qualco", portal_referral: "Παραπομπή στο Portal",
        ask_identification: "Ζητάμε στοιχεία ταυτοποίησης", manual: "Χειρισμός από το προσωπικό",
        forward: "Προώθηση", reply: "Απάντηση με πρότυπο", bank_referral: "Παραπομπή στην τράπεζα",
        activity: "Καταγραφή δραστηριότητας", no_action: "Καμία ενέργεια" },
  en: { request: "File a Qualco request", portal_referral: "Refer to the Portal", ask_identification: "Ask for identification",
        manual: "Handled by staff", forward: "Forward", reply: "Reply with template", bank_referral: "Refer to the bank",
        activity: "Log an activity", no_action: "No action" },
};
const REASONS_EL = [
  [/^no tax ID \(AFM\) found/, "Δεν βρέθηκε ΑΦΜ στο email ή στα συνημμένα"],
  [/^tax ID not found in the customer registry/, "Ο ΑΦΜ δεν υπάρχει στο μητρώο πελατών"],
  [/^confidence (\d+)% is below (\d+)%/, "Βεβαιότητα $1% (κάτω από το όριο $2%)"],
  [/^its tax IDs lead to different categories: (.*)/, "Οι ΑΦΜ του email οδηγούν σε διαφορετικές κατηγορίες: $1"],
  [/^no category fits/, "Καμία κατηγορία δεν ταιριάζει"],
  [/^an attachment could not be read/, "Ένα συνημμένο δεν διαβάστηκε"],
  [/^classification failed/, "Η αυτόματη ταξινόμηση απέτυχε"],
  [/^the classifier returned no result/, "Η αυτόματη ταξινόμηση δεν έδωσε αποτέλεσμα"],
  [/^the name in the email differs/, "Το όνομα στο email διαφέρει από τον κάτοχο του ΑΦΜ/λογαριασμού στο μητρώο"],
  [/^the customer is only a possible match/, "Ο πελάτης είναι μόνο πιθανή αντιστοίχιση (από όνομα ή email)"],
  [/^the customer details could not be read/, "Δεν διαβάστηκαν τα στοιχεία πελάτη"],
  [/^email not found in/, "Το email δεν βρέθηκε στα αρχεία παραλαβής"],
];

// ------------------------------------------------------------------ state
let lang = store("lang") || "el";
const S = { user: null, mode: "dev", categories: [], items: [], queue: store("queue") || "review", day: "all",
            win: "all", basis: "received", sort: "newest", q: "", openId: null, detail: null, presence: {},
            viewer: { tab: "email", page: null, images: false }, choice: null };

function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem("rv." + key);
    localStorage.setItem("rv." + key, value);
  } catch (e) { /* private window: fine without */ }
  return null;
}
const t = (key, vars = {}) => (T[lang][key] || T.el[key] || key).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
const $ = (sel, root = document) => root.querySelector(sel);

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "text") el.textContent = v;
    else if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid);
  return el;
}

async function api(path, options = {}) {
  const init = { credentials: "same-origin", headers: {}, ...options };
  if (options.json !== undefined) {
    init.method = init.method || "POST";
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.json);
  }
  const res = await fetch(path, init);
  if (res.status === 401) { showSignin(); throw new Error("signin"); }
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

// ------------------------------------------------------------------ time (Athens)
const PARTS = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Athens", year: "numeric", month: "2-digit",
  day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
function ath(iso) {
  if (!iso) return null;
  const p = Object.fromEntries(PARTS.formatToParts(new Date(iso)).map((x) => [x.type, x.value]));
  return { day: `${p.year}-${p.month}-${p.day}`, hour: +p.hour, time: `${p.hour}:${p.minute}` };
}
const pad = (n) => String(n).padStart(2, "0");
const winLabel = (w) => `${pad(w * 4)}:00–${pad(w * 4 + 4 === 24 ? 24 : w * 4 + 4)}:00`;
function dayLabel(day) {
  const [y, m, d] = day.split("-").map(Number);
  return new Intl.DateTimeFormat(lang === "el" ? "el-GR" : "en-GB", { weekday: "short", day: "numeric", month: "short",
    year: y === new Date().getFullYear() ? undefined : "numeric", timeZone: "UTC" }).format(Date.UTC(y, m - 1, d));
}
function when(iso) {
  const a = ath(iso);
  if (!a) return "";
  return a.day === ath(new Date().toISOString()).day ? a.time : `${dayLabel(a.day)} ${a.time}`;
}

// ------------------------------------------------------------------ list
const queueOf = (it) => it.status === "REVIEWED" ? "reviewed"
  : it.status === "CLASSIFIED" && it.route === "AUTO" ? "auto" : "review";
const basisTime = (it) => S.basis === "reviewed" ? it.reviewedAt : it.receivedAt;
const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const fromOf = (it) => it.from || "";

function statusPill(it) {
  if (it.status === "REVIEWED") {
    const by = it.reviewedBy && it.reviewedBy.name;
    return h("span", { class: "pill done", title: by ? `${by}, ${when(it.reviewedAt)}` : null,
      text: by ? `${t("stReviewed")} · ${by}` : t("stReviewed") });
  }
  if (it.status === "CLASSIFYING") return h("span", { class: "pill working", text: t("stClassifying") });
  if (it.status === "RECEIVED") return h("span", { class: "pill plain", text: t("stReceived") });
  if (it.route === "AUTO") return h("span", { class: "pill auto", text: t("stAuto") });
  if (it.route === "EXCEPTION") return h("span", { class: "pill bad", text: t("stException") });
  return h("span", { class: "pill review", text: t("stReview") });
}

function filtered() {
  const q = norm(S.q.trim());
  return S.items.filter((it) => {
    if (q && !norm([it.subject, it.from, it.finalCategory, it.modelCategory, it.id].join(" ")).includes(q)) return false;
    const a = ath(basisTime(it));
    if (S.basis === "reviewed" && !a) return false;
    if (S.day !== "all" && (!a || a.day !== S.day)) return false;
    if (S.day !== "all" && S.win !== "all" && Math.floor(a.hour / 4) !== +S.win) return false;
    return true;
  });
}

function renderQueues(base) {
  const counts = { review: 0, auto: 0, reviewed: 0, all: base.length };
  base.forEach((it) => counts[queueOf(it)]++);
  const nav = $("#queues");
  nav.replaceChildren(...[["review", "qReview"], ["auto", "qAuto"], ["reviewed", "qReviewed"], ["all", "qAll"]].map(
    ([key, label]) => h("button", { role: "tab", type: "button", "aria-selected": String(S.queue === key),
      onclick: () => { S.queue = key; store("queue", key); renderList(); } },
    h("span", { class: "count", text: String(counts[key]) }), t(label))));
}

function renderDays() {
  const sel = $("#day");
  const days = new Map();
  S.items.forEach((it) => { const a = ath(basisTime(it)); if (a) days.set(a.day, (days.get(a.day) || 0) + 1); });
  const sorted = [...days.keys()].sort().reverse();
  if (S.day !== "all" && !days.has(S.day)) S.day = "all";
  sel.replaceChildren(h("option", { value: "all", text: `${t("allDays")}` }),
    ...sorted.map((d) => h("option", { value: d, text: `${dayLabel(d)} (${days.get(d)})` })));
  sel.value = S.day;
}

function renderWindows(base) {
  const box = $("#windows");
  if (S.day === "all") { box.hidden = true; return; }
  box.hidden = false;
  const counts = [0, 0, 0, 0, 0, 0];
  const toReview = [0, 0, 0, 0, 0, 0];
  base.forEach((it) => {
    const a = ath(basisTime(it));
    if (a && a.day === S.day) { const w = Math.floor(a.hour / 4); counts[w]++; if (queueOf(it) === "review") toReview[w]++; }
  });
  const nowA = ath(new Date().toISOString());
  const current = nowA.day === S.day ? Math.floor(nowA.hour / 4) : -1;
  box.replaceChildren(
    h("button", { type: "button", class: "whole", "aria-pressed": String(S.win === "all"),
      onclick: () => { S.win = "all"; renderList(); } }, `${t("wholeDay")} · `, h("span", { class: "n", text: String(counts.reduce((a, b) => a + b, 0)) })),
    ...counts.map((n, w) => h("button", { type: "button", class: n ? "" : "empty", "aria-pressed": String(String(S.win) === String(w)),
      title: toReview[w] ? `${toReview[w]} ${t("qReview").toLowerCase()}` : null,
      onclick: () => { S.win = String(w); renderList(); } },
    `${winLabel(w)} · `, h("span", { class: "n", text: String(n) }), w === current ? ` (${t("stillArriving")})` : "")));
}

function renderList() {
  const base = filtered();
  renderQueues(base);
  renderWindows(S.items.filter((it) => !S.q || base.includes(it)));
  const items = base.filter((it) => S.queue === "all" || queueOf(it) === S.queue)
    .sort((a, b) => (basisTime(a) || "").localeCompare(basisTime(b) || "") * (S.sort === "oldest" ? 1 : -1));
  const list = $("#list");
  if (!items.length) {
    list.replaceChildren(h("div", { class: "none", text: S.basis === "reviewed" ? `${t("noItems")} ${t("noReviewTime")}` : t("noItems") }));
    return;
  }
  const out = [];
  let group = null;
  for (const it of items) {
    const a = ath(basisTime(it));
    const key = a ? `${a.day}|${Math.floor(a.hour / 4)}` : "none";
    if (key !== group) {
      group = key;
      const count = items.filter((x) => { const b = ath(basisTime(x)); return b && `${b.day}|${Math.floor(b.hour / 4)}` === key; }).length;
      out.push(h("div", { class: "group" }, h("span", { text: a ? `${dayLabel(a.day)} · ${winLabel(Math.floor(a.hour / 4))}` : "—" }),
        h("span", { text: String(count) })));
    }
    const viewers = Object.entries(S.presence).filter(([id]) => id !== S.user.id).filter(([, p]) => p.caseId === it.id).map(([, p]) => p.name);
    const atts = (it.sourceRefs && it.sourceRefs.attachments || []).length;
    out.push(h("button", { class: "item", type: "button", "aria-current": String(S.openId === it.id), "data-id": it.id,
      onclick: () => openCase(it.id) },
    h("div", { class: "top" }, h("span", { class: "from", text: fromOf(it) || "—" }), h("span", { text: when(basisTime(it)) })),
    h("div", { class: "subject", text: it.subject || "—" }),
    h("div", { class: "tags" }, statusPill(it),
      h("span", { class: "cat", text: it.finalCategory || it.modelCategory || "" }),
      atts ? h("span", { class: "muted small", text: t("attachments", { n: atts }) }) : null,
      viewers.length ? h("span", { class: "presence", text: t("openBy", { n: viewers.join(", ") }) }) : null)));
  }
  list.replaceChildren(...out);
}

async function loadCases() {
  const res = await api("/api/cases");
  if (!res.ok) return;
  S.items = res.data.items || [];
  S.classifier = res.data.classifier || { running: false };
  renderDays();
  renderList();
  renderClassifier();
}

// Progress chip in the top bar while the classifier job works through the waiting emails.
function renderClassifier() {
  const c = S.classifier || {};
  const el = $("#clf");
  el.hidden = !c.running;
  if (!c.running) return;
  const preparing = c.phase === "preparing";
  const label = preparing ? t("clfPreparing") : t("clfRunning", { done: Math.min(c.done + 1, c.total), total: c.total });
  el.replaceChildren(h("span", { class: "spinner", "aria-hidden": "true" }), h("span", { text: label }),
    h("span", { class: "bar", "aria-hidden": "true" },
      h("span", { style: `width:${c.total ? Math.round((100 * c.done) / c.total) : 0}%` })));
}

// The list refreshes every 20 s, and every 4 s while the classifier runs, so each email is seen moving on.
async function pollCases() {
  await loadCases().catch(() => null);
  setTimeout(pollCases, S.classifier && S.classifier.running ? 4000 : 20000);
}

// ------------------------------------------------------------------ case
// ------------------------------------------------------------------ loading states
const spinner = (label) => h("div", { class: "loading", role: "status" }, h("span", { class: "spinner", "aria-hidden": "true" }),
  h("span", { text: label || t("loading") }));
const skeletonLines = (n) => Array.from({ length: n }, (_, i) => h("div", { class: "sk", style: `width:${[92, 70, 84, 56, 77][i % 5]}%` }));
function showCaseLoading() {
  const pane = $("#case");
  pane.setAttribute("aria-busy", "true");
  pane.replaceChildren(h("div", { class: "case-head" }, h("div", { class: "sk sk-title" }), h("div", { class: "sk", style: "width:45%" })),
    spinner(t("loadingEmail")),
    ...[4, 3, 5].map((n) => h("section", { class: "card sk-card" }, h("div", { class: "body" }, ...skeletonLines(n)))));
  $("#viewer-body").replaceChildren(spinner(t("loadingEmail")));
}
/* Wrap an iframe/img so a spinner covers it until it has actually loaded. */
function whenLoaded(el, label, watch = el) {
  const cover = spinner(label);
  cover.classList.add("cover");
  const done = () => cover.remove();
  watch.addEventListener("load", done);
  watch.addEventListener("error", done);
  setTimeout(done, 20000);  // never leave a spinner over a frame the browser handled silently
  return h("div", { class: "frame-wrap" }, el, cover);
}
function busy(button, label) {
  const text = button.textContent;
  button.disabled = true;
  button.classList.add("busy");
  button.textContent = label;
  return () => { button.disabled = false; button.classList.remove("busy"); button.textContent = text; };
}

let openToken = 0;
async function openCase(id, keepViewer) {
  if (S.openId && S.openId !== id) api(`/api/cases/${encodeURIComponent(S.openId)}/release`, { json: {} });
  S.openId = id;
  history.replaceState(null, "", `#${id}`);
  renderList();
  const token = ++openToken;
  if (!keepViewer) showCaseLoading();
  document.querySelector(`#list .item[data-id="${CSS.escape(id)}"]`)?.classList.add("opening");
  const res = await api(`/api/cases/${encodeURIComponent(id)}`).catch(() => null);
  if (token !== openToken) return;  // a newer click won; drop this answer
  document.querySelector(`#list .item[data-id="${CSS.escape(id)}"]`)?.classList.remove("opening");
  if (!res || !res.ok) { $("#case").removeAttribute("aria-busy"); $("#case").replaceChildren(h("div", { class: "empty" }, h("p", { text: t("error") }))); return; }
  S.detail = res.data;
  S.choice = null;
  S.forceEdit = false;
  S.comment = undefined;
  S.addOpen = false;
  S.enter = true; // animate this render only, not re-renders while reviewing
  if (!keepViewer) S.viewer = { tab: "email", page: null, images: false };
  api(`/api/cases/${encodeURIComponent(id)}/open`, { json: {} });
  renderCase();
  renderViewer();
}

function card(title, sub, ...body) {
  return h("section", { class: "card" }, h("h3", {}, h("span", { text: title }), sub ? h("span", { class: "sub", text: sub }) : null),
    h("div", { class: "body" }, ...body));
}

function reasonText(r) {
  if (lang !== "el") return r;
  for (const [re, out] of REASONS_EL) if (re.test(r)) return r.replace(re, out);
  return r;
}
function certaintyWord(c) {
  if (c === null || c === undefined) return "";
  const pct = Math.round(c * 100);
  // 90% is where automatic classification starts (AUTO_ACCEPT_THRESHOLD).
  const word = lang === "el" ? (c >= .98 ? "πολύ υψηλή" : c >= .9 ? "υψηλή" : c >= .7 ? "μέτρια" : "χαμηλή")
    : (c >= .98 ? "very high" : c >= .9 ? "high" : c >= .7 ? "medium" : "low");
  return `${t("certainty")}: ${word} (${pct}%)`;
}
function whereText(w) {
  if (!w) return "";
  if (w.kind === "attachment") return `${w.file}, ${t("page", { n: w.page })}`;
  const names = { el: { subject: "Θέμα", body: "Κείμενο email", thread: "Προηγούμενο μήνυμα", sender: "Αποστολέας" },
                  en: { subject: "Subject", body: "Email text", thread: "Earlier message", sender: "Sender" } };
  return names[lang][w.kind] || w.kind;
}
function sourceChip(w) {
  return h("button", { class: "src", type: "button", title: w.snippet || null, onclick: () => showSource(w), text: whereText(w) });
}
function showSource(w) {
  const keep = { images: S.viewer.images, hl: true };
  if (w.kind === "attachment") {
    const a = S.detail.attachments.find((x) => x.name === w.file);
    // Evidence is visible in the text view; the original PDF cannot be marked up by the browser.
    S.viewer = { ...keep, tab: a ? `a${a.n}` : "email", page: w.page, mode: a && a.hasText ? "text" : "original" };
  } else S.viewer = { ...keep, tab: "email", page: null, mode: "original" };
  renderViewer();
}
/* A quote shown as evidence, coloured like its highlight; click opens it where it was written. */
function quoteRow(e) {
  return h("div", { class: `quote q-${e.supports === "category" ? "class" : "action"}` },
    h("span", { text: `“${e.quote}”` }), " ", sourceChip({ ...e.where, snippet: e.quote }));
}
function snippet(text, value) {
  if (!text) return null;
  const el = h("div", { class: "snippet" });
  const i = value ? text.indexOf(value) : -1;
  if (i < 0) el.textContent = text;
  else el.append(text.slice(0, i), h("mark", { text: value }), text.slice(i + value.length));
  return el;
}

function decisionCard(c) {
  const parts = [];
  if (c.modelCategory) {
    parts.push(h("div", { class: "suggest" }, h("span", { class: "muted", text: t("suggestion") }),
      h("span", { class: "big", text: c.modelCategory }), h("span", { class: "muted", text: certaintyWord(c.confidence) })));
  } else parts.push(h("p", { class: "muted", text: t("noSuggestion") }));
  if (c.status !== "REVIEWED" && (c.routeReasons || []).length) {
    parts.push(h("div", { class: "small muted", text: t("whyReview") }),
      h("ul", { class: "reasons" }, ...c.routeReasons.map((r) => h("li", { text: reasonText(r) }))));
  }
  const classQuotes = ((c.understanding || {}).evidence || []).filter((e) => e.supports === "category");
  if (classQuotes.length) parts.push(h("div", { class: "quotes" }, h("div", { class: "small muted", text: t("evidence") }),
    ...classQuotes.map(quoteRow)));
  const votes = Object.entries(c.votes || {}).filter(([k]) => k !== c.modelCategory);
  if (votes.length) parts.push(h("div", { class: "votes" }, h("span", { class: "muted small", text: t("alsoConsidered") }),
    ...votes.map(([k, v]) => h("span", { text: `${k} · ${v}` }))));
  if (c.status === "REVIEWED" && !S.forceEdit) {
    parts.push(h("div", { class: "choice" },
      h("div", {}, h("span", { class: "muted", text: `${t("final")}: ` }), h("strong", { text: c.noMatch ? t("noneFits") : c.finalCategory || "—" })),
      (c.otherCategories || []).length ? h("div", { class: "muted", text: `+ ${c.otherCategories.join(", ")}` }) : null,
      c.reviewComment ? h("div", { class: "snippet", text: c.reviewComment }) : null,
      h("div", { class: "reviewed" }, h("span", { class: "muted", text: t("reviewedBy", { n: c.reviewedBy?.name || "—", d: when(c.reviewedAt) }) }),
        h("button", { class: "secondary", type: "button", text: t("change"), onclick: () => { S.forceEdit = true; S.choice = null; renderCase(); } }),
        resetControl(c))));
  } else parts.push(reviewForm(c));
  return card(editing(c) ? t("stepCategory") : t("decision"), null, ...parts);
}

/* "Reset to To review": a second, in-page step confirms (browsers' confirm() is not used). */
function resetControl(c) {
  const box = h("div", { class: "reset" });
  const ask = () => box.replaceChildren(h("div", { class: "reset-ask" },
    h("p", { text: t("resetQuestion") }),
    h("div", { class: "row" },
      h("button", { class: "danger", type: "button", text: t("resetConfirm"), onclick: async (e) => {
        const restore = busy(e.currentTarget, t("saving"));
        const res = await api(`/api/cases/${encodeURIComponent(c.id)}/reset`, { json: { _etag: c._etag } }).catch(() => ({ ok: false, data: {} }));
        restore();
        if (res.status === 409) { S.detail = res.data.case || S.detail; S.choice = null; renderCase(); notice(t("changed")); return; }
        if (!res.ok) { notice(t("error")); return; }
        toast(t("resetDone"));
        await loadCases();
        openCase(c.id, true);
      } }),
      h("button", { class: "link", type: "button", text: t("cancel"), onclick: idle }))));
  const idle = () => box.replaceChildren(h("button", { class: "link reset-link", type: "button", text: t("resetReview"), onclick: ask }));
  idle();
  return box;
}

// ------------------------------------------------------------------ category picker
const isGreek = (s) => /^[\s_]*[Ͱ-Ͽἀ-῿]/.test(s);
const catLabel = (c) => c.replace(/_/g, " ").replace(/\s+/g, " ").trim();
function sortedCategories() {
  const greek = S.categories.filter(isGreek).sort((a, b) => catLabel(a).localeCompare(catLabel(b), "el", { sensitivity: "base" }));
  const latin = S.categories.filter((c) => !isGreek(c)).sort((a, b) => catLabel(a).localeCompare(catLabel(b), "en", { sensitivity: "base" }));
  return { greek, latin };
}

/* Search box + scrolling list: suggestions first, then Greek A–Ω, then English A–Z. Arrow keys + Enter. */
function categoryPicker({ id, value, suggested, onPick }) {
  let current = value || "";
  let active = -1;
  let options = [];
  const input = h("input", { id, type: "search", class: "picker-search", placeholder: t("findCat"), autocomplete: "off",
    role: "combobox", "aria-controls": `${id}-list`, "aria-expanded": "true" });
  const chosen = h("div", { class: "picked", "aria-live": "polite" });
  const list = h("div", { class: "picker-list", role: "listbox", id: `${id}-list` });
  const pick = (c) => { current = c; onPick(c); paintChosen(); paint(); };
  function paintChosen() {
    chosen.replaceChildren(current ? h("span", { class: "chip" }, catLabel(current),
      h("button", { type: "button", class: "chip-x", "aria-label": t("clear"), text: "×", onclick: () => pick("") })) : "");
  }
  function paint() {
    const q = norm(input.value.trim()).replace(/_/g, " ");
    const hit = (c) => !q || norm(catLabel(c)).includes(q);
    const { greek, latin } = sortedCategories();
    const sugg = [...new Set(suggested || [])].filter((c) => S.categories.includes(c) && hit(c));
    const groups = [[t("suggestedCats"), sugg], [t("greekCats"), greek.filter((c) => hit(c) && !sugg.includes(c))],
      [t("englishCats"), latin.filter((c) => hit(c) && !sugg.includes(c))]].filter(([, items]) => items.length);
    options = groups.flatMap(([, items]) => items);
    if (active >= options.length) active = options.length - 1;
    let i = 0;
    list.replaceChildren(...groups.flatMap(([title, items]) => [h("div", { class: "picker-group", text: title }),
      ...items.map((c) => {
        const index = i++;
        return h("button", { type: "button", role: "option", class: `picker-opt${index === active ? " active" : ""}`,
          "aria-selected": String(c === current), onclick: () => pick(c) }, catLabel(c));
      })]), options.length ? "" : h("div", { class: "picker-none", text: t("noMatchCats") }));
    const el = list.querySelector(".picker-opt.active");
    if (el) el.scrollIntoView({ block: "nearest" });
  }
  input.addEventListener("input", () => { active = input.value ? 0 : -1; paint(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { active = Math.min(active + 1, options.length - 1); paint(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { active = Math.max(active - 1, 0); paint(); e.preventDefault(); }
    else if (e.key === "Enter" && options[Math.max(active, 0)]) { pick(options[Math.max(active, 0)]); e.preventDefault(); }
  });
  paintChosen();
  paint();
  return h("div", { class: "picker" }, chosen, input, list);
}

// ------------------------------------------------------------------ review: 1 category · 2 actions · 3 save
const editing = (c) => c.status !== "REVIEWED" || S.forceEdit;
const finalCategoryNow = (c) => S.choice === "accept" ? c.modelCategory : S.choice === "other" ? S.pick : null;
const actionText = (a) => `${ACTION[lang][a.do] || a.do}${[].concat(a.to || []).length ? " → " + [].concat(a.to).join(", ") : ""}`;
const codesOf = (a) => [a.open, a.closed, ...(a.codes || [])].filter(Boolean).filter((x, i, arr) => arr.indexOf(x) === i);
const asChoice = (a, source) => ({ ...a, to: a.to ? [].concat(a.to) : [], codes: a.codes || [], source, on: true });

function reviewForm(c) {
  if (S.choice === null) {
    const reviewed = c.status === "REVIEWED";
    S.choice = reviewed ? (c.noMatch ? "none" : c.finalCategory === c.modelCategory ? "accept" : "other")
      : c.modelCategory && c.route !== "EXCEPTION" ? "accept" : "other";
    S.pick = reviewed ? c.finalCategory || "" : "";
    S.pickExtra = (c.otherCategories || [])[0] || "";
    const u = c.understanding || {};
    S.acts = (c.finalActions || []).length ? c.finalActions.map((a) => ({ ...a, on: true }))
      : (u.actions || []).map((a) => asChoice(a, "suggested"));
  }
  const u = c.understanding || {};
  const suggested = [...Object.keys(c.votes || {}).filter((k) => k !== c.modelCategory), ...(u.otherRequests || [])];
  const cat = categoryPicker({ id: "rv-cat", value: S.pick, suggested, onPick: (v) => { S.pick = v; renderCase(); } });
  const opt = (value, label, extraEl) => h("div", { class: `opt${S.choice === value ? " on" : ""}` },
    h("label", {}, h("input", { type: "radio", name: "rv-choice", value, checked: S.choice === value,
      onchange: () => { S.choice = value; renderCase(); } }), h("span", { text: label })), extraEl || "");
  const extra = h("details", { class: "more extra", open: S.pickExtra ? true : null },
    h("summary", { text: t("extra") }),
    categoryPicker({ id: "rv-extra", value: S.pickExtra, suggested: u.otherRequests || [], onPick: (v) => { S.pickExtra = v; } }));
  return h("div", { class: "choice" },
    c.modelCategory ? opt("accept", `${t("accept")}: ${catLabel(c.modelCategory)}`) : "",
    opt("other", t("other"), S.choice === "other" ? h("div", { class: "reveal" }, cat) : ""),
    opt("none", t("noneFits")),
    extra);
}

function actionRow(a, u, editable) {
  const quotes = (u.evidence || []).filter((e) => e.supports === "action" && (a.because || []).includes(`${e.flag}=true`));
  const head = h("div", { class: "what" }, actionText(a),
    a.source === "added" ? h("span", { class: "pill plain", text: t("addedByYou") }) : "");
  const body = [
    a.category ? h("div", { class: "muted small", text: catLabel(a.category) }) : "",
    codesOf(a).length ? h("div", { class: "codes" }, ...codesOf(a).map((x) => h("code", { text: String(x) }))) : "",
    a.missing ? h("div", { class: "caveat", text: `${lang === "el" ? "Λείπει" : "Missing"}: ${a.missing}` }) : "",
    (a.reasons || []).length ? h("ul", {}, ...a.reasons.map((r) => h("li", { text: r }))) : "",
    ...quotes.map(quoteRow),
  ];
  if (!editable) return h("div", { class: "action" }, head, ...body);
  return h("div", { class: `action pickable${a.on === false ? " off" : ""}` },
    h("label", { class: "action-check" },
      h("input", { type: "checkbox", checked: a.on !== false, onchange: (e) => { a.on = e.target.checked; renderCase(); } }), head),
    a.source === "added" ? h("button", { class: "link remove", type: "button", text: t("remove"),
      onclick: () => { S.acts = S.acts.filter((x) => x !== a); renderCase(); } }) : "",
    ...body);
}

/* "Add an action": the rule table's actions for the chosen category first, then general ones; typing searches all. */
function actionAdder(category) {
  const catalog = S.catalog || { byCategory: {}, general: [] };
  const input = h("input", { type: "search", class: "picker-search", placeholder: t("findAction"), autocomplete: "off" });
  const list = h("div", { class: "picker-list" });
  const paint = () => {
    const q = norm(input.value.trim());
    const label = (o, cat) => norm(`${actionText(o)} ${codesOf(o).join(" ")} ${catLabel(cat || "")}`);
    const groups = [];
    if (category && catalog.byCategory[category]) groups.push([catLabel(category), catalog.byCategory[category].map((o) => [o, category])]);
    groups.push([t("generalActions"), catalog.general.map((o) => [o, null])]);
    if (q) for (const [cat, options] of Object.entries(catalog.byCategory)) if (cat !== category) groups.push([catLabel(cat), options.map((o) => [o, cat])]);
    const shown = groups.map(([title, items]) => [title, items.filter(([o, cat]) => !q || label(o, cat).includes(q))]).filter(([, items]) => items.length);
    list.replaceChildren(...shown.flatMap(([title, items]) => [h("div", { class: "picker-group", text: title }),
      ...items.map(([o, cat]) => h("button", { type: "button", class: "picker-opt", onclick: () => {
        S.acts.push(asChoice({ ...o, category: cat }, "added"));
        S.addOpen = true;
        renderCase();
      } }, actionText(o), codesOf(o).length ? h("span", { class: "muted small", text: `  ${codesOf(o).join(" · ")}` }) : ""))]),
    shown.length ? "" : h("div", { class: "picker-none", text: t("noMatchCats") }));
  };
  input.addEventListener("input", paint);
  paint();
  return h("details", { class: "more extra adder", open: S.addOpen ? true : null,
    ontoggle: (e) => { S.addOpen = e.target.open; } },
  h("summary", { text: t("addAction") }), h("div", { class: "picker" }, input, list));
}

function actionsCard(u, c) {
  const proposed = u.actions || [];
  if (!editing(c)) {
    const chosen = c.finalActions || [];
    if (chosen.length) return card(t("actions"), t("chosenActions"), ...chosen.map((a) => actionRow(a, u, false)));
    if (!proposed.length) return card(t("actions"), null, h("p", { class: "muted", text: t("noActions") }));
    return card(t("actions"), t("proposedOnly"), ...proposed.map((a) => actionRow(a, u, false)));
  }
  const finalCat = finalCategoryNow(c);
  const other = finalCat && c.modelCategory && finalCat !== c.modelCategory && S.acts.some((a) => a.source === "suggested");
  return card(t("stepActions"), t("tickActions"),
    other ? h("div", { class: "notice info", text: t("actionsForOther", { c: catLabel(c.modelCategory) }) }) : "",
    ...(S.acts.length ? S.acts.map((a) => actionRow(a, u, true)) : [h("p", { class: "muted", text: t("noActionsChosen") })]),
    actionAdder(finalCat || c.modelCategory));
}

function saveBar(c) {
  if (!editing(c)) return "";
  const comment = h("textarea", { id: "rv-comment", placeholder: t("comment"), rows: 2 });
  comment.value = S.comment ?? c.reviewComment ?? "";
  comment.addEventListener("input", () => { S.comment = comment.value; });
  const err = h("p", { class: "error", role: "alert" });
  const next = h("input", { type: "checkbox", id: "rv-next", checked: store("next") !== "0" });
  const chosen = S.acts.filter((a) => a.on !== false);
  const save = h("button", { class: "primary", type: "button", text: t("save"), onclick: async () => {
    const body = { _etag: c._etag, comment: comment.value, otherCategories: S.pickExtra ? [S.pickExtra] : [],
      finalActions: chosen.map(({ do: d, category, codes, open, closed, to, source }) => ({ do: d, category, codes, open, closed, to, source })) };
    if (S.choice === "none") body.noMatch = true;
    else body.finalCategory = S.choice === "accept" ? c.modelCategory : S.pick;
    if (!body.noMatch && !S.categories.includes(body.finalCategory)) { err.textContent = t("badCat"); return; }
    const restore = busy(save, t("saving"));
    const res = await api(`/api/cases/${encodeURIComponent(c.id)}/review`, { json: body }).catch(() => ({ ok: false, data: {} }));
    restore();
    if (res.status === 409) { S.detail = res.data.case || S.detail; S.choice = null; S.forceEdit = false; renderCase(); notice(t("changed")); return; }
    if (!res.ok) { err.textContent = res.data.error === "category" ? t("badCat") : t("error"); return; }
    store("next", next.checked ? "1" : "0");
    toast(t("saved"));
    await loadCases();
    if (next.checked) {
      const ids = [...document.querySelectorAll("#list .item")].map((b) => b.dataset.id).filter((id) => id !== c.id);
      if (ids.length) return openCase(ids[0]);
    }
    openCase(c.id, true);
  } });
  const summary = `${S.choice === "none" ? t("noneFits") : catLabel(finalCategoryNow(c) || "—")} · ${t("actionsCount", { n: chosen.length })}`;
  return h("section", { class: "savebar" },
    h("div", { class: "savebar-head" }, h("strong", { text: t("stepSave") }), h("span", { class: "muted small", text: summary })),
    comment, err,
    h("div", { class: "row" }, save,
      S.forceEdit ? h("button", { class: "link", type: "button", text: t("cancel"),
        onclick: () => { S.forceEdit = false; S.choice = null; S.comment = undefined; renderCase(); } }) : "",
      h("label", { class: "small muted" }, next, " ", t("next"))));
}

function customerCard(u) {
  const body = [];
  const principal = (u.people || []).find((p) => p.principal);
  if (principal) body.push(h("p", {}, h("span", { class: "muted", text: `${t("aboutPerson")}: ` }), h("strong", { text: principal.name }),
    ` · ${ROLE[lang][principal.role] || principal.role} `, sourceChip({ ...principal.where, snippet: principal.evidence })));
  const customers = u.customers || [];
  if (!customers.length) body.push(h("p", { class: "muted", text: t("noCustomer") }));
  for (const c of customers) {
    const status = h("span", { class: `pill ${c.status === "confirmed" ? "done" : "review"}`, text: t(c.status) });
    const kv = h("dl", { class: "kv" },
      h("dt", { text: t("taxId") }), h("dd", { text: c.taxId }),
      c.customerCodes?.length ? [h("dt", { text: t("custCode") }), h("dd", { text: c.customerCodes.join(", ") })] : null,
      c.portfolios?.length ? [h("dt", { text: t("portfolio") }), h("dd", { text: c.portfolios.join(", ") })] : null,
      c.statuses?.length ? [h("dt", { text: t("status") }), h("dd", { text: c.statuses.join(", ") })] : null,
      c.sources?.length ? [h("dt", { text: t("source") }), h("dd", { text: c.sources.join(", ") })] : null,
      h("dt", { text: t("portal") }), h("dd", { text: c.portal ? t("yes") : t("no") }));
    const matched = h("div", { class: "matched" }, h("span", { class: "muted small", text: `${t("matchedOn")}:` }),
      ...c.matchedOn.map((m) => h("span", { class: "src", title: whereText(m.where) || null,
        text: `${FIELD[lang][m.kind] || (m.kind === "name" ? (lang === "el" ? "Όνομα" : "Name") : m.kind)} ${m.value}` })));
    const accounts = c.accounts?.length ? h("details", { class: "more" }, h("summary", { text: t("accounts", { n: c.accountsTotal }) }),
      h("table", { class: "mini" }, h("tr", {}, ...[t("account"), t("type"), t("settlement"), t("portfolio")].map((x) => h("th", { text: x }))),
        ...c.accounts.map((a) => h("tr", {}, ...[a.account || a.serviceAccount, a.type, a.settlement, a.portfolio].map((x) => h("td", { text: x || "—" })))))) : null;
    const recent = c.recentRequests?.length ? h("details", { class: "more" }, h("summary", { text: t("recent") }),
      h("table", { class: "mini" }, h("tr", {}, ...[t("type"), t("status"), t("created")].map((x) => h("th", { text: x }))),
        ...c.recentRequests.map((r) => h("tr", {}, ...[r.type, r.status, r.created].map((x) => h("td", { text: x || "—" })))))) : null;
    body.push(h("div", { class: "person" },
      h("div", { class: "row" }, h("span", { class: "name", text: c.name || c.taxId }), " ", status),
      c.nameMismatch ? h("div", { class: "caveat", text: t("nameMismatch") }) : null,
      c.sameNameCount > 1 ? h("div", { class: "caveat", text: t("sameName", { n: c.sameNameCount }) }) : null,
      kv, matched, accounts, recent));
  }
  for (const note of u.lookupNotes || []) {
    const [kind, value, n] = note.split(":");
    if (kind === "too_many_name_matches") body.push(h("p", { class: "caveat", text: t("tooMany", { v: value, n }) }));
  }
  if ((u.unmatched || []).length) body.push(h("p", { class: "muted small", text: `${t("unmatched")}: ${u.unmatched.map((x) => `${FIELD[lang][x.kind] || x.kind} ${x.value}`).join(", ")}` }));
  const others = (u.people || []).filter((p) => !p.principal);
  if (others.length) body.push(h("details", { class: "more" }, h("summary", { text: `${t("people")} (${others.length})` }),
    ...others.map((p) => h("div", { class: "small" }, h("strong", { text: p.name }), ` · ${ROLE[lang][p.role] || p.role} `, sourceChip({ ...p.where, snippet: p.evidence })))));
  const file = (u.registrySource || "").split("/").pop();
  return card(t("customer"), file ? t("customerFrom", { f: file }) : null, ...body);
}

function foundCard(u) {
  const rows = (u.extracted || []);
  if (!rows.length) return card(t("found"), null, h("p", { class: "muted", text: t("foundNone") }));
  return card(t("found"), null, h("table", { class: "mini" },
    h("tr", {}, ...[lang === "el" ? "Στοιχείο" : "Item", t("value"), t("belongs"), t("where")].map((x) => h("th", { text: x }))),
    ...rows.map((e) => h("tr", {},
      h("td", { text: FIELD[lang][e.type] || e.type }),
      h("td", {}, h("strong", { text: e.value }), e.checked ? h("div", { class: "ok", text: `✓ ${t("checked")}` }) : null),
      h("td", { text: e.role ? ROLE[lang][e.role] || e.role : "—" }),
      h("td", {}, ...(e.sources || []).map((s) => h("div", {}, sourceChip(s), snippet(s.snippet, e.value))))))));
}

/* One audit entry as a timeline row: when, who, what changed. Used per case and in the activity log. */
const EVENT_LABEL = { registered: "evRegistered", classified: "evClassified", reviewed: "evReviewed", "left mailbox": "evLeft",
  rerouted: "evRerouted", reset: "evReset" };
function eventRow(e, extra) {
  const who = e.byName || (e.by === "classifier" ? t("system") : e.by || "");
  let detail = "";
  if ((e.action === "classified" || e.action === "rerouted") && e.after) {
    const pct = e.after.confidence == null ? "—" : `${Math.round(e.after.confidence * 100)}%`;
    detail = t("evClassifiedAs", { c: catLabel(e.after.category || "—"), p: pct, r: t(`route${e.after.route}`) });
  } else if (e.action === "reset" && e.before) {
    detail = t("evResetDetail", { b: e.before.noMatch ? t("noneFits") : catLabel(e.before.finalCategory || "—") });
  } else if (e.action === "reviewed" && e.after) {
    const b = e.after.finalCategory ? catLabel(e.after.finalCategory) : t("noneFits");
    const a = e.before && e.before.finalCategory ? catLabel(e.before.finalCategory) : "";
    detail = a && a !== b ? t("evChanged", { a, b }) : t("evFirst", { b });
  }
  return h("div", { class: `event ev-${(e.action || "").replace(/\s/g, "-")}` },
    h("div", { class: "ev-head" }, h("strong", { text: t(EVENT_LABEL[e.action] || e.action) }),
      h("span", { class: "muted", text: ` · ${who} · ${when(e.at)}` })),
    extra || "",
    detail ? h("div", { class: "ev-detail", text: detail }) : "",
    e.after && e.after.reviewComment ? h("div", { class: "snippet", text: `“${e.after.reviewComment}”` }) : "");
}
function historyCard(events) {
  return card(t("history"), null, h("div", { class: "timeline" }, ...[...events].reverse().map((e) => eventRow(e))));
}

// ------------------------------------------------------------------ activity log (all emails)
async function openActivity() {
  const panel = $("#activity");
  panel.hidden = false;
  requestAnimationFrame(() => panel.classList.add("open"));
  const body = $("#activity-body");
  body.replaceChildren(spinner(t("loading")));
  const res = await api("/api/activity");
  const onlyReviews = $("#activity-reviews");
  const paint = () => {
    const events = (res.data.events || []).filter((e) => !onlyReviews.checked || e.action === "reviewed");
    body.replaceChildren(...(events.length ? events.map((e) => h("button", { type: "button", class: "activity-row",
      onclick: () => { closeActivity(); openCase(e.caseId); } }, eventRow(e, h("div", { class: "ev-subject", text: e.subject || e.caseId }))))
      : [h("p", { class: "muted", text: t("noEvents") })]));
  };
  onlyReviews.onchange = paint;
  paint();
}
function closeActivity() {
  const panel = $("#activity");
  panel.classList.remove("open");
  setTimeout(() => { panel.hidden = true; }, 220);
}

function notice(text) {
  const n = h("div", { class: "notice warn", role: "alert", text });
  $("#case").prepend(n);
}

function renderCase() {
  const d = S.detail;
  if (!d) return;
  const c = d.case;
  const m = d.message || {};
  const from = m.from?.emailAddress || {};
  const u = c.understanding || {};
  const lockedByOther = d.lock && d.lock.holder !== S.user.id;
  const pane = $("#case");
  pane.removeAttribute("aria-busy");
  pane.dataset.caseId = c.id;
  pane.classList.remove("enter");
  if (S.enter) { void pane.offsetWidth; pane.classList.add("enter"); pane.scrollTop = 0; S.enter = false; }
  pane.replaceChildren(
    h("div", { class: "case-head" },
      h("h2", { text: c.subject || "—" }),
      h("div", { class: "meta" },
        h("span", { text: from.name ? `${from.name} <${from.address}>` : from.address || c.from || "" }),
        h("span", { text: when(c.receivedAt) }), statusPill(c))),
    lockedByOther ? h("div", { class: "notice warn", text: t("lockedBy", { n: d.lock.holderName }) }) : "",
    c.mailboxState === "removed" ? h("div", { class: "notice info", text: t("leftMailbox") }) : "",
    u.error ? h("div", { class: "notice warn", text: t("readError", { e: u.error }) }) : "",
    decisionCard(c),
    actionsCard(u, c),
    ...(c.understanding && !u.error ? [customerCard(u), foundCard(u)] : []),
    u.analysis ? h("p", { class: "muted small", text: `${t("analysis")}: ${u.analysis}` }) : "",
    historyCard(d.events || []),
    saveBar(c));
}

// ------------------------------------------------------------------ viewer
function renderViewer() {
  const pane = $("#viewer");
  const d = S.detail;
  $(".layout").classList.toggle("no-viewer", !d);
  if (!d) { pane.hidden = true; return; }
  pane.hidden = false;
  const id = encodeURIComponent(d.case.id);
  const tabs = [{ key: "email", label: t("email") }, ...d.attachments.map((a) => ({ key: `a${a.n}`, label: a.name, a }))];
  $("#viewer-tabs").replaceChildren(...tabs.map((tab) => h("button", { role: "tab", type: "button", title: tab.label,
    "aria-selected": String(S.viewer.tab === tab.key), text: tab.label,
    onclick: () => { S.viewer = { tab: tab.key, page: null, images: S.viewer.images }; renderViewer(); } })));
  const body = $("#viewer-body");
  const tools = $("#viewer-tools");
  if (S.viewer.hl === undefined) S.viewer.hl = true;
  const hlToggle = h("label", { class: "hl-toggle" }, h("input", { type: "checkbox", checked: S.viewer.hl,
    onchange: (e) => { S.viewer.hl = e.target.checked; renderViewer(); } }), " ", t("highlights"));
  const legend = h("span", { class: "legend" }, ...[["class", "lgClass"], ["action", "lgAction"], ["id", "lgId"]].map(
    ([k, label]) => h("span", { class: `lg lg-${k}`, text: t(label) })));
  if (S.viewer.tab === "email") {
    const original = d.message.original;
    const query = [S.viewer.images ? "images=1" : "", S.viewer.hl ? "hl=1" : ""].filter(Boolean).join("&");
    tools.replaceChildren(hlToggle, S.viewer.hl ? legend : "",
      h("button", { class: "link", type: "button", text: S.viewer.images ? t("hideImages") : t("showImages"),
        onclick: () => { S.viewer.images = !S.viewer.images; renderViewer(); } }),
      h("span", { class: "spacer" }),
      original ? h("a", { href: `/api/cases/${id}/export/original`, text: t("downloadEmail", { x: "." + original }) }) : null,
      h("a", { href: `/api/cases/${id}/export/zip`, text: t("downloadAll") }));
    body.replaceChildren(whenLoaded(h("iframe", { title: t("email"), sandbox: "allow-popups allow-popups-to-escape-sandbox",
      src: `/api/cases/${id}/message${query ? "?" + query : ""}` }), t("loadingEmail")));
    return;
  }
  const att = d.attachments.find((a) => `a${a.n}` === S.viewer.tab);
  if (!att) { S.viewer.tab = "email"; return renderViewer(); }
  const url = `/api/cases/${id}/files/${att.n}`;
  const mode = att.hasText && S.viewer.mode === "text" ? "text" : "original";
  const modes = att.hasText ? h("div", { class: "seg", role: "group" }, ...[["original", "viewOriginal"], ["text", "viewText"]].map(
    ([m, label]) => h("button", { type: "button", "aria-pressed": String(mode === m), text: t(label),
      onclick: () => { S.viewer.mode = m; renderViewer(); } }))) : "";
  tools.replaceChildren(modes, mode === "text" ? hlToggle : "", mode === "text" && S.viewer.hl ? legend : "",
    h("span", { class: "spacer" }),
    att.viewable ? h("a", { href: url, target: "_blank", rel: "noopener", text: t("openTab") }) : null,
    h("a", { href: `${url}?download=1`, text: t("download") }));
  const kind = (att.contentType || "").toLowerCase();
  if (mode === "text") {
    const src = `${url}/text${S.viewer.hl ? "?hl=1" : ""}${S.viewer.page ? `#p${S.viewer.page}` : ""}`;
    body.replaceChildren(whenLoaded(h("iframe", { title: att.name, sandbox: "", src }), t("loading")));
  } else if (!att.viewable) body.replaceChildren(h("div", { class: "nopreview" }, h("p", { text: t("noPreview") }), h("a", { class: "secondary", href: `${url}?download=1`, text: t("download") })));
  else if (kind.startsWith("image/")) {
    const img = h("img", { src: url, alt: att.name });
    body.replaceChildren(whenLoaded(h("div", { class: "img" }, img), t("loading"), img));
  }
  else body.replaceChildren(whenLoaded(h("iframe", { title: att.name, src: S.viewer.page ? `${url}#page=${S.viewer.page}` : url }), t("loading")));
}

// ------------------------------------------------------------------ chrome
function toast(text) {
  const el = h("div", { class: "toast", role: "status", text });
  document.body.append(el);
  setTimeout(() => { el.classList.add("leaving"); setTimeout(() => el.remove(), 250); }, 2000);
}

function applyWords() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
  $("#search").placeholder = t("search");
  $("#lang").textContent = lang === "el" ? "English" : "Ελληνικά";
  const opts = (sel, pairs, value) => { $(sel).replaceChildren(...pairs.map(([v, k]) => h("option", { value: v, text: t(k) }))); $(sel).value = value; };
  opts("#basis", [["received", "byArrival"], ["reviewed", "byReview"]], S.basis);
  opts("#sort", [["newest", "newest"], ["oldest", "oldest"]], S.sort);
}

// ------------------------------------------------------------------ email intake (clock in the top bar)
async function loadIngest() {
  const res = await api("/api/ingest").catch(() => null);
  if (!res || !res.ok) return;
  const info = res.data;
  const last = info.lastRun;
  $("#clock-pop").replaceChildren(
    h("strong", { text: t("ingestTitle") }),
    h("p", { text: info.mode === "schedule" ? t("ingestSchedule") : t("ingestManual") }),
    h("dl", { class: "kv" },
      h("dt", { text: t("ingestLast") }),
      h("dd", { text: last ? `${when(last.at)} · ${t("ingestCount", { n: last.emails ?? "—" })}${last.imported ? ` (${t("ingestImported")})` : ""}` : t("ingestNone") }),
      info.mode === "schedule" ? [h("dt", { text: t("ingestNext") }), h("dd", { text: info.nextRun ? when(info.nextRun) : "—" })] : ""),
    h("p", { class: "muted small", text: t("ingestDelay") }));
}

function showSignin() {
  $("#splash").hidden = true;
  $("#app").hidden = true;
  $("#signin").hidden = false;
  $("#si-code-row").hidden = S.mode !== "demo";
  $("#si-name").value = store("name") || "";
  $("#si-email").value = store("email") || "";
  applyWords();
}

async function start() {
  $("#splash").hidden = true;
  $("#signin").hidden = true;
  $("#app").hidden = false;
  $("#list").replaceChildren(...Array.from({ length: 6 }, () => h("div", { class: "item sk-item" }, ...skeletonLines(3))));
  const meta = await api("/api/meta");
  S.categories = meta.data.categories || [];
  S.catalog = meta.data.actions || { byCategory: {}, general: [] };
  $("#me").textContent = S.user.name;
  applyWords();
  loadIngest();
  setInterval(loadIngest, 60000);
  await loadCases();
  const fromHash = decodeURIComponent(location.hash.slice(1));
  if (fromHash) openCase(fromHash);
  setTimeout(pollCases, S.classifier && S.classifier.running ? 4000 : 20000);
  setInterval(sync, 15000);
  sync();
}

async function sync() {
  const res = await api("/api/sync", { json: { open: S.openId } }).catch(() => null);
  if (!res || !res.ok) return;
  S.presence = Object.fromEntries((res.data.presence || []).map((p) => [p.userId, p]));
  renderList();
}

function wire() {
  $("#signin-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    $("#si-error").textContent = "";
    const restore = busy($("#signin-form button[type=submit]"), t("signingIn"));
    const body = { name: $("#si-name").value, email: $("#si-email").value, code: $("#si-code").value };
    const res = await fetch("/api/login", { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).catch(() => null);
    const data = res ? await res.json().catch(() => ({})) : { error: "network" };
    restore();
    if (!res || !res.ok) {
      $("#si-error").textContent = t({ code: "errCode", too_many: "errMany", network: "error" }[data.error] || "errName");
      return;
    }
    store("name", body.name); store("email", body.email);
    S.user = data.user;
    start();
  });
  $("#signout").addEventListener("click", async () => { await api("/api/logout", { json: {} }); location.hash = ""; location.reload(); });
  $("#lang").addEventListener("click", () => { lang = lang === "el" ? "en" : "el"; store("lang", lang); applyWords(); renderDays(); renderList(); renderCase(); renderViewer(); });
  $("#search").addEventListener("input", (e) => { S.q = e.target.value; renderList(); });
  $("#day").addEventListener("change", (e) => { S.day = e.target.value; S.win = "all"; renderList(); });
  $("#basis").addEventListener("change", (e) => { S.basis = e.target.value; S.day = "all"; S.win = "all"; renderDays(); renderList(); });
  $("#sort").addEventListener("change", (e) => { S.sort = e.target.value; renderList(); });
  $("#activity-open").addEventListener("click", openActivity);
  $("#activity-close").addEventListener("click", closeActivity);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#activity").hidden) closeActivity(); });
  window.addEventListener("pagehide", () => { if (S.openId) navigator.sendBeacon(`/api/cases/${encodeURIComponent(S.openId)}/release`); });
}

(async function boot() {
  wire();
  const res = await fetch("/api/session", { credentials: "same-origin" }).then((r) => r.json()).catch(() => ({}));
  S.mode = res.mode || "dev";
  if (!res.user) return showSignin();
  S.user = res.user;
  start();
})();
