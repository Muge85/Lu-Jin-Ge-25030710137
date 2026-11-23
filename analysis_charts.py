# -*- coding: utf-8 -*-
"""
analysis_charts.py - 统计分析与图表输出
======================================
基于 NumPy / pandas / SciPy / Matplotlib / Seaborn / PyEcharts，
读取 air_quality_web/data/*.js（与前端同源的数据），输出：

  analysis/figures/*.png      七张静态统计图（Matplotlib + Seaborn，含官方权威数据对照图）
  air_quality_web/analysis_charts.html  交互式图表（PyEcharts，站点内唯一入口，引用 js/echarts.min.js）
  analysis/stats_summary.json SciPy 统计检验摘要 + 官方基准对照摘要（供课程报告引用）

第 7 张图读取 official_benchmark.py 产出的 analysis/official_benchmark.json；
该文件不存在时会跳过，不影响原有六张图与交互页的生成。

可单独运行：python analysis_charts.py
通常由 build_real_data.py 的 analyze 阶段调用。
"""
import json
import os
import re
import shutil
from collections import Counter

import numpy as np
import pandas as pd
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from pyecharts import options as opts
from pyecharts.charts import Bar, HeatMap, Line, Page, Pie
from pyecharts.globals import CurrentConfig

# PyEcharts 默认从 CDN 加载 ECharts；改为引用站点自带文件，保证离线可打开
CurrentConfig.ONLINE_HOST = "../air_quality_web/js/"

sns.set_theme(style="whitegrid", font="Microsoft YaHei")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun"]
plt.rcParams["axes.unicode_minus"] = False

POLLUTANTS = ["AQI", "PM2.5", "O3", "NO2", "SO2", "CO"]
COLORS = {"AQI": "#c0392b", "PM2.5": "#8e6fd8", "O3": "#e67e22"}


def num(x, default=0.0):
    """前端数据里可能存在 null，统一转成数值。"""
    return default if x is None else round(float(x), 1)


def load_js(path):
    """解析 window.XXX = {...}; 形式的前端数据文件。"""
    txt = open(path, encoding="utf-8").read()
    m = re.search(r"window\.\w+\s*=\s*(\{.*\})\s*;", txt, re.S)
    if not m:
        raise ValueError("无法解析数据文件: " + path)
    return json.loads(m.group(1))


def load_all(web_dir):
    d = os.path.join(web_dir, "data")
    return (load_js(os.path.join(d, "year_avg.js")),
            load_js(os.path.join(d, "month_avg.js")),
            load_js(os.path.join(d, "corr_data.js")),
            load_js(os.path.join(d, "city_rank.js")))


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  图:", os.path.basename(path), os.path.getsize(path), "bytes")


