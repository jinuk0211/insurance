# KFinLegal-Harness

한국 금융상품(보험·대출) 약관의 법적 취약점을 자동 탐지하는 Claude Code 하네스.

## 프로젝트 구조

```
kfinlegal-harness/
├── agents/                    # 에이전트 역할 정의
│   ├── contract-parser.md     # Stage 1 — PDF 파싱·조항 구조화
│   ├── vulnerability-spotter.md  # Stage 2 — 취약점 탐지
│   ├── legal-validator.md     # Stage 3 — 판례 grounding·검증
│   └── severity-classifier.md # Stage 4 — 심각도 분류·리포트
├── skills/
│   └── kfinlegal-harness/
│       └── SKILL.md           # 하네스 진입점 + Runtime Charter
├── commands/
│   ├── analyze.md             # /analyze — 약관 분석 실행
│   ├── validate.md            # /validate — 취약점 판례 검증
│   └── report.md              # /report — 리포트 생성
├── hooks/
│   └── hooks.json             # PreToolUse / PostToolUse 훅
├── rules/
│   └── kfinlegal-rules.md     # 항상 지켜야 할 규칙
├── data/
│   ├── raw/precedents/        # 판결문 TXT (사례별 1파일)
│   ├── raw/disputes/          # 분쟁사례 TXT (사례별 1파일)
│   └── raw/contracts/보험사명/ # 약관 PDF (보험사별 폴더)
└── workspace/                 # File-backed State (런타임 생성)
    ├── contract_state.json
    ├── findings_ledger.json
    ├── validated_findings.json
    ├── final_report.json
    └── audit_trail.log
```

## 에이전트 실행 순서

```
/analyze 약관.pdf → contract-parser
                  → vulnerability-spotter
                  → legal-validator        (citation hook 필수)
                  → severity-classifier
                  → final_report.json
```

## 핵심 규칙

1. **판례 없는 법조항 인용 금지** — legal-validator의 citation 검증 없이 법령 인용 불가
2. **File-backed State** — 모든 중간 결과는 workspace/*.json에 저장
3. **역할 경계 엄수** — 각 에이전트는 자기 Stage만 담당

## 데이터 파이프라인 (Python, 최초 1회)

```bash
# 판결문·분쟁사례 파싱 + pgvector 인덱싱
python pipeline/parse_precedents.py --input-dir data/raw/precedents
python pipeline/parse_disputes.py --input-dir data/raw/disputes
python pipeline/index_contracts.py --contracts-dir data/raw/contracts
```

## 슬래시 커맨드

- `/analyze` — 약관 PDF 분석 시작
- `/validate` — findings_ledger 판례 검증
- `/report` — 최종 리포트 생성
