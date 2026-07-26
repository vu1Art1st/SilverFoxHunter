/* 个人中心逻辑 —— 改用户名/密码/头像 + API 密钥配置。对接 /api/profile 与 /api/settings。 */
"use strict";

const API = "/api";
const MODE_LABELS = {
  urlscan: "URLScan",
  certspotter: "CertSpotter",
  rdap: "RDAP/WHOIS",
  doh: "DNS (DoH)",
  control: "控制接口",
  payload: "载荷解析",
};
const KEY_COLLECTORS = ["urlscan", "certspotter"];
const DEFAULT_AVATAR =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72"><rect width="72" height="72" rx="12" fill="#1c2230"/><text x="36" y="48" font-size="36" text-anchor="middle" fill="#f78c3c">🦊</text></svg>'
  );

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2600);
}
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );
}

async function api(path, opts) {
  const res = await fetch(`${API}${path}`, opts);
  if (res.status === 401) {
    location.href = "/login";
    throw new Error("未登录");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

/* ---------- 账户资料 ---------- */
async function loadProfile() {
  const p = await api("/profile");
  document.getElementById("username").value = p.username || "";
  document.getElementById("avatar-preview").src = p.avatar || DEFAULT_AVATAR;
}

document.getElementById("btn-username").addEventListener("click", async () => {
  const username = document.getElementById("username").value.trim();
  try {
    await api("/profile/username", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username }),
    });
    toast("用户名已更新");
  } catch (e) {
    toast("失败: " + e.message);
  }
});

/* ---------- 头像 ---------- */
const avatarFile = document.getElementById("avatar-file");
document.getElementById("btn-avatar").addEventListener("click", () => avatarFile.click());
avatarFile.addEventListener("change", () => {
  const file = avatarFile.files[0];
  if (!file) return;
  if (file.size > 512 * 1024) {
    toast("头像过大 (>512KB)");
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => {
    const dataUrl = reader.result;
    try {
      await api("/profile/avatar", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ avatar: dataUrl }),
      });
      document.getElementById("avatar-preview").src = dataUrl;
      toast("头像已更新");
    } catch (e) {
      toast("失败: " + e.message);
    }
  };
  reader.readAsDataURL(file);
});
document.getElementById("btn-avatar-clear").addEventListener("click", async () => {
  try {
    await api("/profile/avatar", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ avatar: "" }),
    });
    document.getElementById("avatar-preview").src = DEFAULT_AVATAR;
    toast("头像已清除");
  } catch (e) {
    toast("失败: " + e.message);
  }
});

/* ---------- 修改密码 ---------- */
document.getElementById("btn-password").addEventListener("click", async () => {
  const oldPw = document.getElementById("old-password").value;
  const newPw = document.getElementById("new-password").value;
  const newPw2 = document.getElementById("new-password2").value;
  if (newPw !== newPw2) {
    toast("两次输入的新密码不一致");
    return;
  }
  try {
    await api("/profile/password", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old_password: oldPw, new_password: newPw }),
    });
    toast("密码已更新, 请重新登录");
    document.getElementById("old-password").value = "";
    document.getElementById("new-password").value = "";
    document.getElementById("new-password2").value = "";
    setTimeout(() => (location.href = "/login"), 1200);
  } catch (e) {
    toast("失败: " + e.message);
  }
});

/* ---------- API 密钥配置 ---------- */
const configPanel = document.getElementById("config-panel");
let configLoaded = false;

document.getElementById("btn-config").addEventListener("click", async () => {
  configPanel.hidden = !configPanel.hidden;
  if (!configPanel.hidden && !configLoaded) {
    await loadConfig();
    configLoaded = true;
  }
});

async function loadConfig() {
  const cfg = await api("/settings/apikeys");
  const modesGrid = document.getElementById("modes-grid");
  modesGrid.innerHTML =
    "<h4 class='config-title'>采集器模式</h4>" +
    Object.keys(MODE_LABELS)
      .map((name) => {
        const mode = (cfg.modes && cfg.modes[name]) || "mock";
        return `<label class="config-item">${esc(MODE_LABELS[name])}
          <select data-mode="${name}">
            <option value="mock" ${mode === "mock" ? "selected" : ""}>mock</option>
            <option value="live" ${mode === "live" ? "selected" : ""}>live</option>
          </select></label>`;
      })
      .join("");

  const keysGrid = document.getElementById("keys-grid");
  keysGrid.innerHTML =
    "<h4 class='config-title'>API 密钥</h4>" +
    KEY_COLLECTORS.map((name) => {
      const info = (cfg.api_keys && cfg.api_keys[name]) || {};
      const ph = info.set ? `已配置 (${esc(info.masked)})` : "未配置";
      return `<label class="config-item">${esc(MODE_LABELS[name])} 密钥
        <input type="text" data-key="${name}" placeholder="${ph}" />
        <small class="auth-hint">留空表示不修改</small></label>`;
    }).join("");
}

document.getElementById("btn-save-config").addEventListener("click", async () => {
  const modes = {};
  document.querySelectorAll("[data-mode]").forEach((el) => {
    modes[el.dataset.mode] = el.value;
  });
  const api_keys = {};
  document.querySelectorAll("[data-key]").forEach((el) => {
    const v = el.value.trim();
    if (v !== "") api_keys[el.dataset.key] = v; // 留空则不改动
  });
  try {
    await api("/settings/apikeys", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modes, api_keys }),
    });
    toast("配置已保存并生效");
    configLoaded = false;
    await loadConfig();
    configLoaded = true;
    document.querySelectorAll("[data-key]").forEach((el) => (el.value = ""));
  } catch (e) {
    toast("失败: " + e.message);
  }
});

/* ---------- 退出登录 ---------- */
document.getElementById("btn-logout").addEventListener("click", async () => {
  try {
    await fetch(`${API}/auth/logout`, { method: "POST" });
  } catch (e) {
    /* 忽略 */
  }
  location.href = "/login";
});

/* ---------- 启动 ---------- */
loadProfile().catch((e) => toast("加载失败: " + e.message));
