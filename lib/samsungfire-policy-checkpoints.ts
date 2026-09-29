export const SAMSUNGFIRE_POLICY_DOCUMENT_ID = "samsungfire-direct-realloss-conversion-2605-1"
export const SAMSUNGFIRE_POLICY_SHA256 = "db0ed9738c9f59fbb28b678b910e0bdd3ef4bf08bdac52643c2e2dd167003415"

export interface SamsungfirePolicyCheckpoint {
  title: string
  summary: string
  advisorCheck: string
  evidence: Array<{ article: string; page: number; anchor: string }>
}

// Reading prompts for the pinned contract-conversion PDF, not claim decisions.
export const SAMSUNGFIRE_POLICY_CHECKPOINTS: SamsungfirePolicyCheckpoint[] = [
  {
    title: "전환 중 계속된 입원·통원",
    summary: "계약전환 전부터 이어진 입원·통원은 전환 전 약관에 따라 보상하도록 정합니다. 약관에 적힌 새 최초 입원·통원 기준에 해당하면 새 계약 조항을 적용하는 예외도 있습니다.",
    advisorCheck: "전환 전 계약의 약관과 최초 입원·통원일, 치료가 계속된 기간을 대조하세요.",
    evidence: [
      { article: "보통약관 제3조 상해급여 제11·12항", page: 26, anchor: "전환전 계약의 약관에 따라 보상합니다" },
      { article: "보통약관 제3조 질병급여 제11·12항", page: 27, anchor: "전환전 계약의 약관에 따라 보상합니다" },
    ],
  },
  {
    title: "급여 입원과 통원 공제",
    summary: "급여 입원 보상표에는 본인부담금의 80%가 기재되어 있습니다. 급여 통원은 의료기관 유형별 공제금액 등을 뺀 뒤 계산하므로 입원과 같은 비율로 단정할 수 없습니다.",
    advisorCheck: "급여·비급여 구분, 입원·통원, 의료기관 종류와 영수증의 본인부담금을 확인하세요.",
    evidence: [
      { article: "보통약관 제3조 상해급여", page: 24, anchor: "본인부담금 ( 본인이 실제로 부담한 금액" },
      { article: "보통약관 제3조 상해급여", page: 24, anchor: "의 80% 에 해 당하는 금액" },
      { article: "보통약관 제3조 질병급여", page: 26, anchor: "통원항목별 공제금액" },
    ],
  },
  {
    title: "중증·비중증 비급여 구분",
    summary: "중증 비급여와 비중증 비급여는 별도 특별약관입니다. 각 조항은 산정특례 대상 질환 여부와 보장종목을 다르게 규정하므로 비급여라는 이유만으로 같은 담보로 볼 수 없습니다.",
    advisorCheck: "실제 가입한 특별약관과 산정특례 대상 여부, 치료 항목을 확인하세요.",
    evidence: [
      { article: "특별약관1 제1조", page: 50, anchor: "산정특례 대상 질환으로 인한 비급여" },
      { article: "특별약관2 제1조", page: 62, anchor: "산정특례 대상 질환이 아닌 질환으로 인한 비급여" },
    ],
  },
  {
    title: "여러 실손 계약의 비례분담",
    summary: "다수보험의 경우 약관은 각 계약의 보장대상 의료비와 보장책임액을 기준으로 비례분담액을 계산하도록 정합니다.",
    advisorCheck: "다른 실손 계약의 존재와 각 계약의 공제금액·보장책임액을 확인하세요.",
    evidence: [
      { article: "보통약관 제38조", page: 41, anchor: "각 계약의 비례분담액을 지급합니다" },
    ],
  },
  {
    title: "1년 갱신과 비중증 비급여 차등",
    summary: "갱신계약 보험기간은 1년이고 보험료는 갱신 시 다시 계산됩니다. 약관 요약에는 비중증 비급여 특별약관2의 의료 이용량에 따른 5단계 보험료 차등을 2028년 5월 6일부터 적용한다고 기재합니다.",
    advisorCheck: "갱신일·갱신 안내와 특별약관2 가입 여부, 실제 적용 시점의 약관을 확인하세요.",
    evidence: [
      { article: "보통약관 제47조", page: 43, anchor: "갱신계약의 보험기간은 1 년으로 합니다" },
      { article: "보통약관 제52조", page: 43, anchor: "보험료는 갱신일 현재의 보험요율" },
      { article: "상품·약관 요약서", page: 10, anchor: "5 단계로 차등 ( 할인∙할증 ) 부과합니다" },
      { article: "상품·약관 요약서", page: 10, anchor: "2028 년 5 월 6 일부터 적용" },
    ],
  },
]
