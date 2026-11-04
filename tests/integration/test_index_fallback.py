import unittest
from unittest.mock import patch

import pandas as pd

from pykrx import stock
from pykrx.website.comm.util import PykrxRequestError


class IndexFallbackTests(unittest.TestCase):
    def test_index_name_raises_meaningful_error_when_krx_blocks(self):
        from pykrx.website.comm.webio import set_http_session
        from pykrx.website.krx.market.ticker import IndexTicker

        set_http_session(None)
        IndexTicker._instance = None
        with patch(
            "pykrx.website.krx.market.core.전체지수기본정보.fetch",
            side_effect=PykrxRequestError("blocked"),
        ):
            with self.assertRaises(PykrxRequestError):
                stock.get_index_ticker_name("1001", fallback=False)

    def test_index_fallback_name_when_krx_blocks(self):
        from pykrx.website.comm.webio import set_http_session
        from pykrx.website.krx.market.ticker import IndexTicker

        set_http_session(None)
        IndexTicker._instance = None
        with patch(
            "pykrx.website.krx.market.core.전체지수기본정보.fetch",
            side_effect=PykrxRequestError("blocked"),
        ):
            self.assertEqual(stock.get_index_ticker_name("1001", fallback=True), "코스피")

    def test_index_fallback_ticker_list_when_krx_blocks(self):
        from pykrx.website.comm.webio import set_http_session
        from pykrx.website.krx.market.ticker import IndexTicker

        set_http_session(None)
        IndexTicker._instance = None
        with patch(
            "pykrx.website.krx.market.core.전체지수기본정보.fetch",
            side_effect=PykrxRequestError("blocked"),
        ):
            self.assertEqual(
                stock.get_index_ticker_list("20210118", "KOSPI", fallback=True), ["1001"]
            )

    def test_index_fallback_listing_date_when_krx_blocks(self):
        with patch(
            "pykrx.website.krx.market.core.전체지수기본정보.fetch",
            side_effect=PykrxRequestError("blocked"),
        ):
            df = stock.get_index_listing_date("KOSPI", fallback=True)
            self.assertIsInstance(df, pd.DataFrame)
            self.assertFalse(df.empty)

    def test_index_fallback_price_change_when_krx_blocks(self):
        xml = """<?xml version='1.0' encoding='utf-8'?>
<protocol>
  <chartdata>
    <item data='20210104|100.0|110.0|90.0|105.0|1234'/>
    <item data='20210105|105.0|115.0|95.0|110.0|2345'/>
  </chartdata>
</protocol>
"""

        with patch(
            "pykrx.website.krx.market.core.개별지수시세.fetch",
            side_effect=PykrxRequestError("blocked"),
        ):
            with patch("pykrx.website.naver.core.Sise.fetch", return_value=xml):
                with patch(
                    "pykrx.website.krx.get_nearest_business_day_in_a_week",
                    side_effect=["20210104", "20210129"],
                ):
                    df = stock.get_index_price_change_by_ticker(
                        "20210101", "20210130", fallback=True
                    )
                    self.assertIsInstance(df, pd.DataFrame)
                    self.assertFalse(df.empty)

    def test_index_fallback_ohlcv_by_date_when_krx_blocks(self):
        xml = """<?xml version='1.0' encoding='utf-8'?>
<protocol>
  <chartdata>
    <item data='20210104|100.0|110.0|90.0|105.0|1234'/>
    <item data='20210105|105.0|115.0|95.0|110.0|2345'/>
  </chartdata>
</protocol>
"""

        with patch(
            "pykrx.website.krx.market.core.개별지수시세.fetch",
            side_effect=PykrxRequestError("blocked"),
        ):
            with patch("pykrx.website.naver.core.Sise.fetch", return_value=xml):
                df = stock.get_index_ohlcv_by_date(
                    "20210101", "20210130", "1001", fallback=True
                )
                self.assertIsInstance(df, pd.DataFrame)
                self.assertFalse(df.empty)

    def test_index_fallback_fundamental_by_date_when_krx_blocks(self):
        xml = """<?xml version='1.0' encoding='utf-8'?>
<protocol>
  <chartdata>
    <item data='20210104|100.0|110.0|90.0|105.0|1234'/>
    <item data='20210105|105.0|115.0|95.0|110.0|2345'/>
  </chartdata>
</protocol>
"""

        with patch(
            "pykrx.website.krx.market.core.개별지수시세.fetch",
            side_effect=PykrxRequestError("blocked"),
        ):
            with patch("pykrx.website.naver.core.Sise.fetch", return_value=xml):
                df = stock.get_index_fundamental_by_date(
                    "20210101", "20210130", "1001", fallback=True
                )
                self.assertIsInstance(df, pd.DataFrame)
                self.assertFalse(df.empty)

    def test_index_fallback_portfolio_deposit_file_when_krx_blocks(self):
        from pykrx.website.comm.webio import set_http_session

        set_http_session(None)
        with patch(
            "pykrx.website.krx.market.core.지수구성종목.fetch",
            side_effect=PykrxRequestError("blocked"),
        ):
            pdf = stock.get_index_portfolio_deposit_file(
                "1001", "20210129", fallback=True
            )
            self.assertIsInstance(pdf, list)
            self.assertEqual(len(pdf), 0)
