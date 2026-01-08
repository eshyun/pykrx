import datetime

from .bond import *
from .etx import *
from .future import *
from .krxio import (
    clear_session_file,
    enable_auto_login,
    is_auto_login_enabled,
    krx_extend_session,
    krx_login,
    krx_start_keepalive,
)
from .market import *


def login(*args, **kwargs):
    return krx_login(*args, **kwargs)


def extend_session(*args, **kwargs):
    return krx_extend_session(*args, **kwargs)


def start_keepalive(*args, **kwargs):
    return krx_start_keepalive(*args, **kwargs)


def enable_auto_login_on_failure(
    enabled: bool = True, *, allow_dup_login: bool = False
):
    return enable_auto_login(enabled, allow_dup_login=allow_dup_login)


def auto_login_on_failure_enabled() -> bool:
    return is_auto_login_enabled()


def datetime2string(dt, freq="d"):
    if freq.upper() == "Y":
        return dt.strftime("%Y")
    elif freq.upper() == "M":
        return dt.strftime("%Y%m")
    else:
        return dt.strftime("%Y%m%d")


def get_nearest_business_day_in_a_week(date: str = None, prev: bool = True) -> str:
    """인접한 영업일을 조회한다.

    Args:
        date (str , optional): 조회할 날짜로 입력하지 않으면 현재 시간으로 대체
        prev (bool, optional): 이전 영업일을 조회할지 이후 영업일을 조회할지
                               조정하는 flag

    Returns:
        str: 날짜 (YYMMDD)
    """
    if date is None:
        curr = datetime.datetime.now()
    else:
        curr = datetime.datetime.strptime(date, "%Y%m%d")

    if prev:
        prev = curr - datetime.timedelta(days=7)
        curr = curr.strftime("%Y%m%d")
        prev = prev.strftime("%Y%m%d")
        df = get_index_ohlcv_by_date(prev, curr, "1001")
        return df.index[-1].strftime("%Y%m%d")
    else:
        next = curr + datetime.timedelta(days=7)
        next = next.strftime("%Y%m%d")
        curr = curr.strftime("%Y%m%d")
        df = get_index_ohlcv_by_date(curr, next, "1001")
        return df.index[0].strftime("%Y%m%d")
