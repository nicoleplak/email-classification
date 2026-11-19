from __future__ import annotations

from typing import Any


def _normalize_category_name(value: Any) -> str:
    """
    Normalize category names for stable exact matching.

    Only harmless formatting differences are normalized.
    No fuzzy, partial, keyword, or semantic matching is performed.
    """
    if value is None:
        return ""

    return " ".join(str(value).split()).casefold()


def get_category_metadata(
    category_name: str,
    categories_data: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_name = _normalize_category_name(category_name)

    if not normalized_name:
        return {}

    matches = [
        category_metadata
        for category_metadata in categories_data
        if _normalize_category_name(category_metadata.get("Categories"))
        == normalized_name
    ]

    if not matches:
        return {}

    if len(matches) > 1:
        configured_names = [match.get("Categories") for match in matches]

        raise ValueError(
            "Duplicate category metadata entries after normalization "
            f"for {category_name!r}: {configured_names}"
        )

    return matches[0]
