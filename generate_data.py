# -*- coding: utf-8 -*-
"""
空气质量可视化系统 - 模拟数据生成脚本
依据项目报告设定的数据规律（2015-2024 治理改善趋势、空间集聚、季节周期、
气象相关性）生成结构化数据，导出为前端可直接 <script> 加载的 JS 数据文件。
注意：本项目为课程作业，数据为按公开统计规律模拟生成，非真实监测值。
"""
import json
import math
import random

random.seed(42)

YEARS = list(range(2015, 2025))
POLLUTANTS = ["AQI", "PM2.5", "O3", "NO2", "SO2", "CO"]

# 省份 -> [(城市, 经度, 纬度)]
CITIES = {
    "北京": [("北京", 116.4, 39.9)], "天津": [("天津", 117.2, 39.1)],
    "河北": [("石家庄", 114.5, 38.0), ("唐山", 118.2, 39.6), ("保定", 115.5, 38.9),
             ("邯郸", 114.5, 36.6), ("邢台", 114.5, 37.1), ("沧州", 116.9, 38.3)],
    "山西": [("太原", 112.5, 37.9), ("大同", 113.3, 40.1), ("临汾", 111.5, 36.1),
             ("运城", 111.0, 35.0), ("长治", 113.1, 36.2)],
    "内蒙古": [("呼和浩特", 111.7, 40.8), ("包头", 109.8, 40.7), ("鄂尔多斯", 109.8, 39.6)],
    "辽宁": [("沈阳", 123.4, 41.8), ("大连", 121.6, 38.9), ("鞍山", 123.0, 41.1)],
    "吉林": [("长春", 125.3, 43.9), ("吉林市", 126.5, 43.8)],
    "黑龙江": [("哈尔滨", 126.6, 45.8), ("齐齐哈尔", 123.9, 47.3)],
    "上海": [("上海", 121.5, 31.2)],
    "江苏": [("南京", 118.8, 32.1), ("苏州", 120.6, 31.3), ("徐州", 117.2, 34.3),
             ("无锡", 120.3, 31.6), ("常州", 119.9, 31.8)],
    "浙江": [("杭州", 120.2, 30.3), ("宁波", 121.6, 29.9), ("温州", 120.7, 28.0)],
    "安徽": [("合肥", 117.3, 31.9), ("蚌埠", 117.4, 32.9), ("淮南", 117.0, 32.6)],
    "福建": [("福州", 119.3, 26.1), ("厦门", 118.1, 24.5)],
    "江西": [("南昌", 115.9, 28.7), ("九江", 116.0, 29.7)],
    "山东": [("济南", 117.0, 36.7), ("青岛", 120.4, 36.1), ("淄博", 118.1, 36.8),
             ("聊城", 115.98, 36.46), ("菏泽", 115.5, 35.2), ("烟台", 121.4, 37.5)],
    "河南": [("郑州", 113.6, 34.7), ("洛阳", 112.5, 34.7), ("安阳", 114.4, 36.1),
             ("新乡", 113.9, 35.3), ("焦作", 113.2, 35.2), ("开封", 114.3, 34.8),
             ("濮阳", 115.03, 35.76)],
    "湖北": [("武汉", 114.3, 30.6), ("宜昌", 111.3, 30.7)],
    "湖南": [("长沙", 113.0, 28.2), ("株洲", 113.1, 27.8)],
    "广东": [("广州", 113.3, 23.1), ("深圳", 114.1, 22.5), ("佛山", 113.1, 23.0)],
    "广西": [("南宁", 108.3, 22.8), ("柳州", 109.4, 24.3)],
    "海南": [("海口", 110.3, 20.0)],
    "重庆": [("重庆", 106.5, 29.6)],
    "四川": [("成都", 104.1, 30.7), ("绵阳", 104.7, 31.5)],
    "贵州": [("贵阳", 106.7, 26.6)],
    "云南": [("昆明", 102.7, 25.0)],
    "西藏": [("拉萨", 91.1, 29.7)],
    "陕西": [("西安", 108.9, 34.3), ("咸阳", 108.7, 34.3), ("渭南", 109.5, 34.5)],
    "甘肃": [("兰州", 103.8, 36.1), ("天水", 105.7, 34.6)],
    "青海": [("西宁", 101.8, 36.6)],
    "宁夏": [("银川", 106.2, 38.5), ("石嘴山", 106.4, 39.0)],
    "新疆": [("乌鲁木齐", 87.6, 43.8), ("喀什", 75.99, 39.47)],
}

