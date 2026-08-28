"""2025-C 问题 4: 女胎异常判定（AB 列非整倍体）分类模型.

特征: 13/18/21/X 染色体 Z 值、GC 含量(13/18/21/总)、读段数/比例、BMI。
标签: AB 非空=异常(1)，空=正常(0)。
方法: 逻辑回归（可解释）+ 经典 Z 值阈值法对比（Z>3 判异常）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "toolkit" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from cumcm_toolkit.models.execution import execute  # noqa: E402
import nipt_data  # noqa: E402


def main() -> None:
    fem = nipt_data.load_nipt().female
    fem["abnormal"] = (fem["aneuploidy"].notna() & (fem["aneuploidy"].str.strip() != "")).astype(int)
    print(f"female rows: {len(fem)}, abnormal: {int(fem['abnormal'].sum())}, normal: {int((1-fem['abnormal']).sum())}")

    # features
    feat_cols = ["z13", "z18", "z21", "zx", "gc13", "gc18", "gc21", "gc_content",
                 "total_reads", "mapped_ratio", "dup_ratio", "unique_reads", "bmi", "x_conc"]
    df = fem.dropna(subset=feat_cols + ["abnormal"]).copy()
    # force float (pandas object columns may hold None inside lists)
    for c in feat_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=feat_cols)
    print(f"rows with full features: {len(df)} (abnormal {int(df['abnormal'].sum())})")

    X = [[float(v) for v in row] for row in df[feat_cols].values.tolist()]
    y = [int(v) for v in df["abnormal"].tolist()]

    # --- 1. logistic regression: use probability + tuned threshold (class imbalance) ---
    logit = execute("logistic-regression", {"X": X, "y": y, "seed": 7, "predict_X": X})["result"]
    print("\nlogistic regression (probabilities from executor):")
    probs = logit["probabilities"]
    p1 = [p[1] for p in probs]  # P(abnormal)
    for thr in (0.5, 0.3, 0.2, 0.15):
        preds = [1 if p >= thr else 0 for p in p1]
        tp = sum(1 for a, p in zip(y, preds) if a == 1 and p == 1)
        fp = sum(1 for a, p in zip(y, preds) if a == 0 and p == 1)
        fn = sum(1 for a, p in zip(y, preds) if a == 1 and p == 0)
        tn = sum(1 for a, p in zip(y, preds) if a == 0 and p == 0)
        rec = tp / (tp + fn) if tp + fn else 0
        prec = tp / (tp + fp) if tp + fp else 0
        acc = (tp + tn) / len(y)
        print(f"  thr={thr}: acc={acc:.3f} recall={rec:.3f} precision={prec:.3f} "
              f"TP={tp} FP={fp} FN={fn}")

    # coefficients (feature importance) — shape [[...]]
    print("  coefficients:")
    coefs = logit["coefficients"]
    if coefs and isinstance(coefs[0], list):
        coefs = coefs[0]
    for c, coef in zip(feat_cols, coefs):
        print(f"    {c}: {coef:.3f}")

    # --- 2. classic Z-score threshold: any of z13/z18/z21 > 3 => abnormal ---
    z_abn = [1 if any(df.loc[i, c] > 3 for c in ("z13", "z18", "z21")) else 0 for i in df.index]
    tpz = sum(1 for a, p in zip(y, z_abn) if a == 1 and p == 1)
    fpz = sum(1 for a, p in zip(y, z_abn) if a == 0 and p == 1)
    fnz = sum(1 for a, p in zip(y, z_abn) if a == 1 and p == 0)
    print("\nclassic Z>3 threshold:")
    print(f"  confusion: TP={tpz} FP={fpz} FN={fnz}")
    print(f"  recall={tpz/(tpz+fnz) if tpz+fnz else 0:.3f}")

    # --- 3. per-chromosome Z distributions abnormal vs normal ---
    print("\nZ 值分布（异常 vs 正常，均值）:")
    for c in ("z13", "z18", "z21"):
        ab = df.loc[df["abnormal"] == 1, c]
        no = df.loc[df["abnormal"] == 0, c]
        print(f"  {c}: abnormal_mean={ab.mean():.2f} normal_mean={no.mean():.2f}")

    # --- 5. 按异常类型分型（T13/T18/T21 机制不同，合并稀释信号）---
    print("\n按异常类型分型的特征均值:")
    fem2 = fem.dropna(subset=feat_cols + ["abnormal"]).copy()
    for c in feat_cols:
        fem2[c] = pd.to_numeric(fem2[c], errors="coerce")
    types = {
        "T21": fem2["aneuploidy"].str.contains("T21", na=False),
        "T18": fem2["aneuploidy"].str.contains("T18", na=False),
        "T13": fem2["aneuploidy"].str.contains("T13", na=False),
    }
    for label, mask in types.items():
        ab = fem2.loc[mask, "x_conc"].dropna()
        no = fem2.loc[~mask & (fem2["abnormal"] == 0), "x_conc"].dropna()
        if len(ab):
            r = execute("correlation-analysis",
                        {"x": ab.tolist(), "y": [1]*len(ab) + [0]*len(no.tolist()[:len(ab)]),
                         "method": "pearson"})["result"] if False else None
            print(f"  {label}: n={len(ab)} x_conc_mean={ab.mean():.4f} "
                  f"(normal x_conc_mean={no.mean():.4f})")

    # --- 6. X 染色体浓度阈值判定（主判据）---
    print("\nX 染色体浓度阈值判定:")
    xc = df["x_conc"]
    yl = df["abnormal"].tolist()
    for thr in (-0.03, -0.02, -0.01, 0.0, 0.01):
        preds = [1 if v <= thr else 0 for v in xc]
        tp = sum(1 for a, p in zip(yl, preds) if a == 1 and p == 1)
        fp = sum(1 for a, p in zip(yl, preds) if a == 0 and p == 1)
        fn = sum(1 for a, p in zip(yl, preds) if a == 1 and p == 0)
        tn = sum(1 for a, p in zip(yl, preds) if a == 0 and p == 0)
        rec = tp / (tp + fn) if tp + fn else 0
        prec = tp / (tp + fp) if tp + fp else 0
        acc = (tp + tn) / len(yl)
        print(f"  x_conc<={thr}: acc={acc:.3f} recall={rec:.3f} precision={prec:.3f} TP={tp} FP={fp} FN={fn}")

    # --- 7. 按孕妇去重（同一孕妇多行 → 取一行，避免重复稀释）---
    print("\n按孕妇去重后的 X 浓度阈值（稳健性检查）:")
    dedup = df.sort_values("abnormal", ascending=False).drop_duplicates("mother_id")
    print(f"  unique mothers: {len(dedup)} (abnormal {int(dedup['abnormal'].sum())})")
    xd = dedup["x_conc"]
    yd = dedup["abnormal"].tolist()
    for thr in (-0.03, -0.02, -0.01):
        preds = [1 if v <= thr else 0 for v in xd]
        tp = sum(1 for a, p in zip(yd, preds) if a == 1 and p == 1)
        fp = sum(1 for a, p in zip(yd, preds) if a == 0 and p == 1)
        fn = sum(1 for a, p in zip(yd, preds) if a == 1 and p == 0)
        rec = tp / (tp + fn) if tp + fn else 0
        prec = tp / (tp + fp) if tp + fp else 0
        print(f"  x_conc<={thr}: recall={rec:.3f} precision={prec:.3f} TP={tp} FP={fp} FN={fn}")

    # --- 8. 文献对照（ACMG / 性别机制）---
    print("\n=== 外部证据对照 ===")
    print("  ACMG 2022 guideline: NIPS 对 T21 的 PPV 仅 50-95%，单靠 Z 值不足 → 支持结合多特征")
    print("  ScienceDirect 2022: 男胎 fetal fraction 高于女胎 → 女胎 X 浓度信号机制不同，")
    print("    解释了为何女胎用 X 浓度（而非 Y）判别")


if __name__ == "__main__":
    main()
