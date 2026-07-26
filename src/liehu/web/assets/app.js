/* 猎狐系统仪表盘前端逻辑 —— 纯原生 JS + ECharts, 对接 FastAPI /api。 */
"use strict";

const API = "/api";

const DEFAULT_AVATAR =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" rx="8" fill="#1c2230"/><text x="16" y="23" font-size="18" text-anchor="middle" fill="#f78c3c">🦊</text></svg>'
  );

// 首屏鉴权守卫: 未登录跳登录页; 已登录则回填顶栏用户名/头像。
async function ensureAuth() {
  const res = await fetch(`${API}/auth/me`);
  if (res.status === 401) {
    location.href = "/login";
    return false;
  }
  try {
    const me = await res.json();
    const nameEl = document.getElementById("topbar-username");
    const avaEl = document.getElementById("topbar-avatar");
    if (nameEl) nameEl.textContent = me.username || "个人中心";
    if (avaEl) avaEl.src = me.avatar || DEFAULT_AVATAR;
  } catch (e) {
    /* 顶栏信息为辅助, 失败静默 */
  }
  return true;
}

/* ---------- 工具 ---------- */
async function fetchJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return res.json();
}
function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );
}
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2600);
}

// ECharts 通用暗色配色
const PALETTE = ["#f78c3c", "#58a6ff", "#f778ba", "#3fb950", "#d29922", "#a371f7"];
const CAMPAIGN_COLOR = { noah: "#58a6ff", fezhx: "#f778ba", unknown: "#8b949e" };
const chartInstances = {};
function makeChart(id) {
  const dom = document.getElementById(id);
  if (!dom) return null;
  if (chartInstances[id]) return chartInstances[id];
  const c = echarts.init(dom, "dark");
  chartInstances[id] = c;
  return c;
}
window.addEventListener("resize", () => {
  Object.values(chartInstances).forEach((c) => c && c.resize());
});

/* ---------- 标签页切换 (支持 #hash 深链, 便于收藏/分享/自动化) ---------- */
const loaders = {};
let loadedTabs = new Set();

// 激活指定标签页; 首次进入才触发加载, 之后切回时刷新图表尺寸。
function activateTab(name) {
  const tab = document.querySelector(`.tab[data-tab="${name}"]`);
  const panel = document.getElementById(`tab-${name}`);
  if (!tab || !panel) return; // 未知 hash, 忽略
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  tab.classList.add("active");
  panel.classList.add("active");
  if (!loadedTabs.has(name) && loaders[name]) {
    loadedTabs.add(name);
    loaders[name]();
  } else {
    setTimeout(() => Object.values(chartInstances).forEach((c) => c && c.resize()), 50);
  }
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    const name = tab.dataset.tab;
    // 写入 hash 触发 hashchange -> activateTab; 若 hash 未变则直接激活。
    if (location.hash.slice(1) === name) activateTab(name);
    else location.hash = name;
  });
});

// 响应 hash 变化 (含浏览器前进/后退与外部导航)。
window.addEventListener("hashchange", () => {
  const name = location.hash.slice(1);
  if (name) activateTab(name);
});

