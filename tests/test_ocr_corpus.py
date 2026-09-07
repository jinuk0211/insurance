"""OCR candidates preserve source identity and cannot silently replace inputs."""
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from scripts_evolve.ocr_corpus import candidate_pages, combine_pages


def test_only_flagged_nearly_empty_pdf_pages_are_scheduled():
    row = {'status': 'needs_review', 'pages': 3, 'characters': 320, 'page_characters': [0, 300, 20]}
    assert candidate_pages(row) == [0, 2]
    assert candidate_pages({**row, 'status': 'success'}) == []
    assert candidate_pages({**row, 'characters': 1300}) == []
    assert candidate_pages({'status': 'needs_review', 'pages': None}) == []


def test_short_but_real_supplement_is_not_mistaken_for_an_empty_scan():
    assert candidate_pages({'status': 'needs_review', 'pages': 1, 'characters': 450, 'page_characters': [450]}) == []


def test_combining_ocr_keeps_unprocessed_pages_and_page_boundaries():
    original = ['', 'A complete contractual condition.', '']
    pages = {0: {'text': 'Scanned first page'}, 2: {'text': 'Scanned last page'}}
    text = combine_pages(original, pages)
    assert text == 'Scanned first page\n\f\nA complete contractual condition.\n\f\nScanned last page'
    assert original == ['', 'A complete contractual condition.', '']


def test_outside_page_and_blank_recovery_cannot_destroy_source():
    with pytest.raises(ValueError):
        combine_pages(['source'], {1: {'text': 'outside'}})
    assert combine_pages(['short original'], {0: {'text': '  '}}) == 'short original'


def test_recovery_persists_coordinates_and_verifies_cache(tmp_path, monkeypatch):
    import scripts_evolve.ocr_corpus as module
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    source = tmp_path / 'scan.pdf'
    source.write_bytes(b'original PDF bytes')
    calls = []
    class Page:
        rect = SimpleNamespace(width=600, height=800)
        def get_text(self):
            return ''
        def get_textpage_ocr(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(extractText=lambda: 'Recognized contract condition. ' * 100,
                                   extractWORDS=lambda: [(1, 2, 3, 4, 'Recognized', 0, 0, 0)],
                                   extractBLOCKS=lambda: [(1, 2, 3, 4, 'Recognized', 0, 0)])
    monkeypatch.setattr(module.pymupdf, 'open', lambda path: nullcontext([Page()]))
    row = {'doc_id': 'us_card-scan', 'domain': 'us_card', 'source_path': 'scan.pdf',
           'source_sha256': module.sha256(source.read_bytes()), 'text_sha256': module.sha256(b''),
           'status': 'needs_review', 'pages': 1, 'characters': 0, 'page_characters': [0]}
    result = module.recover(row, str(tmp_path / 'out'), str(tmp_path / 'models'), {'test': True})
    assert result['status'] == 'ocr_candidate'
    assert result['ready_for_model'] is False and result['layout_review_required'] is True
    assert calls[0]['language'] == 'eng' and calls[0]['full'] is True
    assert module.recover(row, str(tmp_path / 'out'), str(tmp_path / 'models'), {'test': True}) == result
    assert len(calls) == 1
    (tmp_path / 'out/documents/us_card-scan/page_0000.json').write_text('{}')
    with pytest.raises(ValueError, match='artifact changed'):
        module.recover(row, str(tmp_path / 'out'), str(tmp_path / 'models'), {'test': True})
