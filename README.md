# KFin Insurance Desk

CODEF 보험계약 조회 결과를 읽기 쉬운 대시보드로 정리하는 Next.js 애플리케이션입니다.

## 배포본

- Production: <https://insurance-eta-gray.vercel.app>
- 접근 잠금이 적용되어 있으며 저장소 소유자가 별도로 자격증명을 관리합니다.
- Railway PostgreSQL 스키마는 배포되어 있지만, 유출된 CODEF 자격증명은 운영 환경에 등록하지 않았습니다.

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
- Preview 접근 잠금에는 `INSURANCE_PREVIEW_USER`, `INSURANCE_PREVIEW_PASSWORD`를 설정합니다.

자세한 제품 범위는 [PRODUCT.md](./PRODUCT.md)를 참고하세요.