# ------------------------------------------------------------------
# Matplotlib + Seaborn 静态统计图
# ------------------------------------------------------------------
def static_charts(year, month, corr, rank, fig_dir):
    cities = pd.DataFrame(year["cities"])
    nat = pd.DataFrame(year["national"])

    # 1) 十年趋势 + SciPy 线性回归拟合线
    fig, ax = plt.subplots(figsize=(10, 5.4))
    x = nat["year"].to_numpy(float)
    for p_ in ("AQI", "PM2.5", "O3"):
        sns.lineplot(data=nat, x="year", y=p_, marker="o", linewidth=2.2,
                     color=COLORS[p_], label=p_, ax=ax)
    y = nat["AQI"].to_numpy(float)
    ok = np.isfinite(y)
    lr = stats.linregress(x[ok], y[ok])
    ax.plot(x, lr.intercept + lr.slope * x, "--", color=COLORS["AQI"], alpha=.85,
            label="AQI 线性拟合 (%+.2f/年, p=%.2g)" % (lr.slope, lr.pvalue))
    ax.set(title="2015—2024 全国污染物年际变化（SciPy 线性趋势检验）",
           xlabel="年份", ylabel="AQI / 浓度")
    ax.set_xticks(x.astype(int))
    ax.legend(frameon=False)
    save(fig, os.path.join(fig_dir, "01_national_trend.png"))

    # 2) 月度周期热力图：按指标 z-score 着色，单元格标注原始月均值
    mon = pd.DataFrame({p_: [num(v) for v in month["national"][p_]]
                        for p_ in POLLUTANTS}, index=month["months"])
    z = (mon - mon.mean()) / mon.std(ddof=0)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    sns.heatmap(z.T, annot=mon.T, fmt=".0f", cmap="RdYlBu_r", center=0,
                cbar_kws={"label": "标准化偏离 (z-score)"}, ax=ax)
    ax.set(title="污染物月均浓度的季节周期（颜色为标准化值，数字为原始均值）",
           xlabel="月份", ylabel="指标")
    save(fig, os.path.join(fig_dir, "02_monthly_cycle.png"))

    # 3) Pearson 相关矩阵热力图
    m = np.asarray([[np.nan if v is None else v for v in row]
                    for row in corr["matrix"]], dtype=float)
    cdf = pd.DataFrame(m, index=corr["labels"], columns=corr["labels"])
    fig, ax = plt.subplots(figsize=(8.2, 6.8))
    sns.heatmap(cdf, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
                vmin=-1, vmax=1, square=True, linewidths=.5, ax=ax)
    ax.set_title("污染物与气象要素 Pearson 相关矩阵")
    save(fig, os.path.join(fig_dir, "03_correlation_heatmap.png"))

    # 4) 2024 年各省代表城市平均 AQI（Seaborn 横向柱状）
    d24 = cities[cities["year"] == 2024]
    prov = d24.groupby("province")["AQI"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(9, 10))
    sns.barplot(x=prov.to_numpy(), y=prov.index.to_numpy(),
                hue=prov.index.to_numpy(), palette="RdYlBu_r",
                legend=False, ax=ax)
    ax.set(title="2024 年各省代表城市平均 AQI", xlabel="AQI", ylabel="省份")
    save(fig, os.path.join(fig_dir, "04_province_aqi_2024.png"))

    # 5) PM2.5 十年改善榜（Matplotlib）
    imp = pd.DataFrame(rank["improve"]).sort_values("pm25_drop_pct")
    fig, ax = plt.subplots(figsize=(9, 6.4))
    bars = ax.barh(imp["city"], imp["pm25_drop_pct"], color="#2fa876")
    ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9)
    ax.axvline(0, color="#888", linewidth=.8)
    ax.set(title="2015→2024 年 PM2.5 降幅 TOP15", xlabel="PM2.5 浓度降幅 (%)", ylabel="城市")
    save(fig, os.path.join(fig_dir, "05_pm25_improvement.png"))

    # 6) 气象-污染物散点 + SciPy Pearson 检验（Seaborn 回归拟合）
    def pts(key, a, b):
        return pd.DataFrame(corr[key], columns=[a, b, "province"]).dropna()
    s1 = pts("scatterTempO3", "temp", "O3")
    s2 = pts("scatterWindPm", "wind", "PM2.5")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, sub, a, b, title in [
            (axes[0], s1, "temp", "O3", "气温 vs O3"),
            (axes[1], s2, "wind", "PM2.5", "风速 vs PM2.5")]:
        sns.regplot(data=sub, x=a, y=b, ax=ax, color="#3a7bd5",
                    scatter_kws={"s": 12, "alpha": .35},
                    line_kws={"color": "#c0392b"})
        r, p = stats.pearsonr(sub[a].to_numpy(float), sub[b].to_numpy(float))
        ax.set_title("%s（抽样散点）  r=%.2f, p=%.2g, n=%d" % (title, r, p, len(sub)))
    axes[0].set_xlabel("月均气温 (℃)"); axes[0].set_ylabel("O3 (μg/m³)")
    axes[1].set_xlabel("月均风速"); axes[1].set_ylabel("PM2.5 (μg/m³)")
    save(fig, os.path.join(fig_dir, "06_weather_scatter.png"))


