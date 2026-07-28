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

// 状态标识中文化 (仅显示层; API 过滤仍使用原始英文值)
const PRIORITY_LABELS = { high: "高优", pending: "待确认", watch: "观察池" };
const DAY_CLASS_LABELS = {
  same_day: "当天注册",
  preexisting: "提前备货",
  rescan: "复扫未变",
  content_change: "内容变更",
  reactivated: "重新激活",
};
// 注册时效分类配色 (与 chip / 柱状图共用, 保证分类间清晰区分)
const DAY_CLASS_COLOR = {
  same_day: "#f85149",
  preexisting: "#58a6ff",
  rescan: "#d29922",
  content_change: "#a371f7",
  reactivated: "#3fb950",
};
const priorityLabel = (p) => PRIORITY_LABELS[p] || p || "?";
const dayClassLabel = (d) => DAY_CLASS_LABELS[d] || d || "?";

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
    { num: data.frontend_total, label: "仿冒站点总数", cls: "accent" },
    { num: (data.by_campaign.noah || 0), label: "noah C2 集群", cls: "" },
    { num: (data.by_campaign.fezhx || 0), label: "fezhx C2 集群", cls: "" },
    { num: data.event_total, label: "差异事件总数", cls: "" },
    { num: evHigh, label: "高优事件", cls: "high" },
    { num: data.error_total, label: "错误账本", cls: "pending" },
  ];
  document.getElementById("stat-cards").innerHTML = cards
    .map((c) => `<div class="stat-card ${c.cls}"><div class="num">${esc(c.num)}</div><div class="label">${esc(c.label)}</div></div>`)
    .join("");

  // C2 集群归属饼图
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

  // 域名注册时效分类 (每类独立配色, y 轴与提示中文化)
  const dc = data.by_dayclass || {};
  const dcKeys = Object.keys(dc);
  makeChart("chart-dayclass").setOption({
    tooltip: {
      trigger: "axis",
      formatter: (ps) => {
        const p = ps[0] || {};
        return `${dayClassLabel(p.name)}: ${p.value}`;
      },
    },
    grid: { left: 90, right: 24, top: 20, bottom: 30 },
    xAxis: { type: "value" },
    yAxis: {
      type: "category",
      data: dcKeys,
      axisLabel: { formatter: (v) => dayClassLabel(v) },
    },
    series: [{
      type: "bar",
      data: dcKeys.map((k, i) => ({
        value: dc[k],
        itemStyle: {
          color: DAY_CLASS_COLOR[k] || PALETTE[i % PALETTE.length],
          borderRadius: [0, 4, 4, 0],
        },
      })),
      label: { show: true, position: "right", color: "#e6edf3" },
    }],
  });

  // 社工诱饵题材
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

  // 事件优先级 (中文标签 + 点击跳转事件流对应优先级)
  const pr = data.events_by_priority || {};
  const prColor = { high: "#f85149", pending: "#d29922", watch: "#3fb950" };
  const priChart = makeChart("chart-priority");
  priChart.setOption({
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { bottom: 0, textStyle: { color: "#8b949e" } },
    series: [{
      type: "pie", radius: "60%",
      data: Object.entries(pr).map(([k, v]) => ({
        name: priorityLabel(k), value: v, priority: k,
        itemStyle: { color: prColor[k] || "#8b949e" },
      })),
      label: { color: "#e6edf3", formatter: "{b}: {c}" },
    }],
  });
  // 避免总览重复加载时叠加多个监听
  priChart.off("click");
  priChart.on("click", (params) => {
    const p = params.data && params.data.priority;
    if (p) jumpToEventsByPriority(p);
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

/* ---------- 仿冒站点 ---------- */
let feView = "card"; // 当前视图: card(卡片) / list(列表)
let feItems = [];    // 最近一次加载的仿冒站点数据
let tbVerdicts = {}; // 微步 L1 批量打标判定: domain -> verdict

// 微步风险徽章 (L1 批量打标结论; 出站检测未检出 ≠ 安全, 悬停提示口径)
function tbBadge(domain) {
  const v = tbVerdicts[domain];
  if (!v) return "";
  if (!v.is_malicious) {
    return `<span class="chip tb-safe" title="微步出站检测未检出 (不代表安全, 可点击域名详查)">微步·未检出</span>`;
  }
  const tags = (v.tags || []).join("/");
  const tip = `判定: ${(v.judgments || []).join(",") || "?"} · 可信度 ${v.confidence_level || "?"} · 严重级别 ${v.severity || "?"}`;
  return `<span class="chip tb-mal" title="${esc(tip)}">微步·恶意${tags ? " · " + esc(tags) : ""}</span>`;
}

function feFilterParams() {
  const qs = new URLSearchParams();
  const campaign = document.getElementById("f-campaign").value;
  const dayClass = document.getElementById("f-dayclass").value;
  const theme = document.getElementById("f-theme").value;
  const domainKw = document.getElementById("f-domain").value.trim();
  if (campaign) qs.set("campaign", campaign);
  if (dayClass) qs.set("day_class", dayClass);
  if (theme) qs.set("theme", theme);
  if (domainKw) qs.set("q", domainKw);
  return qs;
}

// 卡片视图: 域名可点击弹出截图
function renderFrontendCards(items) {
  const box = document.getElementById("frontend-list");
  box.innerHTML = items
    .map((f) => {
      const camp = (f.campaign || "unknown").toLowerCase();
      return `<div class="fe-card ${camp}">
        <a class="domain domain-link" data-shot="${esc(f.domain)}" title="点击查看站点截图">${esc(f.domain)}</a>
        <div class="title">${esc(f.title || "—")}</div>
        <div class="fe-meta">
          <span class="chip ${camp}">${esc(f.campaign || "?")}</span>
          <span class="chip ${esc(f.day_class || "")}">${esc(dayClassLabel(f.day_class))}</span>
          <span class="chip">${esc(f.theme || "—")}</span>
          ${f.control_api ? `<span class="chip">→ ${esc(f.control_api)}</span>` : ""}
          ${tbBadge(f.domain)}
        </div>
      </div>`;
    })
    .join("");
}

// 列表视图: 表格形式展示关键字段
function renderFrontendTable(items) {
  const box = document.getElementById("frontend-table");
  const rows = items
    .map((f) => {
      const camp = (f.campaign || "unknown").toLowerCase();
      return `<tr>
        <td class="mono"><a class="domain-link" data-shot="${esc(f.domain)}" title="点击查看站点截图">${esc(f.domain)}</a></td>
        <td>${esc(f.title || "—")}</td>
        <td class="mono">${esc(f.page_ip || "—")}</td>
        <td><span class="chip ${camp}">${esc(f.campaign || "?")}</span></td>
        <td><span class="chip ${esc(f.day_class || "")}">${esc(dayClassLabel(f.day_class))}</span></td>
        <td>${tbBadge(f.domain) || "—"}</td>
        <td>${esc(f.theme || "—")}</td>
        <td class="mono">${esc(f.control_api || "—")}</td>
        <td class="mono">${esc(f.registered_at || "—")}</td>
        <td class="mono">${esc(f.last_seen || "—")}</td>
      </tr>`;
    })
    .join("");
  box.innerHTML = `<table class="compare fe-table">
    <thead><tr>
      <th>域名</th><th>页面标题</th><th>IP 地址</th><th>C2 集群</th>
      <th>注册时效</th><th>微步情报</th><th>诱饵题材</th><th>C2 控制接口</th><th>注册时间</th><th>最近检测</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function renderFrontends() {
  const cardBox = document.getElementById("frontend-list");
  const tableBox = document.getElementById("frontend-table");
  cardBox.hidden = feView !== "card";
  tableBox.hidden = feView !== "list";
  if (!feItems.length) {
    const empty = `<div class="loading">无匹配仿冒站点</div>`;
    (feView === "card" ? cardBox : tableBox).innerHTML = empty;
    return;
  }
  if (feView === "card") renderFrontendCards(feItems);
  else renderFrontendTable(feItems);
}

async function loadFrontends() {
  const qs = feFilterParams();
  qs.set("limit", "1000");
  const box = document.getElementById(feView === "card" ? "frontend-list" : "frontend-table");
  box.innerHTML = `<div class="loading">加载中…</div>`;
  let data;
  try {
    // 站点列表与微步 L1 判定并行加载 (判定失败不阻断列表)
    const [feData, tbData] = await Promise.all([
      fetchJSON(`${API}/frontends?${qs}`),
      fetchJSON(`${API}/threatbook`).catch(() => null),
    ]);
    data = feData;
    if (tbData) tbVerdicts = tbData.verdicts || {};
  } catch (e) {
    box.innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
    return;
  }
  document.getElementById("f-count").textContent = `共 ${data.count} 个仿冒站点`;
  feItems = data.items;
  renderFrontends();
}

function switchFeView(view) {
  feView = view;
  document.getElementById("btn-view-card").classList.toggle("active", view === "card");
  document.getElementById("btn-view-list").classList.toggle("active", view === "list");
  renderFrontends();
}

loaders.frontends = async function () {
  // 填充下拉 (从 stats 的分类维度)
  try {
    const stats = await fetchJSON(`${API}/stats`);
    const dcSel = document.getElementById("f-dayclass");
    Object.keys(stats.by_dayclass || {}).forEach((k) =>
      dcSel.appendChild(el(`<option value="${esc(k)}">${esc(dayClassLabel(k))}</option>`))
    );
    const thSel = document.getElementById("f-theme");
    Object.keys(stats.by_theme || {}).forEach((k) => thSel.appendChild(el(`<option>${esc(k)}</option>`)));
  } catch (_) { /* 忽略下拉填充失败 */ }
  ["f-campaign", "f-dayclass", "f-theme"].forEach((id) =>
    document.getElementById(id).addEventListener("change", loadFrontends)
  );
  // 域名关键词: 输入防抖 300ms 后刷新 (清空 search 框的 ✕ 也触发 input)
  let feSearchTimer = null;
  document.getElementById("f-domain").addEventListener("input", () => {
    clearTimeout(feSearchTimer);
    feSearchTimer = setTimeout(loadFrontends, 300);
  });
  document.getElementById("btn-view-card").addEventListener("click", () => switchFeView("card"));
  document.getElementById("btn-view-list").addEventListener("click", () => switchFeView("list"));
  // CSV 导出: 携带当前过滤条件, 后端返回 UTF-8 BOM 编码的全量字段 CSV
  document.getElementById("btn-export-csv").addEventListener("click", () => {
    const qs = feFilterParams();
    location.href = `${API}/frontends/export.csv${qs.toString() ? "?" + qs : ""}`;
  });
  loadFrontends();
};

/* ---------- 仿冒站点截图弹窗 ---------- */
const shotModal = document.getElementById("shot-modal");
const shotBody = document.getElementById("shot-body");
const tbIntelBox = document.getElementById("tb-intel");

function closeShotModal() {
  shotModal.hidden = true;
  shotBody.innerHTML = "";
  tbIntelBox.innerHTML = "";
}
document.getElementById("shot-close").addEventListener("click", closeShotModal);
shotModal.addEventListener("click", (e) => {
  if (e.target === shotModal) closeShotModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !shotModal.hidden) closeShotModal();
});

// 截图不可用时的占位: 域名 + 状态标注
function shotFallback(domain, label, cls) {
  return `<div class="shot-fallback ${cls}">
    <div class="shot-fb-domain">${esc(domain)}</div>
    <div class="shot-fb-label">${esc(label)}</div>
  </div>`;
}

// L2 按需详查: 弹窗内加载微步完整情报上下文 (后端带 24h 缓存, 不重复扣配额)
async function loadTbIntel(domain) {
  tbIntelBox.innerHTML = `<div class="loading">正在查询微步情报…</div>`;
  let d;
  try {
    d = await fetchJSON(`${API}/threatbook/${encodeURIComponent(domain)}`);
  } catch (e) {
    tbIntelBox.innerHTML = `<div class="tb-head">微步情报</div><div class="hint">查询失败: ${esc(e.message)}</div>`;
    return;
  }
  const mal = d.is_malicious;
  const verdictChip = mal
    ? `<span class="chip tb-mal">恶意 · ${esc(d.severity || "?")}</span>`
    : `<span class="chip tb-safe">未检出</span>`;
  const chips = [
    ...(d.judgments || []).map((j) => `<span class="chip">${esc(j)}</span>`),
    ...(d.tags || []).map((t) => `<span class="chip tb-tag">${esc(t)}</span>`),
  ].join("");
  const rows = [];
  if (d.confidence_level) rows.push(`<div><b>可信度</b> ${esc(d.confidence_level)}</div>`);
  const whois = d.cur_whois || {};
  if (whois.registrar_name || whois.cdate) {
    rows.push(`<div><b>Whois</b> ${esc(whois.registrar_name || "?")} · 注册于 ${esc(whois.cdate || "?")}</div>`);
  }
  const ips = (d.cur_ips || []).map((x) => x.ip).filter(Boolean);
  if (ips.length) rows.push(`<div><b>解析 IP</b> ${esc(ips.join(", "))}</div>`);
  const samples = d.samples || [];
  if (samples.length) {
    const s = samples[0];
    rows.push(`<div><b>关联样本</b> ${samples.length} 个 · ${esc((s.malware_family || "?") + " " + (s.sha256 || "").slice(0, 16))}…</div>`);
  }
  if (d.detail_error) rows.push(`<div class="hint">详查失败, 已降级为批量打标结论 (${esc(d.detail_error)})</div>`);
  const link = d.permalink
    ? `<a class="key-link" href="${esc(d.permalink)}" target="_blank" rel="noopener noreferrer">X 情报中心详情 ↗</a>`
    : "";
  tbIntelBox.innerHTML = `
    <div class="tb-head">微步情报 ${verdictChip}${d.cached ? '<span class="hint">(缓存)</span>' : ""}</div>
    <div class="tb-chips">${chips || '<span class="hint">无判定标签</span>'}</div>
    <div class="tb-rows">${rows.join("")}</div>
    ${link}`;
}

// 点击仿冒域名 -> 弹窗展示存活探测结果与截图 (默认不展示, 按需加载)
async function openShotModal(domain) {
  document.getElementById("shot-domain").textContent = domain;
  shotBody.innerHTML = `<div class="loading">正在探测站点并采集截图…</div>`;
  shotModal.hidden = false;
  loadTbIntel(domain); // 微步详查与站点探测并行, 互不阻塞
  let info;
  try {
    info = await fetchJSON(`${API}/frontends/${encodeURIComponent(domain)}/screenshot`);
  } catch (e) {
    shotBody.innerHTML = shotFallback(domain, "探测失败: " + e.message, "err");
    return;
  }
  const badgeCls = info.status === "ok" ? "ok" : info.status === "domain_dead" ? "dead" : "err";
  const badge = `<span class="shot-badge ${badgeCls}">${esc(info.status_label || "?")}${info.http_status ? " · HTTP " + esc(info.http_status) : ""}</span>`;
  if (info.status === "ok" && info.screenshot_url) {
    shotBody.innerHTML = badge;
    const img = el(`<img class="shot-img" src="${esc(info.screenshot_url)}" alt="${esc(domain)} 截图" />`);
    // 图片加载失败时回退到域名占位提示
    img.addEventListener("error", () => {
      img.outerHTML = shotFallback(domain, "截图采集失败 · 访问异常", "err");
    });
    shotBody.appendChild(img);
  } else {
    const label = info.status_label || "访问异常";
    shotBody.innerHTML = badge + shotFallback(domain, label, badgeCls);
  }
  if (info.evidence_screenshot_url) {
    shotBody.insertAdjacentHTML(
      "beforeend",
      `<p class="hint shot-evidence">URLScan 历史证据截图:
        <a href="${esc(info.evidence_screenshot_url)}" target="_blank" rel="noopener noreferrer">${esc(info.evidence_screenshot_url)}</a></p>`
    );
  }
}

// 事件委托: 卡片/列表两种视图中的域名点击均弹窗
document.addEventListener("click", (e) => {
  const link = e.target.closest("[data-shot]");
  if (link) openShotModal(link.dataset.shot);
});

/* ---------- C2 控制端 ---------- */
async function loadControls() {
  const box = document.getElementById("control-timeline");
  box.innerHTML = `<div class="loading">加载中…</div>`;
  const start = document.getElementById("c-start").value;
  const end = document.getElementById("c-end").value;
  const qs = new URLSearchParams();
  if (start) qs.set("start", start);
  if (end) qs.set("end", end);
  let data;
  try {
    data = await fetchJSON(`${API}/controls/timeline${qs.toString() ? "?" + qs : ""}`);
  } catch (e) {
    box.innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
    return;
  }
  const timeline = data.timeline || {};
  const apis = Object.keys(timeline);
  const sampleCount = apis.reduce((n, a) => n + timeline[a].length, 0);
  document.getElementById("c-count").textContent =
    `共 ${apis.length} 个控制接口 / ${sampleCount} 次采样`;
  if (!apis.length) {
    box.innerHTML = `<div class="loading">该时间范围内暂无 C2 控制端采样</div>`;
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
}
loaders.controls = async function () {
  document.getElementById("btn-ctl-filter").addEventListener("click", loadControls);
  document.getElementById("btn-ctl-reset").addEventListener("click", () => {
    document.getElementById("c-start").value = "";
    document.getElementById("c-end").value = "";
    loadControls();
  });
  loadControls();
};

/* ---------- 恶意载荷 ---------- */
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
    box.innerHTML = `<div class="loading">暂无恶意载荷观测</div>`;
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
  const catNames = data.categories.map((c) => c.name);
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
        p.dataType === "edge"
          ? `${esc(p.data.source)} → ${esc(p.data.target)}<br>${esc(p.data.relation)}`
          // 节点提示带类型名, 区分仿冒站点与下载路径等 C2 连接件节点
          : `<b>${esc(catNames[p.data.category] || "?")}</b><br>${esc(p.data.name)}`,
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
let eventTypesFilled = false;
// 首次(未过滤)加载时用返回结果里出现的事件类型填充下拉框, 之后不再改动。
function fillEventTypes(items) {
  if (eventTypesFilled) return;
  const sel = document.getElementById("e-type");
  const types = [...new Set((items || []).map((c) => c.event_type).filter(Boolean))].sort();
  types.forEach((t) => sel.appendChild(el(`<option>${esc(t)}</option>`)));
  eventTypesFilled = true;
}
async function loadEvents() {
  const priority = document.getElementById("e-priority").value;
  const etype = document.getElementById("e-type").value;
  const box = document.getElementById("event-list");
  box.innerHTML = `<div class="loading">加载中…</div>`;
  let data;
  try {
    data = await fetchJSON(
      `${API}/events?limit=500${priority ? "&priority=" + priority : ""}${etype ? "&event_type=" + encodeURIComponent(etype) : ""}`
    );
  } catch (e) {
    box.innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
    return;
  }
  fillEventTypes(data.items);
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
          <span class="badge ${p}">${esc(priorityLabel(p))}</span>
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
  document.getElementById("e-type").addEventListener("change", loadEvents);
  loadEvents();
};

/* ---------- 情报库 ---------- */
const PRIORITY_TIER_COLOR = { P1: "#f85149", P2: "#d29922", P3: "#3fb950" };
const IOC_STATUS_LABELS = {
  active: "在线", held: "被 Hold", nxdomain: "NXDOMAIN", unknown: "未知",
};
const DISPOSITION_LABELS = { block: "封禁", correlate_only: "仅聚类" };
let intelTypesFilled = false;

function iocFilterParams() {
  const qs = new URLSearchParams();
  const map = {
    ioc_type: "i-type", priority_tier: "i-priority",
    disposition: "i-disposition", campaign: "i-campaign", status: "i-status",
  };
  Object.entries(map).forEach(([key, id]) => {
    const v = document.getElementById(id).value;
    if (v) qs.set(key, v);
  });
  return qs;
}

function renderIntelCards(stats) {
  const pr = stats.by_priority || {};
  const disp = stats.by_disposition || {};
  const cards = [
    { num: stats.report_total, label: "情报手记", cls: "accent" },
    { num: stats.ioc_total, label: "IOC 总数", cls: "" },
    { num: pr.P1 || 0, label: "P1 高价值", cls: "high" },
    { num: pr.P2 || 0, label: "P2 次高", cls: "pending" },
    { num: pr.P3 || 0, label: "P3 观察池", cls: "" },
    { num: disp.correlate_only || 0, label: "仅聚类不封禁", cls: "" },
  ];
  document.getElementById("intel-cards").innerHTML = cards
    .map((c) => `<div class="stat-card ${c.cls}"><div class="num">${esc(c.num)}</div><div class="label">${esc(c.label)}</div></div>`)
    .join("");
}

function renderIntelTimeline(items) {
  const box = document.getElementById("intel-timeline");
  if (!items.length) {
    box.innerHTML = `<div class="loading">暂无情报手记</div>`;
    return;
  }
  box.innerHTML = items
    .map((r) => {
      const anchors = (r.source_anchors || [])
        .map((a) => `<a class="key-link" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" title="${esc(a.ref || "")}">${esc(a.name)} ↗</a>`)
        .join("");
      const conf = r.confidence || {};
      const confRows = [
        ["已确认", conf.confirmed, "ok"],
        ["高置信", conf.high, "pending"],
        ["尚未确认", conf.not_yet, "watch"],
      ]
        .filter(([, list]) => list && list.length)
        .map(([label, list, cls]) => `<div class="conf-row"><span class="chip ${cls}">${esc(label)}</span> ${esc(list.join("; "))}</div>`)
        .join("");
      const date = (r.published_at || "").slice(0, 10);
      return `<div class="intel-item">
        <div class="intel-item-head">
          <span class="intel-date">${esc(date)}</span>
          <span class="chip">${esc(r.campaign_phase || "")}</span>
          <a class="intel-title" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title)}</a>
        </div>
        <div class="intel-summary">${esc(r.summary || "")}</div>
        ${confRows ? `<div class="intel-conf">${confRows}</div>` : ""}
        ${anchors ? `<div class="intel-anchors">外部锚点: ${anchors}</div>` : ""}
      </div>`;
    })
    .join("");
}

