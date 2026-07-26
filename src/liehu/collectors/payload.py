"""载荷采集器 (包: 下载地址没动, 里面却换了一代)。

对应文章第四节: 完整哈希秒级轮换, 但 MSI/OLE 流、内嵌 PE、导入导出、imphash
以及"去尾字节"后的稳定区更持久。系统据此区分 PAYLOAD_ROTATION (仅完整哈希变)
与 PAYLOAD_STRUCTURAL_CHANGE (结构骨架变)。

Mock 模式回放 dataset.PAYLOAD_ROUNDS; Live 模式对本地样本文件做静态解析
(sha256sum / zipfile / olefile / pefile), 缺库时降级为完整哈希。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..mock import dataset
from ..analysis.stablehash import stable_region_sha256
from ..models import PayloadRecord
from .base import Provider, now_iso

try:  # 静态解析库为可选依赖, 缺失时降级
    import pefile  # type: ignore
except Exception:  # pragma: no cover
    pefile = None

try:
    import olefile  # type: ignore
except Exception:  # pragma: no cover
    olefile = None


class PayloadCollector(Provider):
    """载荷样本静态解析采集器。"""

    source = "payload"

    def analyze(self, round_index: int, file_path: str | None = None) -> PayloadRecord | None:
        """解析一轮载荷。

        round_index: mock 回放轮次; file_path: live 模式下本地样本路径。
        """
        if self.is_live and file_path:
            return self._analyze_live(file_path)
        return self._analyze_mock(round_index)

    # ---- Mock ----------------------------------------------------------------
    def _analyze_mock(self, round_index: int) -> PayloadRecord:
        rounds = dataset.PAYLOAD_ROUNDS
        idx = min(round_index, len(rounds) - 1)
        r = rounds[idx]
        return PayloadRecord(
            download_url=r["download_url"],
            observed_at=r["observed_at"],
            full_sha256=r["full_sha256"],
            msi_size=r["msi_size"],
            embedded_pe_size=r["embedded_pe_size"],
            pe_entry_rva=r["pe_entry_rva"],
            stable_sha256=r["stable_sha256"],
            embedded_pe_sha256=r["embedded_pe_sha256"],
            imphash=r["imphash"],
            ole_stream_count=r["ole_stream_count"],
            ole_identical=r["ole_identical"],
            wix_version=r["wix_version"],
            structure_id=r["structure_id"],
        )

    # ---- Live ----------------------------------------------------------------
    def _analyze_live(self, file_path: str) -> PayloadRecord | None:
        """对本地样本文件做静态解析。"""
        path = Path(file_path)
        if not path.exists():
            return None
        data = path.read_bytes()
        full_sha = hashlib.sha256(data).hexdigest()
        stable_sha = stable_region_sha256(data, trim_tail=2)

        rec = PayloadRecord(
            download_url=str(path.name),
            observed_at=now_iso(),
            full_sha256=full_sha,
            msi_size=len(data),
            stable_sha256=stable_sha,
        )

        # OLE / MSI 流枚举
        if olefile is not None and olefile.isOleFile(str(path)):
            try:
                ole = olefile.OleFileIO(str(path))
                streams = ole.listdir()
                rec.ole_stream_count = len(streams)
                ole.close()
            except Exception:
                pass

        # PE 结构解析
        if pefile is not None:
            try:
                pe = pefile.PE(data=data, fast_load=True)
                pe.parse_data_directories()
                rec.pe_entry_rva = pe.OPTIONAL_HEADER.AddressOfEntryPoint
                rec.imphash = pe.get_imphash()
                pe.close()
            except Exception:
                pass

        rec.structure_id = f"skeleton-{(rec.imphash or full_sha)[:12]}"
        return rec
