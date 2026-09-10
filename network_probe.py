import json
import socket


targets = [
    ("proxy2.cod.phystech.edu", 10210),
    ("10.55.228.95", 22),
    ("10.55.228.95", 10210),
]
results = []
for host, port in targets:
    addresses = []
    try:
        addresses = sorted({row[4][0] for row in socket.getaddrinfo(host, port)})
        with socket.create_connection((host, port), timeout=10) as stream:
            stream.settimeout(10)
            banner = stream.recv(200).decode(errors="replace").strip()
            status = "open"
    except Exception as error:
        status = f"{type(error).__name__}: {error}"
        banner = None
    results.append({
        "host": host, "port": port, "addresses": addresses, "status": status, "banner": banner,
    })
print(json.dumps(results, indent=2), flush=True)
