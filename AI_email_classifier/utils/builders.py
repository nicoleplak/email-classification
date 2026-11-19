from utils.routing_engine import pick_account_for_category


def build_cid_spv_list(rows_df):
    """Return string of 'CST_UNQ_CD,PRTFL_CD' pairs separated by pipes."""
    pairs = [
        f"{r.get('CST_UNQ_CD')},{r.get('PRTFL_CD')}"
        for _, r in rows_df.drop_duplicates(
            subset=["CST_UNQ_CD", "PRTFL_CD"]
        ).iterrows()
    ]
    return " | ".join(pairs)


def build_spv_account_map_and_requests(
    rows_df, category, pick_func=pick_account_for_category
):
    """Return (SPV‑Account string, list of request codes)."""
    spv_accounts = []
    all_request_codes = set()

    for _, r in rows_df.drop_duplicates(subset=["PRTFL_CD"]).iterrows():
        account, request_codes = pick_func(category, r.to_dict())
        if account:
            spv_accounts.append(f"{r.get('PRTFL_CD')},{account}")
        if request_codes:
            all_request_codes.update(request_codes)

    return " | ".join(spv_accounts), sorted(all_request_codes)
