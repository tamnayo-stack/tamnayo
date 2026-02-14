# 리뷰 답글 반자동 RPA (Playwright + Python)

배달의민족 / 쿠팡이츠 / 요기요 / 땡겨요 / 배달특급 사장님 포털의 리뷰 페이지에서,
조건에 맞는 리뷰만 골라 **댓글 작성 → 텍스트 입력 → 등록** 단계를 자동화합니다.

> ⚠️ 본 프로젝트는 로그인/2FA/캡차 우회를 하지 않습니다. 해당 화면이 나오면 사용자가 직접 처리해야 합니다.

## 1) 설치

```bash
cd web_project/review_rpa
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install
```

## 2) 최초 1회 로그인 후 storage_state 저장

각 플랫폼별 `config.yaml`의 `storage_state` 경로를 사용합니다.
기본 구현은 `run.py` 실행 시 기존 세션을 읽고, 종료 시 다시 저장합니다.

### 권장 절차
1. `config.yaml`에서 테스트할 플랫폼 1개만 `enabled: true`로 둡니다.
2. `python run.py` 실행(Headed 모드).
3. 로그인/2FA/캡차가 뜨면 브라우저에서 직접 완료합니다.
4. 실행 종료 후 `storage/*.json`에 세션이 저장됩니다.
5. 이후 실행부터는 저장된 세션을 재사용합니다(만료 시 다시 로그인).

## 3) 실행 방법

> 루트(`/workspace/tamnayo`)에서 실행할 때는 `python web_project/review_rpa/run.py --mode list` 형태로 실행해도 됩니다.


### (A) 답글 등록 실행 (2주마다 수동 실행)

```bash
python run.py --mode reply
```

### (B) 조회만 실행 (답글 가능한 리뷰 목록/내용 출력)

```bash
python run.py --mode list
```

기본 규칙(`config.yaml`):
- `MIN_AGE_DAYS: 13`
- `MAX_AGE_DAYS: 28`

즉 실행 시점 기준, 작성일이 13~28일 전인 리뷰만 대상입니다.
오늘 작성 리뷰는 자동 제외됩니다.

`--mode list`에서는 플랫폼별로 "현재 답글 가능한 리뷰"의 review_id/작성일/리뷰내용을 출력하고, 등록은 하지 않습니다.

## 프로젝트 구조

```text
run.py
config.py
config.yaml
replies.txt
storage/
  history.py
connectors/
  unified.py
utils/
  date_parse.py
  ui.py
logs/
  run_YYYYMMDD.log
```

## 커스터마이징 포인트

- `replies.txt`: 사용할 답글 문구(생성하지 않음)
- `connectors/unified.py`:
  - TODO에 실제 DOM 기반 리뷰 카드 파싱 로직(리뷰ID/날짜/답글여부) 구현
  - role 기반 선택자(`get_by_role`, `get_by_text`) 우선 사용

## 중복 방지

`storage/review_history.db`에 `(platform, review_id)`를 저장해,
같은 리뷰에 중복으로 댓글을 달지 않도록 합니다.

## 로그

실행 로그는 `logs/run_YYYYMMDD.log`에 기록됩니다.
