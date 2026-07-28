"""数据采集模块 (壳/线/包 + 多时钟)。

根据混合模式配置装配各采集器 Provider (Mock / Live)。对外暴露工厂函数
``build_collectors`` 返回一组已配置好的采集器。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from .certspotter import CertSpotterCollector
from .control import ControlCollector
from .doh import DohCollector
from .payload import PayloadCollector
from .rdap import RdapCollector
from .threatbook import ThreatBookCollector
from .urlscan import UrlScanCollector

__all__ = [
    "UrlScanCollector",
    "CertSpotterCollector",
    "RdapCollector",
    "DohCollector",
    "ControlCollector",
    "PayloadCollector",
    "ThreatBookCollector",
    "Collectors",
    "build_collectors",
]


@dataclass
class Collectors:
    """一组已装配的采集器。"""

    urlscan: UrlScanCollector
    certspotter: CertSpotterCollector
    rdap: RdapCollector
    doh: DohCollector
    control: ControlCollector
    payload: PayloadCollector
    threatbook: ThreatBookCollector


def build_collectors() -> Collectors:
    """按 settings 中的混合模式配置装配采集器。"""
    return Collectors(
        urlscan=UrlScanCollector(settings.urlscan.mode, settings.urlscan.api_key),
        certspotter=CertSpotterCollector(
            settings.certspotter.mode, settings.certspotter.api_key
        ),
        rdap=RdapCollector(settings.rdap.mode, settings.rdap.api_key),
        doh=DohCollector(settings.doh.mode, settings.doh.api_key),
        control=ControlCollector(settings.control.mode, settings.control.api_key),
        payload=PayloadCollector(settings.payload.mode, settings.payload.api_key),
        threatbook=ThreatBookCollector(
            settings.threatbook.mode, settings.threatbook.api_key
        ),
    )
