---
name: txt-harness
description: >
  보험 상품요약서 TXT 파일에서 취약점을 탐지하는 하네스.
  제N조 패턴 없는 상품요약서 형식 전용.
  기존 kfinlegal-harness의 Stage 1/2를 TXT 특화 버전으로 대체.
  Stage 3/4는 기존 legal-validator, severity-classifier 그대로 사용.
---

# TXT Harness — Runtime Charter

## 언제 이 스킬을 쓰나

- 약관 PDF가 아닌 **TXT 파일**을 분석할 때
- 상품요약서 형식(◆헤더, Q&A, 번호목록)의 문서를 분석할 때
- `제N조` 패턴이 없는 문서를 분석할 때

정식 약관 PDF는 기존 `/analyze` 커맨드와 `kfinlegal-harness` 스킬을 사용할 것.

## 파이프라인

```
TXT 파일 입력
    ↓
Stage 1: txt-contract-parser   (scripts/parse_txt.py Bash 호출)
    ↓ workspace/findings_ledger.json
Stage 2: txt-vulnerability-spotter
    ↓ workspace/findings_ledger.json (취약점 DRAFT 추가)
Stage 3: legal-validator       (기존 에이전트 그대로)
    ↓ workspace/validated_findings.json
Stage 4: severity-classifier   (기존 에이전트 그대로)
    ↓ workspace/final_report.json
```

## 상품요약서 vs 정식 약관 차이

| 항목 | 상품요약서 (이 스킬) | 정식 약관 (kfinlegal-harness) |
|---|---|---|
| 입력 형식 | TXT | PDF |
| 파서 | scripts/parse_txt.py | scripts/parse_pdf.py |
| 청킹 단위 | ◆헤더/번호섹션 | 제N조 |
| 신뢰도 | confidence -0.10 적용 | 그대로 |
| 주의사항 | 정식 약관 확인 권장 | - |

## 실행 방법

```
/analyze-txt data/raw/contracts/암보험/iM라이프_암보험요약서.txt
             --age 55 --occupation 직장인 --conditions 고혈압
```

또는 단계별:

```
# Stage 1+2
/analyze-txt {txt경로} {옵션}

# Stage 3
/validate

# Stage 4
/report
```

## Workspace 아티팩트

```
workspace/{session_id}/
  contract_state.json      세션 메타 (doc_format: "product_summary" 포함)
  findings_ledger.json     섹션 단위 조항 + 취약점 DRAFT
  validated_findings.json  판례 검증 완료
  final_report.json        최종 리포트
  audit_trail.log          실행 이력
```

## 실패 코드

| 코드 | 정의 | 복구 |
|---|---|---|
| PARSE_FAIL | 헤더 패턴 인식 불가 | 문서 형식 확인, PDF 직접 업로드 시도 |
| NO_ARTIFACT | 이전 스테이지 파일 없음 | 해당 스테이지부터 재실행 |
| NO_PRECEDENT | 판례 없음 | UNVERIFIED 표시 후 계속 |
| CITATION_HALLUCINATION | 허위 법조항 인용 | 해당 인용 삭제, 재검색 1회 |

## 중요 주의사항

상품요약서는 정식 약관의 요약본이다.
- 취약점 탐지 결과는 참고용이며, 실제 약관 원문과 다를 수 있다.
- 모든 final_report에 "상품요약서 기반 분석" 면책 문구가 자동 포함된다.
- confidence가 0.55 미만인 항목은 자동으로 LOW_CONFIDENCE 처리된다.
