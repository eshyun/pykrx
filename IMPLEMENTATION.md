# Implementation Details

## 배경

- 2025-12 말 전후로 KRX Market Data System 응답 정책이 변경되어, 기존의 비로그인 스크래핑 요청이 403/HTML로 차단될 수 있습니다.
- 기존 pykrx 구현은 KRX 파싱 실패를 `dataframe_empty_handler`에서 빈 DataFrame으로 숨기는 구조였고, 그 결과 상위에서 `'지수명'` 같은 컬럼 접근 시 `KeyError`로 표면화되었습니다.

## 변경 사항

### 1) 명확한 예외 노출

- `pykrx.website.comm.util.PykrxRequestError`를 추가했습니다.
- KRX 응답이
  - HTTP status != 200 이거나
  - Content-Type이 JSON이 아닌 경우
  `PykrxRequestError`를 발생시켜 호출자가 즉시 원인을 알 수 있게 했습니다.

- KRX가 일부 API에서 `output` 대신 `OutBlock_*` 형태의 JSON을 반환하는 경우가 있어,
  `KrxWebIo`의 페이로드 검증 로직이 이를 오류로 오인하지 않도록 정상 응답으로 처리합니다.

- 또한 KRX의 finder 계열 API(예: 상장종목 검색)는 `output` 대신 `block1`/`block*` 키로 데이터를 반환합니다.
  따라서 `KrxWebIo._raise_for_error_payload()`는 `output`이 없더라도 `block*` 또는 `OutBlock*` 형태면
  정상 응답으로 간주하도록 확장했습니다.

### 2) HTTPS 적용

- KRX 요청 URL을 `https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd`로 변경했습니다.
- 기본 Referer도 `https://data.krx.co.kr/`로 변경했습니다.

### 3) 테스트 전략

- KRX 네트워크 의존 테스트는, KRX가 차단하는 환경에서는 `skip`되도록 했습니다.
- 403 차단 케이스는 `unittest.mock`으로 `requests.post`를 모킹하여 안정적으로 `PykrxRequestError` 발생을 검증합니다.

### 4) 지수/리스팅 API fallback 옵션

- 지수/리스팅 관련 API에 `fallback` 옵션을 추가했습니다.
- 지수 관련 API들의 기본값은 `fallback=True`입니다.
- 예외가 반드시 필요하면 `fallback=False`를 명시하세요. 이 경우 KRX 응답 실패 시 `PykrxRequestError`를 그대로 발생시킵니다.
- `fallback=True`에서는 KRX 차단 환경에서 일부 API가 예외 대신 빈 결과(`DataFrame()`/`[]`)로 degrade되며,
  대표 지수(코스피/코스닥) 일부는 정적 매핑으로 최소 정보(티커/이름/리스팅 기본값)를 제공합니다.

### 5) KRX 로그인(curl-cffi) 세션 주입

- KRX Data Marketplace 로그인은 `/contents/MDC/COMS/client/MDCCOMS001D1.cmd` 엔드포인트로 수행됩니다.
- `curl-cffi`의 `requests.Session()`을 사용하여 로그인 후 쿠키를 유지하고, 해당 session을 `pykrx.website.comm.webio`에 전역 주입합니다.
- 자격증명은 코드에 하드코딩하지 않고, 인자(`mbr_id`, `password`) 또는 환경변수(`KRX_MBR_ID`, `KRX_PASSWORD`)로 전달합니다.
- 자격증명 파일(`KRX_CREDENTIALS_FILE` 또는 `~/.config/pykrx/krx_credentials.json`)을 통해 자동 로드를 지원합니다.
- 세션 만료를 방지하기 위해 `/contents/MDC/MAIN/main/extendSession.cmd` 호출 helper 및 best-effort keepalive를 제공합니다.
