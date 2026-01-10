import fcntl
import json
import os
import threading
import time
from abc import abstractmethod
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from pykrx.website.comm.util import PykrxRequestError
from pykrx.website.comm.webio import Get, Post, get_http_session, set_http_session


class KrxFutureIo(Get):
    @property
    def url(self):
        return "http://data.krx.co.kr/comm/bldAttendant/executeForResourceBundle.cmd"

    def read(self, **params):
        resp = super().read(**params)
        return resp.json()

    @property
    @abstractmethod
    def fetch(self, **params):
        return NotImplementedError


def _create_curl_session():
    try:
        from curl_cffi import requests as crequests
    except Exception as e:
        raise PykrxRequestError(
            "curl-cffi is required for KRX login. Please install curl-cffi."
        ) from e

    try:
        return crequests.Session(impersonate="chrome")
    except TypeError:
        return crequests.Session()


def _load_krx_credentials_from_file(path: str | None):
    if not path:
        return None
    p = Path(path).expanduser()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise PykrxRequestError(f"Failed to read KRX credentials file: {p}") from e
    if not isinstance(data, dict):
        raise PykrxRequestError(f"Invalid KRX credentials file format: {p}")
    return data


def _resolve_krx_credentials(mbr_id: str | None, password: str | None):
    if mbr_id and password:
        return mbr_id, password

    # 1) env
    if mbr_id is None:
        mbr_id = os.getenv("KRX_MBR_ID") or os.getenv("KRX_ID")
    if password is None:
        password = os.getenv("KRX_PASSWORD") or os.getenv("KRX_PW")
    if mbr_id and password:
        return mbr_id, password

    # 2) credentials file
    cred_path = os.getenv("KRX_CREDENTIALS_FILE")
    if not cred_path:
        cred_path = str(Path("~/.config/krx-session/krx_credentials.json"))
    data = _load_krx_credentials_from_file(cred_path)
    if data:
        mbr_id = mbr_id or data.get("mbrId") or data.get("mbr_id") or data.get("id")
        password = password or data.get("pw") or data.get("password")
    return mbr_id, password


_AUTO_LOGIN_ENABLED = True
_AUTO_LOGIN_ALLOW_DUP_LOGIN = False


def enable_auto_login(enabled: bool = True, *, allow_dup_login: bool = False):
    global _AUTO_LOGIN_ENABLED, _AUTO_LOGIN_ALLOW_DUP_LOGIN
    _AUTO_LOGIN_ENABLED = bool(enabled)
    _AUTO_LOGIN_ALLOW_DUP_LOGIN = bool(allow_dup_login)


def is_auto_login_enabled() -> bool:
    return _AUTO_LOGIN_ENABLED


def _get_session_file_path():
    """Get the session file path from environment or default location."""
    session_file = os.getenv("KRX_SESSION_FILE")
    if session_file:
        return Path(session_file).expanduser()

    session_dir = os.getenv("KRX_SESSION_DIR")
    if session_dir:
        return Path(session_dir).expanduser() / "session.json"

    return Path("~/.config/krx-session/session.json").expanduser()


def _serialize_session_cookies(session):
    """Serialize session cookies to a dict."""
    try:
        # curl_cffi session
        if hasattr(session, "cookies"):
            cookies = {}
            for cookie in session.cookies:
                cookies[cookie.name] = {
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "secure": cookie.secure,
                    "expires": cookie.expires,
                }
            return cookies
    except Exception:
        pass
    return {}


def _deserialize_session_cookies(session, cookies_dict):
    """Deserialize cookies dict back to session."""
    try:
        if hasattr(session, "cookies"):
            for name, attrs in cookies_dict.items():
                session.cookies.set(
                    name=name,
                    value=attrs.get("value"),
                    domain=attrs.get("domain"),
                    path=attrs.get("path"),
                )
    except Exception:
        pass


def _save_session_to_file(session, mbr_no=None, ttl_minutes=30):
    """Save session to file with file locking."""
    session_file = _get_session_file_path()
    session_file.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    expires_at = now + timedelta(minutes=ttl_minutes)

    session_data = {
        "cookies": _serialize_session_cookies(session),
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "last_used": now.isoformat(),
        "mbr_no": mbr_no,
        "ttl_minutes": ttl_minutes,
    }

    # Write with file locking
    lock_file = session_file.parent / f"{session_file.name}.lock"
    try:
        with open(lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            try:
                with open(session_file, "w", encoding="utf-8") as f:
                    json.dump(session_data, f, indent=2)
            finally:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
    except Exception:
        # Best effort - if locking fails, still try to save
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2)
        except Exception:
            pass


