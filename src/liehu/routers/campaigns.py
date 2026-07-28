"""战役关联图路由 (壳/线/包 连接件关系)。

从 links 表构建 ECharts 关系图友好的 nodes + links 结构, 并提供手动触发一次
追踪周期的接口。
"""

from __future__ import annotations

from fastapi import APIRouter

from ..db import get_connection

router = APIRouter(tags=["campaigns"])

# 节点类型 -> ECharts category 序号 (壳/线/包 分组)
_CATEGORY = {
    "frontend": 0,   # 壳
    "control": 1,    # 线-控制接口
    "analytics": 2,  # 线-分析ID
    "download": 3,   # 线-下载路径
    "payload": 4,    # 包
}
_CATEGORY_NAMES = ["仿冒站点", "C2 控制接口", "统计 ID", "下载路径", "恶意载荷骨架"]


@router.get("/campaigns/graph")
def campaign_graph(campaign: str | None = None) -> dict:
    """返回壳->线->包关系图 (可按战役过滤)。"""
    where, params = "", []
    if campaign:
        where = "WHERE campaign = ?"
        params.append(campaign)

    conn = get_connection()
    try:
        edges = conn.execute(
            f"SELECT src, src_type, dst, dst_type, relation, campaign FROM links {where}",
            params,
        ).fetchall()
    finally:
        conn.close()

    nodes: dict[str, dict] = {}

    def add_node(name: str, ntype: str, campaign_tag: str | None):
        if name not in nodes:
            nodes[name] = {
                "id": name,
                "name": name,
                "category": _CATEGORY.get(ntype, 0),
                "node_type": ntype,
                "campaign": campaign_tag,
            }

    links_out = []
    for e in edges:
        add_node(e["src"], e["src_type"], e["campaign"])
        add_node(e["dst"], e["dst_type"], e["campaign"])
        links_out.append({
            "source": e["src"], "target": e["dst"],
            "relation": e["relation"], "campaign": e["campaign"],
        })

    return {
        "categories": [{"name": n} for n in _CATEGORY_NAMES],
        "nodes": list(nodes.values()),
        "links": links_out,
    }


@router.post("/campaigns/trigger")
def trigger_cycle() -> dict:
    """手动触发一次完整追踪周期 (壳/线/包/DNS)。"""
    from ..tracker import run_full_cycle

    result = run_full_cycle()
    return {"status": "ok", "result": result}
