#!/usr/bin/env python3
import argparse
import collections
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    for run_dir in sorted(path for path in args.root.iterdir() if path.is_dir()):
        modes = {}
        for mode in ("forced_final_24", "reasoning_low_4096"):
            rows = [json.loads(line) for line in (run_dir / f"{mode}.jsonl").read_text().splitlines()]
            modes[mode] = {row["id"]: row for row in rows}
            empty_gold = [row for row in rows if not row["gold"]]
            nonempty_gold = [row for row in rows if row["gold"]]
            report = {
                "run": run_dir.name,
                "mode": mode,
                "gold_empty_pred_none": sum(row["final"] == "NONE" for row in empty_gold),
                "gold_nonempty_pred_none": sum(row["final"] == "NONE" for row in nonempty_gold),
                "gold_empty_pred_label": sum(row["final"] != "NONE" for row in empty_gold),
                "final_counts": collections.Counter(row["final"] for row in rows).most_common(12),
                "invalid_finals": [row["final"] for row in rows if row["error"]],
                "completion_tokens_max": max(row["completion_tokens"] for row in rows),
            }
            print("MODE_DETAIL=" + json.dumps(report, ensure_ascii=False))
        forced = modes["forced_final_24"]
        reasoning = modes["reasoning_low_4096"]
        paired = {
            "run": run_dir.name,
            "exact_0_to_1": sum(not forced[key]["exact"] and reasoning[key]["exact"] for key in forced),
            "exact_1_to_0": sum(forced[key]["exact"] and not reasoning[key]["exact"] for key in forced),
            "f1_improved": sum(reasoning[key]["f1"] > forced[key]["f1"] for key in forced),
            "f1_worsened": sum(reasoning[key]["f1"] < forced[key]["f1"] for key in forced),
            "same_final": sum(reasoning[key]["final"] == forced[key]["final"] for key in forced),
        }
        print("PAIR_DETAIL=" + json.dumps(paired))


if __name__ == "__main__":
    main()
