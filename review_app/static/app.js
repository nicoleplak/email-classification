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
    accept: "Η πρόταση είναι σωστή", other: "Άλλη κατηγορία", noneFits: "No Match Found · χειρισμός από το προσωπικό",
    chooseCat: "Γράψτε ή επιλέξτε κατηγορία", extra: "Επιπλέον αιτήματα στο ίδιο email (προαιρετικό)",
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
    found: "Στοιχεία που βρέθηκαν", foundCount: "{n} στοιχεία", foundNone: "Δεν βρέθηκαν αναγνωριστικά.", value: "Τιμή", belongs: "Ανήκει σε",
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
    stepCategory: "1 · Κατηγορία", stepActions: "2 · Ενέργειες", stepSave: "3 · Σχόλια", changeTo: "Αντικατάσταση με:",
    tickActions: "Τσεκάρετε όσες θα γίνουν", chosenActions: "Επιλέχθηκαν στον έλεγχο",
    proposedOnly: "Προτάσεις συστήματος — δεν έχουν επιλεγεί ακόμη",
    actionsForOther: "Οι προτεινόμενες ενέργειες αφορούν την αρχική κατηγορία «{c}». Ελέγξτε αν ισχύουν ή προσθέστε άλλες.",
    noActionsChosen: "Δεν έχει επιλεγεί καμία ενέργεια.", addAction: "Προσθήκη ενέργειας", findAction: "Αναζήτηση ενέργειας ή κωδικού…",
    generalActions: "Γενικές ενέργειες", addedByYou: "προστέθηκε", remove: "Αφαίρεση", actionsCount: "{n} ενέργειες",
    accountLabel: "Λογαριασμός", pickAccount: "Επιλέξτε λογαριασμό…", stOpen: "ανοιχτή υπόθεση", stClosed: "κλειστή υπόθεση (_Cust)",
    stUnknown: "ανοιχτή/κλειστή: δεν είναι γνωστό", folderLabel: "Φάκελος", templateLabel: "Πρότυπο απάντησης",
    cv_not_identified: "Ο πελάτης δεν ταυτοποιήθηκε με ΑΦΜ ή λογαριασμό· πριν την καταχώρηση χρειάζονται στοιχεία.",
    cv_not_in_registry: "Ο ΑΦΜ ή ο λογαριασμός δεν βρέθηκε στο μητρώο.",
    cv_account_not_identified: "Ο λογαριασμός δεν ταυτοποιήθηκε από το email· επιλέξτε λογαριασμό ή στείλτε «Χρειάζονται στοιχεία».",
    autoExtras: "Οι κατηγορίες με βεβαιότητα 80% ή περισσότερο προστέθηκαν αυτόματα, μαζί με τις ενέργειές τους.",
    autoExtraTip: "Προστέθηκε αυτόματα (βεβαιότητα 80%+)",
    forRequest: "Δραστηριότητα του αιτήματος {c}", bySenderRule: "Εσωτερικός αποστολέας (@dovaluegreece.gr): η κατηγορία ορίστηκε από τη διεύθυνση, χωρίς κλήση στο μοντέλο.",
    senderLabel: "Αποστολέας", senderAll: "Όλοι", senderExternal: "Εξωτερικοί", senderInternal: "Εσωτερικό",
    senderRetail: "Προώθηση Retail Support", senderInternalTip: "Αποστολέας από τη doValue (@dovaluegreece.gr)",
    senderRetailTip: "Προώθηση από το Retail Support (λίστα στο inputs/sender_flags.json)",
    extraCount: "{n} επιλεγμένα", extraNone: "κανένα", addCategory: "Προσθήκη κατηγορίας…",
    toLabel: "Προς", ccLabel: "Κοιν.", evCategory: "Κατηγορία", evActions: "Ενέργειες", evOthers: "Επιπλέον κατηγορίες",
    evComment: "Σχόλιο", evUnchanged: "χωρίς αλλαγή", evSystem: "πρόταση συστήματος", evAdded: "προστέθηκε", evRemoved: "αφαιρέθηκε",
    showEmails: "Εμφάνιση αυτών των email", clickHint: "Πατήστε έναν αριθμό για να δείτε τα email του",
    mQuality: "Ποιότητα και ελεγκτές", mCombined: "Κατηγορία και ενέργειες", mCombinedSub: "Ελεγμένα email: τι κράτησε ο ελεγκτής",
    mCatRight: "Σωστή κατηγορία", mCatWrong: "Άλλαξε η κατηγορία", mActSame: "Ενέργειες χωρίς αλλαγή", mActChanged: "Άλλαξαν οι ενέργειες",
    mReviewers: "Ελεγκτές", mReviewersSub: "Email που έλεγξε ο καθένας στην περίοδο", mReviewer: "Ελεγκτής",
    mCatChanged: "Άλλαξε κατηγορία", mMedian: "Διάμεσος χρόνος", mLast: "Τελευταίος έλεγχος",
    catFilter: "Κατηγορία", allCats: "Όλες οι κατηγορίες", exportExcel: "Excel", exportExcelTip: "Εξαγωγή των email της λίστας σε Excel", exporting: "Εξαγωγή…",
    exported: "Εξήχθησαν {n} email", fromStats: "Από τα στατιστικά", clearFilter: "Κατάργηση φίλτρου",
    viewEmails: "Email", viewMetrics: "Στατιστικά", range7: "7 ημέρες", range30: "30 ημέρες", range90: "90 ημέρες",
    rangeAll: "Όλα", rangeLabel: "Περίοδος", mPeriod: "{a} – {b} · ώρα Ελλάδας", mReceived: "Παραλήφθηκαν",
    mAuto: "Αυτόματα", mReview: "Χρειάστηκαν έλεγχο", mException: "Σφάλμα", mWaiting: "Χωρίς ταξινόμηση ακόμη",
    mOpen: "Εκκρεμούν για έλεγχο", mReviewed: "Ελέγχθηκαν", mTurnaround: "Διάμεσος χρόνος έως τον έλεγχο",
    mOfClassified: "{p} των ταξινομημένων", mHours: "{n} ώρες", mNoData: "Δεν υπάρχουν email σε αυτή την περίοδο.",
    mDaily: "Email ανά ημέρα", mDailySub: "Πώς δρομολογήθηκε κάθε email που παραλήφθηκε", mDay: "Ημέρα",
    mTotal: "Σύνολο", mAsTable: "Προβολή ως πίνακας", mRouting: "Δρομολόγηση", mActionsTitle: "Ενέργειες",
    mReasons: "Γιατί χρειάστηκαν έλεγχο", mReasonsSub: "Email ανά λόγο· ένα email μπορεί να έχει πολλούς λόγους",
    mOutcome: "Αποτέλεσμα ελέγχου ανά δρομολόγηση", mOutcomeSub: "Πόσο συχνά ο ελεγκτής κράτησε την κατηγορία του συστήματος",
    mRoute: "Δρομολόγηση", mEmails: "Email", mAccepted: "Σωστή κατηγορία", mChanged: "Άλλαξε", mNoneFits: "No Match Found",
    mAcceptRate: "Ποσοστό σωστών", mBands: "Βεβαιότητα και ακρίβεια", mBandsSub: "Βοηθά να οριστεί το όριο αυτόματης ταξινόμησης (σήμερα 90%)",
    mBand: "Βεβαιότητα", mCategories: "Κατηγορίες", mCategoriesSub: "Κατηγορία συστήματος· αυτόματα και προς έλεγχο",
    mCategory: "Κατηγορία", mAutoShare: "Αυτόματα %", mProposed: "Προτάθηκαν", mKept: "Κρατήθηκαν", mRemoved: "Αφαιρέθηκαν",
    mAdded: "Προστέθηκαν από ελεγκτές", mKeptRate: "Ποσοστό που κρατήθηκε", mUnchanged: "Έλεγχοι χωρίς αλλαγή ενεργειών",
    mActionsSub: "Προτάσεις των κανόνων και τι έκαναν οι ελεγκτές", mKind: "Ενέργεια", mFinal: "Τελικές",
    mProposedAll: "Προτάθηκαν (όλα τα email)", mProposedReviewed: "Προτάθηκαν (ελεγμένα)",
    mCodes: "Συχνότεροι κωδικοί αιτημάτων Qualco", mCodesSub: "Στις τελικές ενέργειες των ελεγμένων email", mCode: "Κωδικός",
    mCount: "Φορές", mNoReviews: "Δεν υπάρχουν ακόμη ελεγμένα email σε αυτή την περίοδο.", mNone: "—",
    mOfReviewed: "των ελεγμένων με προτάσεις", mAllCats: "Όλες οι κατηγορίες ({n})", mFewerCats: "Μόνο οι 10 συχνότερες",
    rs_low_confidence: "Χαμηλή βεβαιότητα", rs_no_tax_id: "Δεν βρέθηκε ΑΦΜ", rs_tax_id_unknown: "Ο ΑΦΜ δεν είναι στο μητρώο",
    rs_split_categories: "ΑΦΜ με διαφορετικές κατηγορίες", rs_no_category: "Καμία κατηγορία δεν ταιριάζει",
    rs_attachment_unread: "Συνημμένο δεν διαβάστηκε", rs_failed: "Η ταξινόμηση απέτυχε", rs_no_result: "Χωρίς αποτέλεσμα",
    rs_name_mismatch: "Το όνομα διαφέρει από το μητρώο", rs_possible_customer: "Μόνο πιθανός πελάτης",
    rs_no_customer: "Δεν βρέθηκε πελάτης", rs_details_unread: "Στοιχεία πελάτη δεν διαβάστηκαν",
    rs_email_missing: "Λείπει το email", rs_reset: "Επαναφορά ελέγχου", rs_other: "Άλλο",
    rs_account_unknown: "Δεν ταυτοποιήθηκε λογαριασμός/SPV", rs_complaint_secondary: "Παράπονο μαζί με άλλο αίτημα",
    rs_distress: "Αυτοτραυματισμός ή απειλή νομικών μέτρων",
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
    accept: "The suggestion is right", other: "Another category", noneFits: "No Match Found · handled by staff",
    chooseCat: "Type or pick a category", extra: "Further requests in the same email (optional)",
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
    found: "Details found", foundCount: "{n} items", foundNone: "No identifiers found.", value: "Value", belongs: "Belongs to",
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
    stepCategory: "1 · Category", stepActions: "2 · Actions", stepSave: "3 · Comments", changeTo: "Replace with:",
    tickActions: "Tick the ones to carry out", chosenActions: "Chosen in the review",
    proposedOnly: "System proposals — none chosen yet",
    actionsForOther: "The proposed actions were made for the original category “{c}”. Check they still apply or add others.",
    noActionsChosen: "No action chosen.", addAction: "Add an action", findAction: "Search actions or codes…",
    generalActions: "General actions", addedByYou: "added", remove: "Remove", actionsCount: "{n} actions",
    accountLabel: "Account", pickAccount: "Pick an account…", stOpen: "open case", stClosed: "closed case (_Cust)",
    stUnknown: "open/closed: not known", folderLabel: "Folder", templateLabel: "Reply template",
    cv_not_identified: "The customer is not identified by tax ID or account; details are needed before filing.",
    cv_not_in_registry: "The tax ID or account is not in the registry.",
    cv_account_not_identified: "The email does not identify the account; pick one or send “Need more Info”.",
    autoExtras: "Categories with 80% certainty or more were added automatically, with their actions.",
    autoExtraTip: "Added automatically (80%+ certainty)",
    forRequest: "Activity of request {c}", bySenderRule: "Internal sender (@dovaluegreece.gr): category set by the address, without calling the model.",
    senderLabel: "Sender", senderAll: "All", senderExternal: "External", senderInternal: "Internal",
    senderRetail: "Forwarded by Retail Support", senderInternalTip: "Sent from doValue (@dovaluegreece.gr)",
    senderRetailTip: "Forwarded by Retail Support (list in inputs/sender_flags.json)",
    extraCount: "{n} chosen", extraNone: "none", addCategory: "Add a category…",
    toLabel: "To", ccLabel: "Cc", evCategory: "Category", evActions: "Actions", evOthers: "Further categories",
    evComment: "Comment", evUnchanged: "unchanged", evSystem: "system suggestion", evAdded: "added", evRemoved: "removed",
    showEmails: "Show these emails", clickHint: "Click a number to see its emails",
    mQuality: "Quality and reviewers", mCombined: "Category and actions", mCombinedSub: "Reviewed emails: what the reviewer kept",
    mCatRight: "Right category", mCatWrong: "Category changed", mActSame: "Actions unchanged", mActChanged: "Actions changed",
    mReviewers: "Reviewers", mReviewersSub: "Emails each person reviewed in the period", mReviewer: "Reviewer",
    mCatChanged: "Category changed", mMedian: "Median time", mLast: "Last review",
    catFilter: "Category", allCats: "All categories", exportExcel: "Excel", exportExcelTip: "Export the listed emails to Excel", exporting: "Exporting…",
    exported: "{n} emails exported", fromStats: "From metrics", clearFilter: "Remove filter",
    viewEmails: "Emails", viewMetrics: "Metrics", range7: "7 days", range30: "30 days", range90: "90 days",
    rangeAll: "All", rangeLabel: "Period", mPeriod: "{a} – {b} · Greek time", mReceived: "Received",
    mAuto: "Automatic", mReview: "Needed review", mException: "Error", mWaiting: "Not classified yet",
    mOpen: "Still to review", mReviewed: "Reviewed", mTurnaround: "Median time to review",
    mOfClassified: "{p} of classified", mHours: "{n} hours", mNoData: "No emails in this period.",
    mDaily: "Emails per day", mDailySub: "How each received email was routed", mDay: "Day",
    mTotal: "Total", mAsTable: "Show as table", mRouting: "Routing", mActionsTitle: "Actions",
    mReasons: "Why emails needed review", mReasonsSub: "Emails per reason; one email can have several",
    mOutcome: "Review outcome by route", mOutcomeSub: "How often the reviewer kept the system's category",
    mRoute: "Route", mEmails: "Emails", mAccepted: "Right category", mChanged: "Changed", mNoneFits: "No Match Found",
    mAcceptRate: "Right %", mBands: "Certainty and accuracy", mBandsSub: "Helps set the automatic threshold (now 90%)",
    mBand: "Certainty", mCategories: "Categories", mCategoriesSub: "System category; automatic and to review",
    mCategory: "Category", mAutoShare: "Automatic %", mProposed: "Proposed", mKept: "Kept", mRemoved: "Removed",
    mAdded: "Added by reviewers", mKeptRate: "Kept rate", mUnchanged: "Reviews with actions unchanged",
    mActionsSub: "What the rules proposed and what reviewers did", mKind: "Action", mFinal: "Final",
    mProposedAll: "Proposed (all emails)", mProposedReviewed: "Proposed (reviewed)",
    mCodes: "Most used Qualco request codes", mCodesSub: "In the final actions of reviewed emails", mCode: "Code",
    mCount: "Times", mNoReviews: "No reviewed emails in this period yet.", mNone: "—",
    mOfReviewed: "of reviewed emails with proposals", mAllCats: "All categories ({n})", mFewerCats: "Only the 10 most frequent",
    rs_low_confidence: "Low certainty", rs_no_tax_id: "No tax ID found", rs_tax_id_unknown: "Tax ID not in registry",
    rs_split_categories: "Tax IDs in different categories", rs_no_category: "No category fits",
    rs_attachment_unread: "Attachment not read", rs_failed: "Classification failed", rs_no_result: "No result",
    rs_name_mismatch: "Name differs from registry", rs_possible_customer: "Only a possible customer",
    rs_no_customer: "No customer found", rs_details_unread: "Customer details not read",
    rs_email_missing: "Email missing", rs_reset: "Review reset", rs_other: "Other",
    rs_account_unknown: "Account/SPV not identified", rs_complaint_secondary: "Complaint with another request",
    rs_distress: "Self-harm or legal threat",
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
        activity: "Δραστηριότητα Qualco (activity)", no_action: "Καμία ενέργεια", outlook_folder: "Μεταφορά σε φάκελο Outlook" },
  en: { request: "File a Qualco request", portal_referral: "Refer to the Portal", ask_identification: "Ask for identification",
        manual: "Handled by staff", forward: "Forward", reply: "Reply with template", bank_referral: "Refer to the bank",
        activity: "Log a Qualco activity", no_action: "No action", outlook_folder: "Move to an Outlook folder" },
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
  [/^no customer found in the registry by tax ID or account/, "Δεν βρέθηκε πελάτης στο μητρώο με ΑΦΜ ή λογαριασμό"],
  [/^the account or portfolio \(SPV\) the request concerns is not identified/, "Δεν ταυτοποιήθηκε ο λογαριασμός ή το χαρτοφυλάκιο (SPV) του αιτήματος"],
  [/^the complaint is not the main request: the email also asks for (.*)/, "Το παράπονο δεν είναι το κύριο αίτημα· το email ζητά επίσης: $1"],
  [/^the email mentions self-harm or threatens legal action/, "Το email αναφέρει αυτοτραυματισμό ή απειλεί με νομικά μέτρα"],
  [/^the customer is only a possible match/, "Ο πελάτης είναι μόνο πιθανή αντιστοίχιση (από όνομα ή email)"],
  [/^the customer details could not be read/, "Δεν διαβάστηκαν τα στοιχεία πελάτη"],
  [/^email not found in/, "Το email δεν βρέθηκε στα αρχεία παραλαβής"],
];

