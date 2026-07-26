"""DoH 采集器 (DNS: 先看存活)。

对应文章第三节: DNS 层只保存 A/AAAA/CNAME/NS 的 JSON 快照并做差。Google DoH
返回 HTTP 200 只代表查询传输成功, 解析结论要看响应中的 Status
(0=NOERROR, 3=NXDOMAIN)。

Mock 模式返回复原数据集中的 DNS 状态; Live 模式调用 Google Public DNS DoH。
"""

from __future__ import annotations

import httpx

from ..mock import dataset
from ..models import DnsSnapshotRecord
from .base import Provider, dump_evidence, now_iso

# DNS 记录类型
_RTYPES = {"A": 1, "AAAA": 28, "CNAME": 5, "NS": 2}


class DohCollector(Provider):
    """DNS over HTTPS 采集器。"""

    source = "doh"

    def resolve(self, domain: str) -> DnsSnapshotRecord:
        """解析域名, 返回 DNS 快照。"""
        if self.is_live:
            return self._resolve_live(domain)
        return self._resolve_mock(domain)

    def _resolve_mock(self, domain: str) -> DnsSnapshotRecord:
        snap = dataset.DNS_SNAPSHOTS.get(domain)
        if snap is None:
            # 默认解析成功指向共享地址
            return DnsSnapshotRecord(
                domain=domain, observed_at=now_iso(),
                dns_status=0, a_records=["156.250.163.180"],
                ns_records=["ns3.dnsv5.com", "ns4.dnsv5.com"],
            )
        return DnsSnapshotRecord(
            domain=domain,
            observed_at=now_iso(),
            dns_status=snap["dns_status"],
            a_records=snap.get("a_records", []),
            ns_records=snap.get("ns_records", []),
        )

    def _resolve_live(self, domain: str) -> DnsSnapshotRecord:
        snap = DnsSnapshotRecord(domain=domain, observed_at=now_iso())
        status_seen: int | None = None
        for rtype, _ in _RTYPES.items():
            try:
                resp = httpx.get(
                    "https://dns.google/resolve",
                    params={"name": domain, "type": rtype}, timeout=15.0,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                raise RuntimeError(f"doh live query failed: {exc}") from exc
            dump_evidence(self.source, f"{domain}_{rtype}", data)
            # DNS 结论看 Status 字段, 而非 HTTP 200
            status_seen = data.get("Status", status_seen)
            answers = [a.get("data") for a in data.get("Answer", [])]
            if rtype == "A":
                snap.a_records = answers
            elif rtype == "AAAA":
                snap.aaaa_records = answers
            elif rtype == "CNAME":
                snap.cname_records = answers
            elif rtype == "NS":
                snap.ns_records = answers
        snap.dns_status = status_seen
        return snap
