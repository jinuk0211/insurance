# KFinLegal 실행 가이드


```
git clone https://github.com/affaan-m/everything-claude-code.git
cd everything-claude-code
```

node.js 설치

path 설정

```powershell
$env:Path +=";C:\Program Files\nodejs"
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
npm install
#.\install.ps1 --profile full

```

claude --version

정상 작동시 claude 실행

## 1. 파일 준비

```
kfinlegal-harness/
├── data/
│   ├── raw/
│   │   ├── contracts/
│   │   │   ├── 암보험/        ← PDF 여기
│   │   │   ├── 종신보험/      ← PDF 여기
│   │   │   ├── 질병보험/      ← PDF 여기
│   │   │   └── 정기보험/      ← PDF 여기
│   │   ├── precedents/        ← 판결문 TXT 여기
│   │   └── disputes/          ← 분쟁사례 TXT 여기
```

## 2. 설치

```bash
pip install pymupdf
```

## 3. 판결문/분쟁사례 JSON 변환 (최초 1회)

```bash
python scripts/parse_raw_data.py
```

→ `data/precedents.json`, `data/dispute_cases.json` 자동 생성

## 4. Claude Code 실행

```bash
cd kfinlegal-harness
claude
```

## 5. 약관 분석

```
/analyze data/raw/contracts/암보험/삼성생명_암보험약관.pdf
/analyze --contract data\raw\contracts\암보험\iM라이프_iM_프리미엄건강보험_무배당_2404_1종(암보장형) --age 55 --occupation 직장인 --conditions 고혈압 --riders 암진단특약,입원특약
```

Claude가 물어보는 것들:

- 나이
- 직업
- 기존 병력 (없으면 없다고)
- 가입 특약 (암보험특약, 입원비특약 등)

## 6. 결과 확인

```
workspace/final_report.json  ← 최종 리포트
workspace/audit_trail.log    ← 실행 이력
```
