# KFin Insurance Desk

CODEF 보험계약 조회 결과를 읽기 쉬운 대시보드로 정리하는 Next.js 애플리케이션입니다.

## 배포본

- Production: <https://insurance-eta-gray.vercel.app>
- 공개 페이지는 합성 데이터 시연과 공식 약관 탐색에 사용합니다.
- 배포 환경의 실데이터 API는 CODEF 자격증명이나 과거 미리보기 암호의 설정 여부와 관계없이 503으로 닫습니다. GA 설계사 인증과 고객별 접근 검증을 구현하기 전에는 저장된 고객 조회 이력을 제공하지 않습니다.

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
- Vercel의 DATABASE_URL에는 Railway 외부 TCP 연결 URL을 사용합니다.
- 최초 배포 전 pnpm db:migrate를 한 번 실행합니다.
- 공개 제출본에는 INSURANCE_DEMO_ONLY=true를 설정합니다.
- 로컬 개발에서만 CODEF 테스트가 필요하면 자격증명과 INSURANCE_DEMO_ONLY=false, INSURANCE_LOCAL_LIVE_TEST=true를 함께 설정합니다. 이 설정은 GA 조직 인증이나 고객 접근 권한을 대신하지 않습니다.
- 기존 INSURANCE_PREVIEW_USER 및 INSURANCE_PREVIEW_PASSWORD는 실데이터 API 접근 권한이 아닙니다.

자세한 제품 범위는 [PRODUCT.md](./PRODUCT.md)를 참고하세요.

## 전체 PDF 자료실

- `/insurance/terms`는 `lib/generated/product-summary-catalog.json`의 전체 PDF 목록을 기본으로 표시합니다. 건수와 보험사 수는 데이터에서 계산합니다.
- 보험사·상품명 검색과 분야·보험사·문서 유형 필터를 함께 사용할 수 있습니다. 각 자료의 **이 문서에 질문**은 동일한 문서 ID의 질문 자료를 선택합니다.
- 조항 분석이 있는 약관은 **분석 약관** 탭 또는 `/insurance/terms?view=analysis`에서 확인합니다. `/insurance/corpus`의 기존 전체 목록도 계속 사용할 수 있습니다.
