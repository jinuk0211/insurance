export const NHLIFE_POLICY_DOCUMENT_ID = "nhlife-wonderful-memory-dementia-2605"
export const NHLIFE_POLICY_SHA256 = "eef7bb8c3810e1078d81716eee1511183c2d9f686da10a3287b6a9a1d6bbdb88"

interface NHLifePolicyCheckpoint {
  title: string
  summary: string
  advisorCheck: string
  evidence: Array<{ article: string; page: number; anchor: string }>
}

// These prompts apply to this PDF revision; a customer's enrolled riders and policy version still require verification.
export const NHLIFE_POLICY_CHECKPOINTS: NHLifePolicyCheckpoint[] = [
  {
    title: "치매생활자금 특약 가입 형태",
    summary: "치매생활자금은 별도 특약입니다. 1종(실속형)은 중증치매 보장, 2종(종합형)은 중증·중등도 이상·경도 이상 보장을 구분합니다.",
    advisorCheck: "증권에서 치매생활자금특약 가입 여부와 1종·2종, 세부보장 가입금액을 확인하세요.",
    evidence: [
      { article: "치매생활자금특약 제4조①", page: 86, anchor: "① 1종(실속형)" },
      { article: "치매생활자금특약 제4조②", page: 86, anchor: "② 2종(종합형)" },
      { article: "치매생활자금특약 제4조②", page: 87, anchor: "3. 경도이상치매보장" },
    ],
  },
  {
    title: "치매보장개시일과 재해 예외",
    summary: "치매보장개시일은 원칙적으로 계약일 또는 부활일부터 그 날을 포함해 1년이 지난 날의 다음 날입니다. 재해로 인한 뇌 손상이 직접 원인인 경우 별도 예외가 있습니다.",
    advisorCheck: "계약·부활 날짜, 증상의 발생일과 원인, 특약의 보장개시일을 대조하세요.",
    evidence: [
      { article: "치매생활자금특약 제2조 3.가", page: 83, anchor: "그 날을 포함하여 1년이 지난 날의 다음날" },
      { article: "치매생활자금특약 제2조 3.가", page: 83, anchor: "재해로 인한 뇌의 손상을 직접적인 원인으로" },
    ],
  },
  {
    title: "CDR 단계·90일 지속·진단 제외",
    summary: "중증·중등도 이상·경도 이상은 각각 CDR 3·2·1점 이상 또는 동등한 검사로 정의됩니다. 상태가 90일 이상 지속되고 최종 진단확정되어야 하며, 약관의 일부 인지기능 장애는 제외됩니다.",
    advisorCheck: "치매 전문의 진단서, CDR 또는 동등 검사, 증상 지속기간과 원인질환을 확인하세요.",
    evidence: [
      { article: "치매생활자금특약 제3조①·②", page: 84, anchor: "발생시점부터 90일 이상 계속되어" },
      { article: "치매생활자금특약 제3조②", page: 84, anchor: "검사 결과가 3점 이상" },
      { article: "치매생활자금특약 제3조④", page: 84, anchor: "검사 결과가 2점이상" },
      { article: "치매생활자금특약 제3조⑥", page: 85, anchor: "검사 결과가 1점이상" },
      { article: "치매생활자금특약 제3조⑧", page: 85, anchor: "정신분열증이나 우울증과 같은 정신질환" },
    ],
  },
  {
    title: "생활자금 지급기간과 생존 조건",
    summary: "해당 단계의 최초 진단확정 이후에도 매년 진단확정일의 생존 여부를 봅니다. 경도 이상 생활자금은 최대 10년(120회)으로 제한됩니다.",
    advisorCheck: "실제 가입한 단계별 세부보장, 최초 진단확정일, 매년 생존 여부와 기존 지급 회차를 확인하세요.",
    evidence: [
      { article: "치매생활자금특약 제4조②", page: 87, anchor: "매년 ‘경도이상치매 진단확정일’에 살아 있을 때" },
      { article: "치매생활자금특약 제4조②", page: 87, anchor: "최대 10년(120회)까지 지급" },
      { article: "치매생활자금특약 제5조⑤", page: 88, anchor: "매월 ‘경도이상치매 월진단확정 해당일’에 12회 확정지급" },
    ],
  },
  {
    title: "납입기간 중 중도 해지 환급금",
    summary: "주계약 해약환급금일부지급형은 보험료 납입기간 중 해지 시 비교용 표준형 해약환급금의 50%로 규정합니다. 표준형은 판매하지 않는 비교용입니다.",
    advisorCheck: "증권의 가입 형태와 납입기간, 실제 해지 시점의 보험사 환급금 표를 확인하세요.",
    evidence: [
      { article: "주계약 제32조①", page: 68, anchor: "표준형”의 해약환급금 대비 적은 해약환급금" },
      { article: "주계약 제32조① 유의사항", page: 69, anchor: "표준형” 해약환급금의 50%에 해당하는 금액" },
      { article: "주계약 제32조① 유의사항", page: 69, anchor: "‘표준형’은 판매하지 않으며 비교 안내만을 위한 상품" },
    ],
  },
]
