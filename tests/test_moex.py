from datetime import date

from services.moex import fetch_coupons, search_securities

COUPON_COLUMNS = [
    "coupondate",
    "recorddate",
    "value",
    "valueprc",
    "value_rub",
    "faceunit",
    "name",
    "isin",
]

SEARCH_COLUMNS = [
    "secid",
    "shortname",
    "isin",
    "type",
    "group",
    "is_traded",
    "emitent_title",
]


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload, status=200):
        self._payload = payload
        self._status = status

    def get(self, url, params=None):
        return FakeResponse(self._payload, self._status)


async def test_fetch_coupons_parses_and_sorts_rows():
    payload = {
        "coupons": {
            "columns": COUPON_COLUMNS,
            "data": [
                ["2026-12-01", "2026-11-25", 35.4, 5.0, 35.4, "RUB", "ОФЗ", "RU1"],
                ["2026-06-01", "2026-05-25", None, None, None, "RUB", "ОФЗ", "RU1"],
            ],
        }
    }

    coupons = await fetch_coupons(FakeSession(payload), "SU26238RMFS4")

    assert len(coupons) == 2
    assert coupons[0].coupon_date == date(2026, 6, 1)
    assert coupons[0].value is None
    assert coupons[1].value_rub == 35.4
    assert coupons[1].recorddate == date(2026, 11, 25)


async def test_fetch_coupons_skips_invalid_dates():
    payload = {
        "coupons": {
            "columns": COUPON_COLUMNS,
            "data": [
                ["not-a-date", None, 1.0, 1.0, 1.0, "RUB", "X", "RU2"],
                ["2027-01-10", None, 1.0, 1.0, 1.0, "RUB", "X", "RU2"],
            ],
        }
    }

    coupons = await fetch_coupons(FakeSession(payload), "TEST")

    assert [c.coupon_date for c in coupons] == [date(2027, 1, 10)]


async def test_fetch_coupons_returns_empty_list_without_block():
    payload = {"coupons": {"columns": [], "data": []}}

    assert await fetch_coupons(FakeSession(payload), "TEST") == []


async def test_fetch_coupons_returns_none_on_http_error():
    assert await fetch_coupons(FakeSession({}, status=500), "TEST") is None


async def test_search_filters_and_ranks_exact_match():
    payload = {
        "securities": {
            "columns": SEARCH_COLUMNS,
            "data": [
                ["SBERBOND", "Сбер Бонд", "RU1", "corp", "stock_bonds", 1, "Сбер"],
                ["SBER", "Сбер Облигация", "RU2", "corp", "stock_bonds", 1, "Сбер"],
                ["SBERP", "Сбер преф", "RU3", "common", "stock_shares", 1, "Сбер"],
                ["SBERX", "Сбер X", "RU4", "corp", "stock_bonds", 0, "Сбер"],
            ],
        }
    }

    found = await search_securities(FakeSession(payload), "SBER")

    assert [item.secid for item in found] == ["SBER", "SBERBOND"]
    assert all(item.group == "stock_bonds" for item in found)


async def test_search_returns_empty_for_blank_query():
    assert await search_securities(FakeSession({}), "   ") == []
