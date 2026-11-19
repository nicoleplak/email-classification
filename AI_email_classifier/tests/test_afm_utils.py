from utils.afm_utils import afm_checksum_valid, extract_afms


def test_valid_afm_checksum():
    """Valid AFM should pass; invalid should fail."""
    assert afm_checksum_valid("090000045")  # valid example
    assert not afm_checksum_valid("123456789")  # invalid checksum
    assert not afm_checksum_valid("")  # empty
    assert not afm_checksum_valid("000000000")  # all zeros


def test_extract_afms():
    """Only valid AFMs should be extracted from text."""
    text = "Ο ΑΦΜ μου είναι 090000045 και 123456789 και 000000000"
    afms = extract_afms(text)
    assert "090000045" in afms
    assert "123456789" not in afms  # invalid filtered out
    assert "000000000" not in afms  # invalid filtered out
    # Ensure uniqueness
    text_dup = "ΑΦΜ 090000045 090000045"
    afms_dup = extract_afms(text_dup)
    assert afms_dup == ["090000045"]
