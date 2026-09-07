"""
2025_Q2 하위 폴더에서 PDF 10개를 뽑아 e1_preprocessing_us.py 실행
"""
import sys, json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from e1_preprocessing_us import run_experiment

Q2_DIR = Path(__file__).parent.parent / "2025_Q2"

def collect_pdfs(limit: int) -> list[Path]:
    pdfs = []
    for company_dir in sorted(Q2_DIR.iterdir()):
        if not company_dir.is_dir():
            continue
        for pdf in sorted(company_dir.glob("*.pdf")):
            pdfs.append(pdf)
            if len(pdfs) >= limit:
                return pdfs
    return pdfs

def main():
    pdfs = collect_pdfs(10)
    print(f"대상 PDF {len(pdfs)}개:")
    for p in pdfs:
        print(f"  {p.parent.name} / {p.name}")

    agg: dict = defaultdict(lambda: defaultdict(list))
    all_results = []

    for pdf_path in pdfs:
        try:
            res = run_experiment(pdf_path)
            all_results.append(res)
            for strat, metrics in res["results"].items():
                for k, v in metrics.items():
                    agg[strat][k].append(v)
        except Exception as e:
            print(f"  [오류] {pdf_path.name}: {e}")

    if not agg:
        print("처리된 파일 없음")
        return

    avg = {
        strat: {k: round(sum(v) / len(v), 4) for k, v in metrics.items()}
        for strat, metrics in agg.items()
    }

    print(f"\n{'='*65}")
    print(f"E1 평균 결과 ({len(all_results)}개 PDF)")
    print(f"{'='*65}")
    print(f"{'전략':<12} {'Tokens':>8} {'Comp.Rate':>10} {'KW Recall':>10} {'Sem.Sim':>8}")
    print("-" * 55)
    for strat, m in avg.items():
        marker = " ◀" if strat == "Ours" else ""
        print(f"{strat:<12} {m['tokens']:>8,.0f} {m['compression_rate']:>10.4f} "
              f"{m['keyword_recall']:>10.4f} {m['semantic_sim']:>8.4f}{marker}")

    out = Path(__file__).parent / "results" / "e1_us_batch10.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(
        {"pdfs": [str(p) for p in pdfs], "avg": avg, "per_file": all_results},
        ensure_ascii=False, indent=2
    ))
    print(f"\n[완료] 저장: {out}")

if __name__ == "__main__":
    main()
