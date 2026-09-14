#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

import torch
import transformers
from huggingface_hub import hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer, Mxfp4Config


RESULTS_REPO = "AverageMetaheuristicsEnjoyer/moe-routing-drift-results"
SERIES = "gepa/civil-v2-user-only-20260911-v2"
TEST_RESPONSES = "quality/qwen/qwen_frozen_gepa_n2000.responses.jsonl"
MODEL = "openai/gpt-oss-20b"
REVISION = "6cee5e81ee83917806bbde320786a8fb61efebee"
LABELS = ("toxicity", "obscene", "threat", "insult", "identity_attack")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", required=True, metavar="RUN")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n", type=int, default=2000)
    return parser.parse_args()


def download(name: str) -> Path:
    return Path(hf_hub_download(RESULTS_REPO, name, repo_type="dataset"))


def decode(raw: str) -> tuple[str, str]:
    final = analysis = ""
    for part in ("<|start|>assistant" + raw).split("<|start|>"):
        if part.startswith("assistant<|channel|>final<|message|>"):
            final = part.split("<|message|>", 1)[1].split("<|return|>", 1)[0]
        elif part.startswith("assistant<|channel|>analysis<|message|>"):
            analysis = part.split("<|message|>", 1)[1].split("<|end|>", 1)[0]
    return final.strip(), analysis.strip()


def parse(final: str) -> tuple[list[str], bool, bool, bool]:
    first = final.strip().split("\n", 1)[0]
    if first.lower().lstrip().startswith("answer:"):
        first = first.lstrip()[len("answer:"):]
    tokens = [token.strip().lower().strip(".") for token in first.split(",")]
    predicted = sorted({token for token in tokens if token in LABELS}, key=LABELS.index)
    saw_none = "none" in tokens
    return predicted, saw_none, saw_none and bool(predicted), not saw_none and not predicted


def f1(predicted: list[str], gold: list[str]) -> float:
    p, g = set(predicted), set(gold)
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    return 2 * len(p & g) / (len(p) + len(g))


def summarize(rows: list[dict]) -> dict:
    tokens = [row["completion_tokens"] for row in rows]
    return {
        "n": len(rows),
        "f1_mean": statistics.mean(row["f1"] for row in rows),
        "exact_mean": statistics.mean(row["exact"] for row in rows),
        "literal_none_rate": statistics.mean(row["final"] == "NONE" for row in rows),
        "empty_pred_rate": statistics.mean(not row["predicted_labels"] for row in rows),
        "unparsable_rate": statistics.mean(row["unparsable"] for row in rows),
        "mixed_none_rate": statistics.mean(row["mixed_none"] for row in rows),
        "blank_rate": statistics.mean(not row["final"] for row in rows),
        "truncated_rate": statistics.mean(not row["finished"] for row in rows),
        "reasoning_nonempty_rate": statistics.mean(bool(row["analysis"]) for row in rows),
        "completion_tokens_mean": statistics.mean(tokens),
        "completion_tokens_median": statistics.median(tokens),
        "completion_tokens_p95": sorted(tokens)[int(0.95 * len(tokens)) - 1],
        "completion_tokens_max": max(tokens),
        "top_finals": Counter(row["final"] for row in rows).most_common(15),
    }


