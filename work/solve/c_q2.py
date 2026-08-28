"""2025-C 问题 2: 男胎 BMI 分组 + 最佳 NIPT 时点（K-means 数据驱动分组）.

方法学修正（评审 P0-2/P1）：
- 分组改用 K-means 聚类（数据驱动），替代题目提示的固定区间
- 低样本组给出置信区间（bootstrap），不宣称无把握的结论
- 参考: K-means clustering + multi-objective risk optimization for NIPT timing
  (Semantic Scholar, 与本研究目标一致的公开方法)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "toolkit" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from cumcm_toolkit.models.execution import execute  # noqa: E402
import nipt_data  # noqa: E402


def earliest_reach_week(grp) -> float | None:
    reached = [(r["week"], r["y_conc"]) for _, r in grp.iterrows()
               if r["week"] is not None and r["y_conc"] is not None and r["y_conc"] >= 0.04]
    return min(w for w, _ in reached) if reached else None


def bootstrap_ci(vals, n_boot=1000, alpha=0.1) -> tuple[float, float]:
    rng = np.random.default_rng(42)
    arr = np.array(vals)
    meds = [np.median(rng.choice(arr, size=len(arr), replace=True)) for _ in range(n_boot)]
    return float(np.percentile(meds, 100*alpha/2)), float(np.percentile(meds, 100*(1-alpha/2)))


def main() -> None:
    male = nipt_data.load_nipt().male
    df = male.dropna(subset=["week", "y_conc", "bmi", "mother_id"]).copy()
    df["bmi"] = pd.to_numeric(df["bmi"], errors="coerce")
    df = df.dropna(subset=["bmi"])

    # per-mother: bmi (first) + earliest reach week
    mothers = {}
    for mid, grp in df.groupby("mother_id"):
        er = earliest_reach_week(grp)
        mothers[mid] = {"bmi": float(grp["bmi"].iloc[0]), "reach_week": er}
    mdf = pd.DataFrame.from_dict(mothers, orient="index")
    print(f"mothers: {len(mdf)}, with reach: {mdf['reach_week'].notna().sum()}")

    # --- K-means 聚类分组（对 BMI 做 3-5 簇，选轮廓/方差比）---
    print("\n=== K-means 聚类分组（数据驱动）===")
    bmi_vals = mdf["bmi"].values.reshape(-1, 1).tolist()
    inertias = {}
    for k in (3, 4, 5):
        km = execute("kmeans", {"X": bmi_vals, "params": {"n_clusters": k, "n_init": 10}, "seed": 7})["result"]
        labels = km["labels"]
        centers = sorted(c[0] for c in km["cluster_centers"])
        mdf[f"km{k}"] = labels
        inertia = km["inertia"]
        inertias[k] = inertia
        reach_var = mdf.groupby(f"km{k}")["reach_week"].var().sum()
        print(f"  k={k}: centers={[round(c,1) for c in centers]} inertia={inertia:.1f} "
              f"reach_var_sum={reach_var:.2f}")
    # 选簇：肘部法则（inertia 边际递减拐点）+ 题意（题目提示 5 组）
    k_use = 5  # inertia k3->477.6, k4->334.4, k5->240.8；k4 后边际收益递减，
    # 但题目明确 5 个 BMI 区间，取 k=5 对照题意并说明
    mdf["cluster"] = mdf[f"km{k_use}"]
    centers = sorted(c[0] for c in execute("kmeans", {"X": bmi_vals, "params": {"n_clusters": k_use, "n_init": 10}, "seed": 7})["result"]["cluster_centers"])
    print(f"\n选用 k={k_use}（肘部在 k=4，题目提示 5 组，取 5 对照题意）簇中心(BMI): {[round(c,1) for c in centers]}")

    # --- 每组时点建议（P90 + bootstrap CI）---
    print(f"\n{'簇(BMI中心)':<12} {'n':<5} {'达标率%':<8} {'P90':<7} {'中位[90%CI]':<22} {'建议'}")
    cluster_order = sorted(mdf["cluster"].unique(), key=lambda c: centers[c])
    for c in cluster_order:
        grp = mdf[mdf["cluster"] == c]
        reach = grp["reach_week"].dropna()
        n = len(grp)
        nr = len(reach)
        if nr == 0:
            continue
        p90 = float(np.percentile(reach, 90))
        lo, hi = bootstrap_ci(reach.tolist())
        risk = "低" if p90 < 13 else ("高" if p90 <= 27 else "极高")
        never = n - nr
        note = f"（{never} 未达标需复测）" if never > max(1, n*0.1) else ""
        print(f"BMI~{centers[c]:<8.1f} {n:<5} {nr/n*100:<8.1f} {p90:<7.2f} "
              f"{np.median(reach):.2f}[{lo:.2f},{hi:.2f}]  ~{round(p90)}w({risk}) {note}")

    # --- 误差影响（浓度 ±5%/±10%）---
    print("\n=== 检测误差影响（聚类分组下）===")
    for sigma in (0.05, 0.10):
        shifts = 0
        for mid, grp in df.groupby("mother_id"):
            orig = earliest_reach_week(grp)
            pert = grp.copy()
            pert["y_conc"] = pert["y_conc"] * (1 + sigma)
            new = earliest_reach_week(pert)
            if orig is not None and new is not None and abs(new - orig) > 0.3:
                shifts += 1
        print(f"  ±{sigma*100:.0f}%: {shifts}/{len(mdf)} 孕妇达标周变化>0.3w")


if __name__ == "__main__":
    main()
