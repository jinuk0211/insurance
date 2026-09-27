export const DB_POLICY_DOCUMENT_ID = "db-direct-cancer-2607"
export const DB_POLICY_SHA256 = "d9525158bda7f6f7a7cb44e68118a683c3813b86a548d8a0a23532e6a92e108e"

export interface DBPolicyCheckpoint {
  title: string
  summary: string
  advisorCheck: string
  evidence: Array<{ article: string; page: number; anchor: string }>
}

// Reading prompts for this PDF revision; a customer's enrolled riders still require proof.
export const DB_POLICY_CHECKPOINTS: DBPolicyCheckpoint[] = [
  {
    title: "암 보장개시일과 갱신·부활",
    summary: "암진단비Ⅱ(유사암제외) 담보는 최초계약에서 계약일을 포함해 90일이 지난 다음 날 보장을 시작합니다. 갱신계약은 갱신일이고, 실효 후 부활에는 다시 90일 규정이 적용됩니다.",
    advisorCheck: "실제 가입 담보, 최초·갱신·부활 상태와 진단일을 대조하세요.",
    evidence: [
      { article: "암진단비Ⅱ 1.②", page: 58, anchor: "보험계약일로부터 그 날을 포함하여 90일이 지난날의 다음날" },
      { article: "암진단비Ⅱ 1.②", page: 58, anchor: "갱신형(갱신계약) 이 담보의 갱신일" },
      { article: "암진단비Ⅱ 5.", page: 59, anchor: "부활(효력회복)일로부터 그 날을 포함하여 90일이 지난날의 다음날" },
    ],
  },
  {
    title: "초기 2년 감액과 최초 1회",
    summary: "암진단비Ⅱ(유사암제외)는 최초계약에서 보험계약일부터 2년 미만이면 가입금액의 50%, 2년 이상이면 100%로 적혀 있습니다. 갱신계약은 100%이며 담보 지급은 최초 1회입니다.",
    advisorCheck: "가입금액, 최초계약일·갱신일과 이전 지급 이력을 확인하세요.",
    evidence: [
      { article: "암진단비Ⅱ 1.①", page: 58, anchor: "보험계약일로부터 2년미만 보험가입금액의 50%" },
      { article: "암진단비Ⅱ 1.①", page: 58, anchor: "보험계약일로부터 2년이상 보험가입금액의 100%" },
      { article: "암진단비Ⅱ 1.", page: 58, anchor: "진단확정된 경우 최초 1회에 한하여" },
    ],
  },
  {
    title: "유사암 네 분류의 별도 지급",
    summary: "유사암진단비Ⅱ는 제자리암·경계성종양·기타피부암·갑상선암을 나누고, 각 분류에 대해 1회 지급 조항을 둡니다. 일반암진단비와 상품명만으로 합산하지 않습니다.",
    advisorCheck: "진단서의 분류와 유사암 담보 가입·과거 지급 여부를 확인하세요.",
    evidence: [
      { article: "유사암진단비Ⅱ 1.", page: 60, anchor: "제자리암, 경계성종양, 기타피부암, 갑상선암으로 진단확정된 경우 각각 1회" },
      { article: "유사암진단비Ⅱ 1.", page: 60, anchor: "보험가입금액의 100%" },
    ],
  },
  {
    title: "원발부위와 진단확정 시점",
    summary: "암(유사암제외) 분류는 원발부위가 확인되면 그 부위를 기준으로 하고, 진단확정 시점은 원칙적으로 지정된 검사 결과보고 시점입니다. 전이 부위 코드나 최초 진료일만으로 판단하지 않습니다.",
    advisorCheck: "원발암·전이 기록, 병리 또는 진단검사의학 결과보고서를 확인하세요.",
    evidence: [
      { article: "암진단비Ⅱ 3. 유의사항", page: 59, anchor: "원발부위(최초 발생한 부위)를 기준으로 분류합니다" },
      { article: "암진단비Ⅱ 3.⑤", page: 59, anchor: "진단확정 시점은 상기 검사에 의한 결과보고 시점" },
    ],
  },
  {
    title: "보장개시 전 진단과 담보 무효",
    summary: "암진단비Ⅱ(유사암제외) 담보는 보험계약일부터 보장개시일 전일까지 해당 암이 진단확정되면 담보를 무효로 하고 이미 납입한 보험료를 돌려준다고 정합니다.",
    advisorCheck: "계약일, 보장개시일과 결과보고 시점, 실제 가입 담보를 대조하세요.",
    evidence: [
      { article: "암진단비Ⅱ 4.", page: 59, anchor: "보장개시일(책임개시일)의 전일 이전에 암" },
      { article: "암진단비Ⅱ 4.", page: 59, anchor: "담보는 무효로 하며, 이미 납입한 보험료를 돌려드립니다" },
    ],
  },
]
