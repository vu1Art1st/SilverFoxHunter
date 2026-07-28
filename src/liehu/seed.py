"""数据库初始化与种子回放。

运行本脚本将:
    1. 初始化 SQLite 表结构;
    2. 执行一次前台发现周期, 落地文章 7·23 的 143 个前台;
    3. 依次回放控制端各轮采样, 触发 ROUTE_MERGE;
    4. 依次回放载荷各轮解析, 触发 PAYLOAD_STRUCTURAL_CHANGE / PAYLOAD_ROTATION;
    5. 采集 DNS 快照 (page-admin.site 为 NXDOMAIN)。

    6. 写入 16 篇情报手记 (intel_reports) 与全量 IOC 目录 (iocs), 幂等 UPSERT。

用法:
    uv run python -m liehu.seed
"""

from __future__ import annotations

import json
import sqlite3

from . import tracker
from .analysis import correlation, diff
from .collectors import build_collectors
from .db import db_session, init_db
from .models import EventType
from .mock import dataset, intel_dataset

# 战役 -> 控制接口 (为下载线派生事件补全 object_ref)
_CAMPAIGN_CONTROL_API = {
    "page": "page-admin.site/api.php",
    "noah": "noah-admin.site/api.php",
    "fezhx": "fezhx.com/api.php",
}


def seed() -> dict:
    """执行完整种子回放, 返回统计结果。"""
    init_db()
    collectors = build_collectors()
    summary: dict = {"frontend": None, "control_rounds": [], "payload_rounds": [], "dns": []}

    with db_session() as conn:
        # 1) 前台发现 (143 个)
        summary["frontend"] = tracker.run_frontend_cycle(collectors, conn)

        # 2) 控制端: 回放全部轮次 (7·22 分离 -> 7·23 合流)
        for _ in range(len(dataset.CONTROL_ROUNDS)):
            summary["control_rounds"].append(
                tracker.run_control_cycle(collectors, conn)
            )

        # 3) 载荷: 回放全部轮次 (9.1MB -> 6.9MB 结构换代 -> 哈希轮换)
        for _ in range(len(dataset.PAYLOAD_ROUNDS)):
            summary["payload_rounds"].append(
                tracker.run_payload_cycle(collectors, conn)
            )

        # 4) DNS 快照
        summary["dns"].append(tracker.run_dns_cycle(collectors, conn))

        # 5) 情报库: 16 篇手记 + 全量 IOC 目录 (幂等)
        summary["intel"] = seed_intel(conn)

        # 6) 把情报方法学接入核心模块: 从 iocs 派生真实事件 + 关联图边
        summary["intel_events"] = seed_intel_events(conn)

    return summary


def seed_intel(conn: sqlite3.Connection) -> dict:
    """写入 intel_reports + iocs (幂等 UPSERT), 返回入库计数。

    保留现有 143 前台复原不变: 全部文章域名进 iocs 目录, 不并入前台基线。
    """
    reports = intel_dataset.build_reports()
    for r in reports:
        conn.execute(
            """
            INSERT INTO intel_reports
                (slug, url, title, published_at, campaign_phase, summary,
                 confidence_json, source_anchors_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                url=excluded.url, title=excluded.title,
                published_at=excluded.published_at,
                campaign_phase=excluded.campaign_phase, summary=excluded.summary,
                confidence_json=excluded.confidence_json,
                source_anchors_json=excluded.source_anchors_json
            """,
            (
                r["slug"], r["url"], r["title"], r["published_at"],
                r["campaign_phase"], r["summary"],
                json.dumps(r["confidence"], ensure_ascii=False),
                json.dumps(r["source_anchors"], ensure_ascii=False),
            ),
        )

    iocs = intel_dataset.build_iocs()
    for ioc in iocs:
        conn.execute(
            """
            INSERT INTO iocs
                (ioc_type, value, priority_tier, disposition, campaign, status,
                 succeeds, first_report_date, report_slug, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ioc_type, value) DO UPDATE SET
                priority_tier=excluded.priority_tier,
                disposition=excluded.disposition, campaign=excluded.campaign,
                status=excluded.status, succeeds=excluded.succeeds,
                first_report_date=excluded.first_report_date,
                report_slug=excluded.report_slug, notes=excluded.notes
            """,
            (
                ioc["ioc_type"], ioc["value"], ioc["priority_tier"],
                ioc["disposition"], ioc["campaign"], ioc["status"],
                ioc["succeeds"], ioc["first_report_date"], ioc["report_slug"],
                ioc["notes"],
            ),
        )

    return {"reports": len(reports), "iocs": len(iocs)}


