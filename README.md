# KFin Insurance Desk

## 논문 파일럿 최신 결과 — 2026-09-08

[실험·코드 안내](research/PILOT_RELEASE_20260908.md) ·
[검증된 결과](research/pilot_results_20260908.md) ·
[논문 PDF (Drive, 소유자 전용)](https://drive.google.com/file/d/1jXLxbYZPrEGSxQ0fMcci2PCa3UtYTD_p/view?usp=drivesdk) ·
[코드·문서 ZIP (Drive, 소유자 전용)](https://drive.google.com/file/d/1xql50eofqCSyGpCfAaYlXHSEkLBOk_CN/view?usp=drivesdk)

1,000개씩 총 3,000개 원본 식별 목록은 유지합니다. 12문서 모델 파일럿과
1,000개 대출의 오프라인 구성요소 실험을 구분합니다. 준비형 검색은 동일
참조 풀의 첫 검색 묶음 시간을 54.27% 줄였으며, 13,572쌍에서 결과 불일치는
0건입니다. 법률 정확도나 3,000문서 본실험 완료를 뜻하지 않습니다.
원래 표·그림을 보존한 논문과 검증 기록을 포함하고, 원문·모델 대화·비밀키는
공개 저장소에 넣지 않았습니다. 아래는 기존 앱 안내입니다.

CODEF 보험계약 조회 결과를 읽기 쉬운 대시보드로 정리하는 Next.js 애플리케이션입니다.

## 배포본

- Production: <https://insurance-eta-gray.vercel.app>
- 제출용 합성 데이터 데모는 로그인 없이 공개됩니다.
- Railway PostgreSQL 스키마는 배포되어 있지만, 유출된 CODEF 자격증명은 운영 환경에 등록하지 않았습니다.
- 실데이터 API는 자격증명을 안전하게 교체하기 전까지 `503`으로 닫혀 있으며 브라우저 로그인 창을 띄우지 않습니다.

## 로컬 실행

```bash
pnpm install
pnpm env:setup
pnpm dev
```

`.env.local`에 CODEF 샌드박스 자격증명과 PostgreSQL 연결 정보를 설정합니다. 실제 비밀값은 저장소에 커밋하지 않습니다.

## 검증

```bash
pnpm test
pnpm typecheck
pnpm build
```

## 배포

- 앱: Vercel
- 데이터베이스: Railway PostgreSQL
- Vercel의 `DATABASE_URL`에는 Railway 외부 TCP 연결 URL을 사용합니다.
- 최초 배포 전 `pnpm db:migrate`를 한 번 실행합니다.
- 공개 제출본에는 `INSURANCE_DEMO_ONLY=true`를 설정합니다.
- 실데이터 API를 별도로 운영할 때만 CODEF 자격증명과 API 접근용 `INSURANCE_PREVIEW_USER`, `INSURANCE_PREVIEW_PASSWORD`를 설정합니다.

자세한 제품 범위는 [PRODUCT.md](./PRODUCT.md)를 참고하세요.
