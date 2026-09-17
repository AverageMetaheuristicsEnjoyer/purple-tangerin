import base64
import hashlib
import json
from pathlib import Path
import random
import shutil
import statistics
import zlib

root = Path('/home/jovyan/shares/SR006.nfs3/xandi281/dense-replication-qwen-20260916-v1')
arms = ['seed', 'prompt', 'prefix', 'gepa']
splits = ['sae_cal', 'steer_train', 'steer_eval', 'test', 'probe_train', 'probe_val']

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()

result = {'root': str(root), 'captures': {}, 'generation': {}, 'paired': {}, 'directories': sorted(p.name for p in root.iterdir() if p.is_dir())}
records = {}
for arm in arms:
    stage = json.loads((root / f'capture-{arm}.complete.json').read_text())
    assert stage['status'] == 'COMPLETE'
    entries = {}
    result['generation'][arm] = {}
    for split in splits:
        folder = root / 'capture' / arm
        manifest = json.loads((folder / f'{split}.complete.json').read_text())
        path = folder / manifest.get('states_file', f'{split}.states.npy')
        actual = sha(path)
        expected = manifest.get('compressed_sha256', manifest['states_sha256'])
        assert actual == expected, (arm, split, 'state hash mismatch')
        with (folder / f'{split}.records.jsonl').open() as f:
            rows = [json.loads(line) for line in f if line.strip()]
        assert len(rows) == manifest['rows']
        assert rows[0]['self_replay'] == 'exact'
        records[arm, split] = rows
        entries[split] = {'rows':len(rows), 'states_file':path.name, 'bytes':path.stat().st_size, 'verified_sha256':actual, 'data_sha256':manifest['data_sha256'], 'records_sha256':sha(folder/f'{split}.records.jsonl'), 'virtual_offsets':sorted(set(r['virtual_offset'] for r in rows))}
        if split in ['test', 'steer_eval']:
            g = [r['generation'] for r in rows]
            for r, pred in zip(rows, g):
                y, p = set(r['labels']), set(pred['prediction'])
                value = (2*len(y&p)/(len(y)+len(p)) if y or p else 1.) if pred['parse_ok'] else 0.
                assert abs(value - pred['score']) < 1e-10
            result['generation'][arm][split] = {'n':len(rows), 'samples_f1':statistics.mean(p['score'] for p in g), 'parse_ok':sum(p['parse_ok'] for p in g), 'finished':sum(p['finished'] for p in g), 'exact_set_match':sum(p['parse_ok'] and set(p['prediction']) == set(r['labels']) for r,p in zip(rows,g)), 'empty_targets':sum(not r['labels'] for r in rows)}
    result['captures'][arm] = entries
    print('REVIEW_VERIFIED', arm, flush=True)

for split in splits:
    baseline = records['seed',split]
    for arm in arms[1:]:
        current = records[arm,split]
        assert [(r['id'],r['labels']) for r in current] == [(r['id'],r['labels']) for r in baseline]
for split in ['test','steer_eval']:
    result['paired'][split] = {}
    for arm in arms[1:]:
        a,b=records['seed',split],records[arm,split]
        differences=[rb['generation']['score']-ra['generation']['score'] for ra,rb in zip(a,b)]
        rng=random.Random(42)
        means=sorted(statistics.mean(rng.choices(differences,k=len(differences))) for _ in range(3000))
        result['paired'][split][arm]={'delta_f1':statistics.mean(differences),'bootstrap_95_ci':[means[75],means[2924]],'improved':sum(d>0 for d in differences),'degraded':sum(d<0 for d in differences),'unchanged':sum(d==0 for d in differences),'prediction_agreement':sum(ra['generation']['prediction']==rb['generation']['prediction'] and ra['generation']['parse_ok']==rb['generation']['parse_ok'] for ra,rb in zip(a,b))/len(a)}

summary=json.loads((root/'lens/summary.json').read_text())
history=json.loads((root/'lens/history.json').read_text())
assert summary['status']=='COMPLETE' and len(history)==500
summary.pop('instruction_pool',None)
summary['checkpoint_bytes']=(root/'lens/translators.pt').stat().st_size
summary['checkpoint_sha256']=sha(root/'lens/translators.pt')
summary['history_steps']=len(history)
summary['first_step_mean_kl']=statistics.mean(history[0]['per_layer'])
summary['last_step_mean_kl']=statistics.mean(history[-1]['per_layer'])
summary['held_out_mean_kl']=statistics.mean(summary['held_out_kl'])
result['lens']=summary
result['disk_free_gib']={p.name:shutil.disk_usage(p).free/2**30 for p in Path('/home/jovyan/shares').glob('SR006.*')}
result['root_bytes']=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
result['status']='VERIFIED'
raw=json.dumps(result,allow_nan=False).encode()
encoded=base64.b64encode(zlib.compress(raw)).decode()
for i in range(0,len(encoded),1000):
    print('REVIEW_CHUNK',i//1000,encoded[i:i+1000],flush=True)
print('REVIEW_JSON_SHA256',hashlib.sha256(raw).hexdigest(),flush=True)
print('REVIEW_COMPLETE',flush=True)
