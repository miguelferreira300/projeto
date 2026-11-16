from datetime import datetime


def data_br(valor):
    """'2026-11-09 20:15:00' -> '09/11/2026'."""
    try:
        return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return valor or ""
