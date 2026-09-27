export const KB_CARE_POLICY_DOCUMENT_IDS = [
  "kb-25469-2026-09-01",
  "kb-25470-2026-09-01",
] as const
export const KB_CARE_POLICY_SHA256 = "9383617085cc37c4a7dede31cac6e9ef635f7efaa2d3144ada63611521bfcf56"

export interface KBCarePolicyCheckpoint {
  title: string
  summary: string
  advisorCheck: string
  evidence: Array<{ article: string; page: number; anchor: string }>
}

// Both listed forms use the same pinned 26.09 PDF. Apply a rider checkpoint only after checking the policy schedule.
export const KB_CARE_POLICY_CHECKPOINTS: KBCarePolicyCheckpoint[] = [
  {
    title: "간병인 지원과 입원일당은 같은 날 중복 지급되지 않음",
    summary: "간병인지원 상해·질병입원일당 특별약관에서 간병인 지원을 선택하면 해당 입원일당은 지급하지 않습니다. 간호·간병통합서비스를 이용한 경우에는 간병인 지원·사용비용 대신 입원일당을 지급합니다.",
    advisorCheck: "가입한 상해·질병 간병인지원 특약, 입원 원인과 날짜, 회사 지원 신청 및 간호·간병통합서비스 이용 여부를 확인하세요.",
    evidence: [
      { article: "간병인지원 상해입원일당 제1조", page: 252, anchor: "제1항의 상해입원일당은 지급하지 않습니다" },
      { article: "간병인지원 상해입원일당 제1조", page: 252, anchor: "간병인 지원 및 간병인 사용비용을 지급하지 않고 상해입원일당으로 지급합니다" },
      { article: "간병인지원 질병입원일당 제1조", page: 277, anchor: "제1항의 질병입원일당은 지급하지 않습니다" },
      { article: "간병인지원 질병입원일당 제1조", page: 277, anchor: "간병인 지원 및 간병인 사용비용을 지급하지 않고 질병입원일당으로 지급합니다" },
    ],
  },
  {
    title: "간병인 지원은 48시간 전 신청",
    summary: "간병인지원 상해·질병입원일당 특약은 지원 희망일 48시간 전에 회사에 신청하도록 정합니다. 신청 없이 임의로 간병인을 쓰면 간병인지원비용 대신 해당 입원일당을 지급합니다.",
    advisorCheck: "간병지원 특약 가입 여부와 신청 접수 시각, 지원 희망일, 간병인 공급업체의 사업자 등록을 대조하세요.",
    evidence: [
      { article: "간병인지원 상해입원일당 제1조", page: 253, anchor: "48시간 이전에 회사로 신청하여야 하며" },
      { article: "간병인지원 상해입원일당 제1조", page: 253, anchor: "간병인을 신청하지 않고 임의로 간병인을 사용한 경우" },
      { article: "간병인지원 질병입원일당 제1조", page: 278, anchor: "48시간 이전에 회사로 신청하여야 하며" },
      { article: "간병인지원 질병입원일당 제1조", page: 278, anchor: "간병인을 신청하지 않고 임의로 간병인을 사용한 경우" },
    ],
  },
  {
    title: "입원일당과 간병인 지원일수의 합계 한도",
    summary: "상해·질병 간병인지원 특약은 입원일당 지급일수와 간병인 지원일수의 합계를 1회 입원당 180일로 제한합니다. 질병은 같은 질병으로 다시 입원한 경우의 합산과 최종 퇴원일부터 180일 경과 시 새 입원으로 보는 규정도 있습니다.",
    advisorCheck: "입원 원인별 최초·최종 입퇴원일, 이미 지급된 입원일당과 지원일수, 재입원 간격을 확인하세요.",
    evidence: [
      { article: "간병인지원 상해입원일당 제2조", page: 253, anchor: "상해입원일당의 지급일수와 간병인의 지원일수의 합계는 1회 입원당 180일" },
      { article: "간병인지원 질병입원일당 제2조", page: 278, anchor: "질병입원일당의 지급일수와 간병인의 지원일수의 합계는 1회 입원당 180일" },
      { article: "간병인지원 질병입원일당 제2조", page: 279, anchor: "최종 입원의 퇴원일로부터 180일이 지나서 개시한 입원은 새로운 입원으로 봅니다" },
    ],
  },
  {
    title: "고객이 직접 선택한 간병인의 비용 청구 서류",
    summary: "회사에 지원을 신청했지만 회사가 간병인을 지원하지 못해 고객이 직접 사용한 경우, 간병인 사용 기간·금액과 업체 사업자등록번호가 담긴 영수증을 요구합니다. 정해진 영수증을 낼 수 없을 때의 대체 증빙도 약관에 있습니다.",
    advisorCheck: "회사 지원 불가 사실, 실제 유상 간병서비스 이용, 업체 등록, 사용 기간·금액 및 영수증 또는 대체 증빙을 확인하세요.",
    evidence: [
      { article: "간병인지원 상해입원일당 제1조", page: 252, anchor: "회사가 부득이한 이유로 간병인을 지원하지 못하여 실제 고객이 선택한 간병인을 사용" },
      { article: "간병인지원 상해입원일당 제5조", page: 254, anchor: "간병인 사용 기간 및 금액이 기재된 영수증" },
      { article: "간병인지원 질병입원일당 제5조", page: 280, anchor: "간이영수증과 거래방법을 추가로 확인할 수 있는 서류" },
    ],
  },
  {
    title: "보장보험료 납입면제의 제외 특약",
    summary: "보통약관의 납입면제는 정해진 5대기본 사유에 따라 적용되지만, 경증이상알츠하이머치매진단비·파킨슨병진단비·중증치매 산정특례대상보장 등의 보장보험료는 면제 대상에서 제외합니다. 새로 갱신되는 계약에도 이전 사고로 인한 면제를 적용하지 않는다고 정합니다.",
    advisorCheck: "1종·2종, 의무부가 특약, 납입면제 사유와 발생일, 제외 특약 및 갱신 시점을 확인하세요.",
    evidence: [
      { article: "보통약관 제4조", page: 64, anchor: "보장보험료 납입면제 제외 특별약관 경증이상알츠하이머치매진단비 특별약관" },
      { article: "보통약관 제4조", page: 64, anchor: "새롭게 갱신되는 계약에서는 갱신전 보험사고로 인한 보험료 납입면제를 적용하지 않으며" },
      { article: "보통약관 제4조", page: 65, anchor: "보장보험료 납입면제 제외 특별약관 경증이상알츠하이머치매진단비 특별약관" },
    ],
  },
]

export const KB_CARE_NO_REFUND_CHECKPOINTS: KBCarePolicyCheckpoint[] = [
  ...KB_CARE_POLICY_CHECKPOINTS,
  {
    title: "2형은 납입기간 중 해약환급금 미지급",
    summary: "공통 PDF의 2형(표준형 해약환급금의 50% 지급형·납입기간 이후)은 납입기간 중 해지하면 해약환급금을 지급하지 않고, 납입 완료 후 해지하면 표준형 해약환급금의 50%로 정합니다. 갱신계약 특별약관의 환급금은 별도 산출방법을 따릅니다.",
    advisorCheck: "증권의 실제 가입 유형과 납입기간·해지시점, 갱신 특약 여부를 확인하고 환급금 예시표를 대조하세요.",
    evidence: [
      { article: "보통약관 제36조", page: 79, anchor: "보험료 납입기간 중 이 계약이 해지될 경우 해약환급금을 지급하지 않습니다" },
      { article: "보통약관 제36조", page: 79, anchor: "표준형 상품 해약환급금의 50%에 해당하는 금액" },
      { article: "보통약관 제36조", page: 80, anchor: "따라 계산한 금액을 해약환급금으로 지급합니다" },
    ],
  },
]
