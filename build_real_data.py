# -*- coding: utf-8 -*-
"""
build_real_data.py - 真实数据接入管线
=====================================
数据来源（全部真实）：
  1) 空气质量：中国环境监测总站（CNEMC）逐日城市数据，经 quotsoft.net 历史归档
     （china_cities_YYYYMMDD.csv）与 CN-AIR 开源镜像（GewisLab）整理；
     2015-2024 年按每 3 天抽样下载，缓存于 _cache_cnair/
  2) 气象要素：Open-Meteo 历史气象档案 API（ERA5 再分析，缓存于 _weather_cache.json）
  3) 权威基准：生态环境部 / 环境保护部年度公报与空气质量通报（带官方 URL 与原文摘录，
     见 official_benchmark.py），生成 analysis/official_benchmark.json / .csv
     与 air_quality_web/data/official_benchmark.js

依赖：NumPy、pandas、SciPy（数值清洗与统计检验）；
      Matplotlib、Seaborn、PyEcharts（分析图表，见 analysis_charts.py）

用法：
  python build_real_data.py download   # 下载抽样日数据（可断点续传）
  python build_real_data.py build      # 清洗聚合，生成 data/*.js + 权威数据集 + 分析图表
  python build_real_data.py analyze    # 仅重绘分析图表（不重算数据）
  python build_real_data.py official   # 仅重建官方基准数据集并刷新对照图
  python build_real_data.py official --verify   # 联网复核官方 HTML 通报数值后重建
  python build_real_data.py all
"""
import io
import json
import math
import os
import re
import sys
import ast
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
from scipy import stats

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = r"d:/数据分析与可视化"
CACHE = os.path.join(BASE, "_cache_cnair")
WEATHER_CACHE = os.path.join(BASE, "_weather_cache.json")
WEB = os.path.join(BASE, "air_quality_web")
RAW = "https://raw.gitcode.com/GewisLab/CN-AIR/raw/main/"
YEARS = list(range(2015, 2025))
POLLUTANTS = ["AQI", "PM2.5", "O3", "NO2", "SO2", "CO"]
LEVELS = ["优", "良", "轻度污染", "中度污染", "重度污染"]
MONTHS = list(range(1, 13))

# ------------------------------------------------------------------
# 读取城市清单（province -> [(city, lon, lat)]），来自 generate_data.py
# ------------------------------------------------------------------
def load_cities():
    src = open(os.path.join(BASE, "generate_data.py"), encoding="utf-8").read()
    m = re.search(r"CITIES\s*=\s*\{.*?\n\}", src, re.S)
    text = re.sub(r"#.*", "", m.group(0))          # 去掉行内注释再求值
    text = text[text.index("=") + 1:].strip()      # 只保留字典表达式
    return ast.literal_eval(text)

CITIES = load_cities()
CITY_INFO = {}          # city -> (province, lon, lat)
for prov, items in CITIES.items():
    for city, lon, lat in items:
        CITY_INFO[city] = (prov, lon, lat)

# ------------------------------------------------------------------
# 阶段 1：下载抽样日数据（2015-2024，每 3 天 1 天）
# ------------------------------------------------------------------
def sample_dates(year):
    dates = []
    dt, end = date(year, 1, 1), date(year, 12, 31)
    while dt <= end:
        if dt.timetuple().tm_yday % 3 == 1:
            dates.append(dt)
        dt += timedelta(days=1)
    return dates

def download_one(dt):
    y = dt.year
    ymd = dt.strftime("%Y%m%d")
    path = os.path.join(CACHE, ymd + ".csv")
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return ymd, "cached"
    # 首选 CN-AIR 镜像（带 LFS 的稳定 CDN），备选 quotsoft 原始归档
    urls = [urllib.parse.quote(RAW + "城市_{a}-{b}/城市_{a}-{b}/china_cities_{c}.csv".format(
        a="%d0101" % y, b="%d1231" % y, c=ymd), safe=":/")]
    urls.append("https://quotsoft.net/air/data/china_cities_%s.csv" % ymd)
    last = ""
    for i, url in enumerate(urls):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=60).read()
            if len(data) < 10000:
                last = "too-small"
                continue
            with open(path, "wb") as f:
                f.write(data)
            return ymd, "ok" if i == 0 else "ok-mirror"
        except Exception as e:
            last = repr(e)[:60]
    return ymd, "fail:" + last

