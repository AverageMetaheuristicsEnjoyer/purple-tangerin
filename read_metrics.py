import hashlib
import json
from pathlib import Path

root = Path("/home/jovyan/shares/SR006.nfs3/xandi281/moe-revision-20260908")
runs = root / "civil-v2-user-only-peft-v25/runs"
receipts = root / "hf-receipts-v25-user-only"
names = [
    f"multilabel-v2-user-only-{model}-{method}-m100-s42"
    for model in ("gpt-oss-20b", "qwen3-2507")
    for method in ("prompt", "prefix-projected")
]
for name in names:
    run = runs / name
    quality_path = run / "quality.json"
    selection_path = run / "selection.json"
    quality = json.loads(quality_path.read_text())
    selection = json.loads(selection_path.read_text())
    summary = json.loads((run / "training/summary.json").read_text())
    receipt = json.loads((receipts / f"{name}.json").read_text())
    assert (run / "COMPLETE.json").is_file() and summary["status"] == "COMPLETE"
    assert receipt["status"] == "VERIFIED" and receipt["decrypt_and_all_internal_hashes"] == "PASS"
    assert selection["n"] == 200 and len(selection["selected"]) == 1
    best = selection["selected"][0]["best"]
    assert abs(best["score"] - quality["arms"][best["arm"]]["score"]) < 1e-12
    def metrics(arm):
        row = quality["arms"][arm]
        return {field: row[field] for field in ("n", "score", "exact_label_set", "exact_output_protocol", "macro_label_f1", "valid", "finished")}
    step0 = next(arm for arm in quality["arms"] if arm.endswith("step0"))
    print("V25_METRICS=" + json.dumps({
        "cell": name,
        "primary": quality["primary"],
        "baseline": metrics("baseline"),
        "initialization": metrics(step0),
        "best_step": best["step"],
        "best_arm": best["arm"],
        "best": metrics(best["arm"]),
        "quality_sha256": hashlib.sha256(quality_path.read_bytes()).hexdigest(),
        "selection_sha256": hashlib.sha256(selection_path.read_bytes()).hexdigest(),
        "archive_verified": True,
    }), flush=True)
