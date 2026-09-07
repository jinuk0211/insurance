"""Local OCR candidates for nearly empty PDF pages; never replace frozen inputs.

Persist recognized text AND word coordinates for layout review. In particular,
two-column OCR reading order is not certified by a character-count threshold.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path

import pymupdf

from scripts_evolve.full_corpus_v2 import ROOT, quality_flags, sha256, write_once


def candidate_pages(row: dict) -> list[int]:
    if row['status'] != 'needs_review' or not row['pages'] or row['characters'] >= 1000:
        return []
    return [i for i, count in enumerate(row['page_characters']) if count < 40]


def combine_pages(original: list[str], recovered: dict[int, dict]) -> str:
    if any(i < 0 or i >= len(original) for i in recovered):
        raise ValueError('OCR page outside original document')
    return '\n\f\n'.join(recovered[i]['text'] if i in recovered and recovered[i]['text'].strip() else text
                          for i, text in enumerate(original))


def recover(row: dict, output_string: str, models_string: str, protocol: dict) -> dict:
    output, models = Path(output_string), Path(models_string)
    folder = output / 'documents' / row['doc_id']
    source = (ROOT / row['source_path']).resolve()
    if not source.is_relative_to(ROOT) or sha256(source.read_bytes()) != row['source_sha256']:
        raise ValueError('Original PDF identity mismatch')
    path = folder / 'result.json'
    if path.exists():
        previous = json.loads(path.read_text(encoding='utf-8'))
        if previous['source_sha256'] != row['source_sha256'] or previous['protocol'] != protocol:
            raise ValueError('OCR cache identity changed')
        for relative, expected in previous['artifact_sha256'].items():
            if sha256((folder / relative).read_bytes()) != expected:
                raise ValueError('OCR cache artifact changed')
        return previous
    language = 'kor+eng' if row['domain'] == 'kr_insurance' else 'eng'
    result = {'doc_id': row['doc_id'], 'domain': row['domain'], 'source_path': row['source_path'],
              'source_sha256': row['source_sha256'], 'protocol': protocol, 'language': language,
              'status': 'failure', 'layout_review_required': True, 'ready_for_model': False}
    try:
        recovered = {}
        with pymupdf.open(source) as document:
            original = [page.get_text() for page in document]
            if sha256('\n\f\n'.join(original).encode()) != row['text_sha256']:
                raise ValueError('Prior native extraction is not reproducible')
            for index in candidate_pages(row):
                page = document[index]
                textpage = page.get_textpage_ocr(language=language, dpi=220, full=True, tessdata=str(models))
                page_result = {'page_index': index, 'native_characters': len(original[index]),
                               'width': page.rect.width, 'height': page.rect.height,
                               'text': textpage.extractText(), 'words': [list(w) for w in textpage.extractWORDS()],
                               'blocks': [list(b) for b in textpage.extractBLOCKS()]}
                recovered[index] = page_result
                write_once(folder / f'page_{index:04}.json', page_result)
        text = combine_pages(original, recovered)
        folder.mkdir(parents=True, exist_ok=True)
        text_path = folder / 'candidate.txt'
        if text_path.exists():
            if text_path.read_bytes() != text.encode():
                raise ValueError('Existing OCR candidate differs')
        else:
            with text_path.open('xb') as handle:
                handle.write(text.encode())
        result.update(status='ocr_candidate', native_characters=row['characters'], candidate_characters=len(text),
                      ocr_pages=sorted(recovered), mechanical_issues=quality_flags(text),
                      text_path=text_path.relative_to(ROOT).as_posix(), text_sha256=sha256(text.encode()))
    except (OSError, ValueError, RuntimeError, pymupdf.FileDataError) as exc:
        result.update(error_type=type(exc).__name__, error=str(exc))
    result['artifact_sha256'] = {p.relative_to(folder).as_posix(): sha256(p.read_bytes())
                                 for p in folder.glob('*') if p.is_file() and p.name != 'result.json'}
    write_once(path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'research/dataset_3000_ocr_v1')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    output, models = args.output.resolve(), args.models.resolve()
    if not output.is_relative_to(ROOT / 'research') or not models.is_relative_to(ROOT) or not 1 <= args.workers <= 4:
        parser.error('Use workspace model data, a research output, and 1..4 workers')
    manifest = ROOT / 'research/dataset_3000_v2/extraction_manifest.json'
    candidates = [r for r in json.loads(manifest.read_text(encoding='utf-8'))['documents'] if candidate_pages(r)]
    protocol = {'engine': 'PyMuPDF integrated Tesseract', 'pymupdf_version': pymupdf.VersionBind, 'dpi': 220,
                'script_sha256': sha256(Path(__file__).read_bytes()),
                'quality_helper_sha256': sha256(Path(__file__).with_name('full_corpus_v2.py').read_bytes()),
                'parent_manifest_sha256': sha256(manifest.read_bytes()),
                'models': {name: sha256((models / (name + '.traineddata')).read_bytes()) for name in ('eng', 'kor')},
                'model_repository_commit': 'tesseract-ocr/tessdata_fast@87416418657359cb625c412a48b6e1d6d41c29bd',
                'policy': 'Nearly empty pages of already flagged PDFs only. Candidates require layout/semantic review; '
                          'native source and the fixed 3,000-input roster are not overwritten.'}
    write_once(output / 'selection.json', {'protocol': protocol, 'documents': candidates})
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(recover, row, str(output), str(models), protocol) for row in candidates]
        for future in as_completed(futures):
            row = future.result()
            results.append(row)
            print(json.dumps({'processed': len(results), 'total': len(candidates), 'doc_id': row['doc_id'],
                              'status': row['status'], 'candidate_characters': row.get('candidate_characters')}), flush=True)
    results.sort(key=lambda r: r['doc_id'])
    summary = {'documents': len(results), 'ocr_candidates': sum(r['status'] == 'ocr_candidate' for r in results),
               'failures': sum(r['status'] == 'failure' for r in results), 'ready_for_model': False,
               'layout_review_required': True, 'fixed_main_cohort_size': 3000}
    write_once(output / 'manifest.json', {'protocol': protocol, 'summary': summary, 'documents': results})
    print(json.dumps(summary), flush=True)
    return int(summary['failures'] > 0)


if __name__ == '__main__':
    raise SystemExit(main())
