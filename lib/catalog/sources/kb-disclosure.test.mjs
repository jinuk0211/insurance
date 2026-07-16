import assert from "node:assert/strict"
import test from "node:test"

import { parseKbProductList, parseKbProductVersions } from "./kb-disclosure.ts"

const listingHtml = `
  <table class="tb_list"><tbody>
    <tr><td>판매중</td><td>질병보험</td><td>25033</td>
      <td><a href="javascript:detail('25033','d','1');">KB 암보험</a></td></tr>
    <tr><td>판매종료</td><td>질병보험</td><td>10101</td>
      <td><a href="javascript:detail('10101','d','2');">KB 옛날 암보험</a></td></tr>
  </tbody></table>`

const detailHtml = `
  <table class="tb_view"><tbody><tr><td>
    <table class="tb_default04"><tbody>
      <tr><td>20260101</td><td>20260131</td>
        <td><a href="/CG802030003.ec?fileNm=25033_1_1.pdf"><img alt="보험약관"></a></td>
        <td><a href="/CG802030003.ec?fileNm=25033_1_2.pdf"><img alt="사업방법서"></a></td>
        <td><a href="/CG802030003.ec?fileNm=25033_1_3.pdf"><img alt="상품요약서"></a></td><td></td>
      </tr>
      <tr><td>20260201</td><td></td>
        <td><a href="/CG802030003.ec?fileNm=25033_2_1.pdf"><img alt="보험약관"></a></td>
        <td></td><td></td><td></td>
      </tr>
    </tbody></table>
  </td></tr></tbody></table>`

test("parses product code, status and detail identifiers from the disclosure list", () => {
  const products = parseKbProductList(listingHtml)
  assert.deepEqual(products, [
    {
      externalProductCode: "25033",
      name: "KB 암보험",
      productType: "질병보험",
      saleStatus: "on_sale",
      detailGroup: "d",
      detailSequence: "1",
    },
    {
      externalProductCode: "10101",
      name: "KB 옛날 암보험",
      productType: "질병보험",
      saleStatus: "off_sale",
      detailGroup: "d",
      detailSequence: "2",
    },
  ])
})

test("parses only the version table and classifies its official documents", () => {
  const listing = parseKbProductList(listingHtml)[0]
  const versions = parseKbProductVersions(detailHtml, listing)
  assert.equal(versions.length, 2)
  assert.equal(versions[0].versionKey, "2026-01-01")
  assert.equal(versions[0].effectiveTo, "2026-01-31")
  assert.deepEqual(versions[0].documents.map((document) => document.kind), [
    "terms",
    "business_method",
    "product_summary",
  ])
  assert.equal(versions[1].documents[0].fileName, "25033_2_1.pdf")
})
