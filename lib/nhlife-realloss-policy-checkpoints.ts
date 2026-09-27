export const NHLIFE_REALLOSS_DOCUMENT_ID = "nhlife-new-ansimcare-realloss-2605"
export const NHLIFE_REALLOSS_SHA256 = "42ce81976809453b8e3d80ba893c75ef2872897847c2412d1cf24518de95b955"

interface NHLifeRealLossCheckpoint {
  title: string
  summary: string
  advisorCheck: string
  evidence: Array<{ article: string; page: number; anchor: string }>
}

// The customer's enrolled coverages and contract revision must be checked before applying these reading prompts.
export const NHLIFE_REALLOSS_CHECKPOINTS: NHLifeRealLossCheckpoint[] = [
  {
    title: "급여 기본계약과 비급여 추가보장 구분",
    summary: "기본계약은 상해·질병 급여를 다룹니다. 비급여는 중증 질환용 추가보장계약1과 비중증 질환용 추가보장계약2로 나뉩니다.",
    advisorCheck: "증권에서 기본계약과 추가보장계약1·2의 가입 여부 및 보장종목을 각각 확인하세요.",
    evidence: [
      { article: "기본계약 제1조①", page: 28, anchor: "상해급여형, 질병급여형의 2개 보장종목" },
      { article: "추가보장계약1 제1조①", page: 81, anchor: "상해비급여형, 질병비급여형, 3대비급여형" },
      { article: "추가보장계약2 제1조①", page: 105, anchor: "상해비급여형, 질병비급여형, 비급여 자기공명" },
    ],
  },
  {
    title: "급여 입원·통원 보상과 공제금액",
    summary: "급여 기본계약의 입원은 실제 본인부담금의 80%로 규정합니다. 통원은 의료기관 종류와 보장대상 의료비 등에 따라 공제금액을 적용합니다.",
    advisorCheck: "급여 진료비 영수증, 병원 종류, 처방조제 내역, 연간 가입금액과 적용 공제금액을 확인하세요.",
    evidence: [
      { article: "기본계약 제3조 (1)①", page: 29, anchor: "본인부담금(본인이 실제로 부담한 금액" },
      { article: "기본계약 제3조 (1)①", page: 29, anchor: "80%에 해당하 는 금액" },
      { article: "기본계약 제3조 (1)① 표1", page: 30, anchor: "1만원, 보장대상 의료비의 20%" },
      { article: "기본계약 제3조 (1)① 표1", page: 30, anchor: "2만원, 보장대상 의료비의 20%" },
    ],
  },
  {
    title: "중증·비중증 비급여의 적용 범위와 비율",
    summary: "추가보장계약1은 산정특례 대상 질환 치료의 비급여를, 추가보장계약2는 그 외 질환 치료의 비급여를 구분합니다. 입원 비급여의 약관 표에는 각각 70%와 50%가 적혀 있습니다.",
    advisorCheck: "산정특례 대상 여부, 실제 가입한 추가보장, 치료 목적·항목, 병실료와 개별 한도를 확인하세요.",
    evidence: [
      { article: "추가보장계약1 제2조①", page: 81, anchor: "산정특례 대상 질환으로 인한 비급여" },
      { article: "추가보장계약1 제3조 (1)①", page: 85, anchor: "70%에 해당하는 금액" },
      { article: "추가보장계약2 제2조①", page: 105, anchor: "산정특례 대상 질환이 아닌 질환으로 인한 비급여" },
      { article: "추가보장계약2 제3조 (1)①", page: 109, anchor: "50%에 해당하는 금액" },
    ],
  },
  {
    title: "기본계약의 면책과 비급여 분리",
    summary: "기본계약은 제4조에 보상 제외 사유를 두고, 공단에서 사전·사후 환급 가능한 일부 금액을 제외합니다. 비급여의료비는 급여 기본계약에서 보상하지 않습니다.",
    advisorCheck: "사고·질병 원인, 공단 환급 가능액, 청구서의 급여·비급여 항목 구분을 확인하세요.",
    evidence: [
      { article: "기본계약 제4조", page: 35, anchor: "제4조【보상하지 않는 사항】" },
      { article: "기본계약 제4조 (1)③", page: 36, anchor: "국민건강보험공단으로부터 사전 또는 사후 환급이 가능한 금액" },
      { article: "기본계약 제4조의2①", page: 39, anchor: "기본계약(급여 실손의료비)에서 보상하지 않습니다" },
    ],
  },
  {
    title: "1년 갱신과 보험료 변경",
    summary: "보험기간은 1년 만기 갱신이며, 갱신 거절 통지·보험료 납입 조건을 확인해야 합니다. 갱신 보험료는 나이와 보험요율 변경으로 인상될 수 있습니다.",
    advisorCheck: "갱신 안내, 갱신 거절 통지 여부, 갱신 전후 보험료 납입과 새 보험료를 확인하세요.",
    evidence: [
      { article: "기본계약 제22조①", page: 58, anchor: "보험기간은 1년 만기 갱신으로 합니다" },
      { article: "기본계약 제22조②", page: 58, anchor: "보험기간이 끝나는 날의 15일 전까지" },
      { article: "기본계약 제22조②", page: 59, anchor: "갱신계약의 제1회 보험료를 납입하지 않으면" },
      { article: "기본계약 제22조⑦", page: 59, anchor: "변경(특히 인상)될 수 있습니다" },
    ],
  },
  {
    title: "5년 보장내용 변경주기와 재가입",
    summary: "보장내용 변경주기는 원칙적으로 5년입니다. 재가입 시점의 판매 상품으로 이어지며 보장범위와 자기부담금 등이 변경될 수 있습니다.",
    advisorCheck: "최초·재가입 나이, 보장내용 변경주기 종료일, 보험료 완납과 재가입 의사 확인 기록을 대조하세요.",
    evidence: [
      { article: "기본계약 제25조①", page: 61, anchor: "보장내용(보장범위 및 자기부담금 등)" },
      { article: "기본계약 제25조①", page: 61, anchor: "5년으로 합니다" },
      { article: "기본계약 제25조④", page: 62, anchor: "재가입 전 계약의 보험료가 정상적으로 납입완료 되었을 것" },
      { article: "기본계약 제25조⑤", page: 62, anchor: "재가입 시 점에서 회사가 판매하는 실손의료보험 상품" },
    ],
  },
]
