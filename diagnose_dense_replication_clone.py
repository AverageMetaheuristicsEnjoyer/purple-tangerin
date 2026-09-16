import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import urllib.error
import urllib.request


def main():
    print('HOST=' + socket.gethostname(), flush=True)
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                         capture_output=True, text=True, timeout=30)
    print('GPU=' + gpu.stdout.strip(), flush=True)
    volumes = {str(p): shutil.disk_usage(p).free for p in [Path('/tmp'),
               *sorted(Path('/home/jovyan/shares').glob('SR006.*'))]}
    print('FREE_BYTES=' + json.dumps(volumes), flush=True)
    output = Path('/home/jovyan/shares/SR006.nfs3/xandi281/dense-replication-qwen-20260916-v1')
    print('EXISTING_OUTPUTS=' + json.dumps(sorted(p.name for p in output.iterdir())), flush=True)
    repo = 'https://github.com/AverageMetaheuristicsEnjoyer/purple-tangerin'
    for suffix in ['', '/info/refs?service=git-upload-pack']:
        try:
            with urllib.request.urlopen(repo + suffix, timeout=45) as response:
                print('HTTP=' + json.dumps({'path': suffix, 'status': response.status,
                      'content_type': response.headers.get('Content-Type'),
                      'request_id': response.headers.get('X-GitHub-Request-Id')}), flush=True)
        except urllib.error.URLError as exc:
            print('HTTP_ERROR=' + type(exc).__name__ + ':' + str(getattr(exc, 'code', 'transport')), flush=True)
    expected = {'codex/dense-replication-qwen-v1': 'e7280821cd65dbfb26772cdce32290f584c79873',
                'codex/dense-replication-qwen-v2': 'b930a3f76750bf612706b4d5979e5467e8355be1'}
    passed = gpu.returncode == 0
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_TRACE_CURL': '1',
           'GIT_TRACE_CURL_NO_DATA': '1', 'GIT_TRACE_REDACT': '1'}
    with tempfile.TemporaryDirectory(prefix='replication-git-diagnostic-') as directory:
        for i, (branch, commit) in enumerate(expected.items()):
            target = Path(directory) / str(i)
            result = subprocess.run(['git', 'clone', '--depth', '1', '--branch', branch,
                                     repo, str(target)], env=env, capture_output=True, text=True, timeout=180)
            for line in result.stderr.splitlines():
                if 'Recv header: HTTP/' in line or 'fatal:' in line:
                    print('GIT_EVENT=' + line, flush=True)
            actual = None
            if result.returncode == 0:
                actual = subprocess.check_output(['git', '-C', str(target), 'rev-parse', 'HEAD'], text=True).strip()
            ok = result.returncode == 0 and actual == commit
            passed &= ok
            print('CLONE=' + json.dumps({'branch': branch, 'exit': result.returncode,
                                        'commit': actual, 'expected': commit, 'pass': ok}), flush=True)
    storage_ok = (volumes['/tmp'] >= 90 * 1024**3 and
                  volumes['/home/jovyan/shares/SR006.nfs3'] >= 24 * 1024**3)
    print('STORAGE_READY=' + str(storage_ok), flush=True)
    print('CLONE_DIAGNOSTIC=' + ('PASS' if passed and storage_ok else 'FAIL'), flush=True)
    return 0 if passed and storage_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
