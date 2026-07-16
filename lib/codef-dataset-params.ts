import { createHash } from "node:crypto"
import {
  CODEF_DATASETS,
  normalizeTelecom,
  type CodefDatasetInput,
} from "./codef-dataset-definitions.ts"

function opaqueRequestId(input: CodefDatasetInput): string {
  return createHash("sha256")
    .update(`${input.phoneNo}|${input.birthDate}|${input.datasetKey}`)
    .digest("hex")
    .slice(0, 32)
}

export function buildCodefDatasetParams(input: CodefDatasetInput): Record<string, unknown> {
  const telecom = normalizeTelecom(input.telecom)
  const commonSimpleAuth = {
    loginType: "5",
    loginTypeLevel: "5",
    userName: input.userName.trim(),
    identity: input.birthDate,
    phoneNo: input.phoneNo.replace(/\D/g, ""),
    telecom,
    id: opaqueRequestId(input),
  }

  switch (input.datasetKey) {
    case "medical_treatment":
      return {
        organization: "0002",
        ...commonSimpleAuth,
        timeOut: "170",
        startDate: input.startDate || "",
        endDate: input.endDate || "",
        type: "0",
        drugImageYN: "0",
        medicationDirectionYN: "0",
        detailYN: "0",
      }
    case "medical_history":
      return {
        organization: "0002",
        ...commonSimpleAuth,
        examinee: "",
        startDate: input.startDate || "",
        endDate: input.endDate || "",
      }
    case "nps_expected":
    case "nps_history":
      return {
        organization: "0001",
        ...commonSimpleAuth,
      }
    case "pension_all":
      return {
        organization: "0001",
        loginType: "4",
        authMethod: "1",
        userName: input.userName.trim(),
        phoneNo: input.phoneNo.replace(/\D/g, ""),
        telecom,
        personalInfoYN: "1",
        personalInfoYN1: "1",
      }
    default: {
      const exhaustive: never = input.datasetKey
      throw new Error(`지원하지 않는 데이터셋: ${exhaustive}`)
    }
  }
}

export function codefDatasetEndpoint(input: CodefDatasetInput): string {
  return CODEF_DATASETS[input.datasetKey].endpoint
}
