# Changelog

## Unreleased

- KRX 데이터 조회 시 서버가 403/비JSON(HTML) 응답을 반환하는 경우 `KeyError: '지수명'`로 터지던 문제를 개선했습니다.
- KRX 응답이 정상 JSON이 아니면 `PykrxRequestError`를 발생시켜 원인(로그인 필요/차단 가능성)을 명확히 알리도록 변경했습니다.
- KRX가 세션 만료 시 plain text `LOGOUT`을 반환하는 경우, 세션 파일/전역 세션을 삭제하고 auto-login 재시도가 동작하도록 개선했습니다.
- KRX가 일부 API에서 `output` 대신 `OutBlock_*` 형태의 JSON을 반환하더라도 정상 응답으로 처리하도록 개선했습니다.
- KRX가 일부 finder 계열 API에서 `output` 대신 `block1`/`block*` 형태의 JSON을 반환하더라도 정상 응답으로 처리하도록 개선했습니다.
- KRX 요청 URL 및 Referer를 `https://data.krx.co.kr`로 변경했습니다.
- 지수/리스팅 관련 API에 `fallback=True` 옵션을 추가/확장했습니다. KRX 접근이 불가한 환경에서 대표 지수(코스피/코스닥) 일부는 최소 정보로 제공되며, 나머지는 빈 결과(DataFrame/[])로 degrade될 수 있습니다.
- 지수 관련 API들의 `fallback` 기본값을 `True`로 변경했습니다. (강제로 예외가 필요하면 `fallback=False`를 명시하세요.)
- `pyproject.toml`에 `setuptools` 기반 빌드 설정을 추가하고(PEP 621), wheel/sdist 빌드가 가능하도록 패키징 메타데이터/패키지 데이터(`*.ttf`) 설정을 정리했습니다.
- 빌드 시 패키지를 import하지 않도록 `setup.py`를 수정하여(버전은 `pyproject.toml`에서 로드), 빌드 격리 환경에서의 의존성 문제를 완화했습니다.
- `curl-cffi` 기반 KRX 로그인(`krx_login`)을 추가했습니다. 로그인된 세션을 전역 HTTP 레이어에 주입하여 KRX 요청이 인증 세션으로 수행될 수 있습니다.
- `krx.login()` 별칭을 추가하고, `extend_session`/`start_keepalive`로 로그인 세션 연장을 지원합니다.
- KRX 로그인 성공 판별을 강화하여(`MBR_NO` 필수), 애매한 200/JSON 응답을 성공으로 오인하지 않도록 개선했습니다.
- 자격증명은 환경변수 외에도 `KRX_CREDENTIALS_FILE` 또는 `~/.config/krx-session/krx_credentials.json`에서 자동 로드할 수 있습니다.
- **[Breaking Change]** 자격증명 파일 기본 위치가 `~/.config/pykrx/krx_credentials.json`에서 `~/.config/krx-session/krx_credentials.json`으로 변경되었습니다.
- 로그인 세션이 파일(`~/.config/krx-session/session.json`)에 자동 저장되어 **프로세스 간 세션 공유**가 가능합니다.
- 여러 Python 스크립트나 패키지(pykrx, FinanceDataReader 등)가 동일한 KRX 세션을 공유하여 중복 로그인을 방지합니다.
- 세션 파일 위치는 `KRX_SESSION_FILE` 또는 `KRX_SESSION_DIR` 환경변수로 커스터마이징 가능합니다.
- `clear_session_file()` 함수를 추가하여 저장된 세션을 수동으로 삭제할 수 있습니다.
- KRX 요청 실패 시 1회 자동 로그인 후 재시도하는 기능(`enable_auto_login_on_failure`)을 추가했습니다. (기본값: 활성화)
- `stock.krx_login()` / `stock.enable_auto_login_on_failure()` wrapper를 추가했습니다.
- 세션 파일 락을 POSIX 전용 `fcntl`에서 `portalocker`로 교체하여 Windows에서도 세션 파일 락이 동작하도록 개선했습니다.