def _load_session_from_file():
    """Load session from file if valid."""
    session_file = _get_session_file_path()
    if not session_file.exists():
        return None

    lock_file = session_file.parent / f"{session_file.name}.lock"

    try:
        # Read with file locking
        with open(lock_file, "w") as lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_SH)
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    session_data = json.load(f)
            finally:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
    except Exception:
        # Best effort - if locking fails, try to read anyway
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)
        except Exception:
            return None

    # Check expiration
    expires_at_str = session_data.get("expires_at")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now() >= expires_at:
                # Session expired
                return None
        except Exception:
            return None

    # Restore session
    try:
        session = _create_curl_session()
        cookies_dict = session_data.get("cookies", {})
        _deserialize_session_cookies(session, cookies_dict)

        # Update last_used timestamp
        session_data["last_used"] = datetime.now().isoformat()
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2)
        except Exception:
            pass

        return session
    except Exception:
        return None


def clear_session_file():
    """Clear the saved session file."""
    session_file = _get_session_file_path()
    if session_file.exists():
        try:
            session_file.unlink()
        except Exception:
            pass


def krx_login(
    mbr_id: str | None = None,
    password: str | None = None,
    *,
    session=None,
    set_global_session: bool = True,
    site: str = "mdc",
    allow_dup_login: bool = False,
):
    mbr_id, password = _resolve_krx_credentials(mbr_id, password)
    if not mbr_id or not password:
        raise PykrxRequestError(
            "KRX login requires credentials. Provide mbr_id/password or set environment variables "
            "KRX_MBR_ID and KRX_PASSWORD. You may also set KRX_CREDENTIALS_FILE or use ~/.config/krx-session/krx_credentials.json"
        )

    if session is None:
        session = _create_curl_session()

    base = "https://data.krx.co.kr"
    login_page = f"{base}/contents/MDC/COMS/client/view/login.jsp?site={site}"
    login_api = f"{base}/contents/MDC/COMS/client/MDCCOMS001D1.cmd"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"{base}/contents/MDC/COMS/client/MDCCOMS001.cmd",
        "Origin": base,
    }

    # Establish cookies/session
    try:
        session.get(login_page, headers=headers, timeout=30)
    except TypeError:
        session.get(login_page, headers=headers)

    payload = {
        "mbrId": mbr_id,
        "pw": password,
        "mbrNm": "",
        "telNo": "",
        "di": "",
        "certType": "",
    }

    try:
        resp = session.post(login_api, headers=headers, data=payload, timeout=30)
    except TypeError:
        resp = session.post(login_api, headers=headers, data=payload)

    if getattr(resp, "status_code", None) != 200:
        snippet = (getattr(resp, "text", "") or "")[:200]
        raise PykrxRequestError(
            f"KRX login failed with status={resp.status_code}. Response snippet: {snippet}"
        )

    def _parse_json_response(r):
        try:
            return r.json()
        except Exception:
            txt = getattr(r, "text", "") or ""
            try:
                return json.loads(txt)
            except Exception as e:
                ctype = (r.headers.get("content-type") or "").lower()
                snippet = txt[:200]
                raise PykrxRequestError(
                    f"KRX login response is not JSON (content-type={ctype}). Response snippet: {snippet}"
                ) from e

    data = _parse_json_response(resp)

    # Heuristic failure detection (API uses error codes like CD00x)
    err = (
        data.get("errorCode")
        or data.get("ERROR_CODE")
        or data.get("error_code")
        or data.get("_error_code")
    )
    msg = (
        data.get("_error_message")
        or data.get("error_message")
        or data.get("ERROR_MESSAGE")
    )

    # Some KRX endpoints return success codes in _error_code (e.g. CD001 with message '정상')
    success_codes = {"CD001"}

    if err and err in success_codes:
        err = None

    if err:
        if err == "CD011" and allow_dup_login:
            payload["skipDup"] = "Y"
            try:
                resp2 = session.post(
                    login_api, headers=headers, data=payload, timeout=30
                )
            except TypeError:
                resp2 = session.post(login_api, headers=headers, data=payload)
            data2 = _parse_json_response(resp2)
            err2 = (
                data2.get("errorCode")
                or data2.get("ERROR_CODE")
                or data2.get("error_code")
                or data2.get("_error_code")
            )
            if err2:
                msg2 = (
                    data2.get("_error_message")
                    or data2.get("error_message")
                    or data2.get("ERROR_MESSAGE")
                )
                if msg2:
                    raise PykrxRequestError(
                        f"KRX login failed (errorCode={err2}). {msg2}"
                    )
                snippet2 = str(data2)[:200]
                raise PykrxRequestError(
                    f"KRX login failed (errorCode={err2}). Payload snippet: {snippet2}"
                )
            data = data2
        else:
            if msg:
                raise PykrxRequestError(f"KRX login failed (errorCode={err}). {msg}")
            snippet = str(data)[:200]
            raise PykrxRequestError(
                f"KRX login failed (errorCode={err}). Payload snippet: {snippet}"
            )

    # More strict success check
    mbr_no = data.get("MBR_NO") or data.get("mbrNo")
    if not mbr_no:
        snippet = str(data)[:200]
        raise PykrxRequestError(
            "KRX login did not return expected success fields (MBR_NO). "
            f"Payload snippet: {snippet}"
        )

    if set_global_session:
        set_http_session(session)

    # Save session to file for cross-process sharing
    _save_session_to_file(session, mbr_no=mbr_no, ttl_minutes=30)

    return session, data


