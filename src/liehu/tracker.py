"""追踪定位编排器 (tracker)。

把采集层、处理分析层、状态存储层与告警层串起来, 实现文章第五节"值班流程":
手工追清一条链后, 自动化只负责按不同速度重复。提供四类周期任务:
    - run_frontend_cycle : 壳 (URLScan 发现前台 + 多时钟分类 + 连接件归因)
    - run_control_cycle  : 线 (控制端分时采样 + 路径合流/分流)
    - run_payload_cycle  : 包 (载荷结构对比 + 轮换/换代)
    - run_dns_cycle      : DNS 存活状态

所有周期均遵循"只推变化": 仅在差异出现时写入 events 表。
"""

from __future__ import annotations

import json

from .alerting import priority_for
from .analysis import correlation, dedup, diff
from .collectors import Collectors, build_collectors
from .collectors.base import now_iso, record_error
from .config import settings
from .db import db_session, init_db


# ---- 元数据 (mock 回放轮次) ---------------------------------------------------

def get_meta_int(conn, key: str, default: int = 0) -> int:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return int(row["value"]) if row else default


def set_meta_int(conn, key: str, value: int) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


# ---- 事件持久化 --------------------------------------------------------------

def persist_event(conn, event: dict) -> None:
    """写入一条差异事件 (自动分配优先级)。"""
    conn.execute(
        "INSERT INTO events (event_type, object_ref, priority, first_observed, "
        "last_observed, prev_state, curr_state, fact, evidence_url, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event["event_type"], event["object_ref"],
            event.get("priority") or priority_for(event["event_type"]),
            event.get("first_observed") or now_iso(),
            event.get("last_observed") or now_iso(),
            event.get("prev_state"), event.get("curr_state"),
            event.get("fact"), event.get("evidence_url"), now_iso(),
        ),
    )


def _persist_links(conn, links: list[dict]) -> None:
    for lk in links:
        conn.execute(
            "INSERT OR IGNORE INTO links (src, src_type, dst, dst_type, relation, campaign) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (lk["src"], lk["src_type"], lk["dst"], lk["dst_type"],
             lk["relation"], lk.get("campaign")),
        )


# ---- 壳: 前台发现周期 --------------------------------------------------------

def run_frontend_cycle(collectors: Collectors, conn) -> dict:
    """发现前台 -> 去重 -> 多时钟分类 -> 连接件归因 -> 差异事件。"""
    window = settings.cadence.frontend_window_minutes
    all_records = []
    for control_domain in settings.seed_control_domains:
        try:
            recs = collectors.urlscan.discover(control_domain, window)
            all_records.extend(recs)
        except Exception as exc:
            record_error(conn, "urlscan", control_domain, str(exc))

    # 去重 (UUID) + 归一化汇总 (page.domain)
    deduped = dedup.dedup_by_uuid(all_records)
    aggregated = dedup.aggregate_by_domain(deduped)

    event_count = 0
    frontends_for_links: list[dict] = []
    for domain, rec in aggregated.items():
        # 多时钟分类 (注册 vs 首见)
        reg_class = correlation.classify_registration(rec.registered_at, rec.first_seen)
        day_class = "reactivated" if reg_class == "reactivated" else reg_class
        # 连接件归因
        campaign = correlation.attribute_campaign(rec.control_api)

        prev = conn.execute(
            "SELECT * FROM frontends WHERE domain = ?", (domain,)
        ).fetchone()
        prev_dict = dict(prev) if prev else None

        curr = {
            "domain": domain, "first_seen": rec.first_seen,
            "last_seen": rec.last_seen, "title": rec.title,
            "page_ip": rec.page_ip, "http_status": rec.http_status,
            "control_domain": rec.control_domain, "control_api": rec.control_api,
            "analytics_id": rec.analytics_id, "theme": rec.theme,
            "registered_at": rec.registered_at, "ns": rec.ns,
            "day_class": day_class, "campaign": campaign,
            "evidence_url": rec.evidence_url, "task_uuid": rec.task_uuid,
        }
        frontends_for_links.append(curr)

        # 差异事件
        for ev in diff.diff_frontend(prev_dict, curr):
            ev["first_observed"] = rec.first_seen
            ev["last_observed"] = rec.last_seen
            persist_event(conn, ev)
            event_count += 1

        # upsert 状态卡
        conn.execute(
            "INSERT INTO frontends (domain, first_seen, last_seen, title, page_ip, "
            "http_status, control_domain, control_api, analytics_id, theme, "
            "registered_at, ns, day_class, campaign, evidence_url, task_uuid, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(domain) DO UPDATE SET last_seen=excluded.last_seen, "
            "title=excluded.title, page_ip=excluded.page_ip, "
            "http_status=excluded.http_status, control_api=excluded.control_api, "
            "day_class=excluded.day_class, campaign=excluded.campaign, "
            "updated_at=excluded.updated_at",
            (domain, rec.first_seen, rec.last_seen, rec.title, rec.page_ip,
             rec.http_status, rec.control_domain, rec.control_api, rec.analytics_id,
             rec.theme, rec.registered_at, rec.ns, day_class, campaign,
             rec.evidence_url, rec.task_uuid, now_iso()),
        )

    # 关系图边
    _persist_links(conn, correlation.build_links(frontends_for_links, [], []))
    return {"frontends": len(aggregated), "events": event_count}