def stage_download():
    os.makedirs(CACHE, exist_ok=True)
    tasks = [d for y in YEARS for d in sample_dates(y)]
    print("计划下载 %d 个抽样日（2015-2024，每 3 天 1 天）" % len(tasks))
    ok = fail = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(download_one, d): d for d in tasks}
        for i, fut in enumerate(as_completed(futs), 1):
            ymd, st = fut.result()
            if st.startswith("fail"):
                fail += 1
                if fail <= 5:
                    print("  FAIL", ymd, st)
            else:
                ok += 1
            if i % 100 == 0:
                print("  进度 %d/%d  成功 %d  失败 %d  用时 %.0fs" % (i, len(tasks), ok, fail, time.time() - t0))
    print("下载完成：成功 %d，失败 %d，用时 %.0fs" % (ok, fail, time.time() - t0))

# ------------------------------------------------------------------
# 解析：CN-AIR 逐日 CSV -> (date, city, pollutant) 长表
# ------------------------------------------------------------------
def parse_cache():
    rows = []
    files = sorted(f for f in os.listdir(CACHE) if f.endswith(".csv"))
    print("解析 %d 个逐日数据文件 ..." % len(files))
    for i, fn in enumerate(files, 1):
        df = None
        for enc in ("utf-8", "gbk"):
            try:
                df = pd.read_csv(os.path.join(CACHE, fn), encoding=enc)
                break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        if df is None or "type" not in df.columns:
            continue
        df = df[df["type"].isin(POLLUTANTS)]
        if df.empty:
            continue
        ymd = fn[:8]
        date = "%s-%s-%s" % (ymd[:4], ymd[4:6], ymd[6:8])
        long = df.melt(id_vars=["date", "hour", "type"], var_name="city", value_name="v")
        # NumPy：数值化后用有限值掩码剔除缺失、非数值与超量程异常
        v = pd.to_numeric(long["v"], errors="coerce").to_numpy(dtype=float)
        long = long.assign(v=v)[np.isfinite(v) & (v > 0) & (v < 2000)]
        g = long.groupby(["city", "type"])["v"].mean().reset_index()
        for _, r in g.iterrows():
            if r["city"] in CITY_INFO:
                rows.append((date, r["city"], r["type"], round(float(r["v"]), 2)))
        if i % 100 == 0:
            print("  已解析 %d/%d" % (i, len(files)))
    df = pd.DataFrame(rows, columns=["date", "city", "type", "v"])
    df = df.pivot_table(index=["date", "city"], columns="type", values="v",
                        aggfunc="mean").reset_index()
    return df

