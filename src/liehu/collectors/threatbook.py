"""微步在线 (ThreatBook) 情报采集器 (两级联动, 见 docs/threatbook-integration.md)。

    - L1 批量打标: verdict_batch() 调用失陷检测接口 v3/scene/dns,
      单次最多 100 个域名, 143 域名仅需 2 次调用, 返回轻量判定;
    - L2 按需详查: domain_detail() 调用域名分析接口 v3/domain/query,
      单域名全维度上下文 (含 Phishing 判定 / whois / 样本 / 解析 IP)。

认证: apikey 作为请求参数传递 (非请求头)。支持录入多个 API KEY
(逗号/分号/换行分隔), 当前 KEY 达到限额时自动切换下一个, 轮换索引
持久化到 app_settings, 重启后从上次可用的 KEY 继续。

Mock 模式基于复原数据集生成合理判定 (银狐团伙标签), 无密钥即可演示完整链路。
"""

from __future__ import annotations

import json

import httpx

from ..config import parse_api_keys
from ..mock import dataset
from .base import Provider, dump_evidence, now_iso

SCENE_DNS_URL = "https://api.threatbook.cn/v3/scene/dns"
DOMAIN_QUERY_URL = "https://api.threatbook.cn/v3/domain/query"

#: 单次批量查询上限 (官方: resource 逗号分隔最多 100 个)
BATCH_LIMIT = 100

#: 视为"当前 KEY 配额耗尽/受限, 应切换下一个 KEY"的 response_code
QUOTA_CODES = {-1, -4}  # -1 权限受限(套餐/配额), -4 调用频率或次数超限


class ThreatBookKeyRing:
    """多 API KEY 轮换环。

    从多 KEY 配置串解析密钥列表, 按索引顺序使用; 当前索引持久化到
    app_settings (key=threatbook.key_index), 限额切换后重启不回退。
    """

    SETTING_KEY = "threatbook.key_index"

    def __init__(self, raw_keys: str | None) -> None:
        self.keys = parse_api_keys(raw_keys)
        self.index = self._load_index() % len(self.keys) if self.keys else 0

    def _load_index(self) -> int:
        from ..db import get_connection  # 延迟导入避免循环依赖

        try:
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT value FROM app_settings WHERE key = ?", (self.SETTING_KEY,)
                ).fetchone()
                return int(row["value"]) if row else 0
            finally:
                conn.close()
        except Exception:
            return 0

    def _save_index(self) -> None:
        from ..db import get_connection

        try:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings(key, value) VALUES (?, ?)",
                    (self.SETTING_KEY, str(self.index)),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass  # 持久化失败不影响本进程内轮换

    def ordered(self) -> list[str]:
        """按当前索引起始返回全部 KEY (轮换尝试顺序)。"""
        if not self.keys:
            return []
        return [self.keys[(self.index + i) % len(self.keys)] for i in range(len(self.keys))]

    def commit(self, offset: int) -> None:
        """固化本次成功使用的 KEY (相对 ordered() 的偏移), 供后续调用直用。"""
        if not self.keys or offset == 0:
            return
        self.index = (self.index + offset) % len(self.keys)
        self._save_index()