# 各省 2015 年 PM2.5 基准(ug/m3)，体现华北、汾渭平原高污染集聚
PROV_PM25_2015 = {
    "北京": 72, "天津": 78, "河北": 84, "山西": 76, "内蒙古": 50, "辽宁": 60,
    "吉林": 46, "黑龙江": 42, "上海": 56, "江苏": 64, "浙江": 50, "安徽": 60,
    "福建": 36, "江西": 44, "山东": 72, "河南": 80, "湖北": 56, "湖南": 50,
    "广东": 40, "广西": 38, "海南": 22, "重庆": 62, "四川": 56, "贵州": 36,
    "云南": 32, "西藏": 18, "陕西": 68, "甘肃": 52, "青海": 40, "宁夏": 58, "新疆": 68,
}
PROV_O3_2015 = {  # 臭氧基准：京津冀鲁豫及华东偏高
    "北京": 130, "天津": 132, "河北": 128, "山西": 120, "内蒙古": 110, "辽宁": 112,
    "吉林": 104, "黑龙江": 100, "上海": 128, "江苏": 126, "浙江": 122, "安徽": 120,
    "福建": 106, "江西": 114, "山东": 130, "河南": 128, "湖北": 118, "湖南": 116,
    "广东": 112, "广西": 108, "海南": 100, "重庆": 116, "四川": 114, "贵州": 104,
    "云南": 100, "西藏": 96, "陕西": 124, "甘肃": 108, "青海": 102, "宁夏": 112, "新疆": 110,
}

MONTHS = list(range(1, 13))


def pm25_seasonal(m):
    return {12: 1.5, 1: 1.55, 2: 1.4, 11: 1.3, 3: 1.1, 10: 1.05,
            4: 0.9, 9: 0.9, 5: 0.8, 6: 0.7, 7: 0.65, 8: 0.65}[m]


def o3_seasonal(m):
    return {6: 1.45, 7: 1.5, 8: 1.4, 5: 1.15, 9: 1.1, 4: 0.95,
            10: 0.85, 3: 0.75, 11: 0.65, 12: 0.55, 1: 0.5, 2: 0.6}[m]


def temp_seasonal(m, lat):
    amp = max(6.0, (abs(lat) - 18) * 0.55)
    return math.cos((m - 7) * math.pi / 6) * amp


def calc_aqi(pm25, o3, no2, so2, co):
    """近似 AQI：以 PM2.5 与 O3 为主控因子"""
    a_pm = pm25 * 1.05 + 12 if pm25 < 35 else pm25 * 0.92 + 24
    a_o3 = o3 * 0.42 + 8
    a_no2 = no2 * 1.2
    a_so2 = so2 * 0.55
    base = max(a_pm, a_o3, a_no2, a_so2, co * 22)
    return base


def level_of(aqi):
    if aqi <= 50: return "优"
    if aqi <= 100: return "良"
    if aqi <= 150: return "轻度污染"
    if aqi <= 200: return "中度污染"
    return "重度污染"


city_records = []       # 城市年均记录
month_records = []      # 城市月度记录（用于相关性/散点/季节图）

