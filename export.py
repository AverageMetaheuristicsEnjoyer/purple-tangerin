import base64
import gzip
import hashlib
import json
from pathlib import Path
import shutil

root = Path('/home/jovyan/shares/SR006.nfs2/xandi281/moe-sae-ad')
runs = {'calibration': 'qwen-layer7-anchor-prefix-cal32-v1',
        'validation': 'qwen-layer7-anchor-test64-v1'}
print('SAE_ABC_EXPORT=STARTED', flush=True)
print('SCRATCH_FREE_BYTES=' + str(shutil.disk_usage('/tmp').free), flush=True)
for split, run in runs.items():
    for name in ('manifest.json', 'd-records.jsonl', 'features-base.jsonl',
                 'features-init.jsonl', 'features-trained.jsonl'):
        print('READING=' + split + '/' + name, flush=True)
        data = (root / run / name).read_bytes()
        encoded = base64.b64encode(gzip.compress(data, mtime=0)).decode()
        chunks = [encoded[i:i+3000] for i in range(0, len(encoded), 3000)]
        for index, chunk in enumerate(chunks):
            print('ARTIFACT_CHUNK=' + json.dumps({'split': split, 'file': name,
                'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                'index': index, 'count': len(chunks), 'gzip_base64': chunk}), flush=True)
print('SAE_ABC_EXPORT=COMPLETE', flush=True)
