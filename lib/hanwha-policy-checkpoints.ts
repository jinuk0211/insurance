export const HANWHA_POLICY_DOCUMENT_ID = "hanwha-e-cancer-2026-04-17"
export const HANWHA_POLICY_SHA256 = "918796d28b8274195258621c08c32c87159c18b1a50fb6e6f653a8c42ba8f7ed"

export interface HanwhaPolicyCheckpoint {
  title: string
  summary: string
  advisorCheck: string
  evidence: Array<{ article: string; page: number; anchor: string }>
}

// These are reading prompts for this PDF revision, not benefit decisions for a customer contract.
export const HANWHA_POLICY_CHECKPOINTS: HanwhaPolicyCheckpoint[] = [
  {
    title: "암 보장 시작일",
    summary: "일반암·특정 고액치료비관련암·특정 소액암·중증 갑상선암은 계약일 또는 부활일부터 그날을 포함해 90일이 지난 다음 날을 암보장개시일로 정합니다. 다른 진단자금과 시작일을 구분해야 합니다.",
    advisorCheck: "진단 분류와 계약일·부활일, 실제 가입 약관을 확인하세요.",
    evidence: [
      { article: "제2조 제2호 라목", page: 23, anchor: "그날을 포함하여 90 일이 지난 날의 다음 날을 말합니다" },
      { article: "제13조", page: 30, anchor: "보장개시일 이후에 기타피부암 , 갑상선암 , 대장점막내암" },
    ],
  },
  {
    title: "가입 초기 2년 감액",
    summary: "제13조의 진단자금 지급사유가 계약일부터 2년 미만에 발생하면 2년 이후 금액의 50%를 지급하도록 정합니다. 경과기간은 계약일부터 진단 확정일까지입니다.",
    advisorCheck: "보험증권의 가입금액과 진단 확정일로 경과기간을 대조하세요.",
    evidence: [
      { article: "제14조 제9항", page: 30, anchor: "계약일부터 2 년 미만에 제 13 조" },
      { article: "제14조 제9항", page: 31, anchor: "유사암 진단자금의 50% 를 지급합니다" },
      { article: "별표1 주2", page: 48, anchor: "지급금액의 경과기간은 보험계약일부터 진단 확정일까지의 경과기간입니다" },
    ],
  },
  {
    title: "고액암 추가 지급과 최초 1회",
    summary: "특정 고액치료비관련암 지급사유에는 일반 암진단자금을 더하지만, 두 진단자금은 각각 최초 1회입니다. 이미 지급된 보험금과 전이 여부를 함께 봐야 합니다.",
    advisorCheck: "과거 암 진단·지급 이력과 이번 진단의 전이 여부를 확인하세요.",
    evidence: [
      { article: "제14조 제10항", page: 31, anchor: "암진단자금을 더하여 지급합니다" },
      { article: "제14조 제10항", page: 31, anchor: "각각 최초 1 회에 한하여 지급" },
      { article: "제14조 제11항", page: 31, anchor: "지급된 암이 전이된 경우에는 회사는 해당" },
    ],
  },
  {
    title: "보험료 납입면제의 대상",
    summary: "보험료 납입기간 중 약관의 일반암·중증 갑상선암 최초 진단 또는 정해진 50% 이상 장해 등은 이후 보험료 납입면제 사유입니다. 특정 소액암과 유사암 진단은 이 사유에 포함되지 않습니다.",
    advisorCheck: "납입기간과 정확한 진단 분류 또는 장해지급률을 확인하세요.",
    evidence: [
      { article: "제14조 제1항", page: 30, anchor: "보험료 납입을 면제하여 드리지 않습니다" },
      { article: "별표1 주1", page: 48, anchor: "차회 이후 보험료 납입을 면제하여 드립니다" },
    ],
  },
  {
    title: "암보장개시일 전 진단",
    summary: "일반암의 암보장개시일 전 진단에는 계약 무효 조항이 있습니다. 특정 소액암·중증 갑상선암에는 별도 계약 취소와 이후 재진단 관련 규정이 있어 암종별로 나누어 검토해야 합니다.",
    advisorCheck: "최초 진단일·암종·취소 선택 여부·이후 진단과 치료 이력을 확인하세요.",
    evidence: [
      { article: "제28조 제1항 제2호", page: 38, anchor: "계약을 무효로 하며 계약자에게 이미 납입한 보험료를 돌려드립니다" },
      { article: "제14조 제15항", page: 32, anchor: "진단일부터 그 날을 포함하여 90 일 이내" },
      { article: "제14조 제17항", page: 33, anchor: "암보장개시일부터 5 년이 지나는 동안" },
    ],
  },
]
