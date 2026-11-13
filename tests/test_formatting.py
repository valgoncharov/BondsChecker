from services.formatting import format_amount, format_date


def test_amount_prefers_rubles():
    assert format_amount(35.4, 35.4, "RUB") == "35.40 руб."


def test_amount_shows_zero():
    assert format_amount(0.0, 0.0, "RUB") == "0.00 руб."


def test_amount_foreign_currency():
    assert format_amount(None, 1.5, "USD") == "1.50 USD"


def test_amount_unknown():
    assert format_amount(None, None, None) == "сумма будет определена"


def test_format_date():
    assert format_date("2026-11-15") == "15.11.2026"
    assert format_date(None) == "—"
    assert format_date("not-a-date") == "not-a-date"