def main() -> None:
    args = arguments()
    if transformers.__version__ != "5.16.1" or torch.__version__ != "2.8.0+cu128":
        raise RuntimeError(f"unexpected runtime: torch={torch.__version__}, transformers={transformers.__version__}")

    test_rows = [json.loads(line) for line in download(TEST_RESPONSES).read_text().splitlines()[:args.n]]
    examples = [{
        "id": row["id"],
        "text": row["prompt"].removeprefix("Text:\n").split("\n\nLabels (use exact names):", 1)[0],
        "labels": list(row["gold"]),
    } for row in test_rows]
    if len(examples) != args.n or sum(not row["labels"] for row in examples) != round(0.33 * args.n):
        raise RuntimeError("test set is not the canonical 33% empty-label set")

    cases = []
    for run in args.case:
        source = download(f"{SERIES}/{run}/optimized_instructions.txt")
        instruction = source.read_text().strip()
        cases.append((run, instruction, hashlib.sha256(source.read_bytes()).hexdigest()))

    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        revision=REVISION,
        dtype=torch.bfloat16,
        device_map="cuda",
        quantization_config=Mxfp4Config(dequantize=True),
        attn_implementation="eager",
    )
    model.eval()
    hardware = torch.cuda.get_device_name()
    experts = getattr(model.config, "_experts_implementation", None)
    if hardware != "NVIDIA H100 80GB HBM3" or experts != "grouped_mm":
        raise RuntimeError(f"unexpected backend: hardware={hardware}, experts={experts}")
    args.out.mkdir(parents=True, exist_ok=True)

    for run, instruction, instruction_sha256 in cases:
        run_dir = args.out / run
        run_dir.mkdir(parents=True, exist_ok=True)
        output = run_dir / "reasoning_low_4096.jsonl"
        existing = [json.loads(line) for line in output.read_text().splitlines()] if output.exists() else []
        completed = {row["id"] for row in existing}
        with output.open("a", buffering=1) as handle:
            for index, example in enumerate(examples, 1):
                if example["id"] in completed:
                    continue
                user = (
                    f"{instruction}\n"
                    "Labels (use exact names): toxicity, obscene, threat, insult, identity_attack\n"
                    f"Text:\n{example['text']}\n"
                    "Return every applicable label in the order listed, separated by commas. "
                    "If no label applies, return exactly NONE. Return no other text.\n"
                    "Answer:"
                )
                rendered = tokenizer.apply_chat_template(
                    [{"role": "user", "content": user}],
                    tokenize=False,
                    add_generation_prompt=True,
                    reasoning_effort="low",
                    strftime_now=lambda _format: "2026-09-07",
                )
                if user.count("Labels (use exact names):") != 1 or user.count("Text:\n") != 1 or "{text}" in user:
                    raise RuntimeError(f"prompt audit failed for {run}")
                prompt_ids = tokenizer(rendered, add_special_tokens=False)["input_ids"]
                ids = torch.tensor([prompt_ids], device=model.device)
                with torch.no_grad():
                    generated = model.generate(
                        input_ids=ids,
                        attention_mask=torch.ones_like(ids),
                        max_new_tokens=4096,
                        do_sample=False,
                        pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=tokenizer.eos_token_id,
                        use_cache=True,
                        num_beams=1,
                        repetition_penalty=1.0,
                    )[0, len(prompt_ids):]
                raw = tokenizer.decode(generated, skip_special_tokens=False)
                final, analysis = decode(raw)
                predicted, saw_none, mixed_none, unparsable = parse(final)
                record = {
                    "id": example["id"],
                    "gold": example["labels"],
                    "final": final,
                    "analysis": analysis,
                    "raw": raw,
                    "predicted_labels": predicted,
                    "f1": f1(predicted, example["labels"]),
                    "exact": set(predicted) == set(example["labels"]),
                    "saw_none": saw_none,
                    "mixed_none": mixed_none,
                    "unparsable": unparsable,
                    "completion_tokens": len(generated),
                    "finished": bool(len(generated) and generated[-1].item() == tokenizer.eos_token_id),
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                if index % 100 == 0:
                    print(f"PROGRESS run={run} {index}/{args.n}", flush=True)

        rows = [json.loads(line) for line in output.read_text().splitlines()]
        if len(rows) != args.n:
            raise RuntimeError(f"{run}: expected {args.n} rows, got {len(rows)}")
        summary = {
            "run": run,
            "mode": "reasoning_low_4096",
            "model": MODEL,
            "revision": REVISION,
            "instruction_sha256": instruction_sha256,
            "gold_empty_rate": statistics.mean(not row["labels"] for row in examples),
            "reasoning_effort": "low",
            "max_new_tokens": 4096,
            "hardware": hardware,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "experts_implementation": experts,
            **summarize(rows),
        }
        (run_dir / "reasoning_low_4096.summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
        )
        print("MODE_RESULT=" + json.dumps(summary, ensure_ascii=False), flush=True)
    print("GEPA_REASONING_TEST2000=PASS", flush=True)


if __name__ == "__main__":
    main()
