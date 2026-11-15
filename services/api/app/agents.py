"""Agent registry. Every agent declares what it can do, what it needs, and whether it has external effects.
Only agents with status IMPLEMENTED_NOT_CONFIGURED or better can be enqueued; the rest are visible but refused."""
from dataclasses import asdict, dataclass, field

RUNNABLE = {"PRODUCTION_READY", "IMPLEMENTED_NOT_CONFIGURED", "PARTIALLY_IMPLEMENTED"}


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    description: str
    capabilities: tuple = ()
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    required_integrations: tuple = ()
    permission_level: str = "read"          # read | write | external
    external_effect: bool = False           # True => every task needs human approval
    status: str = "NOT_IMPLEMENTED"


def _stub(id, name, desc, caps, integrations=(), external=False):
    return Agent(id, name, desc, tuple(caps), {"type": "object"}, {"type": "object"}, tuple(integrations),
                 "external" if external else "write", external, "NOT_IMPLEMENTED")


_AGENTS = [
    # Plumbing agents used to prove the queue, retry and approval machinery.
    Agent("system.echo", "Echo", "Returns its input. Proves queue execution.", ("echo",),
          {"type": "object"}, {"type": "object", "required": ["echo"]}, (), "read", False, "PARTIALLY_IMPLEMENTED"),
    Agent("system.flaky", "Flaky", "Fails a configured number of attempts, then succeeds. Proves retries.",
          ("retry-test",), {"type": "object", "properties": {"fail_times": {"type": "integer"}}},
          {"type": "object"}, (), "read", False, "PARTIALLY_IMPLEMENTED"),
    Agent("system.external_demo", "External action demo",
          "Simulates an external side effect (no real message is sent). Proves the approval gate.",
          ("approval-test",), {"type": "object"}, {"type": "object"}, (), "external", True, "PARTIALLY_IMPLEMENTED"),
    # Product agents from the spec: declared, not built yet.
    _stub("market_research", "Market Research Agent", "Industry and competitor research with sources", ["research"], ["LLM", "SEARCH_API"]),
    _stub("discovery", "Discovery Agent", "Finds businesses from approved sources", ["discover", "dedupe"], ["SEARCH_API"]),
    _stub("verification", "Verification Agent", "Verifies business facts and keeps evidence", ["verify"], ["SEARCH_API"]),
    _stub("website_audit", "Website Audit Agent", "Evidence-based website audits", ["audit"], ["PAGESPEED_API"]),
    _stub("competitor_intel", "Competitor Intelligence Agent", "Competitor positioning analysis", ["analyze"], ["LLM"]),
    _stub("lead_scoring", "Lead Scoring Agent", "Explainable lead scores", ["score"]),
    _stub("sales", "Sales Agent", "Outreach drafts and proposals (sending needs approval)", ["draft"], ["LLM", "EMAIL"], external=True),
    _stub("creative_director", "Creative Director Agent", "Creative briefs and storyboards", ["brief"], ["LLM"]),
    _stub("image_generation", "Image Generation Agent", "Real image generation", ["image"], ["IMAGE_PROVIDER"]),
    _stub("video_production", "Video Production Agent", "Real video generation pipeline", ["video"], ["VIDEO_PROVIDER", "VOICE_PROVIDER"]),
    _stub("content", "Content Agent", "Client-voice content drafts", ["content"], ["LLM"]),
    _stub("qa", "QA Agent", "Independent output review", ["review"], ["LLM"]),
    _stub("financial", "Financial Agent", "Cost tracking and budget enforcement", ["costs"]),
    _stub("reporting", "Reporting Agent", "Reports and executive summaries", ["report"], ["EMAIL"], external=True),
    _stub("learning", "Learning Agent", "Proposes improvements from verified outcomes", ["learn"]),
]

REGISTRY = {a.id: a for a in _AGENTS}


def get(agent_id: str) -> Agent | None:
    return REGISTRY.get(agent_id)


def public_view(a: Agent) -> dict:
    d = asdict(a)
    d["runnable"] = a.status in RUNNABLE
    return d