# ------------------------------------------------------------------
# 第 7 张图：生态环境部官方基准数据集对照
# ------------------------------------------------------------------
def official_compare_chart(off_path, year, fig_dir):
    """官方年度公报值 vs 本项目抽样聚合值；同时输出趋势一致性统计摘要。"""
    if not os.path.exists(off_path):
        print("  跳过官方对照图：未找到", os.path.basename(off_path))
        return None
    with open(off_path, encoding="utf-8") as f:
        off = json.load(f)

    recs = pd.DataFrame(off["records"])
    nat = pd.DataFrame(year["national"])[["year", "PM2.5"]]
    df = recs[["year", "pm25", "good_rate"]].merge(nat, on="year", how="left")
    for c in ("pm25", "good_rate", "PM2.5"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    revised = off.get("revised_good_rate", {}).get("values", {})
    df["revised_good_rate"] = pd.to_numeric(
        [revised.get(str(y)) for y in df["year"]], errors="coerce")

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.8))
    ax = axes[0]
    ax.plot(df["year"], df["pm25"], "o-", color="#c0392b", linewidth=2.4,
            label="生态环境部官方值")
    ax.plot(df["year"], df["PM2.5"], "s--", color="#3a7bd5", linewidth=2.2,
            label="本项目抽样聚合值")
    ax.set(title="PM2.5 年均浓度对照（官方统计 vs 抽样聚合）",
           xlabel="年份", ylabel="μg/m³")
    ax.set_xticks(df["year"].astype(int))
    ax.tick_params(axis="x", rotation=45)
    ax.legend(frameon=False, fontsize=9)

    ax = axes[1]
    ax.plot(df["year"], df["good_rate"], "o-", color="#2fa876", linewidth=2.4,
            label="当年通报口径")
    ax.plot(df["year"], df["revised_good_rate"], "s--", color="#e67e22",
            linewidth=2.2, label="2024 公报回溯口径")
    ax.set(title="优良天数比例：两种官方统计口径", xlabel="年份", ylabel="%")
    ax.set_xticks(df["year"].astype(int))
    ax.tick_params(axis="x", rotation=45)
    ax.legend(frameon=False, fontsize=9)
    ax.text(.98, .04, "当年通报未公布的年份留空，不插值", transform=ax.transAxes,
            ha="right", fontsize=9, color="#6b7c93")
    save(fig, os.path.join(fig_dir, "07_official_compare.png"))

    # NumPy / SciPy：量化两组序列的平均偏差与趋势一致性，写入统计摘要
    both = df[["pm25", "PM2.5"]].dropna()
    gap = float((both["PM2.5"] - both["pm25"]).to_numpy(float).mean())
    r, p = stats.pearsonr(both["pm25"].to_numpy(float), both["PM2.5"].to_numpy(float))
    vf = off.get("verification", [])
    return {
        "dataset": off["meta"]["dataset"],
        "records": int(len(df)),
        "verified_pages": len(vf),
        "verified_match": sum(1 for v in vf
                              if v.get("pm25_match") and v.get("good_rate_match")),
        "pm25_mean_gap": round(gap, 2),
        "pm25_trend_pearson": {"r": round(float(r), 3), "p": float("%.3g" % p),
                               "n": int(len(both))},
        "figure": "07_official_compare.png",
        "citation": off["meta"]["citation"],
    }


