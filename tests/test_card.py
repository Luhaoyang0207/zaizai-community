from zaizai.card import build_card


def _card(text="铂钻 3=2", ad=None, footer=None):
    return build_card(text, 42, 99, 1_700_000_000.0, ad, footer)


def test_card_has_requirement_host_and_board_link():
    e = _card()
    assert "铂钻 3=2" in e.title
    assert "<@42>" in e.description
    assert "<#99>" in e.description
    assert "找人组队看这里" in e.description
    assert "<t:1700000000:R>" in e.description


def test_card_without_ad_omits_ad_slot():
    e = _card(ad=None)
    assert "AD-SLOT" not in e.description
    e2 = _card(ad="AD-SLOT")
    assert "AD-SLOT" in e2.description


def test_card_footer_text():
    assert _card(footer=None).footer.text is None
    assert _card(footer="FOOT").footer.text == "FOOT"


def test_card_empty_text_uses_default_title():
    assert _card(text="").title == "组队中"


def test_card_long_text_truncated_to_title_limit():
    e = _card(text="x" * 500)
    assert len(e.title) == 256
