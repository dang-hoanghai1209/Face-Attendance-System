import os
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "Asia/Nha_Trang"
TIMEZONE_ALIASES = {
    # Asia/Nha_Trang is the project name; IANA uses Asia/Ho_Chi_Minh for Vietnam.
    "Asia/Nha_Trang": "Asia/Ho_Chi_Minh",
}


def configured_timezone_name():
    return os.getenv("APP_TIMEZONE", DEFAULT_TIMEZONE)


def resolved_timezone_name(timezone_name=None):
    configured_name = timezone_name or configured_timezone_name()
    return TIMEZONE_ALIASES.get(configured_name, configured_name)


def get_app_timezone(timezone_name=None):
    resolved_name = resolved_timezone_name(timezone_name)
    try:
        return ZoneInfo(resolved_name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(f"Invalid APP_TIMEZONE: {timezone_name or configured_timezone_name()}") from exc


def now_in_app_timezone():
    return datetime.now(get_app_timezone()).replace(tzinfo=None)
