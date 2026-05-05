import os
import random
import re
import json
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor
from thefuzz import process


def _normalize_text(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


class DistrictMapper:
    """
    Resolves district_id from free-form post text by matching district/state mentions.
    Strategy:
    1) Exact district mention match (highest confidence)
    2) State mention fallback (pick district from same state, weighted by population if present)
    """
    def __init__(self, db_url: str | None = None):
        self.db_url = db_url or os.getenv(
            "DATABASE_URL",
            "postgresql://setu_user:setu_secure_password@localhost:5432/setu_db"
        )
        self.district_rows = []
        self.by_district_name = defaultdict(list)
        self.by_state_name = defaultdict(list)
        self.district_aliases = {}
        self.state_aliases = {}
        self.alias_path = os.getenv(
            "LOCATION_ALIASES_PATH",
            os.path.join(os.path.dirname(__file__), "location_aliases.json")
        )
        self.fuzzy_threshold = int(os.getenv("DISTRICT_FUZZY_THRESHOLD", "92"))
        self._compiled_district_patterns = []
        self._compiled_state_patterns = []
        self._district_name_choices = []
        self._state_name_choices = []
        self._load_aliases()
        self._load_cache()

    def _load_aliases(self):
        self.district_aliases = {}
        self.state_aliases = {}
        if not os.path.exists(self.alias_path):
            return
        try:
            with open(self.alias_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in (data.get("district_aliases") or {}).items():
                self.district_aliases[_normalize_text(k)] = _normalize_text(v)
            for k, v in (data.get("state_aliases") or {}).items():
                self.state_aliases[_normalize_text(k)] = _normalize_text(v)
        except Exception:
            # Keep resolver operational even if alias file is malformed.
            self.district_aliases = {}
            self.state_aliases = {}

    def _load_cache(self):
        conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    state,
                    population,
                    ST_X(ST_Centroid(geom)) AS lng,
                    ST_Y(ST_Centroid(geom)) AS lat
                FROM districts
                """
            )
            self.district_rows = cursor.fetchall()
        finally:
            conn.close()

        self.by_district_name.clear()
        self.by_state_name.clear()

        for row in self.district_rows:
            dn = _normalize_text(row["name"])
            sn = _normalize_text(row["state"])
            if dn:
                self.by_district_name[dn].append(row)
            if sn:
                self.by_state_name[sn].append(row)

        # Longest phrases first to avoid partial matches.
        district_names = sorted(self.by_district_name.keys(), key=len, reverse=True)
        state_names = sorted(self.by_state_name.keys(), key=len, reverse=True)
        self._compiled_district_patterns = [
            (name, re.compile(rf"\b{re.escape(name)}\b")) for name in district_names
        ]
        self._compiled_state_patterns = [
            (name, re.compile(rf"\b{re.escape(name)}\b")) for name in state_names
        ]
        self._district_name_choices = district_names
        self._state_name_choices = state_names

    def refresh(self):
        self._load_cache()

    def resolve(self, text: str) -> dict:
        normalized = _normalize_text(text)
        if not normalized or not self.district_rows:
            return {"district_id": None, "lat": None, "lng": None, "method": "none"}

        normalized = self._apply_aliases(normalized)

        # 1) District-level matching
        for district_name, pattern in self._compiled_district_patterns:
            if pattern.search(normalized):
                candidates = self.by_district_name[district_name]
                best = self._pick_best_candidate(candidates)
                return self._pack(best, "district_mention")

        # 1b) Fuzzy district matching against full text.
        district_match = process.extractOne(normalized, self._district_name_choices) if self._district_name_choices else None
        if district_match:
            district_name, score = district_match
            if score >= self.fuzzy_threshold:
                candidates = self.by_district_name[district_name]
                best = self._pick_best_candidate(candidates)
                return self._pack(best, "district_fuzzy")

        # 2) State-level matching
        for state_name, pattern in self._compiled_state_patterns:
            if pattern.search(normalized):
                candidates = self.by_state_name[state_name]
                best = self._pick_weighted_candidate(candidates)
                return self._pack(best, "state_mention")

        # 2b) Fuzzy state matching fallback
        state_match = process.extractOne(normalized, self._state_name_choices) if self._state_name_choices else None
        if state_match:
            state_name, score = state_match
            if score >= self.fuzzy_threshold:
                candidates = self.by_state_name[state_name]
                best = self._pick_weighted_candidate(candidates)
                return self._pack(best, "state_fuzzy")

        return {"district_id": None, "lat": None, "lng": None, "method": "unresolved"}

    def _apply_aliases(self, normalized_text: str) -> str:
        text = normalized_text
        for alias, canonical in self.district_aliases.items():
            text = re.sub(rf"\b{re.escape(alias)}\b", canonical, text)
        for alias, canonical in self.state_aliases.items():
            text = re.sub(rf"\b{re.escape(alias)}\b", canonical, text)
        return re.sub(r"\s+", " ", text).strip()

    def _pick_best_candidate(self, candidates: list[dict]) -> dict:
        # Highest population first when duplicate district names exist across states.
        return sorted(candidates, key=lambda r: (r.get("population") or 0), reverse=True)[0]

    def _pick_weighted_candidate(self, candidates: list[dict]) -> dict:
        weights = [max(1, int(r.get("population") or 1)) for r in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    def _pack(self, row: dict, method: str) -> dict:
        return {
            "district_id": row["id"],
            "lat": row.get("lat"),
            "lng": row.get("lng"),
            "method": method,
            "district": row.get("name"),
            "state": row.get("state"),
        }
