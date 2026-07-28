"""CertSpotter 采集器 (CT: 证书时间线)。

对应文章"多时钟"之一: CT 说明证书或预证书何时进入公开日志。用于与注册、DNS、
URLScan 交叉印证, 区分"当天现做现用"与"提前备货"。

Mock 模式根据前台首见时间生成一条合理的 issuance 时间线; Live 模式使用
**完全免费、无需 API Key** 的 crt.sh 证书透明日志检索服务替代原先的付费
SSLMate CertSpotter API:
    - 端点: GET https://crt.sh/?q=<domain>&output=json
    - 无需认证, 直接返回该域名 (含子域) 在 CT 日志中的全部证书条目;
    - 每条含 id / name_value(多域名换行分隔) / not_before / issuer_name 等字段,
      归一化为与原 CertSpotter 一致的 {id, dns_names, not_before, issuer} 结构,
      从而保证上层去重 / 多时钟关联逻辑无需改动。
"""

from __future__ import annotations

import time

import httpx

from .base import Provider, dump_evidence


class CertSpotterCollector(Provider):
    """证书透明日志采集器 (免费 crt.sh 数据源)。"""

    source = "certspotter"

    # crt.sh 免费 CT 检索端点 (无需 API Key)
    CRTSH_URL = "https://crt.sh/"

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
        """调用免费的 crt.sh 检索域名 (含子域) 的证书透明日志条目。

        crt.sh 无需 API Key, 通过 ``output=json`` 返回证书数组; 这里将其字段
        归一化为与原 SSLMate CertSpotter 一致的结构, 使上层分析逻辑保持不变:
            - id           <- 每条证书的 crt.sh id (转为字符串)
            - dns_names    <- name_value 按换行拆分并去重 (含通配 / 子域)
            - not_before   <- 证书 not_before
            - issuer       <- issuer_name

        crt.sh 偶发返回非 JSON / 5xx (维护 / 限流 / 高峰过载), 因此做防御式解析
        并带指数退避重试。
        """
        headers = {"User-Agent": "Mozilla/5.0 (SilverFoxHunter CT collector)"}
        last_exc: Exception | None = None
        for attempt in range(3):
            if attempt:
                time.sleep(2 ** attempt)  # 2s, 4s 退避后重试
            try:
                resp = httpx.get(
                    self.CRTSH_URL,
                    params={"q": domain, "output": "json"},
                    # crt.sh 免费服务高峰期响应缓慢 (实测可达 70s+), 超时需给足
                    headers=headers, timeout=90.0, follow_redirects=True,
                )
                if resp.status_code >= 400:
                    raise RuntimeError(f"HTTP {resp.status_code}")
                try:
                    records = resp.json()
                except Exception as exc:  # 非 JSON 响应 (常见于维护/限流页)
                    raise RuntimeError(f"crt.sh returned non-JSON response: {exc}") from exc
                break
            except Exception as exc:
                last_exc = exc
        else:
            raise RuntimeError(
                f"certspotter (crt.sh) live query failed: {last_exc}"
            ) from last_exc

        issuances: list[dict] = []
        seen_ids: set[str] = set()
        for rec in records or []:
            cid = str(rec.get("id", ""))
            if cid and cid in seen_ids:
                continue
            if cid:
                seen_ids.add(cid)
            names = [
                n.strip()
                for n in str(rec.get("name_value", "")).splitlines()
                if n.strip()
            ]
            # 保序去重
            dns_names = list(dict.fromkeys(names)) or [domain]
            issuances.append({
                "id": cid or f"crtsh-{abs(hash((domain, rec.get('not_before')))) % 10_000_000}",
                "dns_names": dns_names,
                "not_before": rec.get("not_before"),
                "issuer": rec.get("issuer_name"),
            })

        dump_evidence(self.source, domain, issuances)
        return issuances
