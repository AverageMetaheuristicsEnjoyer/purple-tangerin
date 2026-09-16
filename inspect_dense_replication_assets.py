#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, action='append', required=True)
    args = parser.parse_args()
    result = {'volumes': [], 'roots': []}
    for volume in sorted(Path('/home/jovyan/shares').glob('SR006.*')):
        usage = shutil.disk_usage(volume)
        result['volumes'].append({'path': str(volume), 'free': usage.free,
                                  'total': usage.total})
    names = {'selection.json', 'summary.json', 'adapter_config.json',
             'adapter_model.safetensors', 'hf_receipt.json', 'instruction.txt',
             'best_instruction.txt', 'best_prompt.txt', 'plan.json'}
    for root in args.root:
        entry = {'path': str(root), 'exists': root.exists(), 'files': []}
        if root.is_dir():
            for parent, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in {'hf', 'hub', 'xet', '.cache',
                                                       'task_logs', 'tensorboard'}]
                if len(Path(parent).relative_to(root).parts) >= 8:
                    dirs[:] = []
                for name in files:
                    if name not in names:
                        continue
                    p = Path(parent) / name
                    item = {'path': str(p), 'bytes': p.stat().st_size}
                    if name == 'adapter_config.json':
                        config = json.loads(p.read_text())
                        item['config'] = {k: config.get(k) for k in
                                          ['peft_type', 'num_virtual_tokens',
                                           'base_model_name_or_path', 'prefix_projection']}
                    entry['files'].append(item)
        result['roots'].append(entry)
    print('DENSE_REPLICATION_ASSETS=' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
