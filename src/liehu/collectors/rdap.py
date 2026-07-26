"""RDAP 采集器 (注册数据: 注册时间/状态/NS)。

对应文章"多时钟"之一: RDAP / WHOIS 说明注册、变更、状态和 NS。文中 .cn 域名的
秒级注册时间来自 CNNIC WHOIS。系统优先按 IANA RDAP Bootstrap 找到对应 TLD 服务,
再请求 RDAP_BASE/domain/TARGET。

Mock 模式直接返回复原数据集中的注册时间; Live 模式做 RDAP 查询。
"""

from __future__ import annotations

import httpx

from ..mock import dataset
from .base import Provider, dump_evidence

# 常见 TLD 的 RDAP 服务基址 (IANA Bootstrap 的简化子集)
RDAP_BASES = {
    "com": "https://rdap.verisign.com/com/v1",
    "net": "https://rdap.verisign.com/net/v1",
    "org": "https://rdap.publicinterestregistry.org/rdap",
    "site": "https://rdap.centralnic.com/site",
}


class RdapCollector(Provider):
    """注册数据采集器。"""

    source = "rdap"

    def lookup(self, domain: str) -> dict:
        """查询域名注册信息。"""
        if self.is_live:
            return self._lookup_live(domain)
        return self._lookup_mock(domain)

    def _lookup_mock(self, domain: str) -> dict:
        # 从复原数据集中检索注册时间
        for row in dataset.generate_frontends():
            if row["domain"] == domain:
                return {
                    "domain": domain,
                    "registered_at": row.get("registered_at"),
                    "ns": (row.get("ns") or "").split(",") if row.get("ns") else [],
                    "status": ["active"],
                }
        return {"domain": domain, "registered_at": None, "ns": [], "status": []}

    def _lookup_live(self, domain: str) -> dict:
        tld = domain.rsplit(".", 1)[-1]
        base = RDAP_BASES.get(tld)
        if not base:
            raise RuntimeError(f"no RDAP base for TLD .{tld}")
        try:
            resp = httpx.get(f"{base}/domain/{domain}", timeout=20.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise RuntimeError(f"rdap live query failed: {exc}") from exc
        dump_evidence(self.source, domain, data)
        registered_at = None
        for event in data.get("events", []):
            if event.get("eventAction") == "registration":
                registered_at = event.get("eventDate")
        ns = [ns.get("ldhName") for ns in data.get("nameservers", [])]
        return {
            "domain": domain,
            "registered_at": registered_at,
            "ns": ns,
            "status": data.get("status", []),
        }
