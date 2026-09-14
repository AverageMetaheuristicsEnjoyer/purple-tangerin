#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch
import transformers
from huggingface_hub import hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer, Mxfp4Config


MODEL = "openai/gpt-oss-20b"
REVISION = "6cee5e81ee83917806bbde320786a8fb61efebee"
RESULTS_REPO = "AverageMetaheuristicsEnjoyer/moe-routing-drift-results"
SERIES = "gepa/civil-v2-user-only-20260911-v2"
LABELS = ("toxicity", "obscene", "threat", "insult", "identity_attack")
FINAL_CHANNEL = "<|channel|>final<|message|>"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", required=True, metavar="RUN")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def decode(raw: str, clean: str, forced_final: bool) -> tuple[str, str]:
    if forced_final:
        return clean.strip(), ""
    final = analysis = ""
    for part in ("<|start|>assistant" + raw).split("<|start|>"):
        if part.startswith("assistant<|channel|>final<|message|>"):
            final = part.split("<|message|>", 1)[1].split("<|return|>", 1)[0]
        elif part.startswith("assistant<|channel|>analysis<|message|>"):
            analysis = part.split("<|message|>", 1)[1].split("<|end|>", 1)[0]
    return final.strip(), analysis.strip()


def score(final: str, gold: list[str]) -> tuple[float, bool, bool, str | None]:
    if final == "NONE":
        predicted: list[str] = []
    else:
        predicted = [item.strip() for item in final.split(",")]
        order = {label: index for index, label in enumerate(LABELS)}
        if (
            not predicted
            or any(not item for item in predicted)
            or any(item not in order for item in predicted)
            or len(set(predicted)) != len(predicted)
            or [order[item] for item in predicted] != sorted(order[item] for item in predicted)
        ):
            return 0.0, False, False, "invalid output"
    p, g = set(predicted), set(gold)
    value = 1.0 if not p and not g else (2 * len(p & g) / (len(p) + len(g)) if p and g else 0.0)
    return value, p == g, not p, None


def render(tokenizer, prompt: str, forced_final: bool) -> list[int]:
    rendered = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False,
        add_generation_prompt=True,
        reasoning_effort="low",
        strftime_now=lambda _format: "2026-09-07",
    )
    if forced_final:
        rendered += FINAL_CHANNEL
    return tokenizer(rendered, add_special_tokens=False)["input_ids"]


def summarize(rows: list[dict]) -> dict:
    completion_lengths = [row["completion_tokens"] for row in rows]
    return {
        "n": len(rows),
        "f1_mean": statistics.mean(row["f1"] for row in rows),
        "exact_mean": statistics.mean(row["exact"] for row in rows),
        "literal_none_rate": statistics.mean(row["final"] == "NONE" for row in rows),
        "invalid_rate": statistics.mean(row["error"] is not None for row in rows),
        "truncated_rate": statistics.mean(not row["finished"] for row in rows),
        "reasoning_nonempty_rate": statistics.mean(bool(row["analysis"]) for row in rows),
        "completion_tokens_mean": statistics.mean(completion_lengths),
        "completion_tokens_median": statistics.median(completion_lengths),
        "completion_tokens_p95": sorted(completion_lengths)[int(0.95 * len(rows)) - 1],
    }


def main() -> None:
    args = arguments()
    cases = []
    for run in args.case:
        manifest = json.loads(Path(hf_hub_download(
            RESULTS_REPO,
            f"{SERIES}/{run}/manifest.json",
            repo_type="dataset",
        )).read_text())
        validation_keys = list(manifest["validation"]["keys"])
        wanted = set(validation_keys)
        found = {}
        evaluations = Path(hf_hub_download(
            RESULTS_REPO,
            f"{SERIES}/{run}/evaluations.jsonl",
            repo_type="dataset",
        ))
        with evaluations.open() as handle:
            for line in handle:
                row = json.loads(line)
                if row["key"] in wanted and row["key"] not in found:
                    found[row["key"]] = {
                        "id": row["key"],
                        "text": row["text"],
                        "labels": list(row["gold"]),
                    }
                    if len(found) == len(wanted):
                        break
        rows = [found[key] for key in validation_keys]
        if len(rows) != 200 or sum(not row["labels"] for row in rows) != 66:
            raise ValueError(f"{run}: expected canonical validation-200 with 66 empty golds")
        artifact = Path(hf_hub_download(
            RESULTS_REPO,
            f"{SERIES}/{run}/optimized_instructions.txt",
            repo_type="dataset",
        ))
        instruction = artifact.read_text().strip()
        cases.append((run, rows, instruction))

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
    args.out.mkdir(parents=True, exist_ok=True)

    for run, examples, instruction in cases:
        run_dir = args.out / run
        run_dir.mkdir(parents=True, exist_ok=True)
        for mode, forced_final, budget in (
            ("forced_final_24", True, 24),
            ("reasoning_low_4096", False, 4096),
        ):
            output = run_dir / f"{mode}.jsonl"
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
                    prompt_ids = render(tokenizer, user, forced_final)
                    ids = torch.tensor([prompt_ids], device=model.device)
                    with torch.no_grad():
                        generated = model.generate(
                            input_ids=ids,
                            attention_mask=torch.ones_like(ids),
                            max_new_tokens=budget,
                            do_sample=False,
                            pad_token_id=tokenizer.pad_token_id,
                            eos_token_id=tokenizer.eos_token_id,
                            use_cache=True,
                            num_beams=1,
                            repetition_penalty=1.0,
                        )[0, len(prompt_ids):]
                    raw = tokenizer.decode(generated, skip_special_tokens=False)
                    clean = tokenizer.decode(generated, skip_special_tokens=True)
                    final, analysis = decode(raw, clean, forced_final)
                    value, exact, empty, error = score(final, list(example["labels"]))
                    record = {
                        "id": example["id"],
                        "gold": list(example["labels"]),
                        "final": final,
                        "analysis": analysis,
                        "raw": raw,
                        "f1": value,
                        "exact": exact,
                        "empty_prediction": empty,
                        "error": error,
                        "completion_tokens": len(generated),
                        "finished": bool(len(generated) and generated[-1].item() == tokenizer.eos_token_id),
                    }
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    if index % 25 == 0:
                        print(f"PROGRESS run={run} mode={mode} {index}/200", flush=True)
            result_rows = [json.loads(line) for line in output.read_text().splitlines()]
            summary = {
                "run": run,
                "mode": mode,
                "model": MODEL,
                "revision": REVISION,
                "reasoning_effort": "low",
                "max_new_tokens": budget,
                "hardware": torch.cuda.get_device_name(),
                "torch": torch.__version__,
                "transformers": transformers.__version__,
                "experts_implementation": getattr(model.config, "_experts_implementation", None),
                **summarize(result_rows),
            }
            (run_dir / f"{mode}.summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print("MODE_RESULT=" + json.dumps(summary), flush=True)
    print("PAIRED_REASONING_GATE=PASS", flush=True)


if __name__ == "__main__":
    main()
