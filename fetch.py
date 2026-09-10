import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-spec", choices=["qwen3-2507", "gpt-oss-20b"], required=True)
    args = parser.parse_args()
    run = (Path("/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260910") /
           "prompt-placement-gate-v1" / args.model_spec)
    if not (run / "COMPLETE").is_file():
        raise RuntimeError(f"Gate is not complete: {run}")
    result = json.loads((run / "result.json").read_text())
    summary = result["gate_summary"]
    compact = {
        "status": result["status"],
        "model_spec": args.model_spec,
        "device": result["device"],
        "torch": result["torch"],
        "behavior": summary["behavior"],
        "paired": summary["paired"],
        "routing_overall": summary["routing"]["overall_layer_mean"],
        "counts": summary["counts"],
        "structural_placement_alignment": summary["structural_placement_alignment"],
    }
    print("GATE_COMPACT=" + json.dumps(compact, separators=(",", ":")), flush=True)

    files = [run / "result.json", run / "gate/manifest.json", run / "gate/summary.json",
             run / "gate/routing.jsonl", run / "weight_hashes.json"]
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path in files:
            archive.add(path, arcname=str(path.relative_to(run)))
    payload = base64.b64encode(buffer.getvalue()).decode()
    chunk_size = 2000
    chunks = [payload[start:start + chunk_size] for start in range(0, len(payload), chunk_size)]
    for index, chunk in enumerate(chunks):
        print(f"GATE_BUNDLE_CHUNK={index}/{len(chunks)}:{chunk}", flush=True)
    print("GATE_BUNDLE_SHA256=" + hashlib.sha256(buffer.getvalue()).hexdigest(), flush=True)


if __name__ == "__main__":
    main()