def krx_extend_session(*, session=None):
    """Extend KRX Data Marketplace session.

    Notes:
        This call requires a logged-in session cookie.
    """
    if session is None:
        from pykrx.website.comm.webio import get_http_session

        session = get_http_session()

    if session is None:
        raise PykrxRequestError(
            "No HTTP session is set. Call krx_login() first or pass session explicitly."
        )

    base = "https://data.krx.co.kr"
    url = f"{base}/contents/MDC/MAIN/main/extendSession.cmd"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"{base}/contents/MDC/MAIN/main/index.cmd",
        "Origin": base,
    }

    try:
        resp = session.post(url, headers=headers, timeout=30)
    except TypeError:
        resp = session.post(url, headers=headers)

    if getattr(resp, "status_code", None) != 200:
        snippet = (getattr(resp, "text", "") or "")[:200]
        raise PykrxRequestError(
            f"KRX extendSession failed with status={resp.status_code}. Snippet: {snippet}"
        )

    ctype = (resp.headers.get("content-type") or "").lower()
    if "json" not in ctype:
        # Some environments might respond with HTML; treat as failure
        snippet = (getattr(resp, "text", "") or "")[:200]
        raise PykrxRequestError(
            f"KRX extendSession response is not JSON (content-type={ctype}). Snippet: {snippet}"
        )

    data = resp.json()
    err = data.get("errorCode") or data.get("ERROR_CODE") or data.get("error_code")
    if err:
        raise PykrxRequestError(f"KRX extendSession failed (errorCode={err}).")
    return data


class KrxSessionKeepAlive:
    def __init__(self, *, session=None, interval_seconds: int = 25 * 60):
        self._session = session
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return

        def _run():
            while not self._stop.wait(self._interval):
                try:
                    krx_extend_session(session=self._session)
                except Exception:
                    # keepalive must be best-effort
                    continue

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)


def krx_start_keepalive(
    *, session=None, interval_seconds: int = 25 * 60
) -> KrxSessionKeepAlive:
    ka = KrxSessionKeepAlive(session=session, interval_seconds=interval_seconds)
    ka.start()
    return ka