for prov, cities in CITIES.items():
    for (name, lon, lat) in cities:
        base_pm = PROV_PM25_2015[prov] * random.uniform(0.9, 1.1)
        base_o3 = PROV_O3_2015[prov] * random.uniform(0.95, 1.05)
        base_no2 = random.uniform(26, 46) * (1.2 if lat > 33 else 1.0)
        base_so2 = random.uniform(30, 60) * (1.15 if lon < 118 and lat > 33 else 0.95)
        base_co = random.uniform(0.9, 1.5)
        annual_temp = 27 - 0.62 * abs(lat) + random.uniform(-2, 2)
        annual_precip = max(80, 1500 - (lat - 18) * 55 + random.uniform(-250, 250))
        base_wind = random.uniform(1.4, 3.2)

        for i, y in enumerate(YEARS):
            # 年际下降：PM2.5 约 -5.5%/年，SO2 -9%，NO2 -3%，CO -3.5%，O3 微降并年中反弹
            f_pm = (1 - 0.055) ** i * random.uniform(0.97, 1.03)
            f_o3 = (1 - 0.012) ** i * (1 + 0.03 * math.exp(-((i - 5) ** 2) / 3)) * random.uniform(0.98, 1.02)
            f_no2 = (1 - 0.03) ** i * random.uniform(0.98, 1.02)
            f_so2 = (1 - 0.09) ** i * random.uniform(0.96, 1.04)
            f_co = (1 - 0.035) ** i
            y_pm = base_pm * f_pm
            y_o3 = base_o3 * f_o3
            y_no2 = base_no2 * f_no2
            y_so2 = base_so2 * f_so2
            y_co = base_co * f_co
            y_aqi = calc_aqi(y_pm, y_o3, y_no2, y_so2, y_co)
            city_records.append({
                "city": name, "province": prov, "lon": lon, "lat": lat, "year": y,
                "AQI": round(y_aqi, 1), "PM2.5": round(y_pm, 1), "O3": round(y_o3, 1),
                "NO2": round(y_no2, 1), "SO2": round(y_so2, 1), "CO": round(y_co, 2),
            })
            # 月度数据（冬季随机污染过程、夏季臭氧增幅，增加等级分布层次）
            episode = random.uniform(1.0, 1.28) if y_pm > 45 else random.uniform(1.0, 1.12)
            o3_surge = random.uniform(1.0, 1.18)
            y_temp, y_precip, y_wind = [], [], []
            for m in MONTHS:
                winter_ep = episode if m in (12, 1, 2) else 1.0
                summer_o3 = o3_surge if m in (6, 7, 8) else 1.0
                pm_m = y_pm * pm25_seasonal(m) * winter_ep * random.uniform(0.88, 1.12)
                o3_m = y_o3 * o3_seasonal(m) * summer_o3 * random.uniform(0.88, 1.12)
                no2_m = y_no2 * (1.18 if m in (12, 1, 2) else 0.94) * winter_ep * random.uniform(0.9, 1.1)
                so2_m = y_so2 * (1.3 if m in (12, 1, 2) else 0.9) * winter_ep * random.uniform(0.9, 1.1)
                co_m = y_co * (1.2 if m in (12, 1, 2) else 0.92) * winter_ep
                t_m = annual_temp + temp_seasonal(m, lat) + random.uniform(-1, 1)
                w = {6: 0.22, 7: 0.24, 8: 0.18, 5: 0.1, 9: 0.08, 4: 0.06,
                     3: 0.04, 10: 0.04, 11: 0.02, 12: 0.01, 1: 0.005, 2: 0.005}[m]
                p_m = annual_precip * w * random.uniform(0.6, 1.4)
                w_m = base_wind * ({4: 1.2, 5: 1.15, 3: 1.1, 6: 1.0, 9: 1.0,
                                    7: 0.85, 8: 0.85, 12: 0.8, 1: 0.8, 2: 0.85,
                                    10: 0.95, 11: 0.9}[m]) * random.uniform(0.85, 1.15)
                aqi_m = calc_aqi(pm_m, o3_m, no2_m, so2_m, co_m)
                month_records.append({
                    "city": name, "province": prov, "year": y, "month": m,
                    "AQI": round(aqi_m, 1), "PM2.5": round(pm_m, 1), "O3": round(o3_m, 1),
                    "NO2": round(no2_m, 1), "SO2": round(so2_m, 1), "CO": round(co_m, 2),
                    "temp": round(t_m, 1), "precip": round(p_m, 1), "wind": round(w_m, 2),
                    "level": level_of(aqi_m),
                })
                y_temp.append(t_m); y_precip.append(p_m); y_wind.append(w_m)
            # 将年均气象量写入城市年均记录（供地图/排名页使用）
            rec = next(r for r in city_records if r["city"] == name and r["year"] == y)
            rec["temp"] = round(sum(y_temp) / 12, 1)
            rec["precip"] = round(sum(y_precip), 1)
            rec["wind"] = round(sum(y_wind) / 12, 2)

# ---------- 汇总：全国年均 ----------
def national_year_avg(year):
    rs = [r for r in city_records if r["year"] == year]
    out = {"year": year}
    for k in POLLUTANTS:
        out[k] = round(sum(r[k] for r in rs) / len(rs), 1)
    return out

NATIONAL_YEAR = [national_year_avg(y) for y in YEARS]

# ---------- 汇总：全国月度均值 ----------
NATIONAL_MONTH = {k: [] for k in POLLUTANTS}
for m in MONTHS:
    rs = [r for r in month_records if r["month"] == m]
    for k in POLLUTANTS:
        NATIONAL_MONTH[k].append(round(sum(r[k] for r in rs) / len(rs), 1))

# ---------- 汇总：分省月度均值（时序页按省筛选） ----------
PROV_MONTH = {}
for prov in CITIES:
    PROV_MONTH[prov] = {k: [] for k in POLLUTANTS}
    for m in MONTHS:
        rs = [r for r in month_records if r["month"] == m and r["province"] == prov]
        for k in POLLUTANTS:
            PROV_MONTH[prov][k].append(round(sum(r[k] for r in rs) / len(rs), 1))

# ---------- 污染等级占比（按年份，基于全国城市-月记录） ----------
LEVELS = ["优", "良", "轻度污染", "中度污染", "重度污染"]
LEVEL_BY_YEAR = {}
for y in YEARS:
    rs = [r for r in month_records if r["year"] == y]
    n = len(rs)
    LEVEL_BY_YEAR[str(y)] = [round(100 * sum(1 for r in rs if r["level"] == lv) / n, 1) for lv in LEVELS]

