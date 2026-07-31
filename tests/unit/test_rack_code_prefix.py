from app.schemas.infrastructure import expand_row_prefixes, generate_slot_codes, letter_to_index, index_to_letter


def test_letter_index_roundtrip():
    assert letter_to_index("A") == 1
    assert letter_to_index("Z") == 26
    assert letter_to_index("AA") == 27
    assert letter_to_index("BZ") == 78
    assert index_to_letter(1) == "A"
    assert index_to_letter(26) == "Z"
    assert index_to_letter(27) == "AA"
    assert index_to_letter(78) == "BZ"


def test_expand_single_letter():
    assert expand_row_prefixes("A", 4) == ["A", "B", "C", "D"]
    assert expand_row_prefixes("Y", 3) == ["Y", "Z", "AA"]


def test_expand_range():
    assert expand_row_prefixes("A-D", 4) == ["A", "B", "C", "D"]
    assert expand_row_prefixes("A-Z", 3) == ["A", "B", "C"]
    assert expand_row_prefixes("A-BZ", 3)[:3] == ["A", "B", "C"]


def test_expand_range_too_short():
    try:
        expand_row_prefixes("A-B", 4)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "4 rows" in str(exc) or "4" in str(exc)


def test_generate_auto_codes_by_row_prefix():
    codes = generate_slot_codes([3, 2], code_mode="auto", code_prefix="A")
    assert codes == [["A01", "A02", "A03"], ["B01", "B02"]]

    codes2 = generate_slot_codes([2, 2, 2], code_mode="auto", code_prefix="A-C")
    assert codes2 == [["A01", "A02"], ["B01", "B02"], ["C01", "C02"]]
