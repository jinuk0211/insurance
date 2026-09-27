export const KB_POLICY_DOCUMENT_ID = "kb-25290-2026-07-01"
export const KB_POLICY_SHA256 = "e97dcee90b7a978792672666bc0813cf40b94805253548761113780f631b2ee5"

export interface KBPolicyCheckpoint {
  title: string
  summary: string
  advisorCheck: string
  evidence: Array<{ article: string; page: number; anchor: string }>
}

// These prompts apply only to the pinned 26.07 PDF and the named benefits or riders.
export const KB_POLICY_CHECKPOINTS: KBPolicyCheckpoint[] = [
  {
    title: "일반암 진단비의 시작일",
    summary: "‘암진단비(유사암제외)(감액없음)’ 보장은 최초 계약일을 포함해 90일이 지난 다음 날부터 시작합니다. 계약일 현재 보험나이 15세 미만이면 계약일부터, 갱신계약이면 갱신일부터 보장합니다.",
    advisorCheck: "실제 가입 담보·보험나이·계약 또는 갱신일·진단 확정일을 대조하세요.",
    evidence: [
      { article: "암진단비 제1조 제2항", page: 118, anchor: "계약일로부터 그날을 포함하여 90일이 지난날의 다음날" },
      { article: "암진단비 제1조 제2항", page: 118, anchor: "보험나이 15세미만 피보험자의 경우 암보장개시일은 계약일" },
      { article: "암진단비 제1조 제3항", page: 118, anchor: "갱신된 계약의 암보장개시일은 이 보장의 갱신일" },
    ],
  },
  {
    title: "일반암과 유사암의 담보 구분",
    summary: "이 일반암 진단비는 기타피부암(C44)과 갑상선암(C73)을 제외하고 최초 1회 지급합니다. 별도의 유사암진단비 보장은 기타피부암·갑상선암·제자리암·경계성종양을 각각 최초 1회 대상으로 정합니다.",
    advisorCheck: "진단 분류코드와 유사암진단비 가입 여부·과거 지급 이력을 확인하세요.",
    evidence: [
      { article: "암진단비 제1조 제1항", page: 118, anchor: "최초 1회의 진단에 한하여" },
      { article: "암진단비 제3조", page: 118, anchor: '기타피부암" 및 제4항에서 정한 "갑상선암"을 제외' },
      { article: "유사암진단비 제1조", page: 119, anchor: "각각 최초 1회의 진단에 한하여" },
      { article: "유사암진단비 제3조", page: 119, anchor: "분류번호 C44" },
    ],
  },
  {
    title: "보장개시일 전 암 진단",
    summary: "‘암진단비(유사암제외)(감액없음)’ 보장은 정해진 암보장개시일 전날까지 대상 암으로 진단 확정되면 해당 보장을 무효로 하고 납입 보험료를 돌려주도록 정합니다.",
    advisorCheck: "진단 확정일과 정확한 담보의 보장개시일을 확인하세요.",
    evidence: [
      { article: "암진단비 제4조", page: 119, anchor: "이 보장은 무효로 하며 이미 납입한 이 보장의 보험료를 돌려 드립니다" },
    ],
  },
  {
    title: "재진단암 특약마다 다른 간격",
    summary: "‘재진단암진단비’ 특약은 첫 암 또는 직전 재진단암 진단일부터 2년 경과 후 보장을 시작합니다. ‘신재진단암진단비Ⅱ(5회한, 1년대기형)’ 특약은 1년 간격과 5회 한도를 정합니다. 두 조건을 섞어 적용하면 안 됩니다.",
    advisorCheck: "증권에 적힌 재진단 특약명과 최초·직전 진단일, 지급 회차를 확인하세요.",
    evidence: [
      { article: "재진단암진단비 제1조 제2항", page: 229, anchor: "진단 확정일부터 그날을 포함하여 2년이 지난 날의 다음날" },
      { article: "신재진단암진단비Ⅱ 제1조 제1항", page: 417, anchor: "5회에 한하여" },
      { article: "신재진단암진단비Ⅱ 제1조 제2항", page: 417, anchor: "진단 확정일부터 그날을 포함하여 1년이 지난 날의 다음날" },
    ],
  },
  {
    title: "감액없음과 다른 특약의 감액",
    summary: "일반암 진단비의 이름에는 ‘감액없음’이 있지만, 표적항암약물허가치료비(최초1회한)Ⅱ 등 일부 치료 특약은 가입 후 1년간 보험금 50% 지급 조건이 따로 표시돼 있습니다.",
    advisorCheck: "진단비와 치료비를 나누고, 실제 가입 특약·치료일·가입금액을 대조하세요.",
    evidence: [
      { article: "암진단비 보장명", page: 118, anchor: "암진단비(유사암제외)(감액없음)" },
      { article: "감액지급 적용 담보표", page: 41, anchor: "표적항암약물허가치료비(최초1회한)" },
      { article: "감액지급 적용 담보표", page: 41, anchor: "가입 후 1년간 보험금 50% 지급" },
    ],
  },
  {
    title: "보험료 납입면제와 갱신",
    summary: "1종 1형의 7대 납입면제형은 암보장개시일 이후 유사암 제외 암 진단 등을 납입면제 사유로 정합니다. 갱신계약에는 갱신 전 사고로 생긴 납입면제를 새 계약에 적용하지 않는다는 조항이 있습니다.",
    advisorCheck: "상품 종·형, 가입 특약, 진단 시점과 갱신 여부를 확인하세요.",
    evidence: [
      { article: "보통약관 제4조 제1항", page: 98, anchor: "【1종 1형 : 7대 납입면제형】" },
      { article: "보통약관 제4조 제1항 제3호", page: 98, anchor: '암보장개시일 이후에 "암(유사암제외)"으로 진단 확정' },
      { article: "보통약관 제4조", page: 98, anchor: "갱신전 보험사고로 인한 보험료 납입면제를 적용하지 않" },
    ],
  },
]
