import json
import shutil
from pathlib import Path
root = Path('/home/jovyan/shares/SR006.nfs3/xandi281/dense-replication-qwen-20260916-v1')
for volume in sorted(Path('/home/jovyan/shares').glob('SR006.*')):
    u = shutil.disk_usage(volume)
    print('DISK', volume.name, json.dumps({'free_gib': u.free / 2**30, 'total_gib': u.total / 2**30}), flush=True)
for p in sorted(root.rglob('*.complete.json')):
    print('COMPLETE', str(p.relative_to(root)), p.read_text(), flush=True)
for name in ['summary.json', 'history.json', 'translators.pt']:
    p = root / 'lens' / name
    if not p.exists():
        print('LENS_MISSING', name, flush=True)
        continue
    print('LENS_FILE', name, p.stat().st_size, flush=True)
    if name == 'summary.json':
        print('LENS_SUMMARY', p.read_text(), flush=True)
    elif name == 'history.json':
        h = json.loads(p.read_text())
        print('LENS_HISTORY', json.dumps({'length': len(h), 'first': h[0], 'last': h[-1]}), flush=True)
print('INSPECTION_COMPLETE', flush=True)
