from pathlib import Path


root = Path(
    "/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260910/"
    "gepa-alignment-pilot-v6/gpt-oss-20b-seed42-n200"
)
for name in ["cloud_result.json", "gepa_stdout.log", "task_server.log", "tests.log"]:
    path = root / name
    print(f"===== {name} =====", flush=True)
    print(path.read_text()[-12000:] if path.is_file() else "MISSING", flush=True)
queue = root / "reflection_queue"
print("===== reflection_queue =====", flush=True)
for path in sorted(queue.glob("*")):
    print(path.name, path.stat().st_size, flush=True)
