"""
NEXUS OS — Lead Discovery Agent
Discovers prospective businesses with a grounded search provider (Gemini + Google Search).

Honesty rules enforced here:
  * No provider configured  -> status NOT_CONFIGURED, zero leads. Nothing is invented.
  * Every lead carries the real source URLs returned by the provider's grounding metadata.
  * No score, price or confidence is fabricated: those fields stay null with an explicit basis.
"""
import json
import os
import re
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

from nexus_os.storage import get_cairo_time

DEFAULT_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest")


class LeadDiscoveryAgent:
    def __init__(self, api_key: Optional[str] = None, cse_api_key: Optional[str] = None, cse_cx: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.cse_api_key = cse_api_key or os.environ.get("GOOGLE_CSE_API_KEY", "")
        self.cse_cx = cse_cx or os.environ.get("GOOGLE_CSE_CX", "")
        self.model = os.environ.get("GEMINI_TEXT_MODEL", DEFAULT_TEXT_MODEL)
        self.agent_name = "LEAD_DISCOVERY_AGENT"

    # -- provider ---------------------------------------------------------
    def _grounded_call(self, prompt: str) -> Dict[str, Any]:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.api_key}")
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
        }
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _sources_from_grounding(res_json: Dict[str, Any]) -> List[str]:
        urls: List[str] = []
        try:
            meta = res_json["candidates"][0].get("groundingMetadata", {})
            for chunk in meta.get("groundingChunks", []):
                uri = (chunk.get("web") or {}).get("uri")
                if uri and uri not in urls:
                    urls.append(uri)
        except (KeyError, IndexError, TypeError):
            pass
        return urls

    @staticmethod
    def _extract_json_array(text: str) -> List[dict]:
        match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    # -- public API -------------------------------------------------------
    def discover_leads(self, sector_focus: Optional[str] = None, market: str = "GLOBAL") -> Dict[str, Any]:
        if not self.api_key:
            return {
                "agent": self.agent_name,
                "status": "NOT_CONFIGURED",
                "count": 0,
                "leads": [],
                "sources": [],
                "tokens_used": 0,
                "qa_score": None,
                "qa_score_basis": "NOT_COMPUTED",
                "message": "No search provider configured (GEMINI_API_KEY missing). No leads fabricated.",
            }

        prompt = f"""
        You are the NEXUS Lead Discovery Agent. Use Google Search grounding.
        Find 3 real, currently active commercial businesses that run marketing or advertising.
        Focus sector: {sector_focus or 'E-Commerce, B2B SaaS, Specialty Retail, Architecture, Direct-to-Consumer'}.
        Target market: {market}.

        Only include a business if you can point to a real public page. Never invent a business,
        phone number or website. If a field is not publicly confirmed, use an empty string.

        Return ONLY a JSON array of objects with keys:
        ["name", "sector", "website", "phone", "observations", "source_url"]
        """

        try:
            res_json = self._grounded_call(prompt)
        except urllib.error.HTTPError as exc:
            return self._error(f"provider HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}")
        except Exception as exc:  # noqa: BLE001 - surface the real failure, never fake success
            return self._error(f"provider error: {exc}")

        try:
            text = res_json["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return self._error("provider returned no candidate text (possibly blocked or empty)")
        tokens_used = int(res_json.get("usageMetadata", {}).get("totalTokenCount") or 0)
        sources = self._sources_from_grounding(res_json)

        leads: List[Dict[str, Any]] = []
        for raw in self._extract_json_array(text):
            name = str(raw.get("name") or "").strip()
            if not name:
                continue
            website = str(raw.get("website") or "").strip()
            source_url = str(raw.get("source_url") or "").strip() or website
            leads.append({
                "id": f"lead_{uuid.uuid4().hex[:10]}",
                "name": name,
                "sector": str(raw.get("sector") or "").strip() or None,
                "market": market,
                "website": website or None,
                "phone": str(raw.get("phone") or "").strip() or None,
                "phone_verified": False,
                "observations": str(raw.get("observations") or "").strip() or None,
                "source": "GEMINI_GOOGLE_SEARCH_GROUNDED",
                "source_url": source_url or None,
                "grounding_sources": sources,
                "discovery_timestamp": get_cairo_time(),
                "verification_status": "DISCOVERED",
                "confidence_score": None,
                "confidence_basis": "NOT_COMPUTED",
            })

        # Deduplicate by normalized (name, website); keep the first occurrence.
        seen = set()
        unique_leads = []
        for lead in leads:
            key = ((lead.get("name") or "").lower(), (lead.get("website") or "").lower())
            if key in seen:
                continue
            seen.add(key)
            unique_leads.append(lead)

        return {
            "agent": self.agent_name,
            "status": "SUCCESS" if unique_leads else "NO_RESULTS",
            "count": len(unique_leads),
            "leads": unique_leads,
            "sources": sources,
            "tokens_used": tokens_used,
            "qa_score": None,
            "qa_score_basis": "NOT_COMPUTED",
            "message": "" if unique_leads else "Provider returned no verifiable businesses.",
        }

    def _error(self, message: str) -> Dict[str, Any]:
        return {
            "agent": self.agent_name,
            "status": "ERROR",
            "count": 0,
            "leads": [],
            "sources": [],
            "tokens_used": 0,
            "qa_score": None,
            "qa_score_basis": "NOT_COMPUTED",
            "message": message,
        }