# ------------------------------------------------------------------
# 气象：Open-Meteo 历史档案（按城市逐请求，缓存）
# ------------------------------------------------------------------
def fetch_weather():
    if os.path.exists(WEATHER_CACHE):
        return json.load(open(WEATHER_CACHE, encoding="utf-8"))
    out = {}
    for i, (city, (prov, lon, lat)) in enumerate(CITY_INFO.items(), 1):
        url = ("https://archive-api.open-meteo.com/v1/archive?"
               "latitude=%s&longitude=%s&start_date=2015-01-01&end_date=2024-12-31"
               "&daily=temperature_2m_mean,precipitation_sum,wind_speed_10m_max"
               "&timezone=Asia%%2FShanghai" % (lat, lon))
        try:
            data = json.loads(urllib.request.urlopen(url, timeout=60).read())
            out[city] = {"time": data["daily"]["time"],
                         "temp": data["daily"]["temperature_2m_mean"],
                         "precip": data["daily"]["precipitation_sum"],
                         "wind": data["daily"]["wind_speed_10m_max"]}
            print("  气象 %d/%d %s" % (i, len(CITY_INFO), city))
        except Exception as e:
            print("  气象 FAIL", city, repr(e)[:80])
    json.dump(out, open(WEATHER_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return out

# ------------------------------------------------------------------
# 阶段 2：清洗聚合 -> 生成 data/*.js
# ------------------------------------------------------------------
def r1(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 1)

def stage_build():
    air = parse_cache()
    air["year"] = air["date"].str[:4].astype(int)
    air["month"] = air["date"].str[5:7].astype(int)
    print("合并后记录：", len(air), " 覆盖城市：", air["city"].nunique(),
          " 年份：", sorted(air["year"].unique()))

    wx = fetch_weather()

    # ---- 城市-年均（含气象） ----
    g = air.groupby(["city", "year"])
    cy = g[list(POLLUTANTS)].mean().reset_index()
    # 气象年聚合
    wrows = []
    for city, w in wx.items():
        df = pd.DataFrame(w)
        df["year"] = df["time"].str[:4].astype(int)
        df["month"] = df["time"].str[5:7].astype(int)
        agg = df.groupby("year").agg(temp=("temp", "mean"), precip=("precip", "sum"),
                                     wind=("wind", "mean")).reset_index()
        agg["city"] = city
        wrows.append(agg)
    wdf = pd.concat(wrows, ignore_index=True)
    cy = cy.merge(wdf[["city", "year", "temp", "precip", "wind"]], on=["city", "year"], how="left")

    prov = {c: CITY_INFO[c][0] for c in cy["city"].unique()}
    cy["province"] = cy["city"].map(prov)
    lonlat = {c: (CITY_INFO[c][1], CITY_INFO[c][2]) for c in cy["city"].unique()}

    # ---- year_avg.js ----
    cities_rows = []
    for _, r in cy.iterrows():
        cities_rows.append({
            "city": r["city"], "province": r["province"],
            "lon": lonlat[r["city"]][0], "lat": lonlat[r["city"]][1],
            "year": int(r["year"]),
            **{p: r1(r[p]) for p in POLLUTANTS},
            "temp": r1(r.get("temp")), "precip": r1(r.get("precip")), "wind": r1(r.get("wind")),
        })
    ny = air.groupby("year")[POLLUTANTS].mean()
    national = [{"year": int(y), **{p: r1(ny.loc[y, p]) for p in POLLUTANTS}}
                for y in sorted(ny.index)]
    year_avg = {"years": YEARS, "national": national, "cities": cities_rows}

    # ---- 月度聚合（多年平均月变化） ----
    cm = air.groupby(["city", "year", "month"])[POLLUTANTS].mean().reset_index()
    cm["province"] = cm["city"].map(prov)
    nat_m = cm.groupby("month")[POLLUTANTS].mean()
    national_m = {p: [r1(nat_m.loc[m, p]) for m in MONTHS] for p in POLLUTANTS}
    prov_m = {}
    for p_ in sorted(cm["province"].unique()):
        sub = cm[cm["province"] == p_].groupby("month")[POLLUTANTS].mean()
        prov_m[p_] = {p: [r1(sub.loc[m, p]) for m in MONTHS] for p in POLLUTANTS}
    # 等级占比：NumPy 向量化分级（GB 3095-2012 阈值）+ bincount 统计
    def level_shares(sub):
        a = pd.to_numeric(pd.Series(sub), errors="coerce").to_numpy(dtype=float)
        a = a[np.isfinite(a)]
        if a.size == 0:
            return [0.0] * 5
        idx = np.searchsorted([50, 100, 150, 200], a, side="left")
        return np.round(np.bincount(idx, minlength=5) / a.size * 100, 1).tolist()
    level_by_year = {str(y): level_shares(cy[cy["year"] == y]["AQI"].dropna()) for y in YEARS}
    level_by_prov = {}
    for p_ in sorted(cy["province"].dropna().unique()):
        level_by_prov[p_] = {str(y): level_shares(
            cy[(cy["province"] == p_) & (cy["year"] == y)]["AQI"].dropna()) for y in YEARS}
    month_avg = {"months": MONTHS, "national": national_m, "byProvince": prov_m,
                 "levelByYear": level_by_year, "levelByProvince": level_by_prov,
                 "levels": LEVELS}

    # ---- 相关性 ----
    monthly = []
    for city, w in wx.items():
        df = pd.DataFrame(w)
        df["year"] = df["time"].str[:4].astype(int)
        df["month"] = df["time"].str[5:7].astype(int)
        df = df[(df["year"] >= 2015) & (df["year"] <= 2024)]
        mdf = df.groupby(["year", "month"]).agg(
            temp=("temp", "mean"), precip=("precip", "sum"), wind=("wind", "mean")).reset_index()
        sub = cm[cm["city"] == city]
        mrg = mdf.merge(sub, on=["year", "month"], how="inner")
        for _, r in mrg.iterrows():
            monthly.append({"city": city, "province": prov[city], **{p: r[p] for p in POLLUTANTS},
                            "temp": r["temp"], "precip": r["precip"], "wind": r["wind"]})
    mdf = pd.DataFrame(monthly)
    vars_ = POLLUTANTS + ["temp", "precip", "wind"]
    corr = mdf[vars_].corr(method="pearson")
    matrix = [[r1(corr.loc[a, b] * 100) / 100 for b in vars_] for a in vars_]
    labels = POLLUTANTS + ["气温", "降水", "风速"]
    # 散点（抽样，控制文件体积）
    def scatter(x, y):
        sub = mdf[[x, y, "province"]].dropna()
        step = max(1, len(sub) // 700)
        return [[r1(r[x]), r1(r[y]), r["province"]] for _, r in sub.iloc[::step].iterrows()]
    # ---- SciPy：相关显著性检验 + 全国十年线性趋势检验 ----
    def pearson_test(x, y):
        sub = mdf[[x, y]].dropna()
        if len(sub) < 3:
            return {"r": None, "p": None, "n": int(len(sub))}
        r, p = stats.pearsonr(sub[x].to_numpy(float), sub[y].to_numpy(float))
        return {"r": round(float(r), 3), "p": float("%.3g" % p), "n": int(len(sub))}

    tests = {"气温-O3": pearson_test("temp", "O3"),
             "风速-PM2.5": pearson_test("wind", "PM2.5"),
             "气温-PM2.5": pearson_test("temp", "PM2.5")}
    yrs = np.asarray([d["year"] for d in national], dtype=float)
    trend = {}
    for p_ in POLLUTANTS:
        vals = np.asarray([d[p_] if d[p_] is not None else np.nan
                           for d in national], dtype=float)
        ok = np.isfinite(vals)
        if ok.sum() < 3:
            continue
        lr = stats.linregress(yrs[ok], vals[ok])
        trend[p_] = {"slope_per_year": round(float(lr.slope), 2),
                     "r": round(float(lr.rvalue), 3),
                     "p": float("%.3g" % lr.pvalue),
                     "change_2015_2024": round(float(lr.slope * 9), 1)}
    print("SciPy 趋势斜率/年：", {k: v["slope_per_year"] for k, v in trend.items()})

    corr_data = {"labels": labels, "matrix": matrix,
                 "scatterTempO3": scatter("temp", "O3"),
                 "scatterWindPm": scatter("wind", "PM2.5"),
                 "tests": tests, "trend": trend}

    # ---- 排名 / 改善榜 / 聚类 ----
    p15 = cy[cy["year"] == 2015].set_index("city")
    p24 = cy[cy["year"] == 2024].set_index("city")
    improve = []
    for city in p24.index.intersection(p15.index):
        a15, a24 = p15.loc[city, "AQI"], p24.loc[city, "AQI"]
        m15, m24 = p15.loc[city, "PM2.5"], p24.loc[city, "PM2.5"]
        if not (a15 and a24 and m15 and m24):
            continue
        improve.append({"city": city, "province": prov[city],
                        "aqi2015": r1(a15), "aqi2024": r1(a24),
                        "pm25_2015": r1(m15), "pm25_2024": r1(m24),
                        "pm25_drop_pct": round((m15 - m24) / m15 * 100, 1)})
    improve.sort(key=lambda d: -d["pm25_drop_pct"])

    means = air.groupby("city")[["PM2.5", "O3"]].mean()
    cluster = {}
    for city, r in means.iterrows():
        if r["PM2.5"] >= 40:
            cluster[city] = "颗粒物主导型"
        elif r["O3"] >= 100:
            cluster[city] = "臭氧主导型"
        else:
            cluster[city] = "优良型"

    top20 = sorted([c for c in cities_rows if c["year"] == 2024],
                   key=lambda d: -d["AQI"])[:20]
    city_rank = {"top20": top20, "improve": improve[:15], "cluster": cluster}

    # ---- 写出 ----
    def dump(name, obj, note):
        header = ("// 真实数据：空气质量数据源自中国环境监测总站 CNEMC"
                  "（经 quotsoft.net 历史归档 / CN-AIR 开源镜像整理，2015-2024 每 3 天抽样），"
                  "气象数据源自 Open-Meteo 历史气象档案（真实再分析数据）\n")
        path = os.path.join(WEB, "data", name)
        open(path, "w", encoding="utf-8").write(
            header + "window.%s = %s;\n" % (note, json.dumps(obj, ensure_ascii=False)))
        print("写出", name, os.path.getsize(path), "bytes")

    dump("year_avg.js", year_avg, "AQI_YEAR_AVG")
    dump("month_avg.js", month_avg, "AQI_MONTH_AVG")
    dump("corr_data.js", corr_data, "AQI_CORR")
    dump("city_rank.js", city_rank, "AQI_RANK")
    print("构建完成")


# ------------------------------------------------------------------
# 阶段 3：统计分析图表（Matplotlib / Seaborn / PyEcharts）
# ------------------------------------------------------------------
def stage_analyze():
    """只读取已生成的 data/*.js 重绘图表，不触碰原始数据缓存。"""
    try:
        import analysis_charts
    except ImportError as e:
        print("跳过分析图表（缺少可视化依赖）：", e)
        return
    analysis_charts.run(WEB, os.path.join(BASE, "analysis"))


# ------------------------------------------------------------------
# 阶段 2.5：官方权威基准数据集（生态环境部公报 / 年度空气质量通报）
# ------------------------------------------------------------------
def stage_official(do_verify=False):
    """重建官方基准数据集；不联网时沿用上一次的联网复核记录。"""
    try:
        import official_benchmark
    except ImportError as e:
        print("跳过官方基准数据集：", e)
        return
    official_benchmark.build(do_verify=do_verify)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    verify = "--verify" in sys.argv[1:]
    if arg in ("download", "all"):
        stage_download()
    if arg in ("build", "all"):
        stage_build()
    if arg in ("official", "build", "all"):
        stage_official(verify)
    if arg in ("analyze", "build", "all", "official"):
        stage_analyze()