class ThreatBookCollector(Provider):
    """微步在线情报采集器 (L1 批量打标 + L2 按需详查)。"""

    source = "threatbook"

    def __init__(self, mode: str = "mock", api_key: str | None = None) -> None:
        super().__init__(mode, api_key)
        self.ring = ThreatBookKeyRing(api_key)

    # ---- L1 批量打标 -----------------------------------------------------------
    def verdict_batch(self, domains: list[str]) -> list[dict]:
        """批量查询域名失陷判定, 返回归一化判定列表 (每域名一条)。"""
        targets = [d for d in dict.fromkeys(domains) if d]
        if not targets:
            return []
        if self.is_live:
            return self._verdict_live(targets)
        return self._verdict_mock(targets)

    # ---- L2 按需详查 -----------------------------------------------------------
    def domain_detail(self, domain: str) -> dict:
        """查询单个域名的完整情报上下文 (whois/样本/解析IP/团伙标签)。"""
        if self.is_live:
            return self._detail_live(domain)
        return self._detail_mock(domain)

    # ---- Mock ------------------------------------------------------------------
    @staticmethod
    def _mock_profile(domain: str) -> dict | None:
        """按复原数据集判定域名角色, 返回 mock 判定要素; 未知域名返回 None。"""
        c2_domains = {dataset.CONTROL_NOAH, dataset.CONTROL_FEZHX, dataset.CONTROL_PAGE}
        download_hosts = {
            dataset.DOWNLOAD_GNRRN.split("/")[0],
            dataset.DOWNLOAD_360.split("/")[0],
        }
        if domain in c2_domains:
            return {"judgments": ["C2", "Trojan"], "severity": "critical"}
        if domain in download_hosts:
            return {"judgments": ["Malware"], "severity": "high"}
        if domain in {f["domain"] for f in dataset.generate_frontends()}:
            return {"judgments": ["Phishing", "Malware"], "severity": "high"}
        return None

    def _verdict_mock(self, domains: list[str]) -> list[dict]:
        verdicts = []
        for domain in domains:
            profile = self._mock_profile(domain)
            verdicts.append({
                "domain": domain,
                "is_malicious": profile is not None,
                "confidence_level": "high" if profile else "low",
                "severity": profile["severity"] if profile else "info",
                "judgments": profile["judgments"] if profile else [],
                "tags": ["银狐"] if profile else [],
                "permalink": f"https://x.threatbook.com/v5/domain/{domain}",
                "queried_at": now_iso(),
            })
        return verdicts

    def _detail_mock(self, domain: str) -> dict:
        verdict = self._verdict_mock([domain])[0]
        profile = self._mock_profile(domain)
        detail = {
            **verdict,
            "source": "mock",
            "intelligences": [],
            "samples": [],
            "cur_ips": [],
            "cur_whois": {},
            "cas": [],
        }
        if profile is None:
            return detail
        detail["intelligences"] = [{
            "source": "微步实验室",
            "find_time": "2026-07-23 19:36:43",
            "confidence": 90,
            "intel_types": profile["judgments"],
            "expired": False,
        }]
        # 载荷分发宿主/C2 关联当晚样本骨架, 与"包"层 IOC 交叉印证
        if set(profile["judgments"]) & {"C2", "Trojan", "Malware"}:
            detail["samples"] = [{
                "sha256": dataset.EMBEDDED_PE_SHA256_0723,
                "scan_time": "2026-07-23 19:28:00",
                "ratio": "42/70",
                "malware_family": "SilverFox",
            }]
        row = next(
            (f for f in dataset.generate_frontends() if f["domain"] == domain), None
        )
        if row:
            detail["cur_ips"] = [{
                "ip": row["page_ip"],
                "carrier": "mock-hosting",
                "location": {"country": "未知", "city": ""},
            }]
            detail["cur_whois"] = {
                "registrar_name": "mock-registrar",
                "registrant_email": "",
                "cdate": row.get("registered_at"),
            }
        return detail

    # ---- Live ------------------------------------------------------------------
    def _http_get(self, url: str, params: dict) -> dict:
        """单次 HTTP 调用 (独立方法便于测试打桩)。"""
        resp = httpx.get(url, params=params, timeout=30.0)
        resp.raise_for_status()
        return resp.json()

    def _call_live(self, url: str, params: dict) -> dict:
        """带多 KEY 轮换的微步 API 调用。

        response_code == 0 视为成功; 命中配额错误码时自动切换下一个 KEY,
        全部 KEY 耗尽则抛错交上层记入错误账本。apikey 不落日志/证据。
        """
        keys = self.ring.ordered()
        if not keys:
            raise RuntimeError("threatbook: 未配置 API KEY (个人中心可录入多个, 分隔符 , ; 或换行)")
        quota_msgs: list[str] = []
        for offset, key in enumerate(keys):
            try:
                data = self._http_get(url, {**params, "apikey": key})
            except Exception as exc:  # 网络/HTTP 错误与配额无关, 直接抛出
                raise RuntimeError(f"threatbook live query failed: {exc}") from exc
            code = data.get("response_code")
            if code == 0:
                self.ring.commit(offset)
                return data
            if code in QUOTA_CODES:
                quota_msgs.append(f"key#{offset + 1}: code={code} {data.get('verbose_msg', '')}")
                continue
            raise RuntimeError(
                f"threatbook API error: code={code} {data.get('verbose_msg', '')}"
            )
        raise RuntimeError(
            f"threatbook: 全部 {len(keys)} 个 API KEY 均已达限额或受限 ({'; '.join(quota_msgs)})"
        )

    @staticmethod
    def _flatten_tags(tags_classes: list | None) -> list[str]:
        """展平 tags_classes ([{tags_type, tags:[..]}]) 为标签数组。"""
        tags: list[str] = []
        for cls in tags_classes or []:
            for t in cls.get("tags", []):
                if t not in tags:
                    tags.append(t)
        return tags

    def _verdict_live(self, domains: list[str]) -> list[dict]:
        verdicts: list[dict] = []
        for i in range(0, len(domains), BATCH_LIMIT):
            batch = domains[i:i + BATCH_LIMIT]
            data = self._call_live(SCENE_DNS_URL, {
                "resource": ",".join(batch),
                "lang": "zh",
            })
            dump_evidence(self.source, f"scene_dns_batch{i // BATCH_LIMIT}", data)
            payload = data.get("data", {})
            for domain in batch:
                item = payload.get(domain) or {}
                verdicts.append({
                    "domain": domain,
                    "is_malicious": bool(item.get("is_malicious")),
                    "confidence_level": item.get("confidence_level"),
                    "severity": item.get("severity"),
                    "judgments": item.get("judgments", []),
                    "tags": self._flatten_tags(item.get("tags_classes")),
                    "permalink": item.get("permalink"),
                    "queried_at": now_iso(),
                })
        return verdicts

    def _detail_live(self, domain: str) -> dict:
        data = self._call_live(DOMAIN_QUERY_URL, {
            "resource": domain,
            "lang": "zh",
            # 裁掉不展示的重量级字段, 减小响应体
            "exclude": "sum_sub_domains,sum_cur_ips",
        })
        dump_evidence(self.source, domain, data)
        item = data.get("data", {}).get(domain) or {}
        return {
            "domain": domain,
            "source": "live",
            "is_malicious": bool(item.get("is_malicious")),
            "confidence_level": item.get("confidence_level"),
            "severity": item.get("severity"),
            "judgments": item.get("judgments", []),
            "tags": self._flatten_tags(item.get("tags_classes")),
            "permalink": item.get("permalink")
            or f"https://x.threatbook.com/v5/domain/{domain}",
            "intelligences": item.get("intelligences", []),
            "samples": item.get("samples", []),
            "cur_ips": item.get("cur_ips", []),
            "cur_whois": item.get("cur_whois", {}),
            "cas": item.get("cas", []),
            "queried_at": now_iso(),
        }


def verdict_row(v: dict) -> tuple:
    """将归一化判定 dict 转为 threatbook_verdicts 表插入参数。"""
    return (
        v["domain"], int(bool(v.get("is_malicious"))), v.get("confidence_level"),
        v.get("severity"), json.dumps(v.get("judgments", []), ensure_ascii=False),
        json.dumps(v.get("tags", []), ensure_ascii=False),
        v.get("permalink"), v.get("queried_at") or now_iso(),
    )
