"""Intervention planner for personalized home pages, notifications, and safe abstention."""
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, List, Optional, Tuple, Set

from src.config import (
    HOME_PAGE_TTL_MINUTES,
    MAX_HOME_PAGE_ROWS,
    MIN_TITLES_PER_ROW,
    MAX_TITLES_PER_ROW,
    ALLOWED_ROW_TYPES,
    is_quiet_hours,
    get_ist_date_str,
    parse_iso,
    to_iso,
    IST,
    PUSH_MAX_TITLE_CHARS,
    PUSH_MAX_BODY_CHARS,
    FORBIDDEN_PUSH_PHRASES,
    APPROVED_WA_TEMPLATES,
    DIALECT_DISPLAY_NAMES
)
from src.data_loader import DataLoader
from src.models import ViewerState, PublishedAction

logger = logging.getLogger("InterventionPlanner")


class InterventionPlanner:
    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader

    def build_home_page(
        self,
        user_id: str,
        dialect: str,
        publish_dt: datetime,
        state: ViewerState,
        goal: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Construct a valid personalized home page according to platform constraints:
        - 1 Hero title in page dialect & available
        - Max 6 rows, each with 3-10 titles in page dialect & available
        - Content slug unique across the entire page
        - Row with < 3 titles is dropped
        """
        used_slugs: Set[str] = set()
        
        # 1. Candidate titles in dialect that are available right now
        available_titles = []
        for tid in self.loader.titles_by_dialect.get(dialect, []):
            if self.loader.is_title_available(tid, publish_dt):
                available_titles.append(self.loader.catalogue[tid])

        if not available_titles:
            return None

        # 2. Hero selection: pick top new release or prominent title in dialect
        hero_title_id = None
        # Sort by release date descending
        sorted_by_date = sorted(available_titles, key=lambda t: t.get("release_date", ""), reverse=True)
        for t in sorted_by_date:
            if t["content_slug"] not in used_slugs:
                hero_title_id = t["title_id"]
                used_slugs.add(t["content_slug"])
                break

        rows: List[Dict[str, Any]] = []

        # 3. Row 1: "next_episode" (if user has unfinished series progress)
        for slug, prog in state.series_progress.items():
            if len(rows) >= MAX_HOME_PAGE_ROWS:
                break
            # Check if this slug has available variants in this dialect
            next_ep = self.loader.get_next_episode(slug, prog.get("last_episode_id"))
            if next_ep:
                # Find available titles for this slug in current dialect
                slug_tids = [
                    t["title_id"] for t in self.loader.catalogue_by_slug.get(slug, [])
                    if t["dialect"] == dialect and self.loader.is_title_available(t["title_id"], publish_dt)
                ]
                # Also include other show titles in dialect to reach >= 3 titles
                other_shows = [
                    t["title_id"] for t in available_titles
                    if t["content_type"] in ("show", "micro_drama") and t["content_slug"] not in used_slugs
                ]
                row_candidates = slug_tids + other_shows
                clean_row = []
                for tid in row_candidates:
                    s = self.loader.catalogue[tid]["content_slug"]
                    if s not in used_slugs:
                        clean_row.append(tid)
                        used_slugs.add(s)
                    if len(clean_row) >= MAX_TITLES_PER_ROW:
                        break
                
                if len(clean_row) >= MIN_TITLES_PER_ROW:
                    rows.append({
                        "row_type": "next_episode",
                        "title_ids": clean_row
                    })

        # 4. Row 2: "because_you_watched" (based on top genre)
        if state.genres_watched and len(rows) < MAX_HOME_PAGE_ROWS:
            top_genre = max(state.genres_watched, key=state.genres_watched.get)
            genre_candidates = [
                t["title_id"] for t in available_titles
                if top_genre in t.get("genres", []) and t["content_slug"] not in used_slugs
            ]
            clean_genre_row = []
            for tid in genre_candidates:
                s = self.loader.catalogue[tid]["content_slug"]
                if s not in used_slugs:
                    clean_genre_row.append(tid)
                    used_slugs.add(s)
                if len(clean_genre_row) >= MAX_TITLES_PER_ROW:
                    break
            
            if len(clean_genre_row) >= MIN_TITLES_PER_ROW:
                rows.append({
                    "row_type": "because_you_watched",
                    "title_ids": clean_genre_row
                })

        # 5. Row 3: "new_releases"
        if len(rows) < MAX_HOME_PAGE_ROWS:
            new_release_candidates = [
                t["title_id"] for t in sorted_by_date
                if t["content_slug"] not in used_slugs
            ]
            clean_new_row = []
            for tid in new_release_candidates:
                s = self.loader.catalogue[tid]["content_slug"]
                if s not in used_slugs:
                    clean_new_row.append(tid)
                    used_slugs.add(s)
                if len(clean_new_row) >= MAX_TITLES_PER_ROW:
                    break
            
            if len(clean_new_row) >= MIN_TITLES_PER_ROW:
                rows.append({
                    "row_type": "new_releases",
                    "title_ids": clean_new_row
                })

        # 6. Row 4 & 5: "popular_in_dialect" & "genre"
        if len(rows) < MAX_HOME_PAGE_ROWS:
            remaining_candidates = [
                t["title_id"] for t in available_titles
                if t["content_slug"] not in used_slugs
            ]
            clean_pop_row = []
            for tid in remaining_candidates:
                s = self.loader.catalogue[tid]["content_slug"]
                if s not in used_slugs:
                    clean_pop_row.append(tid)
                    used_slugs.add(s)
                if len(clean_pop_row) >= MAX_TITLES_PER_ROW:
                    break
            
            if len(clean_pop_row) >= MIN_TITLES_PER_ROW:
                rows.append({
                    "row_type": "popular_in_dialect",
                    "title_ids": clean_pop_row
                })

        # If after filtering we have no valid rows and no hero, abort
        if not rows and not hero_title_id:
            return None

        return {
            "type": "home_page",
            "dialect": dialect,
            "hero_title_id": hero_title_id,
            "rows": rows
        }

    def build_push_message(
        self,
        user_id: str,
        dialect: str,
        at: datetime,
        state: ViewerState,
        goal: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Construct compliant push notification if user opted in and within frequency limits."""
        # 1. Check consent
        if not state.notifications_opt_in or "push" in state.opted_out_channels:
            return None

        # 2. Check quiet hours and scheduling
        send_at = at
        if is_quiet_hours(at):
            # Schedule for 08:15 IST the next morning
            ist_dt = at.astimezone(IST)
            if ist_dt.hour >= 22:
                # Same night, send tomorrow morning at 08:15 IST
                next_day = ist_dt.date() + timedelta(days=1)
                scheduled_ist = datetime(next_day.year, next_day.month, next_day.day, 8, 15, tzinfo=IST)
            else:
                # Early morning before 08:00, send at 08:15 IST today
                scheduled_ist = datetime(ist_dt.year, ist_dt.month, ist_dt.day, 8, 15, tzinfo=IST)
            send_at = scheduled_ist.astimezone(datetime.timezone.utc)

        # 3. Check frequency cap for scheduled date
        target_ist_day = get_ist_date_str(send_at)
        messages_on_day = [
            m for m in state.messages_sent
            if m.get("ist_day") == target_ist_day and m.get("channel") in ("push", "whatsapp")
        ]
        if len(messages_on_day) >= 1:
            return None

        # 4. Find available title in dialect
        candidate_tids = [
            tid for tid in self.loader.titles_by_dialect.get(dialect, [])
            if self.loader.is_title_available(tid, send_at)
        ]
        if not candidate_tids:
            return None

        chosen_tid = candidate_tids[0]
        title_obj = self.loader.catalogue[chosen_tid]
        title_name = title_obj["title"]
        dialect_name = DIALECT_DISPLAY_NAMES.get(dialect, dialect)

        # Create compliant copy without forbidden words
        body = f"Naye episodes dekhiye {title_name} ke {dialect_name} mein."
        if len(body) > PUSH_MAX_BODY_CHARS:
            body = body[:PUSH_MAX_BODY_CHARS]

        title_copy = f"Dekhiye {title_name}"
        if len(title_copy) > PUSH_MAX_TITLE_CHARS:
            title_copy = title_copy[:PUSH_MAX_TITLE_CHARS]

        return {
            "type": "push",
            "send_at": to_iso(send_at),
            "title_id": chosen_tid,
            "text": {
                "title": title_copy,
                "body": body
            },
            "deeplink": f"ott://title/{chosen_tid}"
        }

    def build_whatsapp_message(
        self,
        user_id: str,
        dialect: str,
        at: datetime,
        state: ViewerState,
        goal: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Construct compliant WhatsApp message strictly using approved templates."""
        # 1. Check consent
        if not state.whatsapp_opt_in or "whatsapp" in state.opted_out_channels:
            return None

        # 2. Check quiet hours and scheduling
        send_at = at
        if is_quiet_hours(at):
            ist_dt = at.astimezone(IST)
            if ist_dt.hour >= 22:
                next_day = ist_dt.date() + timedelta(days=1)
                scheduled_ist = datetime(next_day.year, next_day.month, next_day.day, 8, 15, tzinfo=IST)
            else:
                scheduled_ist = datetime(ist_dt.year, ist_dt.month, ist_dt.day, 8, 15, tzinfo=IST)
            send_at = scheduled_ist.astimezone(datetime.timezone.utc)

        # 3. Check frequency cap
        target_ist_day = get_ist_date_str(send_at)
        messages_on_day = [
            m for m in state.messages_sent
            if m.get("ist_day") == target_ist_day and m.get("channel") in ("push", "whatsapp")
        ]
        if len(messages_on_day) >= 1:
            return None

        # 4. Choose template based on lifecycle
        candidate_tids = [
            tid for tid in self.loader.titles_by_dialect.get(dialect, [])
            if self.loader.is_title_available(tid, send_at)
        ]
        if not candidate_tids:
            return None

        chosen_tid = candidate_tids[0]
        title_obj = self.loader.catalogue[chosen_tid]

        if state.subscription_status == "trial_active":
            return {
                "type": "whatsapp",
                "send_at": to_iso(send_at),
                "template_id": "wa_trial_ending_v1",
                "variables": {
                    "plan_price": "₹149"
                },
                "title_id": chosen_tid
            }
        else:
            dialect_name = DIALECT_DISPLAY_NAMES.get(dialect, dialect)
            return {
                "type": "whatsapp",
                "send_at": to_iso(send_at),
                "template_id": "wa_recommend_title_v1",
                "variables": {
                    "title_name": title_obj["title"],
                    "dialect_name": dialect_name
                },
                "title_id": chosen_tid
            }
