import test from "node:test"
import assert from "node:assert/strict"
import { normalizeCodefDataset } from "./codef-dataset-normalizer.ts"

test("normalizes medical visits and medication details without patient identifiers", () => {
  const result = normalizeCodefDataset("medical_treatment", [{
    resHospitalName: "가온의원",
    resTreatStartDate: "20260102",
    resTreatType: "일반외래",
    resVisitDays: "1",
    resPrescribeCnt: "1",
    resMediDetailList: [{
      resPrescribeDrugName: "테스트정",
      resPrescribeDrugEffect: "항히스타민제",
      resTreatDate: "20260102",
      resPrescribeDays: "3",
    }],
    resUserNm: "저장하면 안 되는 이름",
  }])

  assert.equal(result.kind, "medical")
  assert.equal(result.recordCount, 1)
  assert.equal(result.hospitalCount, 1)
  assert.equal(result.medicationCount, 1)
  assert.equal(result.visits[0].medications[0].name, "테스트정")
  assert.equal("resUserNm" in result.visits[0], false)
})
test("normalizes National Pension expected monthly amount", () => {
  const result = normalizeCodefDataset("nps_expected", {
    resNowPensionAmt: "1,250,000",
    resPostTaxNowPensionAmt: "1,210,000",
    resPensionPayDate: "204503",
    resExpectTotalPay: "98,000,000",
    resExpectTotalPayMonth: "240",
  })
  assert.equal(result.kind, "pension")
  assert.equal(result.monthlyExpected, 1_250_000)
  assert.equal(result.postTaxMonthlyExpected, 1_210_000)
  assert.equal(result.paidMonths, 240)
})

test("normalizes integrated public, retirement and private pension products", () => {
  const result = normalizeCodefDataset("pension_all", {
    resNationalPensionList: [{ resPensionType: "노령연금", resExpectPension: "800000" }],
    resRetirementPensionList: [{ resCompanyNm: "가온은행", resProductName: "DC", resReserve: "50000000", resExpectPension: "300000" }],
    resPrivatePensionList: [{ resCompanyNm: "누리생명", resProductName: "연금보험", resReserve: "20000000", resExpectPension: "150000" }],
  })
  assert.equal(result.kind, "pension")
  assert.equal(result.accountCount, 3)
  assert.equal(result.monthlyExpected, 1_250_000)
  assert.equal(result.reserve, 70_000_000)
  assert.deepEqual(result.products.map((item) => item.category), ["국민연금", "퇴직연금", "개인연금"])
})
