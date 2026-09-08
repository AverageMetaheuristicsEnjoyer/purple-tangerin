#!/usr/bin/env python3
import ctypes
import importlib
import importlib.metadata
import importlib.util
import os
import site
import subprocess
import sys
from pathlib import Path

import torch


print(
    "RUNTIME_IDENTITY"
    f" python={sys.version.split()[0]}"
    f" executable={sys.executable}"
    f" torch={torch.__version__}"
    f" torch_cuda={torch.version.cuda}"
    f" cuda_available={torch.cuda.is_available()}"
    f" device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'}"
    f" ld_library_path={os.environ.get('LD_LIBRARY_PATH', '')}",
    flush=True,
)

roots = [Path(sys.prefix), Path(site.getusersitepackages()), *map(Path, site.getsitepackages())]
found = set()
for root in roots:
    for pattern in (
        "nvidia/cuda_runtime/lib/libcudart.so*",
        "torch/lib/libcudart.so*",
        "lib/libcudart.so*",
    ):
        found.update(root.glob(pattern))
search = subprocess.run(
    ["find", "/usr/local", "/opt", "-name", "libcudart.so*", "-type", "f"],
    text=True,
    capture_output=True,
    check=False,
)
found.update(Path(line) for line in search.stdout.splitlines())
candidates = sorted(str(path.resolve()) for path in found)
print(f"CUDART_CANDIDATES={candidates}", flush=True)
print(f"TE_SPEC={importlib.util.find_spec('transformer_engine')}", flush=True)
print(
    "PACKAGE_SPECS"
    f" nvidia={importlib.util.find_spec('nvidia')}"
    f" cuda_runtime={importlib.util.find_spec('nvidia.cuda_runtime')}"
    f" te_version={importlib.metadata.version('transformer_engine')}",
    flush=True,
)
te_spec = importlib.util.find_spec("transformer_engine")
te_common_path = Path(te_spec.origin).parent / "common" / "__init__.py"
for line_number, line in enumerate(te_common_path.read_text().splitlines(), start=1):
    if 270 <= line_number <= 310:
        print(f"TE_SOURCE_{line_number}={line}", flush=True)

try:
    import transformer_engine

    print(f"TE_DIRECT_RESULT=PASS version={transformer_engine.__version__}", flush=True)
except Exception as error:
    print(f"TE_DIRECT_RESULT=FAIL error={error!r}", flush=True)
    for candidate in candidates:
        try:
            ctypes.CDLL(candidate, mode=ctypes.RTLD_GLOBAL)
            print(f"CUDART_PRELOAD_RESULT=PASS path={candidate}", flush=True)
            break
        except OSError as preload_error:
            print(
                f"CUDART_PRELOAD_RESULT=FAIL path={candidate} error={preload_error!r}",
                flush=True,
            )
    for name in tuple(sys.modules):
        if name == "transformer_engine" or name.startswith("transformer_engine."):
            del sys.modules[name]
    importlib.invalidate_caches()
    try:
        import transformer_engine

        print(f"TE_PRELOAD_RESULT=PASS version={transformer_engine.__version__}", flush=True)
    except Exception as retry_error:
        print(f"TE_PRELOAD_RESULT=FAIL error={retry_error!r}", flush=True)

if "TE_LIBPATH_REEXEC" not in os.environ:
    nvidia_root = Path(site.getsitepackages()[0]) / "nvidia"
    lib_dirs = sorted(str(path) for path in nvidia_root.glob("*/lib") if path.is_dir())
    child_env = os.environ.copy()
    child_env["TE_LIBPATH_REEXEC"] = "1"
    child_env["LD_LIBRARY_PATH"] = ":".join(
        [*lib_dirs, child_env.get("LD_LIBRARY_PATH", "")]
    ).rstrip(":")
    print(f"TE_REEXEC_LIB_DIRS={lib_dirs}", flush=True)
    completed = subprocess.run([sys.executable, __file__], env=child_env, check=False)
    print(f"TE_REEXEC_RETURN_CODE={completed.returncode}", flush=True)
