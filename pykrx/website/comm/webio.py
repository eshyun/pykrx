import requests
from abc import abstractmethod


_HTTP_SESSION = None


def set_http_session(session):
    global _HTTP_SESSION
    _HTTP_SESSION = session


def get_http_session():
    return _HTTP_SESSION


class Get:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0", 
            "Referer": "https://data.krx.co.kr/"
        }

    def read(self, **params):
        session = get_http_session()
        if session is None:
            resp = requests.get(self.url, headers=self.headers, params=params)
        else:
            resp = session.get(self.url, headers=self.headers, params=params)
        return resp

    @property
    @abstractmethod
    def url(self):
        return NotImplementedError


class Post:
    def __init__(self, headers=None):
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://data.krx.co.kr/"
        }
        if headers is not None:
            self.headers.update(headers)

    def read(self, **params):
        session = get_http_session()
        if session is None:
            resp = requests.post(self.url, headers=self.headers, data=params)
        else:
            resp = session.post(self.url, headers=self.headers, data=params)
        return resp

    @property
    @abstractmethod
    def url(self):
        return NotImplementedError