function renderIocTable(items) {
  const box = document.getElementById("intel-ioc-table");
  if (!items.length) {
    box.innerHTML = `<div class="loading">无匹配 IOC</div>`;
    return;
  }
  const rows = items
    .map((o) => {
      const camp = (o.campaign || "unknown").toLowerCase();
      const tier = o.priority_tier || "?";
      const dispCls = o.disposition === "block" ? "high" : "watch";
      return `<tr>
        <td><span class="chip" style="border-color:${PRIORITY_TIER_COLOR[tier] || "#8b949e"}">${esc(tier)}</span></td>
        <td class="mono">${esc(o.ioc_type)}</td>
        <td class="mono ioc-value">${esc(o.value)}</td>
        <td><span class="chip ${dispCls}">${esc(DISPOSITION_LABELS[o.disposition] || o.disposition || "?")}</span></td>
        <td><span class="chip ${camp}">${esc(o.campaign || "?")}</span></td>
        <td>${esc(IOC_STATUS_LABELS[o.status] || o.status || "?")}</td>
        <td class="mono">${esc(o.succeeds || "—")}</td>
        <td class="mono">${esc(o.first_report_date || "—")}</td>
        <td>${esc(o.notes || "—")}</td>
      </tr>`;
    })
    .join("");
  box.innerHTML = `<table class="compare fe-table">
    <thead><tr>
      <th>优先级</th><th>类型</th><th>IOC 值</th><th>处置</th><th>战役</th>
      <th>状态</th><th>继承自</th><th>首见日期</th><th>备注</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

async function loadIocs() {
  const box = document.getElementById("intel-ioc-table");
  box.innerHTML = `<div class="loading">加载中…</div>`;
  const qs = iocFilterParams();
  let data;
  try {
    data = await fetchJSON(`${API}/intel/iocs?${qs}`);
  } catch (e) {
    box.innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
    return;
  }
  document.getElementById("i-count").textContent = `共 ${data.count} 条 IOC`;
  renderIocTable(data.items);
}

loaders.intel = async function () {
  const timelineBox = document.getElementById("intel-timeline");
  timelineBox.innerHTML = `<div class="loading">加载中…</div>`;
  try {
    const [stats, reports] = await Promise.all([
      fetchJSON(`${API}/intel/stats`),
      fetchJSON(`${API}/intel/reports`),
    ]);
    renderIntelCards(stats);
    renderIntelTimeline(reports.items || []);
    if (!intelTypesFilled) {
      const sel = document.getElementById("i-type");
      Object.keys(stats.by_type || {}).forEach((k) =>
        sel.appendChild(el(`<option>${esc(k)}</option>`))
      );
      intelTypesFilled = true;
    }
  } catch (e) {
    timelineBox.innerHTML = `<div class="loading">加载失败: ${esc(e.message)}</div>`;
  }
  ["i-type", "i-priority", "i-disposition", "i-campaign", "i-status"].forEach((id) =>
    document.getElementById(id).addEventListener("change", loadIocs)
  );
  loadIocs();
};

// 从总览优先级饼图跳转到事件流, 并按点击的优先级过滤。
function jumpToEventsByPriority(priority) {
  const sel = document.getElementById("e-priority");
  if (sel) sel.value = priority;
  if (location.hash.slice(1) === "events") {
    activateTab("events");
    loadEvents();
  } else {
    const already = loadedTabs.has("events");
    location.hash = "events"; // 触发 hashchange -> activateTab (首次会跑 loader 读取下拉值)
    if (already) loadEvents();
  }
}

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
