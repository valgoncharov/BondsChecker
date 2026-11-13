from datetime import datetime

RUBLE_UNITS = {"RUB", "SUR", "RUR"}


def format_amount(
    value_rub: float | None,
    value: float | None,
    faceunit: str | None,
) -> str:
    if value_rub is not None:
        return f"{value_rub:.2f} руб."
    if value is not None:
        unit = (faceunit or "").upper()
        if not unit or unit in RUBLE_UNITS:
            return f"{value:.2f} руб."
        return f"{value:.2f} {unit}"
    return "сумма будет определена"


def format_date(iso_date: str | None) -> str:
    if not iso_date:
        return "—"
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso_date
