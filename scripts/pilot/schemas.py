"""Provider-side JSON grammars; semantic/range checks still run locally."""

def object_schema(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def rows_schema(key: str, fields: dict, max_items: int = 6) -> dict:
    return object_schema({key: {"type": "array", "items": object_schema(fields),
                                "maxItems": max_items}})


STRING = {"type": "string"}
STRINGS = {"type": "array", "items": STRING}
FINDINGS = rows_schema("findings", {key: STRING for key in
                       ("id", "category", "quote", "explanation", "retrieval_query")})
REFERENCES = rows_schema("issues", {
    **{key: STRING for key in ("id", "explanation", "query")},
    "quote_passage_ids": STRINGS,
    "relevant_passage_ids": STRINGS})
JUDGMENTS = rows_schema("judgments", {"id": STRING,
    "status": {"type": "string", "enum": ["supported", "unsupported", "uncertain"]},
    "reason": STRING, "relevant_ref_ids": STRINGS})
CONFIG = object_schema({"instruction": STRING,
    "preprocessor": {"type": "string", "enum": ["raw", "layout_cleanup"]},
    "retriever": {"type": "string", "enum": ["bm25", "tfidf", "rrf"]},
    "k1": {"type": "number"}, "b": {"type": "number"}})
PROPOSAL = object_schema({"config": CONFIG, "rationale": STRING})


def legal_schema(authority_ids: list[str]) -> dict:
    return rows_schema("queries", {"issue_id": STRING, "query": STRING,
        "relevance": object_schema({key: {"type": "integer", "enum": [0, 1, 2, 3]}
                                    for key in authority_ids}),
        "rationales": object_schema({key: STRING for key in authority_ids}),
        "applicability": object_schema({key: {"type": "string", "enum":
            ["supported", "not_applicable", "uncertain"]} for key in authority_ids}),
        "jurisdiction_note": STRING})