// ------------------------------------------------------------------ state
let lang = store("lang") || "el";
const S = { user: null, mode: "dev", categories: [], items: [], queue: store("queue") || "review", day: "all",
            win: "all", basis: "received", sort: "newest", q: "", openId: null, detail: null, presence: {},
            viewer: { tab: "email", page: null, images: false }, choice: null,
            view: store("view") === "metrics" ? "metrics" : "emails", range: store("range") || "30", metrics: null,
            cat: "all", sender: "all", f: null };

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

// Internal sender or a forward by retail support: shown next to the status, wherever the email is listed.
function senderPill(type) {
  if (type === "internal") return h("span", { class: "pill sender internal", title: t("senderInternalTip"), text: t("senderInternal") });
  if (type === "retail_support") return h("span", { class: "pill sender retail", title: t("senderRetailTip"), text: t("senderRetail") });
  return "";
}

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

const NO_MATCH = "No Match Found";
// The email's category now: the reviewer's when reviewed, otherwise the system's.
const currentCat = (it) => it.status === "REVIEWED" ? (it.noMatch ? NO_MATCH : it.finalCategory) : it.modelCategory;

// A filter set from the Statistics tab: every key present must hold.
function matchesF(it, f) {
  const day = (ath(it.receivedAt) || {}).day;
  if (f.since && (!day || day < f.since)) return false;
  if (f.until && (!day || day > f.until)) return false;
  if (f.route && !f.route.includes(it.route)) return false;
  if (f.outcome && !f.outcome.includes(it.outcome)) return false;
  if (f.actions && it.actionsOutcome !== f.actions) return false;
  if (f.reviewer && ((it.reviewedBy || {}).id || (it.reviewedBy || {}).name) !== f.reviewer) return false;
  if (f.reason && !(it.reasonKeys || []).includes(f.reason)) return false;
  if (f.band && (it.confidence == null || Math.round(it.confidence * 100) < f.band[0] || Math.round(it.confidence * 100) >= f.band[1])) return false;
  if (f.modelCat && it.modelCategory !== f.modelCat) return false;
  if (f.waiting && !["RECEIVED", "CLASSIFYING"].includes(it.status)) return false;
  if (f.open && (it.status === "REVIEWED" || !["REVIEW", "EXCEPTION"].includes(it.route))) return false;
  if (f.reviewed && it.status !== "REVIEWED") return false;
  return true;
}

