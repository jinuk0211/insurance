import test from "node:test"
import assert from "node:assert/strict"

import { buildInsuranceDashboardModel } from "./insurance-dashboard.ts"
import { INSURANCE_DEMO_DATA } from "./insurance-demo-data.ts"

test("normalizes nested CODEF coverage items without converting missing amounts to zero", () => {
  const model = buildInsuranceDashboardModel({
    result: {
      resContractList: [
        {
          resContractNo: "POLICY-1",
          resInsuranceName: "암 건강보험",
          resCompanyName: "테스트생명",
          resContractStatus: "정상",
          resMonthlyPremium: 50000,
          resContractStartDate: "20240510",
          resContractEndDate: "20840510",
          resCoverageList: [
            { resCoverageName: "일반암 진단비", resCoverageAmount: 30000000 },
            { resCoverageName: "갑상선암 진단비", resCoverageAmount: "" },
          ],
        },
      ],
    },
  })

  assert.equal(model.coverageItems.length, 2)
  assert.equal(model.coverageItems[0].amount, 30000000)
  assert.equal(model.coverageItems[1].amount, null)
  assert.equal(model.dataQuality.coverageAmountKnownCount, 1)
  assert.equal(model.dataQuality.coverageAmountMissingCount, 1)
  assert.equal(model.categories.find((category) => category.id === "cancer")?.knownAmount, 30000000)
})

test("keeps contract-name matches separate from confirmed coverage evidence", () => {
  const model = buildInsuranceDashboardModel({
    result: {
      resContractList: [
        {
          resContractNo: "POLICY-2",
          resInsuranceName: "프리미엄 암보험",
          resCompanyName: "테스트손보",
          resContractStatus: "정상",
          resMonthlyPremium: 42000,
          resContractStartDate: "20240101",
          resContractEndDate: "20440101",
        },
      ],
    },
  })

  const cancer = model.categories.find((category) => category.id === "cancer")
  assert.equal(cancer?.signal, "related_contract")
  assert.equal(cancer?.evidenceKind, "contract_name")
  assert.equal(cancer?.knownAmount, 0)
  assert.equal(model.coverageItems.length, 0)
})

test("prioritizes treatment and surgery classifications over broad disease keywords", () => {
  const model = buildInsuranceDashboardModel({
    result: {
      resContractList: [{
        resContractNo: "POLICY-3",
        resInsuranceName: "건강보험",
        resCompanyName: "테스트생명",
        resContractStatus: "정상",
        resCoverageList: [
          { resCoverageName: "갑상선암 항암약물치료비", resCoverageAmount: 10000000 },
          { resCoverageName: "암 직접치료 수술비", resCoverageAmount: 2000000 },
        ],
      }],
    },
  })

  assert.equal(model.coverageItems[0].standardCategoryId, "treatment")
  assert.equal(model.coverageItems[1].standardCategoryId, "surgery")
})

test("builds the end-to-end advisor demo enrichment", () => {
  const model = buildInsuranceDashboardModel(INSURANCE_DEMO_DATA)

  assert.ok(model.contracts.length >= 7)
  assert.ok(model.coverageItems.length >= 10)
  assert.ok(model.enrichment.documents.length >= 4)
  assert.ok(model.enrichment.decisionScenarios.length >= 3)
  assert.ok(model.enrichment.proposals.length >= 1)
  assert.ok(model.dataQuality.overallScore > 0)
})
