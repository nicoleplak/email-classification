def pick_account_for_category(category, registry_row):
    """
    Decide which account and which request codes apply for a given category.
    Returns (account, [request_codes]).
    """

    selected_account = None
    request_codes = []

    if not registry_row:
        return None, request_codes

    spv = (registry_row.get("PRTFL_CD") or "").upper()
    accounts_raw = registry_row.get("ACC_UNQ_CD", "")
    accounts = [a.strip() for a in accounts_raw.split(",") if a.strip()]
    status = (registry_row.get("CST_STS_NM") or "").upper()

    # --- Global override 3869: prefer 02 accounts
    if "3869" in status:
        v02_accounts = [a for a in accounts if a.startswith("02")]
        if v02_accounts:
            return v02_accounts[0], []

    # --- Category: Ν.3869
    if category.startswith("Αιτήματα Ν.3869"):
        v02 = [a for a in accounts if a.startswith("02")]
        v04 = [a for a in accounts if a.startswith("04")]
        if registry_row.get("HAS_DECISION_3869") == "Y":
            if v02:
                return v02[0], ["161 Προσκόμιση απόφασης Ν.3869"]
            elif v04:
                return v04[0], ["161 Προσκόμιση απόφασης Ν.3869"]
            return None, ["161 Προσκόμιση απόφασης Ν.3869"]

        if not v02:
            return None, request_codes

        selected_account = v02[0]
        if registry_row.get("REQ_DOSE_3869") == "Y":
            request_codes.append("113 N.3869/2010_Πληροφορίες δόσης_λογαριασμού")
        if registry_row.get("REQ_PAYMENTS_3869") == "Y":
            request_codes.append("103 N.3869/2010_Βεβαίωση_Καταβολών")
        if registry_row.get("REQ_DEBT_3869") == "Y":
            request_codes.append("105 N.3869/2010_Βεβαίωση_Οφειλής")
        if registry_row.get("REQ_REVERSAL_3869") == "Y":
            request_codes.append("108 N.3869/2010_Αντιλογισμός")
        if registry_row.get("REQ_DISPUTE_3869") == "Y":
            request_codes.append("112 N.3869/2010_Αμφισβήτηση_οφειλής")
        return selected_account, request_codes

    # --- Category: Επικαιροποίηση στοιχείων
    if category == "Επικαιροποίηση στοιχείων με επισύναψη υπεύθυνης δήλωσης":
        if spv == "ERB":
            return None, request_codes
        cands = [a for a in accounts if a.startswith("04")]
        codes = [
            "131 Αίτημα_επικαιροποίησης_στοιχείων_KYC_Cust",
            "64 Αίτημα επικαιροποίησης_στοιχείων_KYC",
        ]
        return (cands[0], codes) if cands else (None, codes)

    # --- Category: Νομιμοποίηση κληρονόμων
    if category == "Νομιμοποίηση κληρονόμων με επισύναψη εγγράφων":
        cands = [a for a in accounts if a.startswith("04")]
        codes = [
            "123 Νομιμοποίηση_Κληρονόμου_Cust",
            "44 Προσκόμιση_Δικαιολογητικών_Κληρονόμου",
        ]
        return (cands[0], codes) if cands else (None, codes)

    # --- Category: Εξουσιοδοτήσεις
    if category == "Εξουσιοδοτήσεις":
        cands = [a for a in accounts if a.startswith("04")]
        codes = ["45 Προσκόμιση_Εξουσιοδότησης", "124 Προσκόμιση_Εξουσιοδότησης_Cust"]
        return (cands[0], codes) if cands else (None, codes)

    # --- Category: Αντιλογισμοί
    if category == "Αντιλογισμοί":
        cands = [a for a in accounts if a.startswith("04")]
        codes = ["152 Αντιλογισμός", "153 Αντιλογισμός_Cust"]
        return (cands[0], codes) if cands else (None, codes)

    # --- Category: Αντίγραφα συμβάσεων
    if category == "Αντίγραφα συμβάσεων":
        cands = [a for a in accounts if a.startswith("04")]
        codes = [
            "154 Χορήγηση_Συμβατικών_Εγγράφων",
            "155 Χορήγηση_Συμβατικών_Εγγράφων_Cust",
        ]
        return (cands[0], codes) if cands else (None, codes)

    # --- Category: Εθελοντική εκποίηση
    if category == "Εθελοντική εκποίηση":
        cands = [a for a in accounts if a.startswith("04")]
        codes = ["40 Νέα_Ρύθμιση", "142 Νέα_Ρύθμιση_Cust"]
        return (cands[0], codes) if cands else (None, codes)

    # --- Category: Αμφισβήτηση οφειλής
    if category == "Αμφισβήτηση οφειλής":
        cands = [a for a in accounts if a.startswith("04")]
        codes = ["146 Αμφισβήτηση_Οφειλής", "147 Αμφισβήτηση_Οφειλής_Cust"]
        return (cands[0], codes) if cands else (None, codes)

    # --- Category: Κίνηση λογαριασμού
    if category == "Κίνηση λογαριασμού":
        cands = [a for a in accounts if a.startswith("04")]
        codes = [
            "119 Εκτύπωση_Αναλυτικής_Κίνησης_Cust",
            "95 Εκτύπωση_Αναλυτικής_Κίνησης",
            "96 Εκτύπωση_Αναλυτικής_Κίνησης_Int",
        ]
        return (cands[0], codes) if cands else (None, codes)

    # --- Category: Ρύθμιση
    if category == "Ρύθμιση":
        cands = [a for a in accounts if a.startswith("04")]
        codes = ["40 Νέα Ρύθμιση", "142 Νέα_Ρύθμιση_Cust"]
        return (cands[0], codes) if cands else (None, codes)

    # --- Category: Πόθεν έσχες
    if category == "Πόθεν έσχες":
        is_3869 = "3869" in status
        codes_3869 = ["109 N.3869/2010_Βεβαίωση Πόθεν έσχες"]
        codes_default = ["111 Ειδική βεβαίωση_int", "122 Ειδική βεβαίωση_Cust"]

        if spv == "ERB":
            return None, (codes_3869 if is_3869 else codes_default)

        cands = [a for a in accounts if a.startswith("04")]
        if not cands:
            return None, (codes_3869 if is_3869 else codes_default)

        selected_account = cands[0]
        return selected_account, (codes_3869 if is_3869 else codes_default)

    # --- Category: Βεβαίωση Καταβολών / Τόκων
    if category == "Βεβαίωση_Καταβολών/Βεβαίωση_Τόκων":
        cands = [a for a in accounts if a.startswith("04")]
        codes = ["98 Βεβαίωση_Τόκων", "120 Βεβαίωση_Τόκων_Cust"]
        return (cands[0], codes) if cands else (None, codes)

    # --- Category: Ν4605
    if category == "Αιτήματα που αφορούν στον εξωδικαστικό 4605":
        cands = [a for a in accounts if a.startswith("04")]
        if not cands:
            return None, []
        selected_account = cands[0]
        # assuming registry_row may have description
        description = (registry_row.get("DESCRIPTION") or "").lower()
        if "αμφισβ" in description:
            return selected_account, ["158 Ν.4605_Αμφισβήτηση Οφειλής"]
        return selected_account, ["78 N4605", "127 Ν4605_Cust"]

    # --- Default
    return None, request_codes
