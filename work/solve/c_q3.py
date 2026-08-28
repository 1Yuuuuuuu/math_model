"""2025-C 问题 3: 多因素综合（身高/体重/年龄/BMI）+ 检测误差 + 达标比例 → BMI 分组与时点.

方法学修正（评审 P0-3/P1）：
- 混合效应模型处理重复测量（孕妇随机截距）
- K-means 数据驱动分组（与 Q2 一致）
- 共线性诊断（weight~bmi 0.827 → 不共入回归）
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.regression.mixed_linear_model import MixedLM

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "toolkit" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from cumcm_toolkit.models.execution import execute  # noqa: E402
import nipt_data  # noqa: E402


def earliest_reach_week(grp) -> float | None:
    reached = [r["week"] for _, r in grp.iterrows()
               if r["week"] is not None and r["y_conc"] is not None and r["y_conc"] >= 0.04]
    return min(reached) if reached else None


def main() -> None:
    male = nipt_data.load_nipt().male
    df = male.dropna(subset=["week", "y_conc", "bmi", "mother_id"]).copy()
    for c in ("age", "height", "weight", "bmi", "week", "y_conc"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["week", "y_conc", "bmi"])

    # per-mother: reach week + features
    mothers = {}
    for mid, grp in df.groupby("mother_id"):
        er = earliest_reach_week(grp)
        first = grp.iloc[0]
        mothers[mid] = {
            "bmi": float(first["bmi"]),
            "age": float(first["age"]) if first["age"] == first["age"] else np.nan,
            "height": float(first["height"]) if first["height"] == first["height"] else np.nan,
            "weight": float(first["weight"]) if first["weight"] == first["weight"] else np.nan,
            "reach_week": er,
        }
    mdf = pd.DataFrame.from_dict(mothers, orient="index").dropna()
    print(f"mothers with full features: {len(mdf)}")

    # --- 1. 共线性诊断 ---
    wb = execute("correlation-analysis",
                 {"x": mdf["weight"].tolist(), "y": mdf["bmi"].tolist(), "method": "pearson"})["result"]
    print(f"\nweight~bmi pearson: {wb['coefficient']:.3f} (共线性，不同入回归)")

    # --- 2. 混合效应: y_conc ~ week + bmi + height（记录级，孕妇随机截距）---
    df2 = df.dropna(subset=["height"]).copy()
    model = MixedLM.from_formula("y_conc ~ week + bmi + height", groups=df2["mother_id"], data=df2)
    res = model.fit(reml=True)
    print("\n=== 混合效应 y_conc ~ week + bmi + height ===")
    for term in ("Intercept", "week", "bmi", "height"):
        print(f"  {term}: {res.params[term]:.5f} (p={res.pvalues[term]:.4g})")
    var_re = res.cov_re.iloc[0, 0]
    icc = var_re / (var_re + res.scale)
    print(f"  ICC: {icc:.3f}")

    # --- 3. 控制 BMI 后 height 的增量（残差相关）---
    print("\n=== 控制 BMI 后的增量因素（残差相关）===")
    bmi_x = [[b] for b in mdf["bmi"]]
    rw = mdf["reach_week"].tolist()
    reg_bmi = execute("linear-regression", {"X": bmi_x, "y": rw, "predict_X": bmi_x})["result"]
    resid = [y - p for y, p in zip(rw, reg_bmi["training_predictions"])]
    for col in ("age", "height", "weight"):
        r = execute("correlation-analysis",
                    {"x": mdf[col].tolist(), "y": resid, "method": "pearson"})["result"]
        print(f"  残差 ~ {col}: r={r['coefficient']:.3f} p={r.get('p_value','?'):.4g}")

    # --- 4. K-means 分组（BMI，与 Q2 一致）→ 达标+健康比例 + 时点 ---
    print("\n=== K-means 分组 + 达标/健康比例 + 时点 ===")
    bmi_vals = mdf["bmi"].values.reshape(-1, 1).tolist()
    km = execute("kmeans", {"X": bmi_vals, "params": {"n_clusters": 5, "n_init": 10}, "seed": 7})["result"]
    mdf["cluster"] = km["labels"]
    centers = sorted(c[0] for c in km["cluster_centers"])
    # health from original male data
    health_map = {}
    for mid, grp in male.groupby("mother_id"):
        h = grp["health"].dropna()
        health_map[mid] = h.iloc[0] if len(h) else "是"
    mdf["health"] = mdf.index.map(lambda m: health_map.get(m, "是"))
    for c in sorted(mdf["cluster"].unique(), key=lambda x: centers[x]):
        grp = mdf[mdf["cluster"] == c]
        reach = grp["reach_week"].dropna()
        ok = grp[(grp["reach_week"].notna()) & (grp["health"] == "是")]
        p90 = float(np.percentile(reach, 90)) if len(reach) else float("nan")
        print(f"  BMI~{centers[c]:.1f}: n={len(grp)} 达标+健康={len(ok)/len(grp)*100:.1f}% "
              f"P90={p90:.2f}w -> ~{round(p90)}w" if not np.isnan(p90) else
              f"  BMI~{centers[c]:.1f}: n={len(grp)} 无达标数据")

    # --- 5. 误差影响 ---
    print("\n=== 误差影响（±10%）===")
    pert = df.copy()
    pert["y_conc"] = pert["y_conc"] * 1.10
    shifts = 0
    for mid, grp in pert.groupby("mother_id"):
        orig = earliest_reach_week(df[df["mother_id"] == mid])
        new = earliest_reach_week(grp)
        if orig is not None and new is not None and abs(new - orig) > 0.3:
            shifts += 1
    print(f"  +10%: {shifts}/{len(mdf)} 孕妇达标周变化>0.3w")


if __name__ == "__main__":
    main()