# ---------- 污染等级占比（分省 × 分年，时序页按省联动） ----------
PROV_LEVEL = {}
for prov in CITIES:
    PROV_LEVEL[prov] = {}
    for y in YEARS:
        rs = [r for r in month_records if r["year"] == y and r["province"] == prov]
        n = len(rs)
        PROV_LEVEL[prov][str(y)] = [round(100 * sum(1 for r in rs if r["level"] == lv) / n, 1) for lv in LEVELS]

# ---------- 相关性矩阵 ----------
CORR_KEYS = ["AQI", "PM2.5", "O3", "NO2", "SO2", "CO", "temp", "precip", "wind"]
CORR_LABELS = ["AQI", "PM2.5", "O3", "NO2", "SO2", "CO", "气温", "降水", "风速"]


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    vx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    vy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return cov / (vx * vy) if vx * vy else 0.0


corr_matrix = []
for k1 in CORR_KEYS:
    row = []
    for k2 in CORR_KEYS:
        xs = [r[k1] for r in month_records]
        ys = [r[k2] for r in month_records]
        row.append(round(pearson(xs, ys), 2))
    corr_matrix.append(row)

# ---------- 散点样本（气温-O3、风速-PM2.5） ----------
sample = random.sample(month_records, 800)
scatter_temp_o3 = [[r["temp"], r["O3"], r["province"]] for r in sample]
scatter_wind_pm = [[r["wind"], r["PM2.5"], r["province"]] for r in random.sample(month_records, 800)]

# ---------- 城市聚类（颗粒物主导型 / 臭氧主导型 / 优良型） ----------
city_cluster = {}
for prov, cs in CITIES.items():
    for (name, lon, lat) in cs:
        rs = [r for r in city_records if r["city"] == name]
        pm = sum(r["PM2.5"] for r in rs) / len(rs)
        o3 = sum(r["O3"] for r in rs) / len(rs)
        aqi = sum(r["AQI"] for r in rs) / len(rs)
        if aqi < 75:
            city_cluster[name] = "优良型"
        elif o3 > 118 and o3 >= pm * 0.95:
            city_cluster[name] = "臭氧主导型"
        else:
            city_cluster[name] = "颗粒物主导型"

# ---------- 排名数据 ----------
TOP20_2024 = sorted([r for r in city_records if r["year"] == 2024],
                    key=lambda r: -r["AQI"])[:20]
improve = []
for prov, cs in CITIES.items():
    for (name, lon, lat) in cs:
        r15 = next(r for r in city_records if r["city"] == name and r["year"] == 2015)
        r24 = next(r for r in city_records if r["city"] == name and r["year"] == 2024)
        improve.append({
            "city": name, "province": prov,
            "aqi2015": r15["AQI"], "aqi2024": r24["AQI"],
            "pm25_2015": r15["PM2.5"], "pm25_2024": r24["PM2.5"],
            "pm25_drop_pct": round(100 * (r15["PM2.5"] - r24["PM2.5"]) / r15["PM2.5"], 1),
        })
IMPROVE_RANK = sorted(improve, key=lambda r: -r["pm25_drop_pct"])


def dump(fname, var, obj):
    with open(f"air_quality_web/data/{fname}", "w", encoding="utf-8") as f:
        f.write(f"// 自动生成：模拟数据，仅供课程演示\nwindow.{var} = ")
        f.write(json.dumps(obj, ensure_ascii=False))
        f.write(";\n")


dump("year_avg.js", "AQI_YEAR_AVG", {
    "years": YEARS,
    "national": NATIONAL_YEAR,
    "cities": city_records,
})
dump("month_avg.js", "AQI_MONTH_AVG", {
    "months": MONTHS,
    "national": NATIONAL_MONTH,
    "byProvince": PROV_MONTH,
    "levelByYear": LEVEL_BY_YEAR,
    "levelByProvince": PROV_LEVEL,
    "levels": LEVELS,
})
dump("corr_data.js", "AQI_CORR", {
    "labels": CORR_LABELS,
    "matrix": corr_matrix,
    "scatterTempO3": scatter_temp_o3,
    "scatterWindPm": scatter_wind_pm,
})
dump("city_rank.js", "AQI_RANK", {
    "top20": TOP20_2024,
    "improve": IMPROVE_RANK,
    "cluster": city_cluster,
})

print("数据生成完成：")
import os
for f in os.listdir("air_quality_web/data"):
    p = os.path.join("air_quality_web/data", f)
    print(f"  {f}: {os.path.getsize(p)/1024:.1f} KB")
