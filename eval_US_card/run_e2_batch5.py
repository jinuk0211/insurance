"""
2025_Q2 에서 PDF 5개를 뽑아 e2_input_format_us.py 실험 실행
(subprocess로 각 PDF 처리 후 결과 합산)
"""
import json, subprocess, sys, io
from pathlib import Path
from collections import defaultdict

# Windows cp949 터미널에서 UTF-8 출력 강제
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

Q2_DIR = Path(__file__).parent.parent / "2025_Q2"
SCRIPT  = Path(__file__).parent / "e2_input_format_us.py"

def collect_pdfs(limit: int) -> list[Path]:
    """2025_Q2 하위 폴더에서 텍스트가 있을 법한 PDF 수집 (0바이트 제외)"""
    pdfs = []
    for company_dir in sorted(Q2_DIR.iterdir()):
        if not company_dir.is_dir():
            continue
        for pdf in sorted(company_dir.glob("*.pdf")):
            if pdf.stat().st_size > 10_000:   # 10KB 이상만
                pdfs.append(pdf)
                if len(pdfs) >= limit:
                    return pdfs
    return pdfs

def main():
    pdfs = collect_pdfs(5)
    print(f"대상 PDF {len(pdfs)}개:")
    for p in pdfs:
        print(f"  {p.parent.name} / {p.name}")
    print()

    all_results = []

    for i, pdf_path in enumerate(pdfs, 1):
        out_file = Path(__file__).parent / "results" / f"e2_us_pdf{i}.json"
        out_file.parent.mkdir(exist_ok=True)

        print(f"[{i}/{len(pdfs)}] {pdf_path.name}")
        result = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--pdf",  str(pdf_path),
             "--out",  str(out_file)],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr[:300])

        if out_file.exists():
            all_results.append(json.loads(out_file.read_text(encoding="utf-8")))

    if not all_results:
        print("[오류] 처리된 결과 없음")
        return

    # 형식별 평균 집계
    agg: dict = defaultdict(lambda: defaultdict(list))
    for res in all_results:
        for fmt, m in res.get("summary", {}).items():
            for k in ["precision", "recall", "f1", "n_detected"]:
                if k in m:
                    agg[fmt][k].append(m[k])

    avg = {
        fmt: {k: round(sum(v) / len(v), 4) for k, v in metrics.items()}
        for fmt, metrics in agg.items()
    }

    print("\n" + "=" * 65)
    print(f"E2 평균 결과 ({len(all_results)}개 PDF)")
    print("=" * 65)
    print(f"{'형식':<22} {'Prec':>7} {'Recall':>7} {'F1':>7} {'탐지':>5}")
    print("-" * 50)
    for fmt, m in avg.items():
        marker = " <--" if fmt == "ours" else ""
        print(f"{fmt:<22} {m['precision']:>7.4f} {m['recall']:>7.4f} "
              f"{m['f1']:>7.4f} {m['n_detected']:>5.1f}{marker}")

    out = Path(__file__).parent / "results" / "e2_us_batch5.json"
    out.write_text(json.dumps(
        {"pdfs": [str(p) for p in pdfs], "avg": avg, "per_file": all_results},
        ensure_ascii=False, indent=2
    ))
    print(f"\n[완료] 저장: {out}")

if __name__ == "__main__":
    main()
