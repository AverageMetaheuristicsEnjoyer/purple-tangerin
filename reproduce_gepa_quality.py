#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path

import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer, Mxfp4Config


RESULTS_REPO = "AverageMetaheuristicsEnjoyer/moe-routing-drift-results"
SERIES = "gepa/civil-v2-user-only-20260911-v2"
TEST_RESPONSES = "quality/qwen/qwen_frozen_gepa_n2000.responses.jsonl"
MODEL = "openai/gpt-oss-20b"
REVISION = "6cee5e81ee83917806bbde320786a8fb61efebee"
LABELS = ("toxicity", "obscene", "threat", "insult", "identity_attack")
FINAL_CHANNEL = "<|channel|>final<|message|>"
END_MARKERS = ("<|return|>", "<|end|>", "<|start|>")
DATE_LINE = re.compile(r"^Current date: \d{4}-\d{2}-\d{2}$", re.MULTILINE)
USER_TEMPLATE = (
    "{instructions}\n"
    "Labels (use exact names): toxicity, obscene, threat, insult, identity_attack\n"
    "Text:\n{comment}\n"
    "Return every applicable label in the order listed, separated by commas. "
    "If no label applies, return exactly NONE. Return no other text.\n"
    "Answer:"
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=32)
    return parser.parse_args()


def download(name: str) -> Path:
    return Path(hf_hub_download(RESULTS_REPO, name, repo_type="dataset"))


def load_test(n: int) -> tuple[list[str], list[list[str]], list[str]]:
    rows = [json.loads(line) for line in download(TEST_RESPONSES).read_text().splitlines()[:n]]
    comments = [
        row["prompt"].removeprefix("Text:\n").split("\n\nLabels (use exact names):", 1)[0]
        for row in rows
    ]
    return comments, [list(row["gold"]) for row in rows], [row["id"] for row in rows]


def render_user(comment: str, instructions: str) -> str:
    return USER_TEMPLATE.format(instructions=instructions.rstrip("\n"), comment=comment)


def render_chat(tokenizer, user_prompt: str) -> str:
    text = tokenizer.apply_chat_template(
        [{"role": "user", "content": user_prompt}],
        tokenize=False,
        add_generation_prompt=True,
        reasoning_effort="low",
    )
    return DATE_LINE.sub("Current date: 2026-09-07", text) + FINAL_CHANNEL


def answer_text(raw: str, clean: str) -> str:
    if "<|channel|>" not in raw:
        return clean
    if FINAL_CHANNEL not in raw:
        return ""
    tail = raw.rsplit(FINAL_CHANNEL, 1)[1]
    for marker in END_MARKERS:
        tail = tail.split(marker)[0]
    return tail


def parse_response(response: str) -> tuple[list[str], bool, bool, bool]:
    first = response.strip().split("\n", 1)[0]
    if first.lower().lstrip().startswith("answer:"):
        first = first.lstrip()[len("answer:"):]
    tokens = [token.strip().lower().strip(".") for token in first.split(",")]
    found = sorted({token for token in tokens if token in LABELS}, key=LABELS.index)
    saw_none = "none" in tokens
    return found, saw_none, saw_none and bool(found), not saw_none and not found


def f1(predicted: list[str], gold: list[str]) -> float:
    p, g = set(predicted), set(gold)
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    return 2 * len(p & g) / (len(p) + len(g))


def generate(model, tokenizer, prompts: list[str], batch_size: int) -> list[str]:
    rendered = [render_chat(tokenizer, prompt) for prompt in prompts]
    encoded = [tokenizer(text, add_special_tokens=False)["input_ids"] for text in rendered]
    groups: dict[int, list[int]] = {}
    for index, ids in enumerate(encoded):
        groups.setdefault(len(ids), []).append(index)
    print(f"PROMPT_GROUPS={len(groups)}", flush=True)
    responses: list[str | None] = [None] * len(prompts)
    done = 0
    started = time.monotonic()
    for length in sorted(groups):
        group = groups[length]
        for start in range(0, len(group), batch_size):
            indexes = group[start:start + batch_size]
            input_ids = torch.tensor([encoded[index] for index in indexes], device=model.device)
            with torch.no_grad():
                generated = model.generate(
                    input_ids=input_ids,
                    attention_mask=torch.ones_like(input_ids),
                    max_new_tokens=24,
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                )
            new_tokens = generated[:, length:]
            raw = tokenizer.batch_decode(new_tokens, skip_special_tokens=False)
            clean = tokenizer.batch_decode(new_tokens, skip_special_tokens=True)
            for index, raw_text, clean_text in zip(indexes, raw, clean):
                responses[index] = answer_text(raw_text, clean_text)
            done += len(indexes)
            if done % 100 < len(indexes) or done == len(prompts):
                print(f"GENERATED={done}/{len(prompts)} seconds={time.monotonic()-started:.1f}", flush=True)
    if any(response is None for response in responses):
        raise RuntimeError("missing responses")
    return [response for response in responses if response is not None]


