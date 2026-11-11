import os
import json
from dotenv import load_dotenv
from helpers.graph_api import get_access_token, copy_message_to_folder

load_dotenv()

PROCESSED_EMAIL = os.getenv("PROCESSED_EMAIL")
FOLDER_MAP_FILE = os.getenv("FOLDER_MAP_FILE")


def build_folder_lookups(folder_map: list[dict]) -> tuple:
    """
    Build all folder lookups needed for routing:

    - category_lookup   : { category_key (lowercase) → folder_id }
                          Only CATEGORY folders with status == "verified" are included.
    - status_folder     : { status_key → folder_id } for SYSTEM routing targets.
                          Populated from entries where folder_role == "SYSTEM"
                          and a "status" field is present.
    - wizard_folder_id  : folder_id for the Wizard routing target.
                          Populated from the ROUTING entry whose folder_name
                          contains "wizard" (case-insensitive).
    - portal_folder_id  : folder_id for the Portal routing target.
                          Populated from the ROUTING entry whose folder_name
                          contains "portal" (case-insensitive).
    - error_folder_id   : folder_id for 04_Processing_Error (hard fallback).
    """
    category_lookup: dict[str, str] = {}
    status_folder: dict[str, str | None] = {
        "needs_review": None,
        "needs_identification": None,
    }
    wizard_folder_id: str | None = None
    portal_folder_id: str | None = None
    error_folder_id: str | None = None

    for folder in folder_map:
        folder_name = folder["folder_name"]
        folder_id = folder["folder_id"]
        folder_role = folder.get("folder_role")
        status = folder.get("status")

        if folder_role == "UAT_ROOT":
            continue

        # Hard fallback — matched by name, always present
        if folder_name == "04_Processing_Error":
            error_folder_id = folder_id

        # ROUTING folders — wizard and portal identified by name
        if folder_role == "ROUTING":
            name_lower = folder_name.lower()
            if "wizard" in name_lower:
                wizard_folder_id = folder_id
            elif "portal" in name_lower:
                portal_folder_id = folder_id

        # Status-based SYSTEM routing targets (needs_review, needs_identification)
        if folder_role == "SYSTEM" and status in status_folder:
            status_folder[status] = folder_id

        # Category routing — only verified CATEGORY folders
        if folder_role == "CATEGORY" and status == "verified":
            key = folder_name.split("_", 1)[1] if "_" in folder_name else folder_name
            category_lookup[key.lower().strip()] = folder_id

    return (
        category_lookup,
        status_folder,
        wizard_folder_id,
        portal_folder_id,
        error_folder_id,
    )


def _resolve_status_destination(
    status: str | None,
    status_folder: dict,
    error_folder_id: str | None,
) -> tuple[str | None, str]:
    """
    Resolve a destination folder_id and a log label for non-verified statuses.
    Returns (destination_id, log_label).
    """
    if status == "needs_review":
        return status_folder["needs_review"], "00_To_Process (needs_review)"
    elif status == "needs_identification":
        return status_folder[
            "needs_identification"
        ], "01_Unverified (needs_identification)"
    else:
        return error_folder_id, "04_Processing_Error (status null or unknown)"


def main():
    token = get_access_token()

    with open(PROCESSED_EMAIL, "r", encoding="utf-8") as f:
        emails = json.load(f)

    with open(FOLDER_MAP_FILE, "r", encoding="utf-8") as f:
        folder_map = json.load(f)

    # Build all lookups and validate required folders exist before processing any email
    (
        category_lookup,
        status_folder,
        wizard_folder_id,
        portal_folder_id,
        error_folder_id,
    ) = build_folder_lookups(folder_map)

    total = len(emails)
    print(f"Loaded {total} categorised email(s) to route.")
    print(f"Category lookup built with {len(category_lookup)} entries.\n")

    success_count = 0
    wizard_count = 0
    portal_count = 0
    fallback_count = 0
    error_count = 0

    for i, email in enumerate(emails, start=1):
        message_id = email.get("id", "")
        subject = email.get("subject", "(no subject)")
        category_raw = email.get("category", "").strip()
        category_key = category_raw.lower()
        status = email.get("status")
        routing_mode = email.get("routing_mode", "internal").strip().lower()

        print(f"[{i}/{total}] {subject}")
        print(f"  Category     : '{category_raw}'")
        print(f"  Status       : '{status}'")
        print(f"  Routing mode : '{routing_mode}'")

        # ── Routing logic ─────────────────────────────────────────────────────
        #
        # Step 1 — routing_mode sets the channel: wizard, portal, or internal.
        #
        # Step 2 — status determines the destination within that channel:
        #   "verified"             → proceed to the channel's target folder
        #   "needs_review"         → 00_To_Process  (overrides channel)
        #   "needs_identification" → 01_Unverified  (overrides channel)
        #   null / unknown         → 04_Processing_Error
        #
        # Step 3 — category is only consulted when channel == internal
        #           AND status == "verified".
        # ──────────────────────────────────────────────────────────────────────

        if routing_mode == "wizard":
            destination_id = wizard_folder_id
            print("  Routed       : R01_Wizard (routing_mode=wizard, status=any)")
            wizard_count += 1

        elif routing_mode == "portal":
            destination_id = portal_folder_id
            print("  Routed       : R02_Portal (routing_mode=portal, status=any)")
            portal_count += 1

        else:
            # routing_mode == "internal" (or null / unrecognised) — use status logic
            if routing_mode not in ("internal",):
                print(
                    f"  WARNING      : unrecognised routing_mode '{routing_mode}' "
                    "— treating as internal"
                )

            if status == "verified":
                destination_id = category_lookup.get(category_key)
                if destination_id:
                    matched_name = next(
                        (
                            f["folder_name"]
                            for f in folder_map
                            if f.get("folder_id") == destination_id
                        ),
                        destination_id,
                    )
                    print(f"  Matched      : {matched_name}")
                    success_count += 1
                else:
                    print(
                        f"  WARNING      : No folder match for '{category_raw}' "
                        "— routing to 04_Processing_Error"
                    )
                    destination_id = error_folder_id
                    fallback_count += 1
            else:
                destination_id, label = _resolve_status_destination(
                    status, status_folder, error_folder_id
                )
                print(f"  Routed       : {label}")
                fallback_count += 1

        try:
            copy_message_to_folder(token, message_id, destination_id)
            print("  Result       : copied ✓")
        except Exception as exc:
            print(f"  ERROR        : could not copy message {message_id}: {exc}")
            error_count += 1

        print()

    print("─" * 50)
    print("Done.")
    print(f"  Routed to category folder : {success_count}")
    print(f"  Routed to Wizard          : {wizard_count}")
    print(f"  Routed to Portal          : {portal_count}")
    print(f"  Routed to fallback/system : {fallback_count}")
    print(f"  Failed (API error)        : {error_count}")


if __name__ == "__main__":
    main()
