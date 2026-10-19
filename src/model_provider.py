"""Model provider interface with mock mode, fault injection, and outage simulation."""
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from src.config import parse_iso

logger = logging.getLogger("ModelProvider")


class ModelProviderException(Exception):
    pass


class ModelUnavailableException(ModelProviderException):
    """Represents an HTTP 503 provider outage."""
    pass


class ModelTimeoutException(ModelProviderException):
    """Represents a model call timeout."""
    pass


class ModelProvider:
    def __init__(self, faults: Dict[str, Dict[str, Any]], timeout_seconds: float = 2.0):
        self.faults = faults
        self.timeout_seconds = timeout_seconds
        self.outage_start: Optional[datetime] = parse_iso("2026-10-01T10:35:00.000Z")
        self.outage_end: Optional[datetime] = parse_iso("2026-10-01T10:42:00.000Z")
        self.call_count = 0

    def query(self, trigger_event_id: str, prompt: str, current_time: datetime) -> Dict[str, Any]:
        """
        Execute model query with realistic failure simulation:
        - Check for simulated 503 outage window
        - Check for injected faults from model_faults.jsonl
        - Return structured evaluation
        """
        self.call_count += 1

        # 1. Check for scheduled provider outage window (HTTP 503)
        if self.outage_start and self.outage_end:
            if self.outage_start <= current_time <= self.outage_end:
                logger.warning(f"Model call rejected: model_provider unavailable (HTTP 503) at {current_time}")
                raise ModelUnavailableException("HTTP 503 Service Unavailable: model_provider is down")

        # 2. Check for injected faults for this specific trigger
        if trigger_event_id in self.faults:
            fault = self.faults[trigger_event_id]
            fault_type = fault.get("fault")

            if fault_type == "timeout":
                logger.warning(f"Injected timeout triggered for {trigger_event_id}")
                # Simulate timeout within our budget constraint
                raise ModelTimeoutException(f"Model call timed out after {self.timeout_seconds}s")

            elif fault_type == "malformed_output":
                logger.warning(f"Injected malformed output for {trigger_event_id}")
                raw_output = fault.get("model_output")
                try:
                    return json.loads(raw_output)
                except Exception as e:
                    raise ModelProviderException(f"Malformed JSON from model: {raw_output}") from e

            elif fault_type == "unsupported_claim":
                logger.warning(f"Injected unsupported claim output for {trigger_event_id}")
                return fault.get("model_output", {})

        # 3. Default realistic mock response
        return {
            "eligible": True,
            "confidence": 0.85,
            "confidence_reason": "Behavioral heuristics and subscription status indicate good fit.",
            "recommended_action": "home_page"
        }
