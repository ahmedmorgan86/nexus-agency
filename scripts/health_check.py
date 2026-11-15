import os
import sys
import urllib.request

base = os.environ.get("NEXUS_API_BASE", "http://127.0.0.1:8000")
try:
    with urllib.request.urlopen(base + "/health", timeout=5) as resp:
        print(resp.read().decode())
except Exception as e:
    print("HEALTH_CHECK_FAILED:", e)
    sys.exit(1)
