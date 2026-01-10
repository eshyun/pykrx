import unittest
from unittest.mock import MagicMock, patch

from pykrx.website.krx.krxio import KrxWebIo, enable_auto_login
from pykrx.website.comm.util import PykrxRequestError


class _DummyIo(KrxWebIo):
    @property
    def bld(self):
        return "dummy"

    def fetch(self, **params):
        return self.read(**params)


class AutoLoginOnFailureTest(unittest.TestCase):
    def test_auto_login_retries_once(self):
        io = _DummyIo()

        # Make the HTTP call always return a 200 response.
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "text/html"}
        resp.text = "{}"

        # First parse returns {}, which triggers PykrxRequestError due to missing 'output'
        # Second parse returns a valid payload
        io._parse_json = MagicMock(side_effect=[{}, {"output": []}])

        with patch("pykrx.website.comm.webio.Post.read", return_value=resp):
            with patch("pykrx.website.krx.krxio.krx_login", return_value=(None, {"MBR_NO": "1"})) as mlogin:
                enable_auto_login(True)
                out = io.read()
                self.assertEqual(out, {"output": []})
                self.assertEqual(mlogin.call_count, 1)

    def test_outblock_payload_is_treated_as_valid(self):
        io = _DummyIo()

        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "application/json"}
        resp.text = "{}"

        io._parse_json = MagicMock(return_value={"OutBlock_1": []})

        with patch("pykrx.website.comm.webio.Post.read", return_value=resp):
            with patch("pykrx.website.krx.krxio.krx_login") as mlogin:
                enable_auto_login(True)
                out = io.read()
                self.assertEqual(out, {"OutBlock_1": []})
                self.assertEqual(mlogin.call_count, 0)

    def test_block_payload_is_treated_as_valid(self):
        io = _DummyIo()

        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "application/json"}
        resp.text = "{}"

        io._parse_json = MagicMock(return_value={"block1": []})

        with patch("pykrx.website.comm.webio.Post.read", return_value=resp):
            with patch("pykrx.website.krx.krxio.krx_login") as mlogin:
                enable_auto_login(True)
                out = io.read()
                self.assertEqual(out, {"block1": []})
                self.assertEqual(mlogin.call_count, 0)

    def test_no_auto_login_when_disabled(self):
        io = _DummyIo()
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "text/html"}
        resp.text = "{}"

        io._parse_json = MagicMock(return_value={})

        with patch("pykrx.website.comm.webio.Post.read", return_value=resp):
            enable_auto_login(False)
            with self.assertRaises(PykrxRequestError):
                io.read()


if __name__ == "__main__":
    unittest.main()
