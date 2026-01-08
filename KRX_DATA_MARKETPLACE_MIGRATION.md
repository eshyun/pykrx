# KRX 회원제 변경 대응 (KRX Data Marketplace Migration)

[[단독] 한국거래소 정보데이터시스템, 회원제 '데이터 마켓플레이스'로 변경 - 글로벌이코노믹](https://www.g-enews.com/view.php?ud=202512070927435241edf69f862c_1)

한국거래소는 2025-12-27부터 기존 정보데이터시스템이 회원 가입해야 이용할 수 있는 **KRX Data Marketplace**로 전면 개편했습니다.

이 변경으로 인해 `data.krx.co.kr` 기반 스크레이핑(예: `getJsonData.cmd`, `executeForResourceBundle.cmd` 등)이 비로그인 상태에서 **403/HTML(비JSON) 응답/세션 만료** 등의 형태로 실패하여, `pykrx`의 일부 API가 동작하지 않는 문제가 발생할 수 있습니다.

관련 이슈:

- https://github.com/sharebook-kr/pykrx/issues/244

본 저장소는 이를 해결하기 위해 `pykrx`를 fork하여 **KRX 로그인 기능(세션/쿠키 확보) 및 자동 로그인(기본 ON)**을 추가했습니다.

## 수정 내용

### 1) KRX 로그인 기능 추가 (`curl-cffi` 기반)

#### 1.1. 목적

KRX Data Marketplace가 회원제 로그인 기반으로 바뀌면서, 기존처럼 단순 `requests.get/post` 요청만으로는 KRX JSON API 호출이 실패하는 경우가 증가했습니다.

따라서 브라우저와 유사한 세션을 구성하여 로그인 후 쿠키를 확보하고, 동일 세션으로 KRX API를 호출하도록 개선했습니다.

#### 1.2. 구현 개요

- 로그인은 KRX Data Marketplace 웹 로그인 API를 호출합니다.
  - 로그인 페이지(세션/쿠키 초기화):
    - `GET https://data.krx.co.kr/contents/MDC/COMS/client/view/login.jsp?site=mdc`
  - 로그인 API(자격증명 제출):
    - `POST https://data.krx.co.kr/contents/MDC/COMS/client/MDCCOMS001D1.cmd`
    - payload(개념): `mbrId`, `pw` 등
- 일반 `requests` 세션으로는 차단되는 환경이 있어, `curl-cffi`의 `requests.Session(impersonate="chrome")`로 브라우저 유사 세션을 생성합니다.
- 로그인 성공 판별을 강화했습니다.
  - HTTP 200 + JSON 응답이라도 실패 케이스가 있어, `MBR_NO` 등의 필드가 없으면 실패로 처리합니다.
  - 에러코드(`CD011` 등) 처리(중복 로그인 케이스 대응) 포함

#### 1.3. 전역 세션 주입

로그인에 성공하면, 생성된 세션을 `pykrx.website.comm.webio`의 전역 세션 레이어에 주입합니다.

- 이후 `pykrx` 내부의 KRX 호출(`Get`/`Post`)이 동일 세션을 사용하여, 쿠키/세션이 유지됩니다.

### 2) 세션 연장(선택)

KRX Data Marketplace 세션이 만료될 수 있어, 세션 연장 helper를 제공합니다.

- `extendSession` 호출:
  - `POST https://data.krx.co.kr/contents/MDC/MAIN/main/extendSession.cmd`
- best-effort keepalive:
  - 주기적으로 `extendSession`을 호출하는 백그라운드 스레드

### 3) 자격증명(credential) 로딩 규칙

자격증명은 코드에 하드코딩하지 않고, 아래 순서로 로드합니다.

1. 함수 인자: `mbr_id`, `password`
2. 환경변수:
   - `KRX_MBR_ID` 또는 `KRX_ID`
   - `KRX_PASSWORD` 또는 `KRX_PW`
3. 자격증명 파일:
   - `KRX_CREDENTIALS_FILE`
   - 기본값: `~/.config/pykrx/krx_credentials.json`

자격증명 파일 포맷 예시:

```json
{
  "mbrId": "YOUR_ID",
  "pw": "YOUR_PASSWORD"
}
```

### 4) 자동 로그인(auto-login) 기본값: ON

- KRX 접근 실패 시, 1회 자동 로그인 후 재시도하는 기능을 제공합니다.
- 본 fork에서는 해당 기능을 **기본 활성화(ON)**로 변경했습니다.
- 단, 자격증명이 없는 경우에는 best-effort로 로그인 시도를 생략합니다.

## 사용법

### 1) 의존성 설치

KRX 로그인에는 `curl-cffi`가 필요합니다.

```bash
pip install curl-cffi
```

(프로젝트 설정에 따라 optional extra로 제공될 수 있습니다.)

### 2) 로그인

```python
from pykrx.website import krx

# (권장) 명시적으로 먼저 로그인
krx.login()
```

### 3) 자동 로그인 설정(기본 ON)

```python
from pykrx.website import krx

# 기본값은 ON
# krx.enable_auto_login_on_failure(True)

# 필요 시 OFF
# krx.enable_auto_login_on_failure(False)
```

### 4) `stock` 레벨 wrapper

```python
from pykrx import stock

stock.krx_login()
# 기본값은 ON
# stock.enable_auto_login_on_failure(False)
```

## 참고

- KRX 서버 정책/차단 로직은 외부 환경 요인에 따라 변할 수 있으며, 로그인/세션이 있어도 특정 환경에서는 응답이 비정상(HTML 등)일 수 있습니다.
- 이 경우 `PykrxRequestError` 등의 예외 메시지에서 원인을 확인할 수 있도록, 응답 타입/스니펫 기반 에러 처리를 강화했습니다.