/* ---------- 总览水位 ---------- */
loaders.overview = async function () {
  let data;
  try {
    data = await fetchJSON(`${API}/stats`);
  } catch (e) {
    document.getElementById("stat-cards").innerHTML =
      `<div class="loading">加载失败: ${esc(e.message)}</div>`;
    return;
  }

  // 水位时间
  document.getElementById("water-mark").textContent = "水位 " + data.water_mark;

  // 统计卡
  const evHigh = (data.events_by_priority && data.events_by_priority.high) || 0;
  const cards = [
    { num: data.frontend_total, label: "前台总数 (壳)", cls: "accent" },
    { num: (data.by_campaign.noah || 0), label: "noah 战役", cls: "" },
    { num: (data.by_campaign.fezhx || 0), label: "fezhx 战役", cls: "" },
    { num: data.event_total, label: "差异事件总数", cls: "" },
    { num: evHigh, label: "高优事件", cls: "high" },
    { num: data.error_total, label: "错误账本", cls: "pending" },
  ];
  document.getElementById("stat-cards").innerHTML = cards
    .map((c) => `<div class="stat-card ${c.cls}"><div class="num">${esc(c.num)}</div><div class="label">${esc(c.label)}</div></div>`)
    .join("");

  // 战役饼图
  makeChart("chart-campaign").setOption({
    tooltip: { trigger: "item" },
    series: [{
      type: "pie", radius: ["40%", "70%"],
      data: Object.entries(data.by_campaign).map(([k, v]) => ({
        name: k, value: v, itemStyle: { color: CAMPAIGN_COLOR[k] || "#8b949e" },
      })),
      label: { color: "#e6edf3", formatter: "{b}: {c}" },
    }],
  });

  // 当天分类
  const dc = data.by_dayclass || {};
  makeChart("chart-dayclass").setOption({
    tooltip: { trigger: "axis" },
    grid: { left: 80, right: 20, top: 20, bottom: 30 },
    xAxis: { type: "value" },
    yAxis: { type: "category", data: Object.keys(dc) },
    series: [{
      type: "bar",
      data: Object.values(dc),
      itemStyle: { color: "#f78c3c", borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: "right", color: "#e6edf3" },
    }],
  });

  // 题材
  const th = data.by_theme || {};
  makeChart("chart-theme").setOption({
    tooltip: { trigger: "item" },
    series: [{
      type: "pie", roseType: "radius", radius: ["25%", "70%"],
      data: Object.entries(th).map(([k, v], i) => ({
        name: k, value: v, itemStyle: { color: PALETTE[i % PALETTE.length] },
      })),
      label: { color: "#e6edf3", fontSize: 11 },
    }],
  });

  // 事件优先级
  const pr = data.events_by_priority || {};
  const prColor = { high: "#f85149", pending: "#d29922", watch: "#3fb950" };
  makeChart("chart-priority").setOption({
    tooltip: { trigger: "item" },
    legend: { bottom: 0, textStyle: { color: "#8b949e" } },
    series: [{
      type: "pie", radius: "60%",
      data: Object.entries(pr).map(([k, v]) => ({
        name: k, value: v, itemStyle: { color: prColor[k] || "#8b949e" },
      })),
      label: { color: "#e6edf3", formatter: "{b}: {c}" },
    }],
  });

  // 数据源模式 + 起点 IOC
  const modes = data.modes || {};
  const pills = Object.entries(modes)
    .map(([k, m]) => `<span class="mode-pill ${esc(m)}">${esc(k)}: ${esc(m)}</span>`)
    .join("");
  const iocs = data.starting_iocs || {};
  const iocHtml = Object.entries(iocs)
    .map(([k, v]) => `<div><b>${esc(k)}</b>: ${esc(Array.isArray(v) ? v.join(", ") : v)}</div>`)
    .join("");
  document.getElementById("modes-box").innerHTML =
    `<div class="mode-row">${pills}</div><div class="ioc-list">${iocHtml}</div>`;
};

/* ---------- 前台 (壳) ---------- */
async function loadFrontends() {
  const campaign = document.getElementById("f-campaign").value;
  const dayClass = document.getElementById("f-dayclass").value;
  const theme = document.getElementById("f-theme").value;
  const qs = new URLSearchParams();
  if (campaign) qs.set("campaign", campaign);
  if (dayClass) qs.set("day_class", dayClass);
  if (theme) qs.set("theme", theme);
  qs.set("limit", "1000");

  const box = document.getElementById("frontend-list");
  box.innerHTML = `<div class="loading">加载中…</div>`;
  let data;
  try {
    data = await fetchJSON(`${API}/frontends?${qs}`);
  } catch (e) {
    box.innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
    return;
  }
  document.getElementById("f-count").textContent = `共 ${data.count} 个前台`;
  if (!data.items.length) {
    box.innerHTML = `<div class="loading">无匹配前台</div>`;
    return;
  }
  box.innerHTML = data.items
    .map((f) => {
      const camp = (f.campaign || "unknown").toLowerCase();
      return `<div class="fe-card ${camp}">
        <div class="domain">${esc(f.domain)}</div>
        <div class="title">${esc(f.title || "—")}</div>
        <div class="fe-meta">
          <span class="chip ${camp}">${esc(f.campaign || "?")}</span>
          <span class="chip ${esc(f.day_class || "")}">${esc(f.day_class || "?")}</span>
          <span class="chip">${esc(f.theme || "—")}</span>
          ${f.control_api ? `<span class="chip">→ ${esc(f.control_api)}</span>` : ""}
        </div>
      </div>`;
    })
    .join("");
}
loaders.frontends = async function () {
  // 填充下拉 (从 stats 的分类维度)
  try {
    const stats = await fetchJSON(`${API}/stats`);
    const dcSel = document.getElementById("f-dayclass");
    Object.keys(stats.by_dayclass || {}).forEach((k) => dcSel.appendChild(el(`<option>${esc(k)}</option>`)));
    const thSel = document.getElementById("f-theme");
    Object.keys(stats.by_theme || {}).forEach((k) => thSel.appendChild(el(`<option>${esc(k)}</option>`)));
  } catch (_) { /* 忽略下拉填充失败 */ }
  ["f-campaign", "f-dayclass", "f-theme"].forEach((id) =>
    document.getElementById(id).addEventListener("change", loadFrontends)
  );
  loadFrontends();
};

