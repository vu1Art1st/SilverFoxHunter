"""仿冒站点路由: 列表 / 详情 / CSV 导出 / 存活探测与截图。"""

from __future__ import annotations

import csv
import io
import socket
import time
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import Response

from ..db import get_connection, rows_to_list

router = APIRouter(tags=["frontends"])


def _build_filters(
    campaign: str | None,
    day_class: str | None,
    theme: str | None,
    q: str | None = None,
):
    """构造列表/导出共用的 WHERE 子句与参数。"""
    clauses, params = [], []
    if campaign:
        clauses.append("campaign = ?")
        params.append(campaign)
    if day_class:
        clauses.append("day_class = ?")
        params.append(day_class)
    if theme:
        clauses.append("theme = ?")
        params.append(theme)
    if q:
        # 域名关键词模糊匹配 (转义 LIKE 通配符, 避免 % _ 被当作通配)
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("domain LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


# CSV 导出列: (字段名, 中文表头) —— 覆盖 frontends 表全部字段
CSV_COLUMNS: tuple[tuple[str, str], ...] = (
    ("domain", "域名"),
    ("page_ip", "IP 地址"),
    ("title", "页面标题"),
    ("http_status", "HTTP 状态"),
    ("campaign", "C2 集群"),
    ("theme", "诱饵题材"),
    ("day_class", "注册时效分类"),
    ("control_domain", "C2 控制域名"),
    ("control_api", "C2 控制接口"),
    ("analytics_id", "统计 ID"),
    ("registered_at", "域名注册时间"),
    ("ns", "NS 记录"),
    ("first_seen", "首次检测时间"),
    ("last_seen", "最近检测时间"),
    ("evidence_url", "证据链接"),
    ("task_uuid", "URLScan 任务 UUID"),
    ("updated_at", "更新时间"),
)


@router.get("/frontends/export.csv")
def export_frontends_csv(
    campaign: str | None = Query(None, description="按 C2 集群过滤: noah/fezhx"),
    day_class: str | None = Query(None, description="按注册时效分类过滤"),
    theme: str | None = Query(None, description="按诱饵题材过滤"),
    q: str | None = Query(None, description="按域名关键词模糊过滤"),
) -> Response:
    """导出仿冒站点全量字段为 CSV。

    UTF-8 with BOM 编码 + CRLF 行尾, 确保 Excel/WPS 等电子表格软件
    双击打开时中文不乱码; 支持与列表页相同的过滤条件。
    """
    where, params = _build_filters(campaign, day_class, theme, q)
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM frontends {where} ORDER BY last_seen DESC", params
        ).fetchall()
    finally:
        conn.close()

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow([label for _, label in CSV_COLUMNS])
    for row in rows_to_list(rows):
        writer.writerow(["" if row.get(f) is None else row.get(f) for f, _ in CSV_COLUMNS])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"fake_sites_{stamp}.csv"
    return Response(
        content="\ufeff" + buf.getvalue(),  # BOM 供 Excel 识别 UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/frontends")
def list_frontends(
    campaign: str | None = Query(None, description="按 C2 集群过滤: noah/fezhx"),
    day_class: str | None = Query(None, description="按注册时效分类过滤"),
    theme: str | None = Query(None, description="按诱饵题材过滤"),
    q: str | None = Query(None, description="按域名关键词模糊过滤"),
    limit: int = Query(200, le=1000),
) -> dict:
    """列出仿冒站点状态卡, 支持按 C2 集群/注册时效/诱饵题材/域名关键词过滤。"""
    where, params = _build_filters(campaign, day_class, theme, q)

    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM frontends {where} ORDER BY last_seen DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    finally:
        conn.close()
    return {"count": len(rows), "items": rows_to_list(rows)}


@router.get("/frontends/{domain}")
def get_frontend(domain: str) -> dict:
    """获取单个仿冒站点的状态卡。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM frontends WHERE domain = ?", (domain,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else {}


# ---- 存活探测与截图 --------------------------------------------------------

# 探测结果内存缓存: domain -> (时间戳, 结果), 避免反复点开弹窗时重复外联探测
_PROBE_CACHE: dict[str, tuple[float, dict]] = {}
_PROBE_TTL_SECONDS = 600


def _probe_site(domain: str) -> dict:
    """探测目标站点存活状态。

    先做 DNS 解析 (失败 -> 域名疑似失效), 再发 HTTPS/HTTP 探测请求
    (连接失败/超时/HTTP>=400 -> 访问异常)。仿冒站点多为短命域名,
    探测结果本身就是有情报价值的存活信号。
    """
    try:
        socket.getaddrinfo(domain, None)
    except socket.gaierror:
        return {"status": "domain_dead", "status_label": "域名疑似失效", "http_status": None}

    last_error: str | None = None
    for scheme in ("https", "http"):
        try:
            resp = httpx.get(
                f"{scheme}://{domain}/",
                timeout=8.0, follow_redirects=True, verify=False,
                headers={"User-Agent": "Mozilla/5.0 (SilverFoxHunter probe)"},
            )
            if resp.status_code < 400:
                return {"status": "ok", "status_label": "可访问", "http_status": resp.status_code}
            last_error = f"HTTP {resp.status_code}"
        except Exception as exc:
            last_error = type(exc).__name__
    return {
        "status": "unreachable",
        "status_label": "访问异常",
        "http_status": None,
        "detail": last_error,
    }


@router.get("/frontends/{domain}/screenshot")
def frontend_screenshot(domain: str) -> dict:
    """仿冒站点存活探测 + 截图地址。

    返回:
        - status / status_label: ok(可访问) / domain_dead(域名疑似失效) / unreachable(访问异常)
        - screenshot_url: 站点可访问时的实时渲染截图 (mshots 渲染服务)
        - evidence_screenshot_url: URLScan 扫描历史截图 (有 task_uuid 时)
    截图由前端点击域名后按需弹窗加载, 探测结果缓存 10 分钟。
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT domain, task_uuid, evidence_url FROM frontends WHERE domain = ?",
            (domain,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"domain": domain, "status": "unknown", "status_label": "未知域名"}

    cached = _PROBE_CACHE.get(domain)
    if cached and time.time() - cached[0] < _PROBE_TTL_SECONDS:
        probe = cached[1]
    else:
        probe = _probe_site(domain)
        _PROBE_CACHE[domain] = (time.time(), probe)

    result = {"domain": domain, **probe}
    if probe["status"] == "ok":
        # mshots 公开渲染服务: 对可访问站点自动爬取实时截图
        result["screenshot_url"] = (
            f"https://s0.wp.com/mshots/v1/{quote(f'https://{domain}/', safe='')}?w=1024"
        )
    task_uuid = row["task_uuid"]
    if task_uuid and not task_uuid.startswith("uuid-"):  # mock 占位 uuid 无真实截图
        result["evidence_screenshot_url"] = f"https://urlscan.io/screenshots/{task_uuid}.png"
    return result
