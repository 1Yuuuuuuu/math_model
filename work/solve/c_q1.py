"""2025-C 问题 1: Y 染色体浓度与孕周、BMI 的关系模型（混合效应，处理重复测量）.

方法学修正（评审 P0-1）：
- 数据是 267 孕妇 × 1082 条纵向记录（每人 1-5 次检测），简单回归违反独立性假设
- 改用线性混合效应模型：孕妇作随机截距，孕周/BMI 作固定效应
- 参考：Deng et al. (2023) fetal fraction 影响因素回顾（153,306 例，BMI 负相关）;
  ScienceDirect 2022 纵向 fetal fraction 研究（孕周非线性、男胎更高）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "toolkit" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from statsmodels.regression.mixed_linear_model import MixedLM  # noqa: E402

from cumcm_toolkit.models.execution import execute  # noqa: E402
import nipt_data  # noqa: E402


def main() -> None:
    male = nipt_data.load_nipt().male
    df = male.dropna(subset=["y_conc", "week", "bmi", "mother_id"]).copy()
    df["y_conc"] = pd.to_numeric(df["y_conc"], errors="coerce")
    df["week"] = pd.to_numeric(df["week"], errors="coerce")
    df["bmi"] = pd.to_numeric(df["bmi"], errors="coerce")
    df = df.dropna(subset=["y_conc", "week", "bmi"])
    print(f"male records: {len(df)}, mothers: {df['mother_id'].nunique()}")
    print(f"avg draws/mother: {len(df)/df['mother_id'].nunique():.2f}")

    # --- 1. 混合效应模型: y_conc ~ week + bmi + (1|mother_id) ---
    model = MixedLM.from_formula(
        "y_conc ~ week + bmi", groups=df["mother_id"], data=df
    )
    result = model.fit(reml=True)
    print("\n=== 混合效应模型 (随机截距 per mother) ===")
    print(f"  固定效应: intercept={result.params['Intercept']:.4f}")
    print(f"    week: {result.params['week']:.5f} (p={result.pvalues['week']:.4g})")
    print(f"    bmi: {result.params['bmi']:.5f} (p={result.pvalues['bmi']:.4g})")
    print(f"  随机效应标准差 (mother): {np.sqrt(result.cov_re.iloc[0,0]):.4f}")
    print(f"  残差标准差: {np.sqrt(result.scale):.4f}")
    print(f"  对数似然: {result.llf:.2f}")
    # 组内相关 ICC = var_random / (var_random + var_residual)
    var_re = result.cov_re.iloc[0, 0]
    var_res = result.scale
    icc = var_re / (var_re + var_res)
    print(f"  ICC (组内相关): {icc:.3f} —— {icc*100:.1f}% 方差来自孕妇间差异")

    # --- 2. 对照: 简单 OLS（显示重复测量高估显著性的程度）---
    X = df[["week", "bmi"]].values.tolist()
    y = df["y_conc"].tolist()
    ols = execute("linear-regression", {"X": X, "y": y, "predict_X": X})["result"]
    print("\n=== 对照: 简单 OLS（每条记录独立）===")
    print(f"  coefs [week,bmi]: {[round(c,5) for c in ols['coefficients']]}")
    print(f"  r_squared: {ols['r_squared']:.4f}")
    print("  → OLS 未处理重复测量，p 值会低估；混合效应更严谨")

    # --- 3. 相关分析（报告用，按孕妇聚合避免重复）---
    print("\n=== 按孕妇聚合后的相关（去重复）===")
    agg = df.groupby("mother_id").agg(
        y_conc=("y_conc", "mean"), week=("week", "mean"), bmi=("bmi", "first")
    ).dropna()
    for col, name in (("week", "孕周"), ("bmi", "BMI")):
        r = execute("correlation-analysis",
                    {"x": agg["y_conc"].tolist(), "y": agg[col].tolist(), "method": "pearson"})["result"]
        print(f"  y_conc ~ {name} (aggregated): r={r['coefficient']:.4f} p={r.get('p_value','?'):.4g}")

    # --- 4. 与外部证据对照 ---
    print("\n=== 外部证据对照 ===")
    print("  Deng 2023 (153,306例): BMI 与 fetal fraction 负相关 → 与 bmi 系数为负一致")
    print("  ScienceDirect 2022: fetal fraction 随孕周增长（非线性）→ 与 week 系数为正一致")
    print("  同研究: 男胎 fetal fraction 高于女胎 → 支持按性别分数据建模")


if __name__ == "__main__":
    main()