def _emit_event_once(conn: sqlite3.Connection, event: dict) -> int:
    """幂等写事件: 按 (类型, 对象, 当前态) 去重, 重复回放不重复入库。"""
    exists = conn.execute(
        "SELECT 1 FROM events WHERE event_type = ? AND object_ref = ? "
        "AND IFNULL(curr_state, '') = IFNULL(?, '') LIMIT 1",
        (event["event_type"], event["object_ref"], event.get("curr_state")),
    ).fetchone()
    if exists:
        return 0
    tracker.persist_event(conn, event)
    return 1


def seed_intel_events(conn: sqlite3.Connection) -> dict:
    """把情报库方法学接入核心模块: 从 iocs 表派生真实差异事件与关联图边。

    不同于旧实现 (新检测函数只有单测、不入管线), 本函数真正调用三个检测器
    并将结果落地到 events / links 表, 使事件流与关联图真实增长:
        - detect_control_succession -> CONTROL_TAKEOVER + 控制节点间 succeeds 边
        - detect_download_migration -> DOWNLOAD_MIGRATION + 下载节点间 migrates_to 边
        - is_dead_link_delivery     -> DEAD_LINK_DELIVERY
    幂等: 事件按 (类型, 对象, 当前态) 去重, 关联图边由 UNIQUE(src,dst,relation) 去重。
    """
    base = intel_dataset.WECHAT_BASE
    events = 0
    links: list[dict] = []

    # ---- 控制面继承 (CONTROL_TAKEOVER) ----
    ctrl = [
        dict(r) for r in conn.execute(
            "SELECT value, campaign, status, succeeds, first_report_date, report_slug "
            "FROM iocs WHERE ioc_type = 'control_api'"
        ).fetchall()
    ]
    by_domain = {c["value"].split("/", 1)[0]: c for c in ctrl}
    # 有继承关系的前任/接管方共享同一份响应体哈希 (文章"逐字节相同")
    digest_of = {c["value"].split("/", 1)[0]: f"intel-unique::{c['value']}" for c in ctrl}
    for c in ctrl:
        pred = c["succeeds"]
        if pred and pred in by_domain:
            shared = f"intel-identical::{pred}"
            digest_of[c["value"].split("/", 1)[0]] = shared
            digest_of[pred] = shared
    samples = [
        {
            "control_domain": c["value"].split("/", 1)[0],
            "control_api": c["value"],
            "status": c["status"],
            "resp_sha256": digest_of[c["value"].split("/", 1)[0]],
        }
        for c in ctrl
    ]
    for succ in correlation.detect_control_succession(samples):
        s_dom, p_dom = succ["successor"], succ["predecessor"]
        s_ioc = by_domain.get(s_dom, {})
        slug = s_ioc.get("report_slug")
        events += _emit_event_once(conn, {
            "event_type": EventType.CONTROL_TAKEOVER,
            "object_ref": s_ioc.get("value", s_dom),
            "fact": f"{s_dom} 以逐字节相同响应接管被 Hold 的 {p_dom}, 并继承其前台",
            "prev_state": p_dom, "curr_state": s_dom,
            "first_observed": s_ioc.get("first_report_date"),
            "last_observed": s_ioc.get("first_report_date"),
            "evidence_url": (base + slug) if slug else None,
        })
        links.append({
            "src": p_dom, "src_type": "control", "dst": s_dom,
            "dst_type": "control", "relation": "succeeds",
            "campaign": s_ioc.get("campaign"),
        })

    # ---- 下载端点迁移 (DOWNLOAD_MIGRATION) + 死链投递 (DEAD_LINK_DELIVERY) ----
    dls = [
        dict(r) for r in conn.execute(
            "SELECT value, campaign, status, succeeds, first_report_date, report_slug "
            "FROM iocs WHERE ioc_type = 'download_path'"
        ).fetchall()
    ]
    host_to_path = {d["value"].split("/", 1)[0]: d for d in dls}
    superseded = {d["succeeds"] for d in dls if d["succeeds"]}
    for d in dls:
        pred_host = d["succeeds"]
        if not pred_host or pred_host not in host_to_path:
            continue
        pred = host_to_path[pred_host]
        capi = _CAMPAIGN_CONTROL_API.get(d["campaign"], f"{d['campaign']}/api.php")
        slug = d.get("report_slug")
        for ev in diff.detect_download_migration(
            {"control_api": capi, "download_link": pred["value"]},
            {"control_api": capi, "download_link": d["value"]},
        ):
            ev["first_observed"] = d.get("first_report_date")
            ev["last_observed"] = d.get("first_report_date")
            ev["evidence_url"] = (base + slug) if slug else None
            events += _emit_event_once(conn, ev)
        links.append({
            "src": pred["value"], "src_type": "download", "dst": d["value"],
            "dst_type": "download", "relation": "migrates_to", "campaign": d["campaign"],
        })

    # 死链投递: 被 Hold/NXDOMAIN 且位于链尾 (未被后继取代) 的下载端点
    dns_status_map = {
        d["value"].split("/", 1)[0]: 3
        for d in dls if d["status"] in ("held", "nxdomain")
    }
    for d in dls:
        host = d["value"].split("/", 1)[0]
        if d["status"] not in ("held", "nxdomain") or host in superseded:
            continue
        capi = _CAMPAIGN_CONTROL_API.get(d["campaign"], f"{d['campaign']}/api.php")
        slug = d.get("report_slug")
        for ev in diff.is_dead_link_delivery(
            {"control_api": capi, "download_link": d["value"]}, dns_status_map
        ):
            ev["first_observed"] = d.get("first_report_date")
            ev["last_observed"] = d.get("first_report_date")
            ev["evidence_url"] = (base + slug) if slug else None
            events += _emit_event_once(conn, ev)

    tracker._persist_links(conn, links)
    return {"events": events, "links": len(links)}


def main() -> None:
    result = seed()
    fe = result["frontend"]
    ev_total = (
        fe["events"]
        + sum(r["events"] for r in result["control_rounds"])
        + sum(r["events"] for r in result["payload_rounds"])
        + sum(r["events"] for r in result["dns"])
    )
    print("=" * 56)
    print("SilverFoxHunter 银狐猎手 · 种子回放完成")
    print("=" * 56)
    print(f"前台 (壳)      : {fe['frontends']} 个")
    print(f"控制端轮次 (线): {len(result['control_rounds'])} 轮")
    print(f"载荷轮次 (包)  : {len(result['payload_rounds'])} 轮")
    print(f"差异事件总数   : {ev_total} 条")
    intel = result.get("intel") or {}
    intel_ev = result.get("intel_events") or {}
    print(f"情报手记/IOC   : {intel.get('reports', 0)} 篇 / {intel.get('iocs', 0)} 条")
    print(f"情报派生事件/图边: {intel_ev.get('events', 0)} 条 / {intel_ev.get('links', 0)} 条")
    print("=" * 56)


if __name__ == "__main__":
    main()
