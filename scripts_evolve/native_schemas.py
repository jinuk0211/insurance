"""Typed write deltas for the original TXT harness roles; no pilot labels."""
from copy import deepcopy


def obj(properties: dict) -> dict:
    return {'type': 'object', 'properties': properties, 'required': list(properties),
            'additionalProperties': False}


def array(items: dict) -> dict:
    return {'type': 'array', 'items': items}


TEXT = {'type': 'string', 'minLength': 1}
SCORE = {'type': 'number', 'minimum': 0, 'maximum': 1}
INDEX = {'type': 'integer', 'minimum': 0}
SPOT = obj({'findings': array(obj({
    'clause_id': TEXT, 'vuln_id': {'type': 'string', 'enum': [f'INS-{i:02}' for i in range(1, 6)]},
    'vuln_name': TEXT, 'triggered_by': TEXT, 'user_relevance_score': SCORE,
    'confidence': {'type': 'number', 'minimum': 0, 'maximum': .9}, 'retrieval_query': TEXT,
}))})
VALIDATE = obj({'decisions': array(obj({
    'finding_index': INDEX, 'status': {'type': 'string', 'enum': ['CONFIRMED', 'UNVERIFIED', 'REJECTED']},
    'confidence': SCORE,
    'statutes': array(obj({'law_name': TEXT, 'article': TEXT})),
    'precedents': array(obj({'case_number': TEXT, 'relevance_score': SCORE})),
    'rejection_reason': {'type': ['string', 'null']}, 'validator_note': TEXT,
}))})
REPORT = obj({
    'executive_summary': TEXT,
    'findings': array(obj({
        'finding_index': INDEX,
        'plain_language_explanation': {**TEXT, 'maxLength': 150},
        'user_impact': {**TEXT, 'maxLength': 100},
        'estimated_risk_scenario': {**TEXT, 'maxLength': 200},
        'recommended_actions': {**array(obj({'action': TEXT, 'priority': TEXT,
            'contact': {'type': ['string', 'null'],
                        'enum': [None, '금융감독원(1332)', '한국소비자원(1372)', '금융분쟁조정위원회']}})),
            'minItems': 1, 'maxItems': 3},
    })),
    'general_recommendations': array(TEXT),
})


def spotting_schema(clause_count: int, max_lines: int) -> dict:
    fields = deepcopy(SPOT['properties']['findings']['items']['properties'])
    del fields['clause_id']
    del fields['triggered_by']
    fields.update(clause_index={'type': 'integer', 'minimum': 0, 'maximum': clause_count - 1},
                  first_line={'type': 'integer', 'minimum': 0, 'maximum': max_lines - 1},
                  last_line={'type': 'integer', 'minimum': 0, 'maximum': max_lines - 1})
    return obj({'findings': array(obj(fields))})


def indexed_schema(base: dict, field: str, indexes: list[int]) -> dict:
    """Require every requested finding as a named key, eliminating row omission."""
    schema = deepcopy(base)
    row = deepcopy(base['properties'][field]['items']['properties'])
    del row['finding_index']
    schema['properties'][field] = obj({str(i): obj(deepcopy(row)) for i in indexes})
    return schema