class KrxWebIo(Post):
    def _raise_for_invalid_response(self, resp):
        if getattr(resp, "status_code", None) != 200:
            snippet = (resp.text or "")[:200]
            raise PykrxRequestError(
                f"KRX request failed with status={resp.status_code}. "
                f"KRX may require login or may be blocking automated access. "
                f"Response snippet: {snippet}"
            )

    def _parse_json(self, resp):
        try:
            return resp.json()
        except Exception:
            txt = getattr(resp, "text", "") or ""
            try:
                return json.loads(txt)
            except Exception as e:
                ctype = (resp.headers.get("content-type") or "").lower()
                snippet = txt[:200]
                raise PykrxRequestError(
                    f"KRX response is not JSON (content-type={ctype}). "
                    f"KRX may require login or may be blocking automated access. "
                    f"Response snippet: {snippet}"
                ) from e

    def _raise_for_error_payload(self, data):
        if not isinstance(data, dict):
            return

        # KRX는 로그인 필요/오류 상황에서도 200 + JSON으로 내려줄 수 있음
        # (예: errorCode, ERROR_CODE, message 등)
        err = (
            data.get("errorCode")
            or data.get("ERROR_CODE")
            or data.get("error_code")
            or data.get("errCode")
            or data.get("ERR_CD")
        )
        if err:
            raise PykrxRequestError(f"KRX returned an error payload (errorCode={err}).")

        has_outblock = any(str(k).startswith("OutBlock") for k in data.keys())
        has_block = any(str(k).startswith("block") for k in data.keys())

        # getJsonData.cmd의 정상 응답은 보통 output 키를 포함한다.
        # 로그인 만료/차단 시 200 + JSON이더라도 output이 없거나 비정상인 경우가 있어 이를 예외로 승격.
        # 다만 일부 finder 계열 API는 block1/block* 형태로 응답한다.
        if "output" not in data and not has_outblock and not has_block:
            snippet = str(data)[:200]
            raise PykrxRequestError(
                "KRX returned an unexpected payload without 'output'. "
                f"KRX may require login or may be blocking automated access. Payload snippet: {snippet}"
            )

        if "output" not in data and (has_outblock or has_block):
            return

        output = data.get("output")
        if output is None:
            raise PykrxRequestError(
                "KRX returned an unexpected payload with null 'output'. "
                "KRX may require login or may be blocking automated access."
            )

        if isinstance(output, str) and (
            "logout" in output.lower() or "login" in output.lower()
        ):
            raise PykrxRequestError(
                "KRX returned an authentication-related payload. "
                "KRX may require login or may be blocking automated access."
            )

        if not isinstance(output, list):
            snippet = str(output)[:200]
            raise PykrxRequestError(
                "KRX returned an unexpected payload: 'output' is not a list. "
                f"Payload snippet: {snippet}"
            )

    def read(self, **params):
        # Try to load session from file if not in memory
        if get_http_session() is None:
            file_session = _load_session_from_file()
            if file_session is not None:
                set_http_session(file_session)

        def _do_request():
            params.update(bld=self.bld)
            if "strtDd" in params and "endDd" in params:
                dt_s = pd.to_datetime(params["strtDd"])
                dt_e = pd.to_datetime(params["endDd"])
                delta = pd.to_timedelta("730 days")

                result = None
                while dt_s + delta < dt_e:
                    dt_tmp = dt_s + delta
                    params["strtDd"] = dt_s.strftime("%Y%m%d")
                    params["endDd"] = dt_tmp.strftime("%Y%m%d")
                    dt_s += delta + pd.to_timedelta("1 days")
                    resp = Post.read(self, **params)
                    self._raise_for_invalid_response(resp)
                    data = self._parse_json(resp)
                    self._raise_for_error_payload(data)
                    if result is None:
                        result = data
                    else:
                        result["output"] += data["output"]

                    # 초당 2년 데이터 조회
                    time.sleep(1)

                if dt_s <= dt_e:
                    params["strtDd"] = dt_s.strftime("%Y%m%d")
                    params["endDd"] = dt_e.strftime("%Y%m%d")
                    resp = Post.read(self, **params)
                    self._raise_for_invalid_response(resp)

                    data = self._parse_json(resp)
                    self._raise_for_error_payload(data)

                    if result is not None:
                        result["output"] += data["output"]
                    else:
                        result = data
                return result
            else:
                resp = Post.read(self, **params)
                self._raise_for_invalid_response(resp)
                data = self._parse_json(resp)
                self._raise_for_error_payload(data)
                return data

        try:
            return _do_request()
        except PykrxRequestError:
            if not is_auto_login_enabled():
                raise

            # Avoid infinite retry per instance
            if getattr(self, "_auto_login_retried", False):
                raise

            try:
                krx_login(
                    set_global_session=True, allow_dup_login=_AUTO_LOGIN_ALLOW_DUP_LOGIN
                )
            except Exception:
                # If login itself fails, surface original error
                raise

            setattr(self, "_auto_login_retried", True)
            return _do_request()

    @property
    def url(self):
        return "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"

    @property
    @abstractmethod
    def bld(self):
        return NotImplementedError

    @bld.setter
    def bld(self, val):
        pass

    @property
    @abstractmethod
    def fetch(self, **params):
        return NotImplementedError
