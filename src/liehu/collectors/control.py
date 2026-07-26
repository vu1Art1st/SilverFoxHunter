"""控制端采集器 (线: 分时看实际去向)。

对应文章第三节: 单次返回只是一张照片, 控制接口要分时采样。至少保存观察时间、
HTTP 状态、响应头、响应体 SHA-256、响应长度、解析出的 download_link 以及错误信息。

Mock 模式按"轮次"回放 dataset.CONTROL_ROUNDS (从 7·22 分离到 7·23 合流);
Live 模式对控制接口发起真实 HTTP 请求 (等价文章的 curl 最小采样模板)。
"""

from __future__ import annotations

import json

import httpx

from ..mock import dataset
from ..models import ControlSampleRecord
from .base import Provider, dump_evidence, now_iso, sha256_hex


class ControlCollector(Provider):
    """控制接口分时采样采集器。"""

    source = "control"

    def sample(self, round_index: int, control_domains: list[str]) -> list[ControlSampleRecord]:
        """采样一轮控制接口。

        round_index: mock 回放的轮次 (超出则钳制到最后一轮, 表示持续监控)。
        control_domains: live 模式下要采样的控制域列表。
        """
        if self.is_live:
            return self._sample_live(control_domains)
        return self._sample_mock(round_index)

    # ---- Mock ----------------------------------------------------------------
    def _sample_mock(self, round_index: int) -> list[ControlSampleRecord]:
        rounds = dataset.CONTROL_ROUNDS
        idx = min(round_index, len(rounds) - 1)
        rnd = rounds[idx]
        results: list[ControlSampleRecord] = []
        for s in rnd["samples"]:
            body = json.dumps(
                {"download_link": s.get("download_link")}, sort_keys=True
            ).encode()
            results.append(ControlSampleRecord(
                control_domain=s["control_domain"],
                control_api=s["control_api"],
                observed_at=rnd["observed_at"],
                http_status=s.get("http_status"),
                resp_sha256=sha256_hex(body) if s.get("download_link") else None,
                resp_length=len(body) if s.get("download_link") else 0,
                download_link=s.get("download_link"),
                headers_json=json.dumps({"content-type": "application/json"}),
                error=s.get("error"),
            ))
        return results

    # ---- Live ----------------------------------------------------------------
    def _sample_live(self, control_domains: list[str]) -> list[ControlSampleRecord]:
        results: list[ControlSampleRecord] = []
        for domain in control_domains:
            api_url = f"https://{domain}/api.php"
            try:
                resp = httpx.get(api_url, timeout=15.0)
                body = resp.content
                download_link = self._extract_download_link(resp)
                dump_evidence(self.source, domain, {
                    "status": resp.status_code,
                    "headers": dict(resp.headers),
                    "body": body.decode(errors="replace"),
                })
                results.append(ControlSampleRecord(
                    control_domain=domain,
                    control_api=f"{domain}/api.php",
                    observed_at=now_iso(),
                    http_status=resp.status_code,
                    resp_sha256=sha256_hex(body),
                    resp_length=len(body),
                    download_link=download_link,
                    headers_json=json.dumps(dict(resp.headers)),
                    error=None,
                ))
            except Exception as exc:
                results.append(ControlSampleRecord(
                    control_domain=domain,
                    control_api=f"{domain}/api.php",
                    observed_at=now_iso(),
                    error=str(exc),
                ))
        return results

    @staticmethod
    def _extract_download_link(resp: httpx.Response) -> str | None:
        """从响应中解析 download_link 字段。"""
        try:
            data = resp.json()
            return data.get("download_link")
        except Exception:
            return None
