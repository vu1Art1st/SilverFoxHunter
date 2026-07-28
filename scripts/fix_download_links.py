"""一次性数据订正: 归一化 links 表中带协议前缀的下载路径节点。

live 控制端采样落库的 download_link 曾以完整 URL 形式写入 links 表
(如 https://360down.net/Install_s9ri.zip), 与 mock/文章 IOC 的
"host/path" 形式不一致, 导致关联图同一宿主分裂为两个节点。
本脚本按 correlation.normalize_download 规则统一订正存量数据。
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from liehu.analysis.correlation import normalize_download

conn = sqlite3.connect("data/liehu.db")
conn.row_factory = sqlite3.Row

fixed = 0
for col in ("src", "dst"):
    type_col = f"{col}_type"
    rows = conn.execute(
        f"SELECT id, {col} AS val FROM links WHERE {type_col} = 'download' "
        f"AND ({col} LIKE 'http://%' OR {col} LIKE 'https://%')"
    ).fetchall()
    for r in rows:
        normalized = normalize_download(r["val"])
        try:
            conn.execute(f"UPDATE links SET {col} = ? WHERE id = ?", (normalized, r["id"]))
            fixed += 1
            print(f"订正 links.{col} #{r['id']}: {r['val']} -> {normalized}")
        except sqlite3.IntegrityError:
            # 归一化后与既有边重复 (UNIQUE 约束), 直接删除冗余边
            conn.execute("DELETE FROM links WHERE id = ?", (r["id"],))
            fixed += 1
            print(f"删除重复边 links #{r['id']}: {r['val']}")

conn.commit()
print(f"共订正 {fixed} 条")

print("\n== 订正后 download 节点 ==")
dl = {r["dst"] for r in conn.execute("SELECT DISTINCT dst FROM links WHERE dst_type='download'")}
dl |= {r["src"] for r in conn.execute("SELECT DISTINCT src FROM links WHERE src_type='download'")}
for d in sorted(dl):
    print(" ", d)
conn.close()
