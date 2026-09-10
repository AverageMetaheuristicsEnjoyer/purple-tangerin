from pathlib import Path


path = Path(
    "/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260910/"
    "gepa-alignment-pilot-v2/gpt-oss-20b-seed42-n200/egress_tunnel.log"
)
print(path.read_text()[-4000:] if path.is_file() else "MISSING", flush=True)
