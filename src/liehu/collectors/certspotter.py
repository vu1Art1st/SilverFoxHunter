"""CertSpotter 采集器 (CT: 证书时间线)。

对应文章"多时钟"之一: CT 说明证书或预证书何时进入公开日志。用于与注册、DNS、
URLScan 交叉印证, 区分"当天现做现用"与"提前备货"。

Mock 模式根据前台首见时间生成一条合理的 issuance 时间线; Live 模式调用
CertSpotter issuances API。
"""

from __future__ import annotations

import httpx

from .base import Provider, dump_evidence


class CertSpotterCollector(Provider):
    """证书透明日志采集器。"""

    source = "certspotter"

    def issuances(self, domain: str, first_seen: str | None = None) -> list[dict]:
        """获取域名的证书签发时间线。"""
        if self.is_live:
            return self._issuances_live(domain)
        return self._issuances_mock(domain, first_seen)

    def _issuances_mock(self, domain: str, first_seen: str | None) -> list[dict]:
        # 用首见时间近似证书进入公开日志的时间
        return [{
            "id": f"ct-{abs(hash(domain)) % 10_000_000}",
            "dns_names": [domain, f"*.{domain}"],
            "not_before": first_seen,
            "issuer": "Let's Encrypt",
        }]

    def _issuances_live(self, domain: str) -> list[dict]:
        params = {
            "domain": domain,
            "include_subdomains": "true",
            "expand": ["dns_names", "issuer"],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            resp = httpx.get(
                "https://api.certspotter.com/v1/issuances",
                params=params, headers=headers, timeout=20.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise RuntimeError(f"certspotter live query failed: {exc}") from exc
        dump_evidence(self.source, domain, data)
        return data
