"""Publish the frozen, public-document pilot without local paths or customer data."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "output/analysis/luna_pilot_2026-09-21"
PUBLIC = ROOT / "public/research/luna-pilot"


def read(name):
    return json.loads((SOURCE / name).read_text(encoding="utf-8-sig"))


def main():
    manifest = read("manifest.json")
    validation = read("grounding_validation.json")
    checks = {r["id"]: r for d in validation["documents"] for r in d["rules"]}
    raw = {d["doc_id"]: d for batch in ("a", "b") for d in read(f"extraction_{batch}.json")["documents"]}
    issues = {
        "D02-R01": {"title": "암 담보의 예외가 빠졌습니다", "detail": "90일 조건은 암 보장에 적용됩니다. 원문은 기타피부암·제자리암·경계성종양·중증 이외 갑상선암·대장점막내암을 계약일부터 보장하는 예외로 구분합니다.", "pages": [1]},
        "D03-R01": {"title": "담보별 보장개시일을 구분해야 합니다", "detail": "표지를 근거로 상품 전체에 90일을 적용했습니다. 8쪽 표의 여성 4대 특정 질환·특정 부인과 질환 등의 급부는 계약일부터 보장합니다.", "pages": [8]},
        "D03-R02": {"title": "감액하지 않는 담보까지 일반화했습니다", "detail": "원문 8쪽에는 감액하지 않는 입원·수술 담보가 있습니다. 17쪽은 50% 감액 범위를 약관 제11조 제2호부터 제11호의 급부로 제한합니다.", "pages": [8, 17]},
        "D02-R08": {"title": "인용문이 결론을 뒷받침하지 않습니다", "detail": "청구서류가 필요하다는 주장에 보험가격지수 표를 인용했습니다. 인용문이 존재해도 해당 주장의 근거라는 뜻은 아닙니다.", "pages": [8]},
    }
    PUBLIC.mkdir(parents=True, exist_ok=True)
    documents = []
    for meta in manifest["documents"]:
        source = Path(meta["source_path"])
        assert hashlib.sha256(source.read_bytes()).hexdigest() == meta["sha256"], meta["doc_id"]
        doc_id = meta["doc_id"]
        shutil.copyfile(source, PUBLIC / f"{doc_id}.pdf")
        rules = []
        for rule in raw[doc_id]["rules"]:
            rules.append({**rule, "quotesMatched": checks[rule["id"]]["all_evidence_found"], "issue": issues.get(rule["id"])})
        documents.append({"id": doc_id, "name": meta["filename"].removesuffix(".pdf").replace("_", " "), "category": meta["category"], "documentType": "상품요약서", "pages": meta["total_pages"], "sha256": meta["sha256"], "pdfPath": f"/research/luna-pilot/{doc_id}.pdf", "rules": rules, "unknownFields": raw[doc_id].get("unknown_fields", [])})
    result = {"date": "2026-09-21", "model": "gpt-5.6-luna", "reasoning": "low", "sourceType": "상품요약서", "samplingSeed": manifest["seed"], "documentCount": len(documents), "pageCount": sum(d["pages"] for d in documents), "ruleCount": sum(len(d["rules"]) for d in documents), "matchedCount": sum(r["quotesMatched"] for d in documents for r in d["rules"]), "issueCount": len(issues), "documents": documents}
    assert (result["documentCount"], result["pageCount"], result["ruleCount"], result["matchedCount"]) == (5, 99, 53, 35)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    assert "D:\\" not in text and "D:/" not in text
    (ROOT / "lib/generated/luna-pilot.json").write_text(text, encoding="utf-8")
    (PUBLIC / "results.json").write_text(text, encoding="utf-8")
    print(f"Published {len(documents)} public PDFs and {result['ruleCount']} frozen rules.")


if __name__ == "__main__":
    main()
