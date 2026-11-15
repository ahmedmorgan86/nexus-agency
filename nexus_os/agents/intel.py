"""
NEXUS OS — Business Intelligence Agent
Performs evidence-based, best-effort public website checks. Does not fabricate metrics.
"""
import urllib.request
import urllib.error
import re
from typing import Dict, Any
from nexus_os.security import is_safe_url

class BusinessIntelligenceAgent:
    def __init__(self):
        self.agent_name = "BUSINESS_INTELLIGENCE_AGENT"

    def audit_prospect(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        name = lead.get("name") or "Unknown Business"
        sector = lead.get("sector") or "General Enterprise"
        website = (lead.get("website") or "").strip()
        findings = []
        evidence = {}

        if not website or not is_safe_url(website):
            findings.append({
                "problem": "WEBSITE_NOT_PROVIDED_OR_UNSAFE",
                "description": "No safe public website URL was provided for evidence-based audit.",
                "evidence": website or None,
                "source_url": website or None,
                "severity": "HIGH",
                "business_impact": "Cannot verify digital presence or conversion funnel without a public URL.",
                "recommended_solution": "Provide a public website URL and rerun audit.",
                "confidence": "HIGH",
            })
            return {
                "agent": self.agent_name,
                "lead_id": lead.get("id"),
                "audit_summary": f"Digital Growth Audit for {name}: no auditable public website provided.",
                "findings": findings,
                "estimated_roas_boost": None,
                "tokens_used": 0,
                "qa_score": 80,
                "evidence": evidence,
            }

        try:
            req = urllib.request.Request(website, headers={"User-Agent": "NEXUS-Audit/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read(200000).decode("utf-8", errors="replace")
                final_url = resp.geturl()
                status = resp.status
        except Exception as e:
            findings.append({
                "problem": "WEBSITE_UNREACHABLE",
                "description": "Public website could not be fetched for audit.",
                "evidence": str(e),
                "source_url": website,
                "severity": "HIGH",
                "business_impact": "Prospects cannot be audited or pitched with verified findings until site is reachable.",
                "recommended_solution": "Verify the URL and retry.",
                "confidence": "HIGH",
            })
            return {
                "agent": self.agent_name,
                "lead_id": lead.get("id"),
                "audit_summary": f"Digital Growth Audit for {name}: website unreachable.",
                "findings": findings,
                "estimated_roas_boost": None,
                "tokens_used": 0,
                "qa_score": 70,
                "evidence": {"url": website, "error": str(e)},
            }

        evidence["final_url"] = final_url
        evidence["http_status"] = status
        lower = html.lower()

        # Title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        evidence["title"] = title
        if not title:
            findings.append({
                "problem": "MISSING_TITLE",
                "description": "Page has no <title> element.",
                "evidence": "No <title> found in HTML.",
                "source_url": final_url,
                "severity": "MEDIUM",
                "business_impact": "Reduced search visibility and click-through rate.",
                "recommended_solution": "Add a descriptive, keyword-relevant title tag.",
                "confidence": "HIGH",
            })

        # Meta description
        meta_desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.IGNORECASE)
        if not meta_desc:
            findings.append({
                "problem": "MISSING_META_DESCRIPTION",
                "description": "No meta description found.",
                "evidence": "No meta[name=description] content found.",
                "source_url": final_url,
                "severity": "LOW",
                "business_impact": "Lower search snippet quality.",
                "recommended_solution": "Add a concise meta description.",
                "confidence": "HIGH",
            })

        # Viewport
        if "viewport" not in lower:
            findings.append({
                "problem": "MISSING_VIEWPORT_META",
                "description": "No viewport meta tag detected.",
                "evidence": "viewport not present in HTML.",
                "source_url": final_url,
                "severity": "HIGH",
                "business_impact": "Poor mobile experience; may reduce mobile conversions.",
                "recommended_solution": "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.",
                "confidence": "HIGH",
            })

        # Forms
        form_count = len(re.findall(r"<form\b", lower))
        evidence["form_count"] = form_count
        if form_count == 0:
            findings.append({
                "problem": "NO_CONVERSION_FORM",
                "description": "No <form> element detected on the audited page.",
                "evidence": "form_count=0",
                "source_url": final_url,
                "severity": "MEDIUM",
                "business_impact": "No direct lead capture mechanism detected on this page.",
                "recommended_solution": "Add a lead capture form or direct contact CTA.",
                "confidence": "MEDIUM",
            })

        # Images missing alt
        imgs = re.findall(r"<img\b[^>]*>", lower)
        missing_alt = sum(1 for i in imgs if "alt=" not in i)
        evidence["image_count"] = len(imgs)
        evidence["images_missing_alt"] = missing_alt
        if missing_alt > 0:
            findings.append({
                "problem": "IMAGES_MISSING_ALT",
                "description": f"{missing_alt} of {len(imgs)} images are missing alt attributes.",
                "evidence": f"missing_alt={missing_alt}, total_images={len(imgs)}",
                "source_url": final_url,
                "severity": "LOW",
                "business_impact": "Accessibility and SEO limitations.",
                "recommended_solution": "Add descriptive alt text to images.",
                "confidence": "HIGH",
            })

        # WhatsApp/contact links
        has_whatsapp = "wa.me" in lower or "whatsapp" in lower
        evidence["has_whatsapp_reference"] = has_whatsapp
        if not has_whatsapp:
            findings.append({
                "problem": "NO_WHATSAPP_CONTACT_PATH",
                "description": "No WhatsApp reference detected on the audited page.",
                "evidence": "No 'wa.me' or 'whatsapp' string found.",
                "source_url": final_url,
                "severity": "MEDIUM",
                "business_impact": "May delay lead response if prospects prefer WhatsApp.",
                "recommended_solution": "Add a visible WhatsApp contact option if appropriate for the business.",
                "confidence": "MEDIUM",
            })

        audit_summary = f"Digital Growth Audit for {name}: fetched {final_url} (HTTP {status}); identified {len(findings)} evidence-based findings."

        return {
            "agent": self.agent_name,
            "lead_id": lead.get("id"),
            "audit_summary": audit_summary,
            "findings": findings,
            "estimated_roas_boost": None,
            "tokens_used": 0,
            "qa_score": 90 if findings else 95,
            "evidence": evidence,
        }
