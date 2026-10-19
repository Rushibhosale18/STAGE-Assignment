"""Data loading, indexing, deduplication, and anomaly detection."""
import csv
import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

from src.config import parse_iso

logger = logging.getLogger("DataLoader")


class DataLoader:
    def __init__(self, pack_dir: str):
        self.pack_dir = Path(pack_dir)
        self.catalogue: Dict[str, Dict[str, Any]] = {}
        self.catalogue_by_slug: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.titles_by_dialect: Dict[str, List[str]] = defaultdict(list)
        self.titles_by_genre: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        self.withdrawn_titles: Dict[str, datetime] = {}
        self.flagged_catalogue_injections: Dict[str, str] = {}
        
        self.episodes_by_slug: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.arms: Dict[str, str] = {}
        self.control_events: List[Dict[str, Any]] = []
        self.model_faults: Dict[str, Dict[str, Any]] = {}

    def load_catalogue(self) -> None:
        """Load and index catalogue.csv, flag prompt injections, index by dialect/genre."""
        cat_file = self.pack_dir / "data" / "catalogue.csv"
        injection_keywords = ["system note", "ai agent", "ignore your previous", "assistant instruction", "skip all checks"]
        
        with open(cat_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tid = row["title_id"]
                slug = row["content_slug"]
                dialect = row["dialect"]
                genres = [g.strip() for g in row["genres"].split("|") if g.strip()]
                
                # Check for prompt injection in description
                desc = row["description"]
                desc_lower = desc.lower()
                for kw in injection_keywords:
                    if kw in desc_lower:
                        self.flagged_catalogue_injections[tid] = desc
                        logger.warning(f"Injected instruction detected in catalogue title {tid} ({row['title']}): {desc}")
                        break
                
                item = {
                    "title_id": tid,
                    "content_slug": slug,
                    "title": row["title"],
                    "dialect": dialect,
                    "language": row["language"],
                    "content_type": row["content_type"],
                    "genres": genres,
                    "release_date": row["release_date"],
                    "available_from": parse_iso(row["available_from"]),
                    "available_until": parse_iso(row["available_until"]) if row.get("available_until") else None,
                    "is_premium": row["is_premium"].lower() == "true",
                    "description": desc
                }
                self.catalogue[tid] = item
                self.catalogue_by_slug[slug].append(item)
                self.titles_by_dialect[dialect].append(tid)
                for g in genres:
                    self.titles_by_genre[(dialect, g)].append(tid)

    def load_episodes(self) -> None:
        """Load episodes.csv and index by content_slug sorted by season and episode."""
        ep_file = self.pack_dir / "data" / "episodes.csv"
        with open(ep_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.episodes_by_slug[row["content_slug"]].append({
                    "episode_id": row["episode_id"],
                    "content_slug": row["content_slug"],
                    "season": int(row["season"]),
                    "episode": int(row["episode"]),
                    "minutes": float(row["minutes"])
                })
        for slug in self.episodes_by_slug:
            self.episodes_by_slug[slug].sort(key=lambda x: (x["season"], x["episode"]))

    def load_profiles(self) -> None:
        """Load profiles_snapshot.csv, resolving duplicates by keeping latest updated_at."""
        prof_file = self.pack_dir / "data" / "profiles_snapshot.csv"
        raw_profiles: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        with open(prof_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_profiles[row["user_id"]].append(row)
        
        for uid, rows in raw_profiles.items():
            if len(rows) == 1:
                self.profiles[uid] = rows[0]
            else:
                # Deduplicate: pick the row with the most recent updated_at timestamp
                best_row = max(rows, key=lambda r: r["updated_at"])
                self.profiles[uid] = best_row

    def load_arms(self) -> None:
        """Load replay/arms.csv to know agent vs holdout arm assignment."""
        arms_file = self.pack_dir / "replay" / "arms.csv"
        with open(arms_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.arms[row["user_id"]] = row["arm"]

    def load_control_events(self) -> None:
        """Load replay/control_events.jsonl."""
        ctrl_file = self.pack_dir / "replay" / "control_events.jsonl"
        if not ctrl_file.exists():
            return
        with open(ctrl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    ev = json.loads(line)
                    ev["at_dt"] = parse_iso(ev["at"])
                    self.control_events.append(ev)
        self.control_events.sort(key=lambda x: x["at_dt"])

    def load_model_faults(self) -> None:
        """Load replay/model_faults.jsonl indexed by trigger_event_id."""
        fault_file = self.pack_dir / "replay" / "model_faults.jsonl"
        if not fault_file.exists():
            return
        with open(fault_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    fault = json.loads(line)
                    self.model_faults[fault["trigger_event_id"]] = fault

    def load_all_static(self) -> None:
        """Load all static catalogues, profiles, arms, and control tables."""
        self.load_catalogue()
        self.load_episodes()
        self.load_profiles()
        self.load_arms()
        self.load_control_events()
        self.load_model_faults()

    def is_title_available(self, title_id: str, at: datetime) -> bool:
        """Check if title exists and is active and available at the given timestamp."""
        # Check title withdrawal from control events
        if title_id in self.withdrawn_titles:
            withdrawal_time = self.withdrawn_titles[title_id]
            if at >= withdrawal_time:
                return False

        item = self.catalogue.get(title_id)
        if not item:
            return False
        if item["available_from"] and at < item["available_from"]:
            return False
        if item["available_until"] and at >= item["available_until"]:
            return False
        return True

    def withdraw_title(self, title_id: str, at: datetime) -> None:
        """Mark title as withdrawn from a specific timestamp."""
        self.withdrawn_titles[title_id] = at
        if title_id in self.catalogue:
            old_until = self.catalogue[title_id]["available_until"]
            if old_until is None or at < old_until:
                self.catalogue[title_id]["available_until"] = at
        logger.info(f"Title {title_id} marked withdrawn as of {at}")

    def get_next_episode(self, content_slug: str, last_episode_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Return the next episode in sequence for a show or micro-drama."""
        episodes = self.episodes_by_slug.get(content_slug, [])
        if not episodes:
            return None
        if not last_episode_id:
            return episodes[0]
        for i, ep in enumerate(episodes):
            if ep["episode_id"] == last_episode_id:
                if i + 1 < len(episodes):
                    return episodes[i + 1]
                return None  # Completed whole series
        return episodes[0]
