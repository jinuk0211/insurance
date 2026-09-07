---
description: findings_ledger의 DRAFT 취약점을 판례·법령으로 검증한다. Stage 3 실행.
---

# /validate

`/analyze` 이후에 실행. legal-validator 에이전트를 위임해
DRAFT 취약점을 판례·분쟁사례·법령으로 grounding한다.

## 사용법

```
/validate
/validate --min-confidence 0.7
```

## 실행 내용

1. **사전 확인**
   - `workspace/findings_ledger.json` 존재 확인
   - DRAFT 취약점 수 출력

2. **legal-validator 에이전트 위임**
   ```
   Task(
     description="DRAFT 취약점 판례 검증",
     prompt="...",
     subagent_type="legal-validator"
   )
   ```

3. **citation_verifier 자동 실행** (에이전트 내부)
   - 모든 법령 인용을 `data/statutes_db.json`과 대조
   - 검증 실패 법령은 자동 드롭

4. 완료 후 요약 출력:
   ```
   ✓ 검증 완료
     CONFIRMED:  {N}건 (판례 grounding 완료)
     UNVERIFIED: {K}건 (판례 미확인, 주의 수준)
     REJECTED:   {M}건 (오탐)
     할루시네이션 차단: {J}건
   
   다음 단계: /report 로 최종 리포트를 생성하세요.
   ```

## 주의사항

- `/analyze` 없이 `/validate`를 실행하면 `NO_ARTIFACT` 오류 발생
- pgvector 미설정 시 `data/precedents.json` JSON 폴백으로 검색 (정확도 낮아짐)