def score(responses: list[str], golds: list[list[str]]) -> tuple[dict[str, object], list[dict[str, object]]]:
    rows = []
    f1s = []
    exact = empty = unparsable = mixed = 0
    literal_none = blank = nonblank_unparsable = answer_echo = saw_none_count = 0
    canonical = []
    for response, gold in zip(responses, golds):
        predicted, saw_none, is_mixed, is_unparsable = parse_response(response)
        value = f1(predicted, gold)
        first = response.strip().split("\n", 1)[0]
        normalized = first[len("answer:"):].strip() if first.lower().startswith("answer:") else first.strip()
        canonical.append(normalized if normalized else "<EMPTY>")
        f1s.append(value)
        exact += set(predicted) == set(gold)
        empty += not predicted
        unparsable += is_unparsable
        mixed += is_mixed
        literal_none += normalized.lower() == "none"
        blank += not response.strip()
        nonblank_unparsable += bool(response.strip()) and is_unparsable
        answer_echo += first.lower().startswith("answer:")
        saw_none_count += saw_none
        rows.append({
            "response": response,
            "predicted_labels": predicted,
            "true_labels": gold,
            "f1": value,
            "exact": set(predicted) == set(gold),
            "mixed_none": is_mixed,
            "unparsable": is_unparsable,
        })
    n = len(rows)
    return {
        "f1_mean": sum(f1s) / n,
        "exact_mean": exact / n,
        "empty_pred_rate": empty / n,
        "unparsable_rate": unparsable / n,
        "mixed_none_rate": mixed / n,
        "literal_none_rate": literal_none / n,
        "blank_rate": blank / n,
        "nonblank_unparsable_rate": nonblank_unparsable / n,
        "answer_prefix_echo_rate": answer_echo / n,
        "saw_none_rate": saw_none_count / n,
        "top_first_lines": Counter(canonical).most_common(15),
    }, rows


def main() -> None:
    args = arguments()
    comments, golds, ids = load_test(args.n)
    if len(comments) != args.n or sum(not gold for gold in golds) != round(0.33 * args.n):
        raise RuntimeError("test set is not the canonical 33% empty-label set")

    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        revision=REVISION,
        dtype=torch.bfloat16,
        device_map="cuda",
        quantization_config=Mxfp4Config(dequantize=True),
        attn_implementation="eager",
    )
    model.eval()
    run_root = args.out_root / args.run
    run_root.mkdir(parents=True, exist_ok=True)

    comparisons = {}
    for variant, artifact in (
        ("current_full_prompt", "optimized_prompt.txt"),
        ("correct_instructions", "optimized_instructions.txt"),
    ):
        source = download(f"{SERIES}/{args.run}/{artifact}")
        instructions = source.read_text().strip()
        prompts = [render_user(comment, instructions) for comment in comments]
        responses = generate(model, tokenizer, prompts, args.batch_size)
        metrics, rows = score(responses, golds)
        payload = {
            "run": args.run,
            "variant": variant,
            "model": MODEL,
            "revision": REVISION,
            "n": args.n,
            "gold_empty_rate": sum(not gold for gold in golds) / args.n,
            "prompt_audit": {
                "artifact": artifact,
                "artifact_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "labels_blocks": prompts[0].count("Labels (use exact names):"),
                "text_blocks": prompts[0].count("Text:\n"),
                "answer_markers": prompts[0].count("Answer:"),
                "has_literal_text_placeholder": "{text}" in prompts[0],
            },
            **metrics,
        }
        out = run_root / variant
        out.mkdir(parents=True, exist_ok=True)
        (out / "summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        with (out / "results.jsonl").open("w") as handle:
            for row_id, row in zip(ids, rows):
                handle.write(json.dumps({"id": row_id, **row}, ensure_ascii=False) + "\n")
        comparisons[variant] = payload
        print("VARIANT_RESULT=" + json.dumps(payload, ensure_ascii=False), flush=True)
    (run_root / "comparison.json").write_text(json.dumps(comparisons, indent=2, ensure_ascii=False) + "\n")
    print("GEPA_QUALITY_REPRO=PASS", flush=True)


if __name__ == "__main__":
    main()
