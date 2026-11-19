import re

AFM_RE = re.compile(r"\b\d{9}\b")


def afm_checksum_valid(afm: str) -> bool:
    if not afm:
        return False
    d = "".join(ch for ch in str(afm).strip() if ch.isdigit())
    if len(d) != 9 or d == "000000000":
        return False
    total = sum(int(d[i]) * (2 ** (8 - i)) for i in range(8))
    check_digit = (total % 11) % 10
    return check_digit == int(d[8])


def extract_afms(text: str):
    return sorted({a for a in AFM_RE.findall(text or "") if afm_checksum_valid(a)})