/* ---------- 控制线 (线) ---------- */
loaders.controls = async function () {
  const box = document.getElementById("control-timeline");
  box.innerHTML = `<div class="loading">加载中…</div>`;
  let data;
  try {
    data = await fetchJSON(`${API}/controls/timeline`);
  } catch (e) {
    box.innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
    return;
  }
  const timeline = data.timeline || {};
  const apis = Object.keys(timeline);
  if (!apis.length) {
    box.innerHTML = `<div class="loading">暂无控制端采样</div>`;
    return;
  }
  box.innerHTML = apis
    .map((api) => {
      const steps = timeline[api]
        .map((s) => {
          const nx = s.http_status === 3 || s.error;
          const link = s.error
            ? `NXDOMAIN / ${esc(s.error)}`
            : esc(s.download_link || "—");
          return `<div class="ctl-step">
            <span class="ctl-time">${esc(s.observed_at)}</span>
            <span class="ctl-link ${nx ? "nx" : ""}">${link}</span>
          </div>`;
        })
        .join("");
      return `<div class="ctl-group"><div class="ctl-api">${esc(api)}</div><div class="ctl-steps">${steps}</div></div>`;
    })
    .join("");
};

/* ---------- 载荷 (包) ---------- */
loaders.payloads = async function () {
  const box = document.getElementById("payload-compare");
  box.innerHTML = `<div class="loading">加载中…</div>`;
  let data;
  try {
    data = await fetchJSON(`${API}/payloads/compare`);
  } catch (e) {
    box.innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
    return;
  }
  const sk = data.skeletons || [];
  if (!sk.length) {
    box.innerHTML = `<div class="loading">暂无载荷观测</div>`;
    return;
  }
  const rows = sk
    .map((s) => `<tr>
      <td class="mono">${esc(s.structure_id)}</td>
      <td>${esc(s.msi_size)}</td>
      <td>${esc(s.embedded_pe_size)}</td>
      <td>${esc(s.pe_entry_rva)}</td>
      <td class="mono">${esc(s.imphash)}</td>
      <td class="mono">${esc(s.stable_sha256)}</td>
      <td>${esc(s.ole_identical)}/${esc(s.ole_stream_count)}</td>
      <td>${esc(s.wix_version)}</td>
      <td>${esc(s.sample_count)} 个<br><span class="rot">完整哈希轮换</span></td>
    </tr>`)
    .join("");
  box.innerHTML = `<table class="compare">
    <thead><tr>
      <th>结构ID</th><th>MSI 大小</th><th>内嵌PE</th><th>入口RVA</th>
      <th>imphash</th><th>稳定区SHA256</th><th>OLE相同/总数</th><th>WiX</th><th>样本</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
};

/* ---------- 关联图 ---------- */
async function loadGraph() {
  const campaign = document.getElementById("g-campaign").value;
  const chart = makeChart("chart-graph");
  chart.showLoading("dark");
  let data;
  try {
    data = await fetchJSON(`${API}/campaigns/graph${campaign ? "?campaign=" + campaign : ""}`);
  } catch (e) {
    chart.hideLoading();
    toast("关联图加载失败: " + e.message);
    return;
  }
  chart.hideLoading();
  const catColor = ["#f78c3c", "#58a6ff", "#3fb950", "#d29922", "#f778ba"];
  const nodes = data.nodes.map((n) => ({
    id: n.id,
    name: n.name,
    category: n.category,
    symbolSize: n.node_type === "payload" ? 34 : n.node_type === "control" ? 26 : 14,
    itemStyle: { color: catColor[n.category] || "#8b949e" },
  }));
  chart.setOption({
    tooltip: {
      formatter: (p) =>
        p.dataType === "edge" ? `${esc(p.data.source)} → ${esc(p.data.target)}<br>${esc(p.data.relation)}` : esc(p.data.name),
    },
    legend: [{ data: data.categories.map((c) => c.name), textStyle: { color: "#8b949e" }, top: 8 }],
    series: [{
      type: "graph",
      layout: "force",
      roam: true,
      draggable: true,
      categories: data.categories,
      force: { repulsion: 180, edgeLength: [50, 160], gravity: 0.08 },
      label: { show: true, color: "#e6edf3", fontSize: 10, position: "right" },
      lineStyle: { color: "source", opacity: 0.5, curveness: 0.1 },
      emphasis: { focus: "adjacency", lineStyle: { width: 3 } },
      data: nodes,
      links: data.links,
    }],
  });
  toast(`关联图: ${data.nodes.length} 节点 / ${data.links.length} 边`);
}
loaders.graph = async function () {
  document.getElementById("g-campaign").addEventListener("change", loadGraph);
  loadGraph();
};

/* ---------- 事件流 ---------- */
async function loadEvents() {
  const priority = document.getElementById("e-priority").value;
  const box = document.getElementById("event-list");
  box.innerHTML = `<div class="loading">加载中…</div>`;
  let data;
  try {
    data = await fetchJSON(`${API}/events?limit=500${priority ? "&priority=" + priority : ""}`);
  } catch (e) {
    box.innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
    return;
  }
  document.getElementById("e-count").textContent = `共 ${data.count} 条差异事件`;
  if (!data.items.length) {
    box.innerHTML = `<div class="loading">无匹配事件</div>`;
    return;
  }
  box.innerHTML = data.items
    .map((c) => {
      const p = c.priority || "watch";
      return `<div class="event-card ${p}">
        <div class="event-head">
          <span class="event-type">${esc(c.event_type)}</span>
          <span class="badge ${p}">${esc(p)}</span>
        </div>
        <div class="event-obj">${esc(c.object)}</div>
        <div class="event-fact">${esc(c.fact || "—")}</div>
        <div class="event-states">${c.prev_state ? esc(c.prev_state) + " → " : ""}${esc(c.curr_state || "")}</div>
        <div class="event-sink">落点: ${esc(c.sink)} · 首见 ${esc(c.first_observed || "?")} · 最近 ${esc(c.last_observed || "?")}</div>
      </div>`;
    })
    .join("");
}
loaders.events = async function () {
  document.getElementById("e-priority").addEventListener("change", loadEvents);
  loadEvents();
};

/* ---------- 手动触发一轮追踪 ---------- */
document.getElementById("btn-trigger").addEventListener("click", async function () {
  const btn = this;
  btn.disabled = true;
  btn.textContent = "追踪中…";
  try {
    const res = await fetch(`${API}/campaigns/trigger`, { method: "POST" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const j = await res.json();
    const r = j.result || {};
    const n = r.events != null ? r.events : (r.new_events != null ? r.new_events : "?");
    toast("已触发一轮追踪, 新增事件: " + n);
    // 重新加载当前活动标签
    loadedTabs.clear();
    const active = document.querySelector(".tab.active");
    if (active && loaders[active.dataset.tab]) {
      loadedTabs.add(active.dataset.tab);
      loaders[active.dataset.tab]();
    }
  } catch (e) {
    toast("触发失败: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "▶ 触发一轮追踪";
  }
});

// 独立加载顶栏水位时间, 使深链进入非总览标签时头部也能正确显示。
async function loadWaterMark() {
  try {
    const data = await fetchJSON(`${API}/stats`);
    document.getElementById("water-mark").textContent = "水位 " + data.water_mark;
  } catch (e) {
    /* 顶栏水位为辅助信息, 失败静默, 不阻断主视图 */
  }
}

/* ---------- 启动: 先鉴权, 再按 URL hash 激活对应标签, 缺省为总览 ---------- */
(async function boot() {
  if (!(await ensureAuth())) return; // 未登录已跳转
  const initial = location.hash.slice(1);
  if (initial && initial !== "overview" && document.querySelector(`.tab[data-tab="${initial}"]`)) {
    loadWaterMark(); // 总览 loader 未运行, 单独补齐顶栏水位
    activateTab(initial);
  } else {
    loadedTabs.add("overview");
    loaders.overview();
  }
})();
