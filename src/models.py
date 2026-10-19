"""Data models and serialization structures for STAGE: One User, One Agent."""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import json


@dataclass
class Fact:
    """A durable fact with source provenance and timestamp."""
    name: str
    value: Any
    source: str
    received_at: str
    occurred_at: Optional[str] = None
    confidence: float = 1.0


@dataclass
class ViewerState:
    """Durable state owned by one viewer's dedicated agent."""
    user_id: str
    arm: str = "agent"  # "agent" or "holdout"
    created_at: str = ""
    updated_at: str = ""
    
    # Resolved viewer facts
    subscription_status: str = "never"  # never, trial_active, active, lapsed
    preferred_dialect: Optional[str] = None
    app_dialect: Optional[str] = None
    preferred_language: Optional[str] = None
    signup_at: Optional[str] = None
    notifications_opt_in: bool = False
    whatsapp_opt_in: bool = False
    opted_out_channels: List[str] = field(default_factory=list)
    platform: Optional[str] = None
    
    # Provenance tracking
    facts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    conflicts_detected: List[Dict[str, Any]] = field(default_factory=list)
    
    # Active plan & goal
    active_goal: Optional[Dict[str, Any]] = None
    goal_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Behavioral and engagement history
    total_app_opens: int = 0
    distinct_active_ist_days: List[str] = field(default_factory=list)
    total_plays_started: int = 0
    total_episodes_completed: int = 0
    last_app_open_at: Optional[str] = None
    last_play_started_at: Optional[str] = None
    
    # Series progress: content_slug -> {"last_episode_id": ..., "completed_episodes": [...], "last_watched_at": ...}
    series_progress: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    genres_watched: Dict[str, int] = field(default_factory=dict)
    
    # Messaging history: list of messages sent with IST dates to enforce frequency caps
    messages_sent: List[Dict[str, Any]] = field(default_factory=list)
    decisions_count: int = 0
    learnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ViewerState":
        return cls(**data)


@dataclass
class Decision:
    """The required machine-readable decision output format."""
    decision_id: str
    viewer_id: str
    trigger: Dict[str, Any]
    goal: Optional[Dict[str, Any]]
    action: str
    dialect: Dict[str, Any]
    content: List[str]
    confidence: float
    confidence_reason: str
    evidence: List[str]
    assumptions: List[str]
    checks: Dict[str, List[str]]
    decided_in_ms: int
    status: str
    no_action_reason: Optional[str] = None
    fallback_used: bool = False
    model_calls: int = 0
    tool_calls: int = 0
    rule_version: str = "2026-09-30"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class PublishedAction:
    """Intervention action published to simulator."""
    action_id: str
    decision_id: str
    user_id: str
    trigger_event_id: str
    type: str  # home_page, push, whatsapp, in_app_message
    published_at: str
    
    # Home Page fields
    dialect: Optional[str] = None
    hero_title_id: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    
    # Push & WhatsApp fields
    send_at: Optional[str] = None
    title_id: Optional[str] = None
    text: Optional[Dict[str, str]] = None
    deeplink: Optional[str] = None
    template_id: Optional[str] = None
    variables: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {k: v for k, v in asdict(self).items() if v is not None}
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class OutcomeJudgment:
    """Evaluation of goal completion after window expiry."""
    judgment_id: str
    decision_id: str
    user_id: str
    goal_id: str
    goal_name: str
    goal_started_at: str
    deadline: str
    status: str  # SUCCEEDED, FAILED, INCONCLUSIVE
    success_event_id: Optional[str] = None
    success_event_type: Optional[str] = None
    evaluated_at: str = ""
    rule_version: str = "2026-09-30"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
