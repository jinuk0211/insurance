export const CODEF_DATASETS = {
  medical_treatment: {
    key: "medical_treatment",
    domain: "medical",
    label: "진료 및 투약정보",
    description: "최근 진료기관, 방문일수, 처방 및 투약내역",
    source: "국민건강보험공단 건강iN",
    menuCode: "KR_PB_PP_018",
    endpoint: "/v1/kr/public/pp/nhis-treatment/information",
    requiresPeriod: false,
  },
  medical_history: {
    key: "medical_history",
    domain: "medical",
    label: "진료받은 내용",
    description: "최근 14개월 전부터 1년간의 진료비 심사 반영 내역",
    source: "국민건강보험공단 민원여기요",
    menuCode: "KR_PB_PP_019",
    endpoint: "/v1/kr/public/pp/nhis-list/medical-history",
    requiresPeriod: true,
  },
  nps_expected: {
    key: "nps_expected",
    domain: "pension",
    label: "예상노령연금",
    description: "현재 산정기준 예상연금액과 수급개시 시점",
    source: "국민연금공단",
    menuCode: "KR_PB_PP_010",
    endpoint: "/v1/kr/public/pp/nps-minwon/expect-mypension",
    requiresPeriod: false,
  },
  nps_history: {
    key: "nps_history",
    domain: "pension",
    label: "국민연금 가입내역",
    description: "가입월수, 납부액, 예상 월 연금액",
    source: "국민연금공단",
    menuCode: "KR_PB_PP_056",
    endpoint: "/v1/kr/public/pp/nps-minwon/member-join-history",
    requiresPeriod: false,
  },
  pension_all: {
    key: "pension_all",
    domain: "pension",
    label: "통합연금 조회",
    description: "국민·퇴직·개인·공무원·사학·주택연금 통합 현황",
    source: "금융감독원 통합연금포털",
    menuCode: "KR_PB_FS_001",
    endpoint: "/v1/kr/public/fs/my-pension/search",
    requiresPeriod: false,
  },
} as const

export type CodefDatasetKey = keyof typeof CODEF_DATASETS
export type CodefDatasetDomain = (typeof CODEF_DATASETS)[CodefDatasetKey]["domain"]

export interface CodefDatasetInput {
  datasetKey: CodefDatasetKey
  userName: string
  birthDate: string
  phoneNo: string
  telecom: string
  startDate?: string
  endDate?: string
}
export function isCodefDatasetKey(value: string): value is CodefDatasetKey {
  return Object.prototype.hasOwnProperty.call(CODEF_DATASETS, value)
}

export function normalizeTelecom(value: string): "0" | "1" | "2" {
  if (value === "1" || value === "4") return "1"
  if (value === "2" || value === "5") return "2"
  return "0"
}
