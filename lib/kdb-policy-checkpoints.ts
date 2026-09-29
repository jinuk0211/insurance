export const KDB_RENEWAL_POLICY_DOCUMENT_ID = "kdb-direct-cancer-renewal-2026-04-01"
export const KDB_RENEWAL_POLICY_SHA256 = "73fda0712d0e484f0717299e2fcbe683347a2ae0b160b63d41e0bcf9925c2673"
export const KDB_STANDARD_POLICY_DOCUMENT_ID = "kdb-direct-cancer-standard-no-refund-2026-04-01"
export const KDB_STANDARD_POLICY_SHA256 = "0bb88e7957e9b29d3e3f963dc44012f6255067c1e55da51cf395d24c5761b1ae"

interface KDBPolicyCheckpoint {
  title: string
  summary: string
  advisorCheck: string
  evidence: Array<{ article: string; page: number; anchor: string }>
}

// Reading prompts for these PDF revisions; enrolled terms and benefit amounts require the customer's policy.
export const KDB_RENEWAL_POLICY_CHECKPOINTS: KDBPolicyCheckpoint[] = [
  {
    title: "최초·갱신·부활 암보장개시일",
    summary: "최초계약의 암 보장은 원칙적으로 계약일을 포함해 90일이 되는 날의 다음 날 시작합니다. 갱신계약은 갱신일, 부활한 계약은 부활일부터 다시 90일 규정을 봅니다. 15세 미만 예외가 있습니다.",
    advisorCheck: "최초·갱신·부활 여부, 해당 날짜, 피보험자 나이와 진단확정일을 확인하세요.",
    evidence: [
      { article: "주계약 제2조 4.나", page: 27, anchor: "암에 대한 보장개시일은 최초계약의" },
      { article: "주계약 제2조 4.나", page: 27, anchor: "갱신계약의 경우 갱 90 , 신일로 합니다" },
      { article: "주계약 제2조 4.나", page: 27, anchor: "부활 효력회복 일 . , ( ) ( ) 부터 그 날을 포함하여 일이 되는 날의 다음 날을 암보장개시일로 합니다 90" },
      { article: "주계약 제2조 4.나", page: 27, anchor: "피보험자의 나이가 세 미만인 경우 최초계약의 계약일" },
    ],
  },
  {
    title: "초기 2년 감액과 갱신계약",
    summary: "진단보험금은 최초계약의 계약일부터 2년 미만 진단 시 50%로 적혀 있습니다. 갱신계약에는 해당 감액을 적용하지 않는다고 별도로 정합니다.",
    advisorCheck: "계약일·갱신일과 진단일, 실제 가입금액 및 이전 지급 이력을 대조하세요.",
    evidence: [
      { article: "주계약 제10조", page: 32, anchor: "최초계약의 계약일부터 년 미만 진단시 지급 ( 1 . , 2 50% )" },
      { article: "주계약 제11조⑲", page: 34, anchor: "단보험금 또는 소액암진단보험금을 삭감하여 지급하지 않습니다" },
    ],
  },
  {
    title: "소액암과 일반암 분류",
    summary: "기타피부암·특정갑상선암·대장점막내암·비침습 방광암은 약관의 일반암 진단보험금 대신 각 소액암 진단보험금 조항을 확인합니다. 소액암도 분류별 최초 1회 규정이 있습니다.",
    advisorCheck: "병리 결과의 질병 분류와 이전 소액암 지급 기록을 확인하세요.",
    evidence: [
      { article: "주계약 제11조⑪", page: 33, anchor: "암에 해당하는 암진단보험금은 지급되지 않습니다" },
      { article: "주계약 제11조⑬", page: 34, anchor: "소액암진단보험금은 소액암 각각 최초 회에 한하여" },
    ],
  },
  {
    title: "자동갱신 조건과 보험료 변동",
    summary: "만기 15일 전 갱신 거절 통지 여부와 갱신계약 첫 보험료 납입 등이 자동갱신 조건에 포함됩니다. 갱신 시 나이와 보험요율에 따라 보험료가 변동될 수 있습니다.",
    advisorCheck: "갱신 통지·납입 상태, 갱신 가능 사유와 새 보험료를 증권 및 안내문에서 확인하세요.",
    evidence: [
      { article: "주계약 제24조①", page: 43, anchor: "보험기간이 끝나는 날의 일 전까지 계약을 갱신하지 않는 15" },
      { article: "주계약 제24조①", page: 43, anchor: "계약은 자동갱신 되는 것으로 합니다" },
      { article: "주계약 제24조⑤", page: 43, anchor: "갱신보험료가 변동될 수 있습니다" },
    ],
  },
]

