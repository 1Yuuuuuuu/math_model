"""生成 C 题论文图表：Y 浓度分布 + BMI 聚类达标时间。

figures-and-tables 维度是审批短板（75 分），补图提升论文质量。
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(r"E:\数学建模国赛")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "toolkit" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import nipt_data  # noqa: E402

FIG_DIR = ROOT / "work/paper/figs"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False


def fig1_y_conc_by_bmi() -> None:
    """Y 浓度 vs 孕周，按 BMI 高低着色。"""
    male = nipt_data.load_nipt().male
    male = male.dropna(subset=["y_conc", "week", "bmi"])
    male["bmi"] = pd.to_numeric(male["bmi"], errors="coerce")
    male["week"] = pd.to_numeric(male["week"], errors="coerce")
    male["y_conc"] = pd.to_numeric(male["y_conc"], errors="coerce")
    male = male.dropna(subset=["y_conc", "week", "bmi"])
    fig, ax = plt.subplots(figsize=(6, 4))
    hi = male[male["bmi"] >= 32]
    lo = male[male["bmi"] < 32]
    ax.scatter(lo["week"], lo["y_conc"], s=8, alpha=0.4, label="BMI<32", color="steelblue")
    ax.scatter(hi["week"], hi["y_conc"], s=8, alpha=0.4, label="BMI≥32", color="coral")
    ax.axhline(0.04, color="red", ls="--", lw=1, label="4% 阈值")
    ax.set_xlabel("孕周 (周)")
    ax.set_ylabel("Y 染色体浓度")
    ax.set_title("Y 染色体浓度与孕周（按 BMI 分层）")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "y_conc_by_week.png", dpi=150)
    plt.close(fig)
    print("saved fig1")


def fig2_reach_week_by_cluster() -> None:
    """K-means 聚类簇的达标周分布（箱线图）。"""
    male = nipt_data.load_nipt().male
    male = male.dropna(subset=["y_conc", "week", "bmi"])
    male["bmi"] = pd.to_numeric(male["bmi"], errors="coerce")
    male["week"] = pd.to_numeric(male["week"], errors="coerce")
    male["y_conc"] = pd.to_numeric(male["y_conc"], errors="coerce")
    male = male.dropna(subset=["y_conc", "week", "bmi"])
    from cumcm_toolkit.models.execution import execute
    mothers = {}
    for mid, grp in male.groupby("mother_id"):
        reached = [r["week"] for _, r in grp.iterrows() if r["y_conc"] >= 0.04]
        if reached:
            mothers[mid] = {"bmi": float(grp["bmi"].iloc[0]), "reach": min(reached)}
    mdf = pd.DataFrame.from_dict(mothers, orient="index")
    bmi_vals = mdf["bmi"].values.reshape(-1, 1).tolist()
    km = execute("kmeans", {"X": bmi_vals, "params": {"n_clusters": 5, "n_init": 10}, "seed": 7})["result"]
    mdf["cluster"] = km["labels"]
    centers = sorted(c[0] for c in km["cluster_centers"])
    order = sorted(mdf["cluster"].unique(), key=lambda c: centers[c])
    fig, ax = plt.subplots(figsize=(6, 4))
    data = [mdf[mdf["cluster"] == c]["reach"].values for c in order]
    labels = [f"BMI~{centers[c]:.0f}" for c in order]
    bp = ax.boxplot(data, patch_artist=True, tick_labels=labels)
    for patch in bp["boxes"]:
        patch.set_facecolor("lightblue")
    ax.axhline(13, color="orange", ls="--", lw=1, label="低风险<13周")
    ax.set_ylabel("最早达标周")
    ax.set_title("K-means 聚类簇的 Y 达标周分布")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "reach_week_by_cluster.png", dpi=150)
    plt.close(fig)
    print("saved fig2")


def fig3_x_conc_by_anomaly() -> None:
    """女胎 X 浓度：正常 vs 异常（分型）。"""
    fem = nipt_data.load_nipt().female
    fem["x_conc"] = pd.to_numeric(fem["x_conc"], errors="coerce")
    fem["abnormal"] = (fem["aneuploidy"].notna() & (fem["aneuploidy"].str.strip() != "")).astype(int)
    fem = fem.dropna(subset=["x_conc"])
    fig, ax = plt.subplots(figsize=(6, 4))
    normal = fem[fem["abnormal"] == 0]["x_conc"]
    abn = fem[fem["abnormal"] == 1]["x_conc"]
    ax.hist(normal, bins=40, alpha=0.6, label="正常", color="steelblue")
    ax.hist(abn, bins=40, alpha=0.6, label="异常", color="coral")
    ax.axvline(-0.02, color="red", ls="--", lw=1, label="阈值 -0.02")
    ax.set_xlabel("X 染色体浓度")
    ax.set_ylabel("频数")
    ax.set_title("女胎 X 染色体浓度：正常 vs 异常")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "x_conc_by_anomaly.png", dpi=150)
    plt.close(fig)
    print("saved fig3")


if __name__ == "__main__":
    fig1_y_conc_by_bmi()
    fig2_reach_week_by_cluster()
    fig3_x_conc_by_anomaly()
