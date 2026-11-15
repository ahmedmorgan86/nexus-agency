"""
NEXUS OS — Media Provider Abstraction

Every provider returns an explicit status. Nothing is fabricated:
  OK              -> real media returned by the provider
  NOT_CONFIGURED  -> missing key/endpoint/model; caller must show NOT_CONFIGURED
  ERROR           -> provider was configured but the call failed (message included)

Providers
  ImageProvider         generic HTTP JSON endpoint  (IMAGE_PROVIDER_URL / IMAGE_PROVIDER_API_KEY)
  VideoProvider         generic HTTP JSON endpoint  (VIDEO_PROVIDER_URL / VIDEO_PROVIDER_API_KEY)
  GeminiImageProvider   Gemini image models via generateContent (GEMINI_API_KEY)
  GeminiVideoProvider   Gemini/Veo long-running prediction (GEMINI_API_KEY + GEMINI_VIDEO_MODEL)
"""
import base64
import json
import os
import pathlib
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image"


def _post_json(url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None,
               timeout: int = 120) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class _HttpProvider:
    def __init__(self, url_env: str, key_env: str):
        self.url_env = url_env
        self.key_env = key_env
        self.url = os.environ.get(url_env, "")
        self.api_key = os.environ.get(key_env, "")

    @property
    def configured(self) -> bool:
        return bool(self.url and self.api_key)

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.url:
            return {"status": "NOT_CONFIGURED", "message": f"{self.url_env} missing"}
        if not self.api_key:
            return {"status": "NOT_CONFIGURED", "message": f"{self.key_env} missing"}
        headers = {}
        auth = os.environ.get(f"{self.key_env.rsplit('_', 1)[0]}_AUTH_HEADER")
        if auth:
            headers["Authorization"] = auth
        try:
            result = _post_json(self.url, payload, headers=headers)
        except urllib.error.HTTPError as exc:
            return {"status": "ERROR", "message": f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}"}
        except Exception as exc:  # noqa: BLE001 - report, never invent a result
            return {"status": "ERROR", "message": str(exc)}
        if isinstance(result, dict):
            return {"status": "OK", **result}
        return {"status": "OK", "raw": result}


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


class GeminiImageProvider:
    """Gemini image generation through generateContent (responseModalities: IMAGE)."""

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model = os.environ.get("GEMINI_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, aspect_ratio: str = "1:1", out_dir: Optional[str] = None,
                 **_: Any) -> Dict[str, Any]:
        if not self.api_key:
            return {"status": "NOT_CONFIGURED", "provider": "gemini_image", "message": "GEMINI_API_KEY missing"}
        url = f"{GEMINI_BASE}/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect_ratio}},
        }
        try:
            res = _post_json(url, payload)
        except urllib.error.HTTPError as exc:
            return {"status": "ERROR", "provider": "gemini_image", "model": self.model,
                    "message": f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}"}
        except Exception as exc:  # noqa: BLE001
            return {"status": "ERROR", "provider": "gemini_image", "model": self.model, "message": str(exc)}

        images: List[Dict[str, Any]] = []
        saved: List[str] = []
        try:
            parts = res["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            return {"status": "ERROR", "provider": "gemini_image", "model": self.model,
                    "message": "provider returned no image parts"}
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if not inline:
                continue
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            data = inline.get("data", "")
            images.append({"mime_type": mime, "data_base64": data})
            if out_dir and data:
                ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".bin")
                path = pathlib.Path(out_dir) / f"gemini_{len(saved) + 1}{ext}"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(base64.b64decode(data))
                saved.append(str(path))
        if not images:
            return {"status": "ERROR", "provider": "gemini_image", "model": self.model,
                    "message": "provider returned no inline image data"}
        return {"status": "OK", "provider": "gemini_image", "model": self.model,
                "images": images, "saved": saved}


class GeminiVideoProvider:
    """Veo long-running prediction. Requires a video model available to the key."""

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model = os.environ.get("GEMINI_VIDEO_MODEL", "")

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def generate(self, prompt: str, **_: Any) -> Dict[str, Any]:
        if not self.api_key:
            return {"status": "NOT_CONFIGURED", "provider": "gemini_video", "message": "GEMINI_API_KEY missing"}
        if not self.model:
            return {"status": "NOT_CONFIGURED", "provider": "gemini_video",
                    "message": "GEMINI_VIDEO_MODEL missing (no Veo model is enabled for this API key)"}
        url = f"{GEMINI_BASE}/{self.model}:predictLongRunning?key={self.api_key}"
        payload = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}}
        try:
            res = _post_json(url, payload)
        except urllib.error.HTTPError as exc:
            return {"status": "ERROR", "provider": "gemini_video", "model": self.model,
                    "message": f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}"}
        except Exception as exc:  # noqa: BLE001
            return {"status": "ERROR", "provider": "gemini_video", "model": self.model, "message": str(exc)}
        return {"status": "OK", "provider": "gemini_video", "model": self.model,
                "operation": res.get("name"), "raw": res}


def provider_status() -> Dict[str, Any]:
    """Honest, side-effect-free provider inventory (no network calls, no secrets)."""
    image = ImageProvider()
    video = VideoProvider()
    gemini_image = GeminiImageProvider()
    gemini_video = GeminiVideoProvider()
    return {
        "image": {
            "configured": image.configured or gemini_image.configured,
            "generic_http": image.configured,
            "gemini": gemini_image.configured,
            "model": gemini_image.model if gemini_image.configured else None,
            "status": "CONFIGURED" if (image.configured or gemini_image.configured) else "NOT_CONFIGURED",
        },
        "video": {
            "configured": video.configured or gemini_video.configured,
            "generic_http": video.configured,
            "gemini": gemini_video.configured,
            "model": gemini_video.model or None,
            "status": "CONFIGURED" if (video.configured or gemini_video.configured) else "NOT_CONFIGURED",
        },
    }
