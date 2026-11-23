/* ============================================================
   main.js - 公共工具、全局筛选、侧边导航注入
   数据来源：data/year_avg.js、month_avg.js、corr_data.js、city_rank.js

   ★ 数据总开关：DATA_ENABLED = true。四个数据文件由
   build_real_data.py 基于真实监测数据生成；改回 false 可让全站
   回到「待接入真实数据」占位状态（用于演示 / 调试）。
   ============================================================ */

var DATA_ENABLED = true;

if (DATA_ENABLED) {
  // 按依赖顺序同步加载数据文件（解析期 document.write 保证顺序）
  document.write('<script src="data/year_avg.js"><\/script>');
  document.write('<script src="data/month_avg.js"><\/script>');
  document.write('<script src="data/corr_data.js"><\/script>');
  document.write('<script src="data/city_rank.js"><\/script>');
}

window.AQ = (function () {

  // 是否已接入数据（四个数据全局变量齐备）
  // ★ 关键：必须实时检测，不能提前捕获。main.js 通过 document.write 注入 data/*.js，
  //   这些脚本在 main.js 自身执行完毕后才运行；若在此处把结果存成变量，
  //   后续页面脚本调用 AQ.hasData() 会拿到陈旧的 false，导致图表进入“待接入真实数据”占位。
  function hasDataNow() {
    return typeof AQI_YEAR_AVG !== "undefined" &&
           typeof AQI_MONTH_AVG !== "undefined" &&
           typeof AQI_CORR !== "undefined" &&
           typeof AQI_RANK !== "undefined";
  }

  // 图表容器无数据占位
  function noData(el, msg) {
    if (!el) return;
    el.innerHTML = '<div class="no-data"><div class="ico">📊</div>' +
      '<div>待接入真实数据</div>' +
      (msg ? '<div style="font-size:12px">' + msg + '</div>' : '') + '</div>';
  }

  var YEARS = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024];

  var POLLUTANTS = ["AQI", "PM2.5", "O3", "NO2", "SO2", "CO"];
  var POLLUTANT_META = {
    "AQI":   { label: "AQI（空气质量指数）", unit: "",     max: 300, color: "#3a7bd5" },
    "PM2.5": { label: "PM2.5（细颗粒物）",   unit: "μg/m³", max: 160, color: "#8e6fd8" },
    "O3":    { label: "O₃（臭氧）",          unit: "μg/m³", max: 200, color: "#e67e22" },
    "NO2":   { label: "NO₂（二氧化氮）",     unit: "μg/m³", max: 80,  color: "#2fa876" },
    "SO2":   { label: "SO₂（二氧化硫）",     unit: "μg/m³", max: 80,  color: "#16a3b8" },
    "CO":    { label: "CO（一氧化碳）",      unit: "mg/m³", max: 3,   color: "#d16ba5" }
  };

  var LEVELS = ["优", "良", "轻度污染", "中度污染", "重度污染"];
  var LEVEL_COLORS = ["#2fa876", "#f2c94c", "#e67e22", "#d35400", "#c0392b"];

  // 污染物 -> 警示色阶（浅蓝洁净 -> 橙红污染）
  function warningPalette() {
    return ["#2f7ad6", "#54a0e8", "#7fc48f", "#f2c94c", "#ef8c3a", "#e2543a"];
  }

  // 全局筛选状态
  var state = { pollutant: "AQI", province: "全国", year: 2024 };
  var listeners = [];

  function provinces() {
    var set = {};
    AQI_YEAR_AVG.cities.forEach(function (r) { set[r.province] = 1; });
    return Object.keys(set);
  }

  // 触发所有图表刷新
  function notify() { listeners.forEach(function (fn) { fn(); }); }

  // ---------- 页面初始化：注入侧边栏 + 筛选栏 ----------
  var NAVS = [
    { key: "index",        href: "index.html",        ico: "🏠", name: "首页总览" },
    { key: "map",          href: "map.html",          ico: "🗺️", name: "空间分布分析" },
    { key: "trend",        href: "trend.html",        ico: "📈", name: "时序趋势分析" },
    { key: "rank",         href: "rank.html",         ico: "🏆", name: "城市排名对比" },
    { key: "correlation",  href: "correlation.html",  ico: "🔗", name: "相关性分析" },
    { key: "official",     href: "official.html",     ico: "▣", name: "权威数据对照" },
    { key: "about",        href: "about.html",        ico: "📖", name: "数据与项目说明" }
  ];

  function initPage(activeKey, opts) {
    opts = opts || {};
    opts.filters = opts.filters || [];
    // 侧边栏
    var side = document.getElementById("sidebar");
    if (side) {
      var navHtml = NAVS.map(function (n) {
        return '<a href="' + n.href + '" class="' + (n.key === activeKey ? "active" : "") + '">' +
               '<span class="ico">' + n.ico + '</span>' + n.name + '</a>';
      }).join("");
      side.innerHTML =
        '<div class="logo"><h1>空气质量时空演变<br>可视化系统</h1>' +
        '<span>2015-2024 · 全国地级市</span></div>' +
        '<nav>' + navHtml + '</nav>' +
        '<div class="foot">学号：25030710137<br>课程大作业 · 数据分析与可视化<br>数据：CNEMC 公开监测数据</div>';
    }
    // 筛选栏（未接入数据时显示占位提示，不渲染控件）
    var bar = document.getElementById("filterBar");
    if (bar) {
      if (!hasDataNow()) {
        bar.innerHTML = '<span class="filter-tip">⏳ 数据待接入：接入真实数据后，筛选与图表将自动启用（见 js/main.js 中 DATA_ENABLED 开关）</span>';
        return;
      }
      var html = "";
      if (opts.filters.indexOf("pollutant") >= 0) {
        html += '<div class="filter-item"><label>污染物指标</label><select id="fPollutant">' +
          POLLUTANTS.map(function (p) {
            return '<option value="' + p + '"' + (p === state.pollutant ? " selected" : "") + '>' +
                   POLLUTANT_META[p].label + '</option>';
          }).join("") + '</select></div>';
      }
      if (opts.filters.indexOf("province") >= 0) {
        html += '<div class="filter-item"><label>省份筛选</label><select id="fProvince">' +
          '<option value="全国">全国</option>' +
          provinces().map(function (p) {
            return '<option value="' + p + '"' + (p === state.province ? " selected" : "") + '>' + p + '</option>';
          }).join("") + '</select></div>';
      }
      if (opts.filters.indexOf("year") >= 0) {
        html += '<div class="filter-item"><label>年份</label>' +
          '<input type="range" id="fYear" min="2015" max="2024" step="1" value="' + state.year + '">' +
          '<span class="year-badge" id="fYearBadge">' + state.year + '</span></div>';
      }
      // 相关性分析页的图表（相关性矩阵、聚类分布等）不随筛选条件变化，
      // 该提示在此页无实际意义，故不显示；其余页面保留说明。
      if (activeKey !== "correlation") {
        html += '<span class="filter-tip">筛选条件变更后，本页所有图表同步刷新</span>';
      }
      bar.innerHTML = html;

      var sel = document.getElementById("fPollutant");
      if (sel) sel.addEventListener("change", function () {
        state.pollutant = this.value; notify();
      });
      var pv = document.getElementById("fProvince");
      if (pv) pv.addEventListener("change", function () {
        state.province = this.value; notify();
      });
      var yr = document.getElementById("fYear");
      if (yr) yr.addEventListener("input", function () {
        state.year = +this.value;
        document.getElementById("fYearBadge").textContent = this.value;
        notify();
      });
    }
  }

  // 注册图表刷新函数
  function onRefresh(fn) { listeners.push(fn); }

  // ---------- 数据查询 ----------
  // 某年（+可选省份）的城市年均记录
  function cityYear(year, province) {
    return AQI_YEAR_AVG.cities.filter(function (r) {
      return r.year === year && (!province || province === "全国" || r.province === province);
    });
  }

  // 某城市十年记录
  function citySeries(cityName) {
    return AQI_YEAR_AVG.cities.filter(function (r) { return r.city === cityName; })
      .sort(function (a, b) { return a.year - b.year; });
  }

  // 全国年均序列
  function nationalSeries() { return AQI_YEAR_AVG.national; }

  // 分省年均值（某年某指标）
  function provinceAvg(year, pollutant) {
    var acc = {};
    AQI_YEAR_AVG.cities.forEach(function (r) {
      if (r.year !== year) return;
      (acc[r.province] = acc[r.province] || { sum: 0, n: 0 });
      acc[r.province].sum += r[pollutant]; acc[r.province].n++;
    });
    return Object.keys(acc).map(function (p) {
      return { province: p, value: +(acc[p].sum / acc[p].n).toFixed(1) };
    });
  }

  // ---------- ECharts 辅助 ----------
  function makeChart(el) {
    var chart = echarts.init(el);
    window.addEventListener("resize", function () { chart.resize(); });
    return chart;
  }

  function baseTooltip(unit) {
    return {
      trigger: "item",
      backgroundColor: "rgba(40, 60, 90, 0.92)",
      borderWidth: 0, textStyle: { color: "#fff", fontSize: 13 },
      formatter: unit === undefined ? undefined : function (ps) {
        var v = ps.value; var extra = "";
        if (ps.data && ps.data.length >= 3) extra = '<br/>省份：' + ps.data[2];
        return (ps.seriesName ? ps.seriesName + '<br/>' : '') + extra;
      }
    };
  }

  return {
    YEARS: YEARS, POLLUTANTS: POLLUTANTS, POLLUTANT_META: POLLUTANT_META,
    LEVELS: LEVELS, LEVEL_COLORS: LEVEL_COLORS, warningPalette: warningPalette,
    state: state, provinces: provinces, hasData: hasDataNow, noData: noData,
    initPage: initPage, onRefresh: onRefresh, notify: notify,
    cityYear: cityYear, citySeries: citySeries, nationalSeries: nationalSeries,
    provinceAvg: provinceAvg,
    makeChart: makeChart, baseTooltip: baseTooltip
  };
})();