function filtered() {
  const q = norm(S.q.trim());
  return S.items.filter((it) => {
    if (q && !norm([it.subject, it.from, it.finalCategory, it.modelCategory, it.id].join(" ")).includes(q)) return false;
    if (S.cat !== "all" && currentCat(it) !== S.cat) return false;
    if (S.sender !== "all" && (it.senderType || "external") !== S.sender) return false;
    if (S.f && !matchesF(it, S.f)) return false;
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

function renderCats() {
  const counts = new Map();
  S.items.forEach((it) => { const c = currentCat(it); if (c) counts.set(c, (counts.get(c) || 0) + 1); });
  if (S.cat !== "all" && !counts.has(S.cat)) counts.set(S.cat, 0);
  const names = [...counts.keys()].sort((a, b) => catLabel(a).localeCompare(catLabel(b), "el", { sensitivity: "base" }));
  const sel = $("#cat");
  sel.replaceChildren(h("option", { value: "all", text: t("allCats") }),
    ...names.map((c) => h("option", { value: c, text: `${catLabel(c)} (${counts.get(c)})` })));
  sel.value = S.cat;
}

function renderSenders() {
  const counts = { all: S.items.length, external: 0, internal: 0, retail_support: 0 };
  S.items.forEach((it) => { counts[it.senderType || "external"]++; });
  const sel = $("#sender");
  sel.replaceChildren(...[["all", "senderAll"], ["external", "senderExternal"], ["internal", "senderInternal"],
    ["retail_support", "senderRetail"]].map(([v, k]) => h("option", { value: v, text: `${t(k)} (${counts[v]})` })));
  sel.value = S.sender;
}

function renderChips() {
  const box = $("#fchips");
  box.hidden = !S.f;
  if (!S.f) return box.replaceChildren();
  const period = S.f.since ? ` · ${dayLabel(S.f.since)} – ${dayLabel(S.f.until || S.f.since)}` : "";
  box.replaceChildren(h("span", { class: "fchip" }, h("span", { text: `${t("fromStats")}: ${S.f.label}${period}` }),
    h("button", { type: "button", class: "chip-x", "aria-label": t("clearFilter"), text: "×",
      onclick: () => { S.f = null; renderList(); } })));
}

// Statistics → Emails: show every email the clicked number counts, whatever queue it is in.
function applyFilter(f, label) {
  const m = S.metrics || {};
  S.f = { since: m.from, until: m.to, ...f, label };
  S.queue = "all"; store("queue", "all");
  S.day = "all"; S.win = "all"; S.cat = "all"; S.sender = "all"; S.q = ""; $("#search").value = "";
  setView("emails");
  renderDays();
  renderList();
}

async function exportExcel(button) {
  const ids = [...document.querySelectorAll("#list .item")].map((b) => b.dataset.id);
  if (!ids.length) return toast(t("noItems"));
  const restore = busy(button, t("exporting"));
  try {
    const res = await fetch("/api/export", { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) });
    if (!res.ok) throw new Error(String(res.status));
    const name = (/filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "") || [])[1] || "emails.xlsx";
    const url = URL.createObjectURL(await res.blob());
    const a = h("a", { href: url, download: name });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    toast(t("exported", { n: ids.length }));
  } catch (e) {
    toast(t("error"));
  } finally {
    restore();
  }
}

function renderList() {
  renderCats();
  renderSenders();
  renderChips();
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
    h("div", { class: "tags" }, statusPill(it), senderPill(it.senderType),
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
  S.extraOpen = false;
  S.changing = null;
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
  // The whole English sentence is replaced, not just the part the pattern names.
  for (const [re, out] of REASONS_EL) if (re.test(r)) return r.replace(new RegExp(`${re.source}[\\s\\S]*`), out);
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
  if (c.classifiedBy === "sender_rule") parts.push(h("div", { class: "notice info", text: t("bySenderRule") }));
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
const finalCategoryNow = (c) => S.choice === "accept" ? c.modelCategory : S.choice === "other" ? S.pick : NO_MATCH;
const actionText = (a) => `${ACTION[lang][a.do] || a.do}${[].concat(a.to || []).length ? " → " + [].concat(a.to).join(", ") : ""}`;
const codesOf = (a) => [a.open, a.closed, ...(a.codes || [])].filter(Boolean).filter((x, i, arr) => arr.indexOf(x) === i);
const asChoice = (a, source) => ({ ...a, to: a.to ? [].concat(a.to) : [], codes: a.codes || [], source, on: true });

function reviewForm(c) {
  if (S.choice === null) {
    const reviewed = c.status === "REVIEWED";
    S.choice = reviewed ? (c.noMatch ? "none" : c.finalCategory === c.modelCategory ? "accept" : "other")
      : c.modelCategory && c.route !== "EXCEPTION" ? "accept" : "other";
    S.pick = reviewed ? c.finalCategory || "" : "";
    // Not reviewed yet: start from the categories added automatically (certainty 80%+).
    S.pickExtras = (c.otherCategories || []).length || reviewed ? [...(c.otherCategories || [])]
      : (c.autoCategories || []).map((a) => a.category);
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
  const extra = extraCategories(c, u, suggested);
  return h("div", { class: "choice" },
    c.modelCategory ? opt("accept", `${t("accept")}: ${catLabel(c.modelCategory)}`) : "",
    opt("other", t("other"), S.choice === "other" ? h("div", { class: "reveal" }, cat) : ""),
    c.modelCategory === NO_MATCH ? "" : opt("none", t("noneFits")),
    extra);
}

/* Further requests in the same email: chosen ones as chips, the system's suggestions one click away, search for the rest. */
function extraCategories(c, u, suggested) {
  const main = finalCategoryNow(c);
  const chosen = (S.pickExtras || []).filter((x) => x !== main);
  const add = (x) => { if (!chosen.includes(x) && chosen.length < 5) S.pickExtras = [...chosen, x]; S.extraOpen = true; renderCase(); };
  const certainty = { ...(((c.payload || {}).records || [])[0] || {}).model_other_categories };
  (c.autoCategories || []).forEach((a) => { certainty[a.category] = a.confidence; });
  const pct = (x) => certainty[x] != null ? ` · ${Math.round(certainty[x] * 100)}%` : "";
  const auto = new Set((c.autoCategories || []).map((a) => a.category));
  const ideas = [...new Set([...Object.keys(certainty), ...suggested])]
    .filter((x) => x && x !== main && x !== NO_MATCH && !chosen.includes(x) && S.categories.includes(x));
  return h("section", { class: "extras" },
    h("div", { class: "extras-head" }, h("span", { text: t("extra") }),
      h("span", { class: "muted small", text: chosen.length ? t("extraCount", { n: chosen.length }) : t("extraNone") })),
    auto.size ? h("div", { class: "muted small", text: t("autoExtras") }) : "",
    chosen.length ? h("div", { class: "chips" }, ...chosen.map((x) => h("span", { class: auto.has(x) ? "chip auto-chip" : "chip",
      title: auto.has(x) ? t("autoExtraTip") : null }, `${catLabel(x)}${pct(x)}`,
      h("button", { type: "button", class: "chip-x", "aria-label": `${t("remove")}: ${catLabel(x)}`, text: "×",
        onclick: () => { S.pickExtras = chosen.filter((y) => y !== x); renderCase(); } })))) : "",
    ideas.length ? h("div", { class: "chips ideas" }, h("span", { class: "muted small", text: `${t("suggestedCats")}:` }),
      ...ideas.map((x) => h("button", { type: "button", class: "chip add", onclick: () => add(x) }, `+ ${catLabel(x)}${pct(x)}`))) : "",
    chosen.length < 5 ? h("details", { class: "more extra", open: S.extraOpen ? true : null, ontoggle: (e) => { S.extraOpen = e.target.open; } },
      h("summary", { text: t("addCategory") }),
      categoryPicker({ id: "rv-extra", value: "", suggested: ideas, onPick: (x) => { if (x) add(x); } })) : "");
}

// A request's Qualco activities travel with it: added, replaced or moved to another account together.
const activitiesOf = (req) => S.acts.filter((x) => x.do === "activity" && x.forRequest === req.code && (x.account || null) === (req.account || null));
function activityChoices(req, codes) {
  return (codes || []).map((code) => asChoice({ do: "activity", code, codes: [code], forRequest: req.code, category: req.category,
    account: req.account, spv: req.spv, accountState: req.accountState }, "added"));
}

// Where a request goes: the account (pickable while reviewing), its portfolio (SPV) and open/closed state.
function accountLine(a, u, editable) {
  if (a.do === "activity" && a.account) {
    return h("div", { class: "account-line small" }, h("span", { class: "muted", text: `${t("accountLabel")}: ` }),
      `${a.account}${a.spv ? " · " + a.spv : ""}`);
  }
  if (a.do !== "request") return "";
  const accounts = (u.customerFacts || {}).accounts || [];
  const state = (x) => t({ open: "stOpen", closed: "stClosed" }[x] || "stUnknown");
  const label = (x) => `${x.account} · ${x.spv} · ${state(x.state)}`;
  if (editable && accounts.length) {
    const pick = h("select", { class: "account-pick", "aria-label": t("accountLabel"), onchange: (e) => {
      const x = accounts.find((y) => y.account === e.target.value);
      if (!x) return;
      // A closed case takes the _cust request, when the rule has one.
      const code = x.state === "closed" && a.closedCode ? a.closedCode : a.openCode || a.code;
      activitiesOf(a).forEach((act) => Object.assign(act, { account: x.account, spv: x.spv, accountState: x.state, forRequest: code }));
      Object.assign(a, { account: x.account, spv: x.spv, accountState: x.state, code, codes: [code],
        codeName: (S.codeNames || {})[code] || a.codeName, caveat: a.caveat === "account_not_identified" ? null : a.caveat });
      renderCase();
    } },
    a.account ? "" : h("option", { value: "", text: t("pickAccount") }),
    ...accounts.map((x) => h("option", { value: x.account, selected: x.account === a.account ? true : null, text: label(x) })));
    return h("label", { class: "account-line" }, h("span", { class: "muted small", text: t("accountLabel") }), pick);
  }
  if (!a.account) return "";
  return h("div", { class: "account-line small" }, h("span", { class: "muted", text: `${t("accountLabel")}: ` }),
    label({ account: a.account, spv: a.spv || "—", state: a.accountState }));
}

function templateBlock(a) {
  if (!a.template) return "";
  const tpl = (S.templates || {})[a.template] || {};
  return h("details", { class: "more template" }, h("summary", { text: `${t("templateLabel")}: ${tpl.label || a.template}` }),
    h("pre", { class: "template-text", text: a.text || tpl.text || "" }));
}

function actionRow(a, u, editable) {
  const quotes = (u.evidence || []).filter((e) => e.supports === "action" && (a.because || []).includes(`${e.flag}=true`));
  const head = h("div", { class: "what" }, actionText(a),
    a.source === "added" ? h("span", { class: "pill plain", text: t("addedByYou") }) : "");
  const codes = a.code ? [a.code] : codesOf(a);
  const missing = [].concat(a.missing || []);
  const body = [
    a.category ? h("div", { class: "muted small", text: catLabel(a.category) }) : "",
    codes.length ? h("div", { class: "codes" }, ...codes.map((x) => h("code", { text: String(x) })),
      a.codeName ? h("span", { class: "small", text: ` ${a.codeName}` }) : "") : "",
    a.forRequest ? h("div", { class: "muted small", text: t("forRequest", { c: a.forRequest }) }) : "",
    accountLine(a, u, editable),
    a.folder ? h("div", { class: "small" }, h("span", { class: "muted", text: `${t("folderLabel")}: ` }), a.folder) : "",
    a.caveat ? h("div", { class: "caveat", text: t(`cv_${a.caveat}`) }) : "",
    missing.length && !a.template ? h("div", { class: "caveat", text: `${lang === "el" ? "Λείπει" : "Missing"}: ${missing.join(", ")}` }) : "",
    templateBlock(a),
    (a.reasons || []).length ? h("ul", {}, ...a.reasons.map((r) => h("li", { text: r }))) : "",
    ...quotes.map(quoteRow),
  ];
  if (!editable) return h("div", { class: "action" }, head, ...body);
  const changing = S.changing === a;
  return h("div", { class: `action pickable${a.on === false ? " off" : ""}${changing ? " changing" : ""}` },
    h("div", { class: "action-tools" },
      h("button", { class: "link change", type: "button", "aria-expanded": String(changing), text: changing ? t("cancel") : t("change"),
        onclick: () => { S.changing = changing ? null : a; renderCase(); } }),
      a.source === "added" ? h("button", { class: "link remove", type: "button", text: t("remove"),
        onclick: () => { const gone = a.do === "request" ? activitiesOf(a) : []; S.acts = S.acts.filter((x) => x !== a && !gone.includes(x)); S.changing = null; renderCase(); } }) : ""),
    h("label", { class: "action-check" },
      h("input", { type: "checkbox", checked: a.on !== false, onchange: (e) => { a.on = e.target.checked; renderCase(); } }), head),
    changing ? h("div", { class: "change-to" }, h("div", { class: "small muted", text: t("changeTo") }),
      actionPicker(a.category || finalCategoryNow(S.detail.case) || S.detail.case.modelCategory, (o, cat) => {
        // A replaced proposal counts as removed + added (Metrics), so the new one is the reviewer's own.
        const old = activitiesOf(a);
        const next = asChoice({ ...o, category: cat }, "added");
        S.acts = S.acts.filter((x) => !old.includes(x));
        S.acts.splice(S.acts.indexOf(a), 1, next, ...(next.do === "request" ? activityChoices(next, o.activities) : []));
        S.changing = null;
        renderCase();
      }, true)) : "",
    ...body);
}

/* Actions to pick from: the rule table's actions for the category first, then general ones; typing searches all. */
function actionPicker(category, onPick, focus) {
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
      ...items.map(([o, cat]) => h("button", { type: "button", class: "picker-opt", onclick: () => onPick(o, cat) },
        actionText(o), codesOf(o).length ? h("span", { class: "muted small", text: `  ${codesOf(o).join(" · ")}` }) : ""))]),
    shown.length ? "" : h("div", { class: "picker-none", text: t("noMatchCats") }));
  };
  input.addEventListener("input", paint);
  paint();
  if (focus) requestAnimationFrame(() => input.focus({ preventScroll: true }));
  return h("div", { class: "picker" }, input, list);
}

