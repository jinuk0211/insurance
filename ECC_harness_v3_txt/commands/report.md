---
description: validated_findings를 개인화 심각도 리포트로 변환한다. Stage 4 실행.
---

# /report

`/validate` 이후에 실행. severity-classifier 에이전트를 위임해
사용자 프로필 기반 개인화 최종 리포트를 생성한다.

## 사용법

```
/report
/report --format json
/report --format markdown
```

## 실행 내용

1. **사전 확인**
   - `workspace/validated_findings.json` 존재 확인

2. **severity-classifier 에이전트 위임**
   ```
   Task(
     description="심각도 분류 및 최종 리포트 생성",
     prompt="...",
     subagent_type="severity-classifier"
   )
   ```

3. **리포트 출력** (`--format markdown` 시):

   ```markdown
   # KFinLegal 취약점 분석 리포트
   
   **분석 대상**: 삼성생명 암보험약관
   **분석 일시**: 2025-01-15
   **전체 위험도**: 🔴 HIGH
   
   ## 핵심 요약
   총 23개 조항 분석 결과, 3개 취약점이 확인되었습니다.
   가장 심각한 취약점은 '고지의무 위반 면책 남용'입니다.
   
   ## 취약점 목록
   
   ### 🔴 [CRITICAL] INS-02 고지의무 위반 면책 남용
   **조항**: 제13조(계약 전 알릴 의무) ①항
   
   **무슨 문제인가요?**
   이 조항은 보험사가 고지의무 위반을 이유로 보험금을 거절할 때...
   
   **이 분에게 어떤 위험이 있나요?**
   고혈압 병력을 가진 68세 은퇴자의 경우...
   
   **관련 판례**: 대법원 2017다245829 (2019-11-14)
   **관련 법령**: 상법 제651조 (검증됨)
   
   **권고사항**:
   1. ✅ [가입 전] 건강검진 결과 전체를 고지하세요.
   2. ✅ [즉시] 금융감독원 분쟁조정 신청을 검토하세요. ☎1332
   
   ---
   ### ⚠️ [UNVERIFIED] INS-05 보험료 산정 불투명
   *판례로 확인되지 않은 항목. 참고 수준으로 활용하세요.*
   ...
   
   ## 면책사항
   본 리포트는 AI 기반 자동 분석 결과로, 법적 효력이 없습니다...
   ```

4. `workspace/final_report.json` 저장 완료 메시지

## 파일 위치

```
workspace/final_report.json   ← JSON 원본
```

Markdown 출력은 터미널에 직접 표시.
