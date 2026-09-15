#!/usr/bin/env python3
import json
from pathlib import Path


root = Path(
    "/home/jovyan/shares/SR006.nfs3/xandi281/moe-revision-20260915/"
    "gepa-reasoning-test2000-v1"
)
summaries = []
for path in sorted(root.glob("*/reasoning_low_4096.summary.json")):
    summary = json.loads(path.read_text())
    summary.pop("top_finals", None)
    summaries.append(summary)
print("REASONING_TABLE=" + json.dumps(summaries, ensure_ascii=False))
