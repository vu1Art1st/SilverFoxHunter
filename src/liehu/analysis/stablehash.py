"""稳定区哈希 (对应文章第四节)。

完整哈希描述"这一刻拿到的文件", 秒级轮换; 去掉不稳定的末尾字节后得到的
"稳定区哈希"更接近"这批文件从哪套生产骨架里出来"。文章示例: 三轮 MSI 末两字节
依次为 006f/007f/008f, 去掉这两字节后的 SHA-256 完全一致。

注意: "去掉末两字节"只是该批样本经逐字节比较得到的稳定边界。换一批样本,
稳定边界可能落在 PE overlay、证书表之后, 也可能根本不存在。因此 trim_tail
是可配置参数。
"""

from __future__ import annotations

import hashlib


def stable_region_sha256(data: bytes, trim_tail: int = 2) -> str:
    """计算去掉末尾 trim_tail 个字节后的稳定区 SHA-256。

    Args:
        data: 完整文件字节。
        trim_tail: 需要裁掉的不稳定末尾字节数 (>=0)。
    """
    if trim_tail < 0:
        raise ValueError("trim_tail must be >= 0")
    region = data[:-trim_tail] if trim_tail else data
    return hashlib.sha256(region).hexdigest()


def is_pure_rotation(prev: dict | None, curr: dict) -> bool:
    """判断两轮载荷是否仅为"完整哈希轮换"(稳定结构保持)。

    对应 PAYLOAD_ROTATION: 完整哈希变, 但稳定区 SHA-256、内嵌 PE、imphash、
    结构骨架均未变。
    """
    if prev is None:
        return False
    if prev.get("full_sha256") == curr.get("full_sha256"):
        return False  # 完整哈希没变, 谈不上轮换
    return (
        prev.get("stable_sha256") == curr.get("stable_sha256")
        and prev.get("embedded_pe_sha256") == curr.get("embedded_pe_sha256")
        and prev.get("imphash") == curr.get("imphash")
        and prev.get("structure_id") == curr.get("structure_id")
    )


def is_structural_change(prev: dict | None, curr: dict) -> bool:
    """判断是否为"结构换代"(生产骨架变化)。

    对应 PAYLOAD_STRUCTURAL_CHANGE: MSI 流数、内嵌 PE、入口、稳定区或结构骨架
    发生改变。
    """
    if prev is None:
        return False
    return (
        prev.get("stable_sha256") != curr.get("stable_sha256")
        or prev.get("embedded_pe_sha256") != curr.get("embedded_pe_sha256")
        or prev.get("structure_id") != curr.get("structure_id")
        or prev.get("pe_entry_rva") != curr.get("pe_entry_rva")
        # OLE 流数在两次观测之间发生变化, 视为生产骨架换代 (而非同一样本内的
        # identical/total 比值, 后者是数据属性而非变化信号)。
        or prev.get("ole_stream_count") != curr.get("ole_stream_count")
    )
