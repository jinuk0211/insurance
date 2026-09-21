# KFin Insurance Desk

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
- 실데이터 모드의 빌드는 `pnpm db:migrate`를 먼저 실행하며, DB 연결 또는 마이그레이션 실패 시 배포를 중단합니다.
- `INSURANCE_DEMO_ONLY=true`인 공개 데모 빌드는 DB 마이그레이션 없이 화면을 빌드합니다. `pnpm db:migrate`를 직접 실행하면 데모 설정과 무관하게 마이그레이션을 수행합니다.
- 공개 제출본에는 `INSURANCE_DEMO_ONLY=true`를 설정합니다.
- 실데이터 API를 별도로 운영할 때만 CODEF 자격증명과 API 접근용 `INSURANCE_PREVIEW_USER`, `INSURANCE_PREVIEW_PASSWORD`를 설정합니다.

자세한 제품 범위는 [PRODUCT.md](./PRODUCT.md)를 참고하세요.

## 약관 추출 실험 보기

`/insurance`의 **약관·위험 → 분석 실험 결과**, 또는 `/insurance/terms?view=research`에서 2026-09-21 Luna 파일럿을 확인할 수 있습니다.

- 상품요약서 5개, 전체 99쪽, 추출 초안 53개를 담았습니다.
- 인용·페이지 일치 35개는 내용 정확도가 아닙니다. 확인된 오류와 모델 인용을 원본 PDF와 함께 검토할 수 있습니다.
- 문서 2~3개를 선택하고 **나란히 비교**를 누르면 지급조건·감액·납입면제 등을 항목별로 대조할 수 있습니다. 항목을 펼쳐 조건·예외와 원문 페이지를 확인할 수 있으며, 추출 결과가 없는 칸은 보장이 없다는 뜻이 아닙니다.
- 고객 계약 근거 및 기존 50개 공식 약관 자료실과 구분됩니다.
- 공개용 스냅샷은 `lib/generated/luna-pilot.json`, 공개 PDF와 다운로드 결과는 `public/research/luna-pilot/`에 있습니다. 로컬 파일 경로나 고객 데이터는 포함하지 않습니다.
- 원본 실험 산출물이 `output/analysis/luna_pilot_2026-09-21/`에 있을 때 `python scripts/publish-luna-pilot.py`로 공개 스냅샷을 재생성할 수 있습니다. 서비스 실행 시 모델을 호출하지 않습니다.