export const KDB_STANDARD_POLICY_CHECKPOINTS: KDBPolicyCheckpoint[] = [
  {
    title: "암보장개시일과 15세 미만 예외",
    summary: "암 보장은 원칙적으로 계약일 또는 부활일부터 그 날을 포함해 90일이 되는 날의 다음 날 시작합니다. 계약일·부활일 현재 15세 미만이면 별도 예외가 있습니다.",
    advisorCheck: "계약·부활 날짜, 해당 시점의 나이와 진단확정일을 대조하세요.",
    evidence: [
      { article: "주계약 제2조 4.나", page: 27, anchor: "보장개시일은 계약일 또는" },
      { article: "주계약 제2조 4.나", page: 27, anchor: "일 현재 피보험자의 나이가 세 미만인" },
    ],
  },
  {
    title: "초기 2년 감액과 최초 1회",
    summary: "암진단보험금과 소액암진단보험금은 계약일부터 2년 미만 진단 시 50% 지급으로 적혀 있으며, 각 지급사유에는 최초 1회 조건이 있습니다.",
    advisorCheck: "진단 시점, 보험금 종류별 가입금액 및 이전 지급 이력을 확인하세요.",
    evidence: [
      { article: "주계약 제10조", page: 32, anchor: "계약일부터 년 미만 진단시 지급 ( 1 . , 2 50% )" },
      { article: "주계약 제11조⑫", page: 33, anchor: "소액암진단보험금은 소액암 각각 최초 회에 한하여" },
    ],
  },
  {
    title: "소액암과 일반암 분류",
    summary: "기타피부암·특정갑상선암·대장점막내암·비침습 방광암에는 각각의 소액암 진단보험금 조항을 적용하며, 해당 원인으로 일반암 진단보험금은 지급되지 않는다고 적혀 있습니다.",
    advisorCheck: "진단서와 병리 결과에 적힌 정확한 분류를 확인하세요.",
    evidence: [
      { article: "주계약 제11조⑩", page: 33, anchor: "암에 해당하는 암진단보험금은 지급되지 않습니다" },
    ],
  },
  {
    title: "해약환급금 미지급형Ⅲ의 중도 해지",
    summary: "해약환급금 미지급형Ⅲ을 선택한 계약은 보험료 납입기간 중 해지 시 환급금이 없고, 납입기간 경과 후에는 약관 표에 표준형 환급금의 50%로 적혀 있습니다. 표준형에는 이 표를 그대로 적용하지 않습니다.",
    advisorCheck: "증권에서 표준형인지 미지급형Ⅲ인지와 보험료 납입기간·미납 여부를 확인하세요.",
    evidence: [
      { article: "주계약 제40조 유의사항", page: 54, anchor: "해약환급금 미지급형Ⅲ 보험료 납입기간 중 없음" },
      { article: "주계약 제40조 유의사항", page: 54, anchor: "보험료 납입기간 경과 후 표준형 해약환급금 × 50%" },
      { article: "주계약 제40조 유의사항", page: 54, anchor: "미납된 보험료 [ ] , 를 모두 납입하여야" },
    ],
  },
]
