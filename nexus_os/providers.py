"""
NEXUS OS — Media Provider Abstraction
Uses configured HTTP providers when available; otherwise returns explicit NOT_CONFIGURED.
Never fabricates media files.
"""
import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any

class _HttpProvider:
    def __init__(self, url_env: str, key_env: str):
        self.url_env = url_env
        self.key_env = key_env
        self.url = os.environ.get(url_env, "")
        self.api_key = os.environ.get(key_env, "")

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.url:
            return {"status": "NOT_CONFIGURED", "message": f"{self.url_env} missing"}
        if not self.api_key:
            return {"status": "NOT_CONFIGURED", "message": f"{self.key_env} missing"}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

class ImageProvider(_HttpProvider):
    def __init__(self):
        super().__init__("IMAGE_PROVIDER_URL", "IMAGE_PROVIDER_API_KEY")
    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        return self._post({"prompt": prompt, "type": "image", **kwargs})

class VideoProvider(_HttpProvider):
    def __init__(self):
        super().__init__("VIDEO_PROVIDER_URL", "VIDEO_PROVIDER_API_KEY")
    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        return self._post({"prompt": prompt, "type": "video", **kwargs})
