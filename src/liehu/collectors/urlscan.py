"""URLScan 采集器 (壳: 发现不断变脸的前台)。

核心方法对应文章第二节: 不搜品牌词, 而是盯住请求关系。
    - 用 domain.keyword 找"哪些扫描碰过这个控制域", 并排除控制域自身;
    - 用 filename.keyword 精确匹配"哪些页面请求过这条 api.php";
    - 采用重叠时间窗 + task.uuid 去重吸收索引延迟。

Mock 模式从复原数据集中按控制域筛选前台; Live 模式调用 URLScan Search API
(官方文档: https://urlscan.io/docs/api/):
    - 端点: GET https://urlscan.io/api/v1/search/
    - 参数: q (ElasticSearch 查询串) / size (默认 100, 最大 10000)
    - 认证: API-Key 请求头 (官方要求使用 api-key 头而非 x-api-key 等其他名称;
      密钥在 https://urlscan.io/user/profile/ 注册账号后创建)。
"""

from __future__ import annotations

import httpx

from ..mock import dataset
from ..models import FrontendRecord
from .base import Provider, dump_evidence


def build_query(control_domain: str, window_minutes: int, precise: bool = True) -> str:
    """构造 URLScan 查询串。

    precise=True 时使用精确 api.php 请求关系查询 (文章统计口径),
    否则使用较宽的 domain.keyword 查询。
    """
    api_url = f"https://{control_domain}/api.php"
    if precise:
        return (
            f'filename.keyword:"{api_url}"'
            f' AND NOT page.domain.keyword:{control_domain}'
            f' AND date:>now-{window_minutes}m'
        )
    return (
        f"domain.keyword:{control_domain}"
        f" AND NOT page.domain.keyword:{control_domain}"
        f" AND date:>now-{window_minutes}m"
    )


class UrlScanCollector(Provider):
    """URLScan 前台发现采集器。"""

    source = "urlscan"

    def discover(self, control_domain: str, window_minutes: int = 15) -> list[FrontendRecord]:
        """发现请求指定控制域的新前台。"""
        if self.is_live:
            return self._discover_live(control_domain, window_minutes)
        return self._discover_mock(control_domain, window_minutes)

    # ---- Mock ----------------------------------------------------------------
    def _discover_mock(self, control_domain: str, window_minutes: int) -> list[FrontendRecord]:
        """从复原数据集中筛选出请求该控制域的前台。"""
        records: list[FrontendRecord] = []
        for row in dataset.generate_frontends():
            if row["control_domain"] != control_domain:
                continue
            records.append(FrontendRecord(
                domain=row["domain"],
                task_uuid=row["task_uuid"],
                first_seen=row.get("first_seen"),
                last_seen=row.get("last_seen"),
                title=row.get("title"),
                page_ip=row.get("page_ip"),
                http_status=row.get("http_status"),
                control_domain=row.get("control_domain"),
                control_api=row.get("control_api"),
                analytics_id=row.get("analytics_id"),
                theme=row.get("theme"),
                registered_at=row.get("registered_at"),
                ns=row.get("ns"),
                evidence_url=row.get("evidence_url"),
            ))
        return records

    # ---- Live ----------------------------------------------------------------
    def _discover_live(self, control_domain: str, window_minutes: int) -> list[FrontendRecord]:
        """调用真实 URLScan Search API。

        严格按官方规范: GET /api/v1/search/?q=...&size=..., 认证使用 API-Key 请求头
        (未认证请求仅享匿名配额), 并按文档建议用 date 过滤缩小查询窗口。
        """
        query = build_query(control_domain, window_minutes, precise=True)
        headers = {"API-Key": self.api_key} if self.api_key else {}
        params = {"q": query, "size": 100}
        try:
            resp = httpx.get(
                "https://urlscan.io/api/v1/search/",
                params=params, headers=headers, timeout=20.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # 网络/配额/鉴权错误 -> 交给上层记账
            raise RuntimeError(f"urlscan live query failed: {exc}") from exc

        dump_evidence(self.source, control_domain, data)
        records: list[FrontendRecord] = []
        for item in data.get("results", []):
            page = item.get("page", {})
            task = item.get("task", {})
            domain = page.get("domain")
            if not domain or domain == control_domain:
                continue
            records.append(FrontendRecord(
                domain=domain,
                task_uuid=task.get("uuid", ""),
                first_seen=task.get("time"),
                last_seen=task.get("time"),
                title=page.get("title"),
                page_ip=page.get("ip"),
                http_status=page.get("status"),
                control_domain=control_domain,
                control_api=f"{control_domain}/api.php",
                evidence_url=item.get("result"),
            ))
        return records
