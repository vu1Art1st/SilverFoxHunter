/* 登录页逻辑 —— 提交到 /api/auth/login, 成功后跳转仪表盘。 */
"use strict";

const form = document.getElementById("login-form");
const errBox = document.getElementById("login-error");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errBox.textContent = "";
  const btn = form.querySelector("button[type=submit]");
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  btn.disabled = true;
  btn.textContent = "登录中…";
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.detail || `登录失败 (HTTP ${res.status})`);
    }
    // 会话 Cookie 已下发, 跳转首页
    location.href = "/";
  } catch (err) {
    errBox.textContent = err.message;
    btn.disabled = false;
    btn.textContent = "登 录";
  }
});
