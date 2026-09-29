export const HYUNDAI_POLICY_DOCUMENT_ID = "hyundai-direct-repeat-cancer-hi2504-20250901"
export const HYUNDAI_POLICY_SHA256 = "be85fdea7a50fc028c183a99835b5f734733113a2e3e19e5105cd0c2c01b1eee"

export interface HyundaiPolicyCheckpoint {
  title: string
  summary: string
  advisorCheck: string
  evidence: Array<{ article: string; page: number; anchor: string }>
}

// Reading prompts for this historical PDF; an enrolled contract and its revision still require proof.
export const HYUNDAI_POLICY_CHECKPOINTS: HyundaiPolicyCheckpoint[] = [
  {
    title: "최초 암 보장개시일과 갱신",
    summary: "암(유사암 제외)은 최초계약의 계약일을 포함해 90일이 지난 다음 날부터 보장하고, 갱신계약은 갱신일을 보장개시일로 정합니다.",
    advisorCheck: "최초계약·갱신·부활 여부, 계약일과 진단확정일을 대조하세요.",
    evidence: [
      { article: "보통약관 제32조⑤", page: 53, anchor: "계약일부터 그 날을 포함하여 90일이 지 난 날의 다음날" },
      { article: "보통약관 제32조⑥", page: 53, anchor: "보장개시일을 갱신일로 합니다" },
    ],
  },
  {
    title: "초기 1년 감액과 최초 1회",
    summary: "암진단Ⅱ(유사암제외) 보장의 지급표는 최초계약의 1년 미만과 1년 이상을 나누어 각각 가입금액의 50%와 100%를 적고, 지급은 최초 1회로 제한합니다.",
    advisorCheck: "가입한 암진단 담보의 정확한 이름, 최초계약일, 가입금액, 과거 지급 이력을 확인하세요.",
    evidence: [
      { article: "보통약관 제3조①", page: 40, anchor: "최초 1회에 한하여" },
      { article: "보통약관 제3조①", page: 40, anchor: "계약일부터 1년 미만 계약일부터 1년 이상" },
      { article: "보통약관 제3조①", page: 40, anchor: "보험가입금액의 50% 해당액" },
      { article: "보통약관 제3조①", page: 40, anchor: "보험가입금액의 100% 해당액" },
    ],
  },
  {
    title: "재진단암 범위와 2년 간격",
    summary: "재진단암에는 새로운 원발암·전이암·재발암 등이 포함될 수 있으나 기타피부암·갑상선암·전립선암은 제외합니다. 첫 재진단암과 이후 재진단암의 보장개시일은 각각 기준 진단확정일부터 2년이 지난 다음 날입니다.",
    advisorCheck: "원발암·전이·재발 진단 기록과 직전 진단확정일, 실제 가입한 재진단암 담보를 대조하세요.",
    evidence: [
      { article: "보통약관 제4조⑦", page: 41, anchor: "새로운 원발암" },
      { article: "보통약관 제4조⑦", page: 41, anchor: "기타피부암’, ‘갑상선암’및 ‘전립선암’은 제외합니다" },
      { article: "보통약관 제32조⑦", page: 53, anchor: "첫 번째 재진단암 : 최초로 발생한" },
      { article: "보통약관 제32조⑦", page: 54, anchor: "두 번째 이후 재진단암 : 직전 재진단암 진단확정일부터" },
    ],
  },
  {
    title: "진단확정의 결과보고 시점",
    summary: "암과 유사암의 진단확정은 원칙적으로 병리 또는 진단검사의학 전문의의 검사에 근거하며, 검사 결과보고 시점을 진단확정 시점으로 정합니다.",
    advisorCheck: "진단서의 날짜와 병리·검사 결과보고서 날짜를 함께 확인하세요.",
    evidence: [
      { article: "보통약관 제4조⑩", page: 42, anchor: "병리 또는 진단 검사의학의 전문 의 자격증을 가진 자" },
      { article: "보통약관 제4조⑩", page: 42, anchor: "결과보고 시점으로 합니다" },
    ],
  },
  {
    title: "갱신 보험료 변동",
    summary: "갱신계약 보험료는 갱신일의 요율을 적용하며 나이 증가나 보험료 산출 기초율 변동에 따라 인상될 수 있습니다.",
    advisorCheck: "갱신 시점의 보험료 안내와 실제 갱신조건을 확인하세요.",
    evidence: [
      { article: "보통약관 제31조③", page: 52, anchor: "갱신계약의 보험료는 갱신일 현재의 보험요율" },
      { article: "보통약관 제31조③", page: 52, anchor: "나이의 증가, 보험료산출에 관한 기초율의 변동" },
    ],
  },
]
