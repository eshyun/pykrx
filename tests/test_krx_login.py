import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import requests

from pykrx.website.comm.util import PykrxRequestError
from pykrx.website.comm.webio import get_http_session, set_http_session
from pykrx.website.krx import krx_login
from pykrx.website.krx.krxio import (
    _load_session_from_file,
    clear_session_file,
    krx_extend_session,
    _save_session_to_file,
)


class KrxLoginTest(unittest.TestCase):
    def setUp(self):
        set_http_session(None)
        clear_session_file()

    def test_krx_login_sets_global_session_on_success(self):
        session = MagicMock()

        # login page GET
        session.get.return_value = MagicMock(
            status_code=200, headers={"content-type": "text/html"}, text=""
        )

        # login POST
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "application/json"}
        resp.json.return_value = {"MBR_NO": "1"}
        resp.text = '{"MBR_NO":"1"}'
        session.post.return_value = resp

        sess, data = krx_login("id", "pw", session=session, set_global_session=True)
        self.assertIs(sess, session)
        self.assertEqual(data["MBR_NO"], "1")
        self.assertIs(get_http_session(), session)

    def test_session_file_lock_and_write(self):
        try:
            import portalocker  # noqa: F401
        except Exception:
            self.skipTest("portalocker is not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["KRX_SESSION_DIR"] = tmpdir
            try:
                session = requests.Session()
                session.cookies.set(
                    name="_test_cookie",
                    value="1",
                    domain="data.krx.co.kr",
                    path="/",
                )

                _save_session_to_file(session, mbr_no="1", ttl_minutes=1)

                session_file = os.path.join(tmpdir, "session.json")
                lock_file = os.path.join(tmpdir, "session.json.lock")
                self.assertTrue(os.path.exists(session_file))
                self.assertTrue(os.path.exists(lock_file))
            finally:
                os.environ.pop("KRX_SESSION_DIR", None)

    def test_krx_login_raises_on_error_code(self):
        session = MagicMock()
        session.get.return_value = MagicMock(
            status_code=200, headers={"content-type": "text/html"}, text=""
        )

        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "application/json"}
        resp.json.return_value = {"errorCode": "CD006"}
        resp.text = '{"errorCode":"CD006"}'
        session.post.return_value = resp

        with self.assertRaises(PykrxRequestError):
            krx_login("id", "pw", session=session, set_global_session=True)

    def test_krx_login_raises_when_mbr_no_missing(self):
        session = MagicMock()
        session.get.return_value = MagicMock(
            status_code=200, headers={"content-type": "text/html"}, text=""
        )

        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "application/json"}
        resp.json.return_value = {"some": "payload"}
        resp.text = '{"some":"payload"}'
        session.post.return_value = resp

        with self.assertRaises(PykrxRequestError):
            krx_login("id", "pw", session=session, set_global_session=False)

    def test_krx_login_parses_json_even_when_content_type_is_html(self):
        session = MagicMock()
        session.get.return_value = MagicMock(
            status_code=200, headers={"content-type": "text/html"}, text=""
        )

        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "text/html; charset=utf-8"}
        resp.text = '{"MBR_NO":"1"}'
        resp.json.side_effect = ValueError("no json")
        session.post.return_value = resp

        sess, data = krx_login("id", "pw", session=session, set_global_session=False)
        self.assertIs(sess, session)
        self.assertEqual(data["MBR_NO"], "1")

    def test_krx_login_treats_cd001_as_success(self):
        session = MagicMock()
        session.get.return_value = MagicMock(
            status_code=200, headers={"content-type": "text/html"}, text=""
        )

        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "text/html; charset=utf-8"}
        resp.text = '{"MBR_NO":"1","_error_code":"CD001","_error_message":"정상"}'
        resp.json.side_effect = ValueError("no json")
        session.post.return_value = resp

        sess, data = krx_login("id", "pw", session=session, set_global_session=False)
        self.assertEqual(data["MBR_NO"], "1")

    def test_krx_login_retries_on_dup_login_when_allowed(self):
        session = MagicMock()
        session.get.return_value = MagicMock(
            status_code=200, headers={"content-type": "text/html"}, text=""
        )

        resp1 = MagicMock()
        resp1.status_code = 200
        resp1.headers = {"content-type": "text/html; charset=utf-8"}
        resp1.text = '{"MBR_NO":"2000017791","_error_code":"CD011","_error_message":"중복 로그인"}'
        resp1.json.side_effect = ValueError("no json")

        resp2 = MagicMock()
        resp2.status_code = 200
        resp2.headers = {"content-type": "application/json"}
        resp2.json.return_value = {"MBR_NO": "2000017791"}
        resp2.text = '{"MBR_NO":"2000017791"}'

        session.post.side_effect = [resp1, resp2]

        sess, data = krx_login(
            "id", "pw", session=session, set_global_session=False, allow_dup_login=True
        )
        self.assertEqual(data["MBR_NO"], "2000017791")

    def test_extend_session_uses_session_and_returns_json(self):
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "application/json"}
        resp.json.return_value = {"ok": True}
        resp.text = '{"ok":true}'
        session.post.return_value = resp

        data = krx_extend_session(session=session)
        self.assertEqual(data["ok"], True)

    @patch("pykrx.website.krx.krxio._save_session_to_file")
    def test_krx_login_saves_session_to_file(self, mock_save):
        session = MagicMock()
        session.get.return_value = MagicMock(
            status_code=200, headers={"content-type": "text/html"}, text=""
        )

        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "application/json"}
        resp.json.return_value = {"MBR_NO": "12345"}
        resp.text = '{"MBR_NO":"12345"}'
        session.post.return_value = resp

        sess, data = krx_login("id", "pw", session=session, set_global_session=False)

        # Verify session was saved
        mock_save.assert_called_once()
        call_args = mock_save.call_args
        self.assertIs(call_args[0][0], session)
        self.assertEqual(call_args[1]["mbr_no"], "12345")


if __name__ == "__main__":
    unittest.main()
