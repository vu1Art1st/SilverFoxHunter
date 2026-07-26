"""稳定区哈希单元测试 (对应文章第四节: 载荷完整哈希轮换 vs 结构换代)。"""

from __future__ import annotations

from liehu.analysis.stablehash import (
    is_pure_rotation,
    is_structural_change,
    stable_region_sha256,
)


def test_stable_region_ignores_tail_bytes():
    """文章示例: 三轮 MSI 末两字节 006f/007f/008f, 去尾两字节后稳定区哈希一致。"""
    base = b"WIX-MSI-PRODUCTION-SKELETON" * 10
    r1 = base + bytes([0x00, 0x6f])
    r2 = base + bytes([0x00, 0x7f])
    r3 = base + bytes([0x00, 0x8f])

    h1 = stable_region_sha256(r1, trim_tail=2)
    h2 = stable_region_sha256(r2, trim_tail=2)
    h3 = stable_region_sha256(r3, trim_tail=2)

    assert h1 == h2 == h3
    # 完整哈希 (不裁尾) 应各不相同
    assert len({stable_region_sha256(x, trim_tail=0) for x in (r1, r2, r3)}) == 3


def test_stable_region_trim_zero_equals_full():
    data = b"payload-bytes"
    assert stable_region_sha256(data, trim_tail=0) == stable_region_sha256(data, 0)


def test_stable_region_rejects_negative_trim():
    import pytest

    with pytest.raises(ValueError):
        stable_region_sha256(b"abc", trim_tail=-1)


def _skeleton(full: str, structure: str = "skeleton-9.1MB") -> dict:
    return {
        "full_sha256": full,
        "stable_sha256": "STABLE-A",
        "embedded_pe_sha256": "PE-A",
        "imphash": "9b760feffec4fca9c313889f9a05ee36",
        "structure_id": structure,
        "pe_entry_rva": 5790106,
        "ole_stream_count": 25,
        "ole_identical": 22,
    }


def test_pure_rotation_true_when_only_full_hash_changes():
    prev = _skeleton("HASH-006f")
    curr = _skeleton("HASH-007f")
    assert is_pure_rotation(prev, curr) is True
    assert is_structural_change(prev, curr) is False


def test_pure_rotation_false_when_hash_unchanged():
    prev = _skeleton("HASH-006f")
    curr = _skeleton("HASH-006f")
    assert is_pure_rotation(prev, curr) is False


def test_pure_rotation_false_without_prev():
    assert is_pure_rotation(None, _skeleton("HASH-006f")) is False


def test_structural_change_detected_on_skeleton_switch():
    """7·23 结构换代: 9.1MB -> 6.9MB, structure_id 改变。"""
    prev = _skeleton("HASH-A", structure="skeleton-9.1MB")
    curr = _skeleton("HASH-B", structure="skeleton-6.9MB")
    curr["stable_sha256"] = "STABLE-B"
    curr["embedded_pe_sha256"] = "PE-B"
    assert is_structural_change(prev, curr) is True
