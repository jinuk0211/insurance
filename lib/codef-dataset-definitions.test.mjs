import test from "node:test"
import assert from "node:assert/strict"
import { CODEF_DATASETS, normalizeTelecom } from "./codef-dataset-definitions.ts"
import { buildCodefDatasetParams } from "./codef-dataset-params.ts"

test("uses the official CODEF medical and pension endpoints", () => {
  assert.equal(CODEF_DATASETS.medical_treatment.endpoint, "/v1/kr/public/pp/nhis-treatment/information")
  assert.equal(CODEF_DATASETS.medical_history.endpoint, "/v1/kr/public/pp/nhis-list/medical-history")
  assert.equal(CODEF_DATASETS.nps_expected.endpoint, "/v1/kr/public/pp/nps-minwon/expect-mypension")
  assert.equal(CODEF_DATASETS.nps_history.endpoint, "/v1/kr/public/pp/nps-minwon/member-join-history")
  assert.equal(CODEF_DATASETS.pension_all.endpoint, "/v1/kr/public/fs/my-pension/search")
})
test("maps MVNO telecom codes without collecting a resident registration number", () => {
  assert.equal(normalizeTelecom("3"), "0")
  assert.equal(normalizeTelecom("4"), "1")
  assert.equal(normalizeTelecom("5"), "2")

  const params = buildCodefDatasetParams({
    datasetKey: "medical_treatment",
    userName: "김가온",
    birthDate: "19900101",
    phoneNo: "01012345678",
    telecom: "3",
  })
  assert.equal(params.organization, "0002")
  assert.equal(params.loginType, "5")
  assert.equal(params.loginTypeLevel, "5")
  assert.equal(params.identity, "19900101")
  assert.equal(params.telecom, "0")
  assert.equal("identityBack" in params, false)
})

test("uses PASS identity verification for the integrated pension portal", () => {
  const params = buildCodefDatasetParams({
    datasetKey: "pension_all",
    userName: "김가온",
    birthDate: "19900101",
    phoneNo: "01012345678",
    telecom: "1",
  })
  assert.equal(params.organization, "0001")
  assert.equal(params.loginType, "4")
  assert.equal(params.authMethod, "1")
  assert.equal(params.personalInfoYN, "1")
  assert.equal(params.personalInfoYN1, "1")
  assert.equal("identity" in params, false)
})
