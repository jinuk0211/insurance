---
description: 약관 PDF를 분석해 취약점을 탐지한다. Stage 1(파싱) + Stage 2(취약점 탐지) 실행.
---

# /analyze

약관 PDF 경로와 사용자 프로필을 받아 Stage 1~2를 실행한다.
완료 후 `/validate`로 판례 검증을 이어서 진행한다.

## 사용법

```
/analyze
/analyze --contract 삼성생명_암보험약관.pdf
/analyze --contract 약관.pdf --age 68 --occupation 은퇴 --conditions 고혈압,당뇨 --product insurance
```

## 실행 내용

1. **사용자 프로필 수집** (미입력 시 대화로 확인)
   - 나이, 직업, 기존 병력, 특약 목록, 상품 유형(보험/대출)

2. **kfinlegal-harness 스킬 로드**
   ```
   Read("skills/kfinlegal-harness/SKILL.md")
   ```

3. **contract-parser 에이전트 위임**
   ```
   Task(
     description="약관 조항 파싱 및 findings_ledger 초기화",
     prompt="...",
     subagent_type="contract-parser"
   )
   ```

4. **vulnerability-spotter 에이전트 위임**
   ```
   Task(
     description="취약점 탐지 및 DRAFT 생성",
     prompt="...",
     subagent_type="vulnerability-spotter"
   )
   ```

5. 완료 후 요약 출력:
   ```
   ✓ 파싱 완료: {N}개 조항
   ✓ 취약점 탐지: {M}건 (LOW_CONFIDENCE: {K}건)
   
   다음 단계: /validate 로 판례 검증을 진행하세요.
   ```

## 재개 (중단된 경우)

```
/analyze --resume
```
`workspace/contract_state.json`을 읽어 중단된 Stage부터 재개.