# ------------------------------------------------------------------
# PyEcharts 交互式图表（合并为单页 HTML）
# ------------------------------------------------------------------
def pyecharts_page(year, month, rank, out_html):
    nat = pd.DataFrame(year["national"])
    cities = pd.DataFrame(year["cities"])
    init = opts.InitOpts(width="1080px", height="420px")

    line = Line(init_opts=init)
    line.add_xaxis([str(y) for y in year["years"]])
    for p_ in ("AQI", "PM2.5", "O3"):
        line.add_yaxis(p_, [num(v) for v in nat[p_]], is_smooth=True,
                       linestyle_opts=opts.LineStyleOpts(width=3),
                       label_opts=opts.LabelOpts(is_show=False))
    line.set_global_opts(
        title_opts=opts.TitleOpts(title="全国污染物十年趋势"),
        tooltip_opts=opts.TooltipOpts(trigger="axis"),
        xaxis_opts=opts.AxisOpts(name="年份"),
        yaxis_opts=opts.AxisOpts(name="AQI / 浓度"),
        datazoom_opts=[opts.DataZoomOpts(type_="inside")])

    d24 = cities[cities["year"] == 2024].nlargest(15, "AQI")
    names = d24["city"].tolist()[::-1]
    vals = [num(v) for v in d24["AQI"].tolist()[::-1]]
    bar = (Bar(init_opts=init)
           .add_xaxis(names)
           .add_yaxis("AQI", vals,
                      itemstyle_opts=opts.ItemStyleOpts(color="#c0392b"))
           .reversal_axis()
           .set_global_opts(
               title_opts=opts.TitleOpts(title="2024 年 AQI 最高 15 城"),
               xaxis_opts=opts.AxisOpts(name="AQI"),
               tooltip_opts=opts.TooltipOpts(trigger="axis")))

    cnt = Counter(rank["cluster"].values())
    pie = (Pie(init_opts=init)
           .add("", list(cnt.items()), radius=["35%", "65%"])
           .set_global_opts(
               title_opts=opts.TitleOpts(title="城市污染类型聚类"),
               legend_opts=opts.LegendOpts(orient="vertical", pos_left="left"))
           .set_series_opts(
               label_opts=opts.LabelOpts(formatter="{b}: {c} ({d}%)")))

    heat_data = [[mi, pi, num(month["national"][p_][mi])]
                 for pi, p_ in enumerate(POLLUTANTS) for mi in range(12)]
    heat = (HeatMap(init_opts=init)
            .add_xaxis(["%d月" % m for m in month["months"]])
            .add_yaxis("浓度", POLLUTANTS, heat_data)
            .set_global_opts(
                title_opts=opts.TitleOpts(title="污染物月度周期热力图"),
                visualmap_opts=opts.VisualMapOpts(min_=0, max_=160,
                                                  orient="horizontal", pos_left="center"),
                tooltip_opts=opts.TooltipOpts(is_show=True)))

    page = Page(page_title="空气质量时空演变 · PyEcharts 交互分析")
    page.add(line, bar, pie, heat)
    page.render(out_html)


def run(web_dir, out_dir):
    year, month, corr, rank = load_all(web_dir)
    fig_dir = os.path.join(out_dir, "figures")
    os.makedirs(fig_dir, exist_ok=True)

    print("生成静态统计图（Matplotlib / Seaborn）...")
    static_charts(year, month, corr, rank, fig_dir)

    print("生成官方权威数据对照图（Matplotlib / Seaborn）...")
    official_summary = official_compare_chart(
        os.path.join(out_dir, "official_benchmark.json"), year, fig_dir)
    if official_summary:
        # 站点根目录是 air_quality_web，同步一份便于网页内直接查看
        web_fig_dir = os.path.join(web_dir, "figures")
        os.makedirs(web_fig_dir, exist_ok=True)
        dst = os.path.join(web_fig_dir, official_summary["figure"])
        shutil.copyfile(os.path.join(fig_dir, official_summary["figure"]), dst)
        print("  站点图:", dst, os.path.getsize(dst), "bytes")

    print("生成交互图表（PyEcharts）...")
    # 仅在站点内生成一份：引用同级 js/echarts.min.js，可通过 serve.py 直接访问
    CurrentConfig.ONLINE_HOST = "js/"
    web_html = os.path.join(web_dir, "analysis_charts.html")
    pyecharts_page(year, month, rank, web_html)
    print("  站点 HTML:", os.path.basename(web_html), os.path.getsize(web_html), "bytes")

    summary = {
        "pearson_tests": corr.get("tests", {}),
        "linear_trend": corr.get("trend", {}),
        "figures": sorted(os.listdir(fig_dir)),
        "web_charts_html": os.path.basename(web_html),
    }
    if official_summary:
        summary["official_benchmark"] = official_summary
    with open(os.path.join(out_dir, "stats_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("分析图表完成 ->", out_dir)


if __name__ == "__main__":
    BASE = os.path.dirname(os.path.abspath(__file__))
    run(os.path.join(BASE, "air_quality_web"), os.path.join(BASE, "analysis"))