/* "Add an action" under the list. */
function actionAdder(category) {
  return h("details", { class: "more extra adder", open: S.addOpen ? true : null,
    ontoggle: (e) => { S.addOpen = e.target.open; } },
  h("summary", { text: t("addAction") }),
  actionPicker(category, (o, cat) => {
    const next = asChoice({ ...o, category: cat }, "added");
    S.acts.push(next, ...(next.do === "request" ? activityChoices(next, o.activities) : []));
    S.addOpen = true;
    renderCase();
  }));
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

// Save: always visible at the top of the case while reviewing; the comment is step 3, at the bottom.
function saveTop(c) {
  if (!editing(c)) return "";
  const err = h("p", { class: "error", role: "alert" });
  const next = h("input", { type: "checkbox", id: "rv-next", checked: store("next") !== "0" });
  const chosen = S.acts.filter((a) => a.on !== false);
  const save = h("button", { class: "primary", type: "button", text: t("save"), onclick: async () => {
    const body = { _etag: c._etag, comment: S.comment ?? c.reviewComment ?? "", otherCategories: S.pickExtras || [],
      finalActions: chosen.map(({ do: d, category, codes, code, open, closed, to, account, spv, accountState, folder, template, forRequest, source }) =>
        ({ do: d, category, codes, code, open, closed, to, account, spv, accountState, folder, template, forRequest, source })) };
    body.finalCategory = finalCategoryNow(c);
    // "No Match Found" is a category for manual handling: nothing else has to be picked.
    if (body.finalCategory === NO_MATCH) body.noMatch = true;
    else if (!S.categories.includes(body.finalCategory)) { err.textContent = t("badCat"); return; }
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
  const category = S.choice === "none" ? t("noneFits") : catLabel(finalCategoryNow(c) || "—");
  return h("div", { class: "savetop" },
    h("div", { class: "savetop-row" },
      h("span", { class: "savetop-summary", title: category },
        h("span", { class: "savetop-cat", text: category }),
        h("span", { class: "savetop-count", text: ` · ${t("actionsCount", { n: chosen.length })}` })),
      h("label", { class: "small muted next" }, next, " ", t("next")),
      S.forceEdit ? h("button", { class: "link", type: "button", text: t("cancel"),
        onclick: () => { S.forceEdit = false; S.choice = null; S.comment = undefined; S.changing = null; renderCase(); } }) : "",
      save),
    err);
}

function commentCard(c) {
  if (!editing(c)) return "";
  const comment = h("textarea", { id: "rv-comment", placeholder: t("comment"), rows: 3 });
  comment.value = S.comment ?? c.reviewComment ?? "";
  comment.addEventListener("input", () => { S.comment = comment.value; });
  return card(t("stepSave"), null, comment);
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
  return card(t("found"), t("foundCount", { n: rows.length }), h("div", { class: "found-scroll", tabindex: "0", role: "region", "aria-label": t("found") }, h("table", { class: "mini" },
    h("tr", {}, ...[lang === "el" ? "Στοιχείο" : "Item", t("value"), t("belongs"), t("where")].map((x) => h("th", { text: x }))),
    ...rows.map((e) => h("tr", {},
      h("td", { text: FIELD[lang][e.type] || e.type }),
      h("td", {}, h("strong", { text: e.value }), e.checked ? h("div", { class: "ok", text: `✓ ${t("checked")}` }) : null),
      h("td", { text: e.role ? ROLE[lang][e.role] || e.role : "—" }),
      h("td", {}, ...(e.sources || []).map((s) => h("div", {}, sourceChip(s), snippet(s.snippet, e.value)))))))));
}

/* One audit entry as a timeline row: when, who, what changed. Used per case and in the activity log. */
const EVENT_LABEL = { registered: "evRegistered", classified: "evClassified", reviewed: "evReviewed", "left mailbox": "evLeft",
  rerouted: "evRerouted", reset: "evReset" };
const actionLabel = (a) => [actionText(a), a.code ? `${a.code}${a.codeName ? " " + a.codeName : ""}` : codesOf(a).join(" "),
  a.account ? `${t("accountLabel").toLowerCase()} ${a.account}` : "", a.template && (S.templates || {})[a.template] ? S.templates[a.template].label : ""]
  .filter(Boolean).join(" · ");
const catOf = (x) => !x ? "—" : x.noMatch ? NO_MATCH : catLabel(x.finalCategory || "—");

// What a review changed: category (with the one it replaced, or the system's for reference), actions, further
// categories and the comment. c gives the system's category for reviews saved before it was recorded.
function reviewChanges(e, c) {
  const before = e.before || {}, after = e.after || {};
  const rows = [];
  const firstReview = before.status !== "REVIEWED";  // automatic emails already carry a category before their first review
  const was = firstReview ? (after.modelCategory || (c || {}).modelCategory) : null;
  const old = firstReview ? (was ? catLabel(was) : null) : catOf(before);
  const now = catOf(after);
  rows.push([t("evCategory"), old && old !== now
    ? h("span", {}, h("s", { class: "old", text: old }), firstReview ? h("span", { class: "muted small", text: ` (${t("evSystem")})` }) : "", " → ", h("b", { text: now }))
    : h("span", {}, h("b", { text: now }), old ? h("span", { class: "muted small", text: ` (${t("evUnchanged")})` }) : "")]);
  const othersBefore = before.otherCategories || [], othersAfter = after.otherCategories || [];
  if (othersAfter.length || othersBefore.length) {
    const added = othersAfter.filter((x) => !othersBefore.includes(x)), removed = othersBefore.filter((x) => !othersAfter.includes(x));
    if (added.length || removed.length || firstReview)
      rows.push([t("evOthers"), h("span", {}, ...added.map((x) => h("span", { class: "ev-add", text: `+ ${catLabel(x)}` })),
        ...removed.map((x) => h("span", { class: "ev-del", text: `− ${catLabel(x)}` })),
        !added.length && !removed.length ? othersAfter.map(catLabel).join(", ") : "")]);
  }
  // Reviews saved before Nov 2026 did not record the proposals: the email's own proposals stand in.
  const reference = firstReview ? (after.proposedActions || ((c || {}).understanding || {}).actions || null) : (before.finalActions || []);
  const finals = after.finalActions || [];
  if (reference) {
    const key = (a) => actionLabel(a);
    const was = reference.map(key), now2 = finals.map(key);
    const added = finals.filter((a) => !was.includes(key(a))), removed = reference.filter((a) => !now2.includes(key(a)));
    rows.push([t("evActions"), added.length || removed.length
      ? h("span", { class: "ev-list" }, ...added.map((a) => h("span", { class: "ev-add", text: `+ ${key(a)}` })),
        ...removed.map((a) => h("span", { class: "ev-del", text: `− ${key(a)}` })))
      : h("span", { class: "muted small", text: `${finals.length ? finals.map(key).join(" · ") : t("noActionsChosen")} (${t("evUnchanged")})` })]);
  } else if (finals.length) {
    rows.push([t("evActions"), h("span", { class: "ev-list" }, ...finals.map((a) => h("span", { text: actionLabel(a) })))]);
  }
  if ((after.reviewComment || "") !== (before.reviewComment || "") && after.reviewComment)
    rows.push([t("evComment"), h("span", { class: "snippet", text: `“${after.reviewComment}”` })]);
  return h("dl", { class: "ev-changes" }, ...rows.flatMap(([k, v]) => [h("dt", { text: k }), h("dd", {}, v)]));
}

function eventRow(e, extra, c) {
  const who = e.byName || (e.by === "classifier" ? t("system") : e.by || "");
  let detail = "";
  if ((e.action === "classified" || e.action === "rerouted") && e.after) {
    const pct = e.after.confidence == null ? "—" : `${Math.round(e.after.confidence * 100)}%`;
    detail = t("evClassifiedAs", { c: catLabel(e.after.category || "—"), p: pct, r: t(`route${e.after.route}`) });
  } else if (e.action === "reset" && e.before) {
    detail = t("evResetDetail", { b: catOf(e.before) });
  }
  return h("div", { class: `event ev-${(e.action || "").replace(/\s/g, "-")}` },
    h("div", { class: "ev-head" }, h("strong", { text: t(EVENT_LABEL[e.action] || e.action) }),
      h("span", { class: "muted", text: ` · ${who} · ${when(e.at)}` })),
    extra || "",
    detail ? h("div", { class: "ev-detail", text: detail }) : "",
    e.action === "reviewed" && e.after ? reviewChanges(e, c) : "");
}
function historyCard(events) {
  return card(t("history"), null, h("div", { class: "timeline" }, ...[...events].reverse().map((e) => eventRow(e, null, (S.detail || {}).case))));
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
      onclick: () => { closeActivity(); setView("emails"); openCase(e.caseId); } }, eventRow(e, h("div", { class: "ev-subject", text: e.subject || e.caseId }))))
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

// Every To / Cc address, as written: name and address, wrapping onto as many lines as needed.
function recipients(label, people) {
  const list = (people || []).map((p) => (p && p.emailAddress) || {}).filter((a) => a.address || a.name);
  if (!list.length) return "";
  return h("div", { class: "recipients" }, h("span", { class: "muted", text: `${label}:` }),
    ...list.map((a) => h("span", { class: "addr", title: a.address || "", text: a.name && a.address && a.name !== a.address
      ? `${a.name} <${a.address}>` : a.address || a.name })));
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
  const body = [
    h("div", { class: "case-head" },
      h("h2", { text: c.subject || "—" }),
      h("div", { class: "meta" },
        h("span", { text: from.name ? `${from.name} <${from.address}>` : from.address || c.from || "" }),
        h("span", { text: when(c.receivedAt) }), statusPill(c), senderPill(d.senderType)),
      recipients(t("toLabel"), m.to), recipients(t("ccLabel"), m.cc)),
    lockedByOther ? h("div", { class: "notice warn", text: t("lockedBy", { n: d.lock.holderName }) }) : "",
    c.mailboxState === "removed" ? h("div", { class: "notice info", text: t("leftMailbox") }) : "",
    u.error ? h("div", { class: "notice warn", text: t("readError", { e: u.error }) }) : "",
    decisionCard(c),
    actionsCard(u, c),
    ...(c.understanding && !u.error ? [customerCard(u), foundCard(u)] : []),
    u.analysis ? h("p", { class: "muted small", text: `${t("analysis")}: ${u.analysis}` }) : "",
    commentCard(c),
    historyCard(d.events || [])];
  // Built last: the review form above sets up the chosen category and actions it summarises.
  pane.replaceChildren(saveTop(c), ...body);
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
  $("#export").title = t("exportExcelTip");
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

// ------------------------------------------------------------------ metrics view
// Routes in a fixed order, bottom of the stack to the top; colours in app.css (--m-*). Validated set.
const M_ROUTES = [["AUTO", "mAuto", "auto"], ["REVIEW", "mReview", "review"], ["EXCEPTION", "mException", "exc"],
  ["WAITING", "mWaiting", "wait"]];
const SVG_NS = "http://www.w3.org/2000/svg";
const fmtN = (n) => n == null ? t("mNone") : new Intl.NumberFormat(lang === "el" ? "el-GR" : "en-GB").format(n);
const fmtP = (p) => p == null ? t("mNone") : `${new Intl.NumberFormat(lang === "el" ? "el-GR" : "en-GB", { maximumFractionDigits: 1 }).format(p)}%`;

function svg(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) el.setAttribute(k, v);
  for (const kid of kids.flat()) if (kid) el.append(kid);
  return el;
}
function niceMax(v) {
  if (v <= 4) return 4;
  const step = 10 ** Math.floor(Math.log10(v / 4));
  const nice = [1, 2, 2.5, 5, 10].map((m) => m * step).find((s) => s * 4 >= v);
  return nice * 4;
}
function shortDay(day) {
  const [y, m, d] = day.split("-").map(Number);
  return new Intl.DateTimeFormat(lang === "el" ? "el-GR" : "en-GB", { day: "numeric", month: "short", timeZone: "UTC" })
    .format(Date.UTC(y, m - 1, d));
}

function statTile(label, value, sub, key, filter) {
  const attrs = { class: filter ? "tile tile-link" : "tile", "data-key": key || null };
  if (filter) Object.assign(attrs, { role: "button", tabindex: "0", title: t("showEmails"),
    onclick: () => applyFilter(filter, label), onkeydown: (e) => { if (e.key === "Enter") applyFilter(filter, label); } });
  return h("div", attrs,
    h("div", { class: "tile-label" }, key ? h("span", { class: `swatch m-${key}`, "aria-hidden": "true" }) : null, label),
    h("div", { class: "tile-value", text: value }),
    sub ? h("div", { class: "tile-sub", text: sub }) : null);
}

function legend() {
  return h("ul", { class: "mlegend" }, ...M_ROUTES.map(([, label, key]) =>
    h("li", {}, h("span", { class: `swatch m-${key}`, "aria-hidden": "true" }), t(label))));
}

// Stacked columns: one per day, routes stacked in M_ROUTES order with a 2px surface gap, rounded top.
function dailyChart(daily) {
  const box = h("div", { class: "chart" });
  const tip = h("div", { class: "tip", role: "status", hidden: true });
  const draw = () => {
    const width = Math.max(box.clientWidth, 280);
    const height = 240, left = 36, right = 8, top = 18, bottom = 26;
    const plotW = width - left - right, plotH = height - top - bottom;
    const max = niceMax(Math.max(1, ...daily.map((d) => d.received)));
    const y = (v) => top + plotH - (v / max) * plotH;
    const band = plotW / daily.length;
    const barW = Math.max(2, Math.min(24, band * 0.62));
    const labelEvery = Math.ceil(daily.length / Math.max(1, Math.floor(plotW / 56)));
    const chart = svg("svg", { width, height, role: "img", "aria-label": `${t("mDaily")}: ${daily.map((d) => `${d.day} ${d.received}`).join(", ")}` });
    for (let i = 0; i <= 4; i++) {
      const v = (max / 4) * i;
      chart.append(svg("line", { x1: left, x2: width - right, y1: y(v), y2: y(v), class: i ? "grid" : "base" }),
        svg("text", { x: left - 6, y: y(v) + 4, "text-anchor": "end", class: "tick" }, document.createTextNode(fmtN(v))));
    }
    daily.forEach((d, i) => {
      const x = left + band * i + (band - barW) / 2;
      const parts = M_ROUTES.map(([route, , key]) => [d[route], key]).filter(([n]) => n > 0);
      let base = 0;
      parts.forEach(([n, key], j) => {
        const y0 = y(base), y1 = y(base + n);
        const last = j === parts.length - 1;
        const gap = j > 0 ? 2 : 0;  // the surface gap sits at the bottom of every segment but the first
        const h0 = Math.max(0, y0 - y1 - gap);
        const r = last ? Math.min(4, h0, barW / 2) : 0;
        const yb = y0 - gap, yt = yb - h0;
        const path = r
          ? `M${x},${yb}V${yt + r}Q${x},${yt} ${x + r},${yt}H${x + barW - r}Q${x + barW},${yt} ${x + barW},${yt + r}V${yb}Z`
          : `M${x},${yb}V${yt}H${x + barW}V${yb}Z`;
        chart.append(svg("path", { d: path, class: `bar m-${key}` }));
        base += n;
      });
      if (d.received && band >= 26) {
        chart.append(svg("text", { x: x + barW / 2, y: y(d.received) - 5, "text-anchor": "middle", class: "cap" },
          document.createTextNode(fmtN(d.received))));
      }
      if (i % labelEvery === 0) {
        chart.append(svg("text", { x: left + band * i + band / 2, y: height - 8, "text-anchor": "middle", class: "tick" },
          document.createTextNode(shortDay(d.day))));
      }
      const hit = svg("rect", { x: left + band * i, y: top, width: band, height: plotH, class: "hit", tabindex: "0",
        "aria-label": `${dayLabel(d.day)}: ${fmtN(d.received)}` });
      const show = () => {
        tip.replaceChildren(h("strong", { text: dayLabel(d.day) }),
          h("div", { class: "tip-row" }, h("span", { text: t("mReceived") }), h("b", { text: fmtN(d.received) })),
          ...[...M_ROUTES].reverse().map(([route, label, key]) => h("div", { class: "tip-row" },
            h("span", {}, h("span", { class: `swatch m-${key}`, "aria-hidden": "true" }), t(label)), h("b", { text: fmtN(d[route]) }))),
          h("div", { class: "tip-row muted" }, h("span", { text: t("mOpen") }), h("b", { text: fmtN(d.open) })));
        tip.hidden = false;
        const cx = left + band * i + band / 2;
        tip.style.left = `${Math.min(Math.max(cx - 90, 0), width - 180)}px`;
        tip.style.top = `${Math.max(y(d.received) - 150, 0)}px`;
        chart.querySelectorAll(".hit").forEach((el) => el.classList.toggle("on", el === hit));
      };
      const hide = () => { tip.hidden = true; hit.classList.remove("on"); };
      hit.addEventListener("mouseenter", show); hit.addEventListener("focus", show);
      hit.addEventListener("mouseleave", hide); hit.addEventListener("blur", hide);
      if (d.received) {
        const open = () => applyFilter({ since: d.day, until: d.day }, dayLabel(d.day));
        hit.addEventListener("click", open);
        hit.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
        hit.classList.add("clickable");
      }
      chart.append(hit);
    });
    box.replaceChildren(chart, tip);
  };
  box._draw = draw;
  return box;
}

function table(head, rows, opts = {}) {
  return h("div", { class: "table-wrap" }, h("table", { class: `mtable ${opts.class || ""}` },
    h("thead", {}, h("tr", {}, ...head.map((x, i) => h("th", { class: i ? "num" : null, text: x })))),
    h("tbody", {}, ...rows.map((r) => h("tr", {}, ...r.map((x, i) => h("td", { class: i ? "num" : null }, x)))))));
}
// A value with a thin bar behind it (single series, so no legend: the column header names it).
function barCell(value, max, shown) {
  return h("div", { class: "barcell" }, h("span", { class: "barfill", style: `width:${max ? (100 * value) / max : 0}%` }),
    h("span", { class: "barval" }, shown ?? fmtN(value)));
}
function mcard(title, sub, ...body) {
  const wide = body[0] === "wide";
  if (wide) body.shift();
  return h("section", { class: wide ? "mcard wide" : "mcard" }, h("h3", {}, h("span", { text: title }), sub ? h("span", { class: "sub", text: sub }) : null), ...body);
}

// A count that opens the Emails tab filtered to the emails it counts.
function go(n, filter, label, text) {
  const shown = text ?? fmtN(n);
  if (!n) return shown;
  return h("button", { type: "button", class: "num-link", title: t("showEmails"), onclick: () => applyFilter(filter, label) }, shown);
}

function renderMetrics() {
  const m = S.metrics;
  const body = $("#metrics-body");
  $("#ranges").replaceChildren(...[["7", "range7"], ["30", "range30"], ["90", "range90"], ["all", "rangeAll"]].map(([v, k]) =>
    h("button", { type: "button", "aria-pressed": String(S.range === v), onclick: () => { S.range = v; store("range", v); loadMetrics(); } }, t(k))));
  if (!m) return;
  const tot = m.totals;
  if (!tot.received) {
    body.replaceChildren(h("p", { class: "muted period", text: t("mPeriod", { a: dayLabel(m.from), b: dayLabel(m.to) }) }),
      h("div", { class: "mcard empty-m", text: t("mNoData") }));
    return;
  }
  const chart = dailyChart(m.daily);
  const r = m.routing, a = m.actions, cb = m.combined || {};
  const routeName = { AUTO: t("mAuto"), REVIEW: t("mReview"), EXCEPTION: t("mException") };
  const routeOf = { AUTO: ["AUTO"], REVIEW: ["REVIEW"], EXCEPTION: ["EXCEPTION"] };
  const maxReason = Math.max(0, ...r.reasons.map((x) => x.emails));
  const maxBand = Math.max(0, ...r.bands.map((x) => x.emails));
  const maxKind = Math.max(0, ...a.byKind.map((x) => x.proposed));
  const anyReviewed = tot.reviewed > 0;
  const WRONG = ["changed", "none_fits"];
  const cell = (n, filter, label) => h("div", { class: "mx-cell" }, go(n, filter, label), h("span", { class: "muted small", text: fmtP(cb.reviewed ? (100 * n) / cb.reviewed : null) }));
  body.replaceChildren(
    h("p", { class: "muted period", text: `${t("mPeriod", { a: dayLabel(m.from), b: dayLabel(m.to) })} · ${t("clickHint")}` }),
    h("div", { class: "tiles" },
      statTile(t("mReceived"), fmtN(tot.received), null, null, {}),
      statTile(t("mAuto"), fmtN(tot.auto), t("mOfClassified", { p: fmtP(tot.autoPct) }), "auto", { route: ["AUTO"] }),
      statTile(t("mReview"), fmtN(tot.review + tot.exception),
        `${t("mOfClassified", { p: fmtP(tot.reviewPct) })} · ${t("mException")}: ${fmtN(tot.exception)}`, "review", { route: ["REVIEW", "EXCEPTION"] }),
      statTile(t("mWaiting"), fmtN(tot.waiting), null, "wait", { waiting: true }),
      statTile(t("mOpen"), fmtN(tot.open), null, null, { open: true }),
      statTile(t("mReviewed"), fmtN(tot.reviewed),
        tot.medianHoursToReview == null ? null : `${t("mTurnaround")}: ${t("mHours", { n: fmtN(tot.medianHoursToReview) })}`, null, { reviewed: true })),
    mcard(t("mDaily"), t("mDailySub"), legend(), chart,
      h("details", { class: "astable" }, h("summary", { text: t("mAsTable") }),
        table([t("mDay"), t("mReceived"), t("mAuto"), t("mReview"), t("mException"), t("mWaiting"), t("mReviewed"), t("mOpen")],
          [...m.daily].reverse().filter((d) => d.received).map((d) => {
            const day = { since: d.day, until: d.day }, label = dayLabel(d.day);
            return [label, go(d.received, day, label), go(d.AUTO, { ...day, route: ["AUTO"] }, `${label} · ${t("mAuto")}`),
              go(d.REVIEW, { ...day, route: ["REVIEW"] }, `${label} · ${t("mReview")}`),
              go(d.EXCEPTION, { ...day, route: ["EXCEPTION"] }, `${label} · ${t("mException")}`),
              go(d.WAITING, { ...day, waiting: true }, `${label} · ${t("mWaiting")}`),
              go(d.reviewed, { ...day, reviewed: true }, `${label} · ${t("mReviewed")}`),
              go(d.open, { ...day, open: true }, `${label} · ${t("mOpen")}`)];
          })))),
    h("h2", { class: "msection", text: t("mQuality") }),
    h("div", { class: "mgrid" },
      mcard(t("mCombined"), t("mCombinedSub"), anyReviewed
        ? h("div", { class: "matrix", role: "table", "aria-label": t("mCombined") },
          h("div", { class: "mx-h" }), h("div", { class: "mx-h", text: t("mActSame") }), h("div", { class: "mx-h", text: t("mActChanged") }),
          h("div", { class: "mx-r", text: t("mCatRight") }),
          cell(cb.rightRight, { outcome: ["accepted"], actions: "same" }, `${t("mCatRight")} · ${t("mActSame")}`),
          cell(cb.rightWrong, { outcome: ["accepted"], actions: "changed" }, `${t("mCatRight")} · ${t("mActChanged")}`),
          h("div", { class: "mx-r", text: t("mCatWrong") }),
          cell(cb.wrongRight, { outcome: WRONG, actions: "same" }, `${t("mCatWrong")} · ${t("mActSame")}`),
          cell(cb.wrongWrong, { outcome: WRONG, actions: "changed" }, `${t("mCatWrong")} · ${t("mActChanged")}`))
        : h("p", { class: "muted pad", text: t("mNoReviews") })),
      mcard(t("mReviewers"), t("mReviewersSub"), (m.reviewers || []).length
        ? table([t("mReviewer"), t("mReviewed"), t("mAccepted"), t("mCatChanged"), t("mActChanged"), t("mMedian"), t("mLast")],
          m.reviewers.map((x) => [x.name,
            go(x.reviewed, { reviewer: x.id, reviewed: true }, `${t("mReviewer")}: ${x.name}`),
            go(x.accepted, { reviewer: x.id, outcome: ["accepted"] }, `${x.name} · ${t("mAccepted")}`, `${fmtN(x.accepted)} (${fmtP(x.acceptedPct)})`),
            go(x.changed + x.noneFits, { reviewer: x.id, outcome: WRONG }, `${x.name} · ${t("mCatChanged")}`),
            go(x.actionsChanged, { reviewer: x.id, actions: "changed" }, `${x.name} · ${t("mActChanged")}`,
              `${fmtN(x.actionsChanged)} (${fmtP(x.actionsChangedPct)})`),
            x.medianHours == null ? t("mNone") : t("mHours", { n: fmtN(x.medianHours) }),
            x.last ? when(x.last) : t("mNone")]))
        : h("p", { class: "muted pad", text: t("mNoReviews") }))),
    h("h2", { class: "msection", text: t("mRouting") }),
    h("div", { class: "mgrid" },
      mcard(t("mReasons"), t("mReasonsSub"), r.reasons.length
        ? table([t("mReasons"), t("mEmails")], r.reasons.map((x) => [t(`rs_${x.key}`),
          barCell(x.emails, maxReason, go(x.emails, { reason: x.key }, t(`rs_${x.key}`)))]), { class: "bars" })
        : h("p", { class: "muted pad", text: t("mNone") })),
      mcard(t("mBands"), t("mBandsSub"),
        table([t("mBand"), t("mEmails"), t("mReviewed"), t("mAcceptRate")],
          [...r.bands].reverse().map((b) => {
            const label = b.to === 100 ? `${b.from}–100%` : `${b.from}–${b.to}%`;
            return [label, barCell(b.emails, maxBand, go(b.emails, { band: [b.from, b.to === 100 ? 101 : b.to] }, `${t("mBand")} ${label}`)),
              go(b.reviewed, { band: [b.from, b.to === 100 ? 101 : b.to], reviewed: true }, `${t("mBand")} ${label} · ${t("mReviewed")}`),
              fmtP(b.acceptedPct)];
          }), { class: "bars" })),
      mcard(t("mOutcome"), t("mOutcomeSub"), "wide", anyReviewed
        ? table([t("mRoute"), t("mEmails"), t("mReviewed"), t("mAccepted"), t("mChanged"), t("mNoneFits"), t("mAcceptRate")],
          Object.entries(r.byRoute).map(([k, v]) => [routeName[k], go(v.emails, { route: routeOf[k] }, routeName[k]),
            go(v.reviewed, { route: routeOf[k], reviewed: true }, `${routeName[k]} · ${t("mReviewed")}`),
            go(v.accepted, { route: routeOf[k], outcome: ["accepted"] }, `${routeName[k]} · ${t("mAccepted")}`),
            go(v.changed, { route: routeOf[k], outcome: ["changed"] }, `${routeName[k]} · ${t("mChanged")}`),
            go(v.noneFits, { route: routeOf[k], outcome: ["none_fits"] }, `${routeName[k]} · ${t("mNoneFits")}`),
            fmtP(v.acceptedPct)]))
        : h("p", { class: "muted pad", text: t("mNoReviews") })),
      mcard(t("mCategories"), t("mCategoriesSub"), "wide",
        table([t("mCategory"), t("mEmails"), t("mAuto"), t("mReview"), t("mAutoShare"), t("mAcceptRate")],
          r.categories.slice(0, S.allCats ? undefined : 10).map((c) => [catLabel(c.category),
            go(c.emails, { modelCat: c.category }, catLabel(c.category)),
            go(c.auto, { modelCat: c.category, route: ["AUTO"] }, `${catLabel(c.category)} · ${t("mAuto")}`),
            go(c.review, { modelCat: c.category, route: ["REVIEW", "EXCEPTION"] }, `${catLabel(c.category)} · ${t("mReview")}`),
            fmtP(c.autoPct), fmtP(c.acceptedPct)]), { class: "cats" }),
        r.categories.length > 10 ? h("button", { type: "button", class: "link more-cats",
          onclick: () => { S.allCats = !S.allCats; renderMetrics(); } },
        S.allCats ? t("mFewerCats") : t("mAllCats", { n: r.categories.length })) : null)),
    h("h2", { class: "msection", text: t("mActionsTitle") }),
    h("div", { class: "tiles" },
      statTile(t("mProposedAll"), fmtN(a.totals.proposed)),
      statTile(t("mKept"), fmtN(a.totals.kept), a.totals.keptPct == null ? null : `${fmtP(a.totals.keptPct)} · ${t("mProposedReviewed")}: ${fmtN(a.totals.proposedReviewed)}`),
      statTile(t("mRemoved"), fmtN(a.totals.removed)),
      statTile(t("mAdded"), fmtN(a.totals.added)),
      statTile(t("mUnchanged"), fmtP(a.totals.unchangedPct), `${fmtN(a.totals.casesWithProposals)} ${t("mOfReviewed")}`, null,
        a.totals.casesWithProposals ? { actions: "same" } : null)),
    h("div", { class: "mgrid" },
      mcard(t("mActionsTitle"), t("mActionsSub"), "wide", a.byKind.length
        ? table([t("mKind"), t("mProposedAll"), t("mProposedReviewed"), t("mKept"), t("mRemoved"), t("mAdded"), t("mKeptRate")],
          a.byKind.map((k) => [ACTION[lang][k.do] || k.do, barCell(k.proposed, maxKind), fmtN(k.proposedReviewed), fmtN(k.kept),
            fmtN(k.removed), fmtN(k.added), fmtP(k.keptPct)]), { class: "bars" })
        : h("p", { class: "muted pad", text: t("mNone") })),
      mcard(t("mCodes"), t("mCodesSub"), a.codes.length
        ? table([t("mCode"), t("mCount")], a.codes.map((c) => [c.code, fmtN(c.count)]))
        : h("p", { class: "muted pad", text: anyReviewed ? t("mNone") : t("mNoReviews") }))));
  chart._draw();
}

async function loadMetrics() {
  renderMetrics();
  if (!S.metrics) $("#metrics-body").replaceChildren(spinner(t("loading")));
  $("#metrics-body").setAttribute("aria-busy", "true");
  const res = await api(`/api/metrics?days=${encodeURIComponent(S.range)}`).catch(() => null);
  $("#metrics-body").removeAttribute("aria-busy");
  if (!res || !res.ok) { $("#metrics-body").replaceChildren(h("p", { class: "error", text: t("error") })); return; }
  S.metrics = res.data;
  renderMetrics();
}

function setView(view) {
  S.view = view;
  store("view", view);
  document.querySelectorAll("#views button").forEach((b) => b.setAttribute("aria-current", String(b.dataset.view === view)));
  $(".layout").hidden = view !== "emails";
  $("#metrics").hidden = view !== "metrics";
  if (view === "metrics") loadMetrics();
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
  S.templates = meta.data.templates || {};
  S.codeNames = meta.data.codeNames || {};
  $("#me").textContent = S.user.name;
  applyWords();
  loadIngest();
  setInterval(loadIngest, 60000);
  await loadCases();
  const fromHash = decodeURIComponent(location.hash.slice(1));
  setView(fromHash ? "emails" : S.view);
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
  $("#lang").addEventListener("click", () => { lang = lang === "el" ? "en" : "el"; store("lang", lang); applyWords(); renderDays(); renderList(); renderCase(); renderViewer(); if (S.view === "metrics") renderMetrics(); });
  $("#search").addEventListener("input", (e) => { S.q = e.target.value; renderList(); });
  $("#day").addEventListener("change", (e) => { S.day = e.target.value; S.win = "all"; renderList(); });
  $("#basis").addEventListener("change", (e) => { S.basis = e.target.value; S.day = "all"; S.win = "all"; renderDays(); renderList(); });
  $("#sort").addEventListener("change", (e) => { S.sort = e.target.value; renderList(); });
  $("#cat").addEventListener("change", (e) => { S.cat = e.target.value; renderList(); });
  $("#sender").addEventListener("change", (e) => { S.sender = e.target.value; renderList(); });
  $("#export").addEventListener("click", (e) => exportExcel(e.currentTarget));
  document.querySelectorAll("#views button").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
  let resizing;
  window.addEventListener("resize", () => { clearTimeout(resizing); resizing = setTimeout(() => { if (S.view === "metrics") renderMetrics(); }, 150); });
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
