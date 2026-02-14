# 배달앱 리뷰 통합 + 템플릿 답글 자동게시

FastAPI + PostgreSQL + Celery + Redis + Next.js 기반 1인 운영용 웹앱 샘플입니다.

## 포함 기능
- 매장 CRUD
- 플랫폼 연결 CRUD(ID/비밀번호 입력값 서버 암호화 저장)
- 커넥터 인터페이스 + Mock 커넥터(리뷰 조회/답글 랜덤 성공/실패)
- 리뷰 동기화(upsert)
- 리뷰 화면(기간 필터 UI, 빠른 버튼, 탭/카운트, 체크박스/전체선택)
- 템플릿 CRUD + 변수 치환 `{매장명} {플랫폼} {고객명} {메뉴}`
- 벌크 자동게시 생성(Reply + ReplyJob)
- 워커가 자동 게시 처리(PENDING -> POSTED/FAILED)

## 프로젝트 구조

- `backend/app/models`: SQLAlchemy 모델
- `backend/alembic`: DB 마이그레이션
- `backend/app/api`: FastAPI 라우트
- `backend/app/workers`: Celery worker/beat task
- `frontend/app/page.tsx`: 통합 관리 UI

## 실행
```bash
cd delivery_review_app
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend Swagger: http://localhost:8000/docs

## RPA/브라우저 자동화(반자동) 확장 포인트
- `app/connectors/base.py` 인터페이스를 유지하고 플랫폼별 구현을 추가하세요.
- 로그인 캡차/2FA는 Playwright/Selenium을 별도 서비스에서 반자동 처리 후 토큰을 `platform_connections`에 저장하는 방식으로 확장합니다.
- 현재는 `MockConnector`가 랜덤 성공/실패를 시뮬레이션합니다.

## TODO
- 실제 플랫폼 API/웹 자동화 연동
- 인증/권한
- ReplyJob 재시도 백오프/데드레터 큐
