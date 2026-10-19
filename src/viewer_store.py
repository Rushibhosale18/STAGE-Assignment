"""Durable per-viewer state store with provenance tracking."""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.config import parse_iso, to_iso, get_ist_date_str
from src.fact_resolver import FactResolver
from src.models import ViewerState, Fact

logger = logging.getLogger("ViewerStore")


class ViewerStore:
    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.states: Dict[str, ViewerState] = {}

    def get_or_create(self, user_id: str, arm: str = "agent") -> ViewerState:
        """Retrieve existing state from cache/disk or initialize a new one."""
        if user_id in self.states:
            return self.states[user_id]
        
        state_file = self.storage_dir / f"{user_id}.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    state = ViewerState.from_dict(data)
                    self.states[user_id] = state
                    return state
            except Exception as e:
                logger.error(f"Failed to read state file for {user_id}: {e}")

        # Initialize fresh state
        state = ViewerState(
            user_id=user_id,
            arm=arm,
            created_at=to_iso(parse_iso("2026-09-01T00:00:00Z")),
            updated_at=to_iso(parse_iso("2026-09-01T00:00:00Z"))
        )
        self.states[user_id] = state
        return state

    def initialize_from_profile(self, user_id: str, profile_row: Dict[str, Any], arm: str = "agent") -> ViewerState:
        """Initialize state from profiles_snapshot.csv with explicit fact provenance."""
        state = self.get_or_create(user_id, arm)
        
        updated_at = profile_row.get("updated_at", "")
        snapshot_at = profile_row.get("snapshot_at", "")
        
        state.subscription_status = profile_row.get("subscription_status", "never")
        state.preferred_dialect = profile_row.get("preferred_dialect")
        state.preferred_language = profile_row.get("preferred_language")
        state.signup_at = profile_row.get("signup_at")
        state.platform = profile_row.get("platform")
        state.notifications_opt_in = profile_row.get("notifications_opt_in", "false").lower() == "true"
        state.whatsapp_opt_in = profile_row.get("whatsapp_opt_in", "false").lower() == "true"
        state.updated_at = updated_at or snapshot_at

        # Record facts with provenance
        state.facts["subscription_status"] = {
            "value": state.subscription_status,
            "source": "data/profiles_snapshot.csv",
            "received_at": snapshot_at,
            "occurred_at": updated_at
        }
        state.facts["preferred_dialect"] = {
            "value": state.preferred_dialect,
            "source": "data/profiles_snapshot.csv",
            "received_at": snapshot_at,
            "occurred_at": updated_at
        }
        state.facts["notifications_opt_in"] = {
            "value": state.notifications_opt_in,
            "source": "data/profiles_snapshot.csv",
            "received_at": snapshot_at,
            "occurred_at": updated_at
        }
        state.facts["whatsapp_opt_in"] = {
            "value": state.whatsapp_opt_in,
            "source": "data/profiles_snapshot.csv",
            "received_at": snapshot_at,
            "occurred_at": updated_at
        }
        if state.signup_at:
            state.facts["signup_at"] = {
                "value": state.signup_at,
                "source": "data/profiles_snapshot.csv",
                "received_at": snapshot_at,
                "occurred_at": state.signup_at
            }
        return state

    def update_from_event(self, event: Dict[str, Any], catalogue: Dict[str, Any]) -> None:
        """Update state from an incoming event with conflict detection and provenance."""
        user_id = event["user_id"]
        state = self.get_or_create(user_id)
        ev_name = event["event"]
        received_at = event["received_at"]
        ev_dt = parse_iso(received_at)
        ist_day = get_ist_date_str(ev_dt)

        if not state.created_at:
            state.created_at = received_at
        state.updated_at = received_at

        # 1. Update dialect
        app_dialect = event.get("app_dialect")
        if app_dialect:
            state.app_dialect = app_dialect
            state.facts["app_dialect"] = {
                "value": app_dialect,
                "source": f"event:{event.get('event_id', 'unknown')}",
                "received_at": received_at,
                "occurred_at": event.get("occurred_at")
            }

        # 2. Track activity & behavioral history
        if ev_name == "app_open":
            state.total_app_opens += 1
            state.last_app_open_at = received_at
            if ist_day not in state.distinct_active_ist_days:
                state.distinct_active_ist_days.append(ist_day)

        elif ev_name == "signup_completed":
            if not state.signup_at:
                state.signup_at = received_at
                state.facts["signup_at"] = {
                    "value": state.signup_at,
                    "source": f"event:{event.get('event_id', 'unknown')}:signup_completed",
                    "received_at": received_at
                }

        elif ev_name == "play_started":
            state.total_plays_started += 1
            state.last_play_started_at = received_at
            tid = event.get("properties", {}).get("title_id")
            if tid and tid in catalogue:
                t = catalogue[tid]
                slug = t["content_slug"]
                for g in t.get("genres", []):
                    state.genres_watched[g] = state.genres_watched.get(g, 0) + 1
                if slug not in state.series_progress:
                    state.series_progress[slug] = {
                        "last_watched_at": received_at,
                        "last_episode_id": event.get("properties", {}).get("episode_id"),
                        "completed_episodes": []
                    }
                else:
                    state.series_progress[slug]["last_watched_at"] = received_at
                    state.series_progress[slug]["last_episode_id"] = event.get("properties", {}).get("episode_id")

        elif ev_name == "episode_completed":
            state.total_episodes_completed += 1
            tid = event.get("properties", {}).get("title_id")
            epid = event.get("properties", {}).get("episode_id")
            if tid and tid in catalogue:
                slug = catalogue[tid]["content_slug"]
                if slug not in state.series_progress:
                    state.series_progress[slug] = {
                        "last_watched_at": received_at,
                        "last_episode_id": epid,
                        "completed_episodes": [epid] if epid else []
                    }
                else:
                    state.series_progress[slug]["last_watched_at"] = received_at
                    if epid and epid not in state.series_progress[slug]["completed_episodes"]:
                        state.series_progress[slug]["completed_episodes"].append(epid)

        elif ev_name == "notification_opt_out":
            channel = event.get("properties", {}).get("channel")
            if channel and channel not in state.opted_out_channels:
                state.opted_out_channels.append(channel)
                state.facts[f"{channel}_opt_in"] = {
                    "value": False,
                    "source": f"event:{event.get('event_id', 'unknown')}:notification_opt_out",
                    "received_at": received_at
                }

        elif ev_name in ("purchase_completed", "subscription_renewed", "subscription_lapsed"):
            status, src, at = FactResolver.resolve_subscription(
                state.subscription_status,
                state.updated_at,
                event
            )
            state.subscription_status = status
            state.facts["subscription_status"] = {
                "value": status,
                "source": src,
                "received_at": received_at
            }

    def record_message_sent(self, user_id: str, channel: str, action_id: str, send_at: str) -> None:
        """Record an outbound message to enforce IST daily frequency caps."""
        state = self.get_or_create(user_id)
        dt = parse_iso(send_at)
        ist_day = get_ist_date_str(dt)
        state.messages_sent.append({
            "action_id": action_id,
            "channel": channel,
            "send_at": send_at,
            "ist_day": ist_day
        })

    def save(self, user_id: str) -> None:
        """Persist state to disk as JSON."""
        if user_id not in self.states:
            return
        state_file = self.storage_dir / f"{user_id}.json"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(self.states[user_id].to_dict(), f, indent=2, ensure_ascii=False)

    def save_all(self) -> None:
        """Persist all in-memory states to disk."""
        for uid in self.states:
            self.save(uid)