# ---- 线: 控制端采样周期 ------------------------------------------------------

def run_control_cycle(collectors: Collectors, conn) -> dict:
    """控制接口分时采样 -> CONTROL_CHANGE + ROUTE_MERGE/SPLIT。"""
    round_index = get_meta_int(conn, "control_round", 0)
    samples = collectors.control.sample(
        round_index, list(settings.seed_control_domains)
    )

    event_count = 0
    for s in samples:
        if s.error:
            record_error(conn, "control", s.control_domain, s.error)

        prev = conn.execute(
            "SELECT * FROM control_samples WHERE control_api = ? "
            "ORDER BY id DESC LIMIT 1", (s.control_api,)
        ).fetchone()
        prev_dict = dict(prev) if prev else None

        curr = {
            "control_api": s.control_api, "download_link": s.download_link,
            "resp_sha256": s.resp_sha256, "error": s.error,
        }
        for ev in diff.diff_control(prev_dict, curr):
            ev["last_observed"] = s.observed_at
            persist_event(conn, ev)
            event_count += 1

        conn.execute(
            "INSERT INTO control_samples (control_domain, control_api, observed_at, "
            "http_status, resp_sha256, resp_length, download_link, headers_json, error) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (s.control_domain, s.control_api, s.observed_at, s.http_status,
             s.resp_sha256, s.resp_length, s.download_link, s.headers_json, s.error),
        )

    # 路径拓扑: 对比上一轮与本轮
    prev_round = get_meta_int(conn, "control_round_prev", -1)
    if prev_round >= 0:
        prev_samples = collectors.control.sample(prev_round, [])
        topo = correlation.detect_route_topology([
            [{"control_api": x.control_api, "download_link": x.download_link}
             for x in prev_samples],
            [{"control_api": x.control_api, "download_link": x.download_link}
             for x in samples],
        ])
        for t in topo:
            ev = {
                "event_type": t["type"],
                "object_ref": t.get("download_link") or ",".join(t.get("control_apis", [])),
                "fact": f"控制线{'合流' if t['type'] == 'ROUTE_MERGE' else '分流'}: "
                        f"{', '.join(t.get('control_apis', []))}",
                "prev_state": None,
                "curr_state": t.get("download_link"),
                "last_observed": samples[0].observed_at if samples else now_iso(),
            }
            persist_event(conn, ev)
            event_count += 1

    # 记录关系图 (控制线 -> 下载路径)
    _persist_links(conn, correlation.build_links([], [
        {"control_api": s.control_api, "download_link": s.download_link}
        for s in samples
    ], []))

    # 推进回放轮次
    set_meta_int(conn, "control_round_prev", round_index)
    if round_index < len(_control_round_count()) - 1:
        set_meta_int(conn, "control_round", round_index + 1)
    return {"samples": len(samples), "events": event_count, "round": round_index}


def _control_round_count():
    from .mock import dataset
    return dataset.CONTROL_ROUNDS


# ---- 包: 载荷分析周期 --------------------------------------------------------

def run_payload_cycle(collectors: Collectors, conn) -> dict:
    """载荷静态解析 -> PAYLOAD_ROTATION / PAYLOAD_STRUCTURAL_CHANGE。"""
    round_index = get_meta_int(conn, "payload_round", 0)
    rec = collectors.payload.analyze(round_index)
    if rec is None:
        return {"payloads": 0, "events": 0}

    prev = conn.execute(
        "SELECT * FROM payloads WHERE download_url = ? ORDER BY id DESC LIMIT 1",
        (rec.download_url,)
    ).fetchone()
    prev_dict = dict(prev) if prev else None

    curr = {
        "download_url": rec.download_url, "full_sha256": rec.full_sha256,
        "stable_sha256": rec.stable_sha256, "embedded_pe_sha256": rec.embedded_pe_sha256,
        "imphash": rec.imphash, "structure_id": rec.structure_id,
        "pe_entry_rva": rec.pe_entry_rva, "ole_identical": rec.ole_identical,
        "ole_stream_count": rec.ole_stream_count,
    }
    event_count = 0
    for ev in diff.diff_payload(prev_dict, curr):
        ev["last_observed"] = rec.observed_at
        persist_event(conn, ev)
        event_count += 1

    conn.execute(
        "INSERT INTO payloads (download_url, observed_at, full_sha256, msi_size, "
        "embedded_pe_size, pe_entry_rva, stable_sha256, embedded_pe_sha256, imphash, "
        "ole_stream_count, ole_identical, wix_version, structure_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (rec.download_url, rec.observed_at, rec.full_sha256, rec.msi_size,
         rec.embedded_pe_size, rec.pe_entry_rva, rec.stable_sha256,
         rec.embedded_pe_sha256, rec.imphash, rec.ole_stream_count,
         rec.ole_identical, rec.wix_version, rec.structure_id),
    )

    from .mock import dataset
    if round_index < len(dataset.PAYLOAD_ROUNDS) - 1:
        set_meta_int(conn, "payload_round", round_index + 1)
    return {"payloads": 1, "events": event_count, "round": round_index}


# ---- DNS: 存活状态周期 -------------------------------------------------------

def run_dns_cycle(collectors: Collectors, conn) -> dict:
    """DNS 解析快照 -> STATUS_CHANGE。"""
    targets = set(settings.seed_control_domains)
    targets.add("page-admin.site")  # 历史控制接口, 观察 NXDOMAIN
    event_count = 0
    for domain in targets:
        try:
            snap = collectors.doh.resolve(domain)
        except Exception as exc:
            record_error(conn, "doh", domain, str(exc))
            continue

        prev = conn.execute(
            "SELECT * FROM dns_snapshots WHERE domain = ? ORDER BY id DESC LIMIT 1",
            (domain,)
        ).fetchone()
        prev_dict = None
        if prev:
            prev_dict = {
                "dns_status": prev["dns_status"],
                "a_records": json.loads(prev["a_records"] or "[]"),
                "ns_records": json.loads(prev["ns_records"] or "[]"),
            }
        curr = {
            "domain": domain, "dns_status": snap.dns_status,
            "a_records": snap.a_records, "ns_records": snap.ns_records,
        }
        for ev in diff.diff_dns(prev_dict, curr):
            ev["last_observed"] = snap.observed_at
            persist_event(conn, ev)
            event_count += 1

        conn.execute(
            "INSERT INTO dns_snapshots (domain, observed_at, dns_status, a_records, "
            "aaaa_records, cname_records, ns_records) VALUES (?,?,?,?,?,?,?)",
            (domain, snap.observed_at, snap.dns_status,
             json.dumps(snap.a_records), json.dumps(snap.aaaa_records),
             json.dumps(snap.cname_records), json.dumps(snap.ns_records)),
        )
    return {"dns": len(targets), "events": event_count}


# ---- 微步在线: L1 批量打标周期 ------------------------------------------------

def run_threatbook_cycle(collectors: Collectors, conn) -> dict:
    """全量域名批量打标 (失陷检测接口, 每批 ≤100 个仅计 1 次调用)。

    查询对象: 仿冒站点全部域名 + seed C2 域名 + 下载路径宿主 (links 表
    download 节点的 host 部分)。判定落库 threatbook_verdicts, 供列表页
    风险徽章与 L2 详查弹窗使用; live 失败仅记错误账本, 不阻断追踪主流程。
    """
    domains: list[str] = [
        r["domain"] for r in conn.execute("SELECT domain FROM frontends").fetchall()
    ]
    domains.extend(settings.seed_control_domains)
    dl_rows = conn.execute(
        "SELECT DISTINCT dst AS node FROM links WHERE dst_type = 'download' "
        "UNION SELECT DISTINCT src FROM links WHERE src_type = 'download'"
    ).fetchall()
    domains.extend(r["node"].split("/")[0] for r in dl_rows)

    try:
        verdicts = collectors.threatbook.verdict_batch(domains)
    except Exception as exc:
        record_error(conn, "threatbook", None, str(exc))
        return {"domains": len(set(domains)), "verdicts": 0, "error": str(exc)}

    from .collectors.threatbook import verdict_row
    malicious = 0
    for v in verdicts:
        malicious += 1 if v.get("is_malicious") else 0
        conn.execute(
            "INSERT OR REPLACE INTO threatbook_verdicts (domain, is_malicious, "
            "confidence_level, severity, judgments_json, tags_json, permalink, "
            "queried_at) VALUES (?,?,?,?,?,?,?,?)",
            verdict_row(v),
        )
    return {"domains": len(verdicts), "verdicts": len(verdicts), "malicious": malicious}


# ---- 全流程 ------------------------------------------------------------------

def run_full_cycle(collectors: Collectors | None = None) -> dict:
    """依次运行壳/线/包/DNS 四个周期 (一次完整值班轮), 收尾微步批量打标。"""
    init_db()
    collectors = collectors or build_collectors()
    result = {}
    with db_session() as conn:
        result["frontend"] = run_frontend_cycle(collectors, conn)
        result["control"] = run_control_cycle(collectors, conn)
        result["payload"] = run_payload_cycle(collectors, conn)
        result["dns"] = run_dns_cycle(collectors, conn)
        result["threatbook"] = run_threatbook_cycle(collectors, conn)
    return result
