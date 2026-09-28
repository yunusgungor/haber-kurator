"""
Haber Kuratör — State Machine Module
======================================
StateMachineMixin for HaberKuratorCore.

Handles: state transitions, persistence, sync, route management.
"""

import json
import logging
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from haber_kurator.modules.models import (
    STATE_LIFECYCLE, STATE_TRANSITIONS, STATE_ALIAS_MAP,
    ROUTE_VERIFIED, ROUTE_HIGH_SLOP, ROUTE_ESCALATED,
    RunState,
    StateError,
)

logger = logging.getLogger(__name__)


class StateMachineMixin:
    """Mixin providing state machine capabilities.

    Expects these attributes on self (set by HaberKuratorCore.__init__):
        active_runs : Path
        archive     : Path
        _state_cache : Dict[str, RunState]
        _state_cache_dir : Path
        _db_path    : str
    """

    # ──────────────────────────────────────────────────────────
    # STATE CACHE — SQLite Backed
    # ──────────────────────────────────────────────────────────

    def _init_db(self):
        """Initialize SQLite state cache."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("CREATE TABLE IF NOT EXISTS state_cache ("
                        "slug TEXT PRIMARY KEY, title TEXT, state TEXT, "
                        "route TEXT, created TEXT, updated TEXT, "
                        "source_type TEXT, verification_level TEXT)")
            conn.commit()
            conn.close()
            logger.debug(f"SQLite state cache initialized at {self._db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize SQLite state cache: {e}")

    def _save_state_cache(self):
        """Persist in-memory state cache to SQLite."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("BEGIN")
            for slug, rs in self._state_cache.items():
                conn.execute(
                    "INSERT OR REPLACE INTO state_cache VALUES (?,?,?,?,?,?,?,?)",
                    (rs.slug, rs.title, rs.state, rs.route,
                     rs.created, rs.updated, rs.source_type, rs.verification_level),
                )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Failed to save state cache: {e}")

    def _load_state_cache(self):
        """Load state cache from SQLite (or migrate from legacy JSON)."""
        # Try SQLite first
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM state_cache")
            for row in cursor.fetchall():
                self._state_cache[row["slug"]] = RunState(
                    slug=row["slug"],
                    title=row["title"],
                    state=STATE_ALIAS_MAP.get(row["state"], row["state"]),
                    route=row["route"],
                    created=row["created"],
                    updated=row["updated"],
                    source_type=row["source_type"],
                    verification_level=row["verification_level"],
                )
            conn.close()
            logger.info(f"Loaded {len(self._state_cache)} entries from SQLite cache")
            return
        except sqlite3.Error as e:
            logger.error(f"Failed to load state cache from SQLite: {e}")

        # Fallback: migrate from legacy JSON
        legacy_path = self._state_cache_dir / "state_cache.json"
        if legacy_path.exists():
            try:
                data = json.loads(legacy_path.read_text(encoding="utf-8"))
                for slug, d in data.items():
                    self._state_cache[slug] = RunState(
                        slug=d["slug"],
                        title=d.get("title", ""),
                        state=STATE_ALIAS_MAP.get(d.get("state", "captured"), d.get("state", "captured")),
                        route=d.get("route", "VERIFIED"),
                        created=d.get("created", ""),
                        updated=d.get("updated", ""),
                        source_type=d.get("source_type", "multi-source"),
                        verification_level=d.get("verification_level", "unverified"),
                    )
                self._save_state_cache()
                legacy_path.rename(legacy_path.with_suffix(".json.migrated"))
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"Legacy JSON cache migration failed: {e}")

    # ──────────────────────────────────────────────────────────
    # STATE TRANSITIONS
    # ──────────────────────────────────────────────────────────

    def _valid_transition(self, from_state: str, to_state: str) -> bool:
        if from_state not in STATE_TRANSITIONS:
            return False
        return to_state in STATE_TRANSITIONS[from_state]

    def update_state(self, slug: str, new_state: str,
                     force: bool = False, route: str = "VERIFIED") -> str:
        """Update state with 5-state lifecycle validation.

        Args:
            slug: Run slug
            new_state: Target state from STATE_LIFECYCLE (legacy names auto-migrated)
            force: Skip transition validation (used by sync_state for FS recovery)
            route: Route classification — VERIFIED, HIGH_SLOP, or ESCALATED
        """
        new_state = STATE_ALIAS_MAP.get(new_state, new_state)
        logger.info("update_state: slug=%s, new_state=%s, force=%s", slug, new_state, force)

        if new_state not in STATE_LIFECYCLE:
            return f"❌ Invalid state: {new_state}"

        run_path = (self.active_runs / slug).resolve()
        if not run_path.exists():
            return f"❌ Run {slug} not found."

        obj_path = run_path / "haber-object.md"

        # Auto-initialize if missing
        if not obj_path.exists():
            obj_path.write_text(f"# {slug}\n\nstate: {new_state}\n", encoding="utf-8")

        content = obj_path.read_text(encoding="utf-8")
        current_state = self.get_state(slug)

        # Validate transition
        if not force and current_state != "unknown":
            if not self._valid_transition(current_state, new_state):
                allowed = STATE_TRANSITIONS.get(current_state, ["any"])
                return f"❌ Invalid transition: {current_state} → {new_state}. Allowed: {allowed}"

        # Update state in haber-object.md
        state_field_pattern = r"(?i)((- \*\*)?(?:status|state)\*{0,2}:\*{0,2}\s*)\w+"
        if re.search(state_field_pattern, content):
            new_content = re.sub(
                state_field_pattern,
                lambda m: f"{m.group(1)}{new_state}",
                content,
            )
        else:
            new_content = content + f"\nstate: {new_state}"

        ts = datetime.now().isoformat()
        if "updated:" in new_content:
            new_content = re.sub(r"updated:.*", f"updated: {ts}", new_content)
        else:
            new_content = f"{new_content}\nupdated: {ts}"

        existing = self._state_cache.get(slug, RunState(slug=slug))
        next_route = route if existing.route == "VERIFIED" else existing.route
        self._state_cache[slug] = RunState(
            slug=slug,
            title=existing.title,
            state=new_state,
            route=next_route,
            created=existing.created or ts,
            updated=ts,
            source_type=existing.source_type,
            verification_level=existing.verification_level,
        )

        obj_path.write_text(new_content, encoding="utf-8")
        self._save_state_cache()
        return f"✅ {slug}: {current_state} → {new_state} (route={next_route})"

    # ──────────────────────────────────────────────────────────
    # STATE SYNC (Filesystem Recovery)
    # ──────────────────────────────────────────────────────────

    def sync_state(self, slug: str) -> str:
        """Scan filesystem and sync haber-object.md to correct state.

        Uses force=True to bypass transition validation — this is intentional:
        filesystem recovery must be able to set any valid state regardless of
        cache state.
        """
        run_path = self.active_runs / slug
        if not run_path.exists():
            run_path = self.archive / slug
            if not run_path.exists():
                return "unknown"

        obj_path = run_path / "haber-object.md"
        if not obj_path.exists():
            return "unknown"

        content = obj_path.read_text(encoding="utf-8")
        st_match = re.search(r"(?i)state:\s*(\w+)", content)
        if st_match:
            state = st_match.group(1)
        else:
            state = "captured"

        try:
            self.update_state(slug, state, force=True)
        except (OSError, PermissionError) as e:
            logger.debug("sync_state update skipped %s: %s", slug, e)
        return state

    # ──────────────────────────────────────────────────────────
    # STATE / ROUTE READERS
    # ──────────────────────────────────────────────────────────

    def get_state(self, slug: str) -> str:
        """Read current state from cache or haber-object.md."""
        if slug in self._state_cache:
            # Cache state is already migrated via _load_state_cache
            return self._state_cache[slug].state
        obj = self.active_runs / slug / "haber-object.md"
        if not obj.exists():
            return "unknown"
        content = obj.read_text(encoding="utf-8")
        m = re.search(r'(?i)(?:status|state)\*{0,2}:\*{0,2}\s*(\w+)', content)
        state = m.group(1) if m else "unknown"
        state = STATE_ALIAS_MAP.get(state, state)
        if state != "unknown":
            rs = RunState(slug=slug, state=state)
            for field, key in [("Route", "route"), ("Title", "title")]:
                fm = re.search(rf'\*{{0,2}}{field}\*{{0,2}}:\*{{0,2}}\s*(.+)', content, re.IGNORECASE)
                if fm:
                    setattr(rs, key, fm.group(1).strip())
            self._state_cache[slug] = rs
        return state

    def get_route(self, slug: str) -> str:
        """Read current route from cache or haber-object.md."""
        if slug in self._state_cache:
            return self._state_cache[slug].route
        obj = self.active_runs / slug / "haber-object.md"
        if not obj.exists():
            return "VERIFIED"
        content = obj.read_text(encoding="utf-8")
        m = re.search(r'(?i)route\*{0,2}:\*{0,2}\s*(\w+)', content)
        route = m.group(1) if m else "VERIFIED"
        if route not in (ROUTE_VERIFIED, ROUTE_HIGH_SLOP, ROUTE_ESCALATED):
            route = "VERIFIED"
        self._state_cache[slug] = RunState(
            slug=slug,
            state=self.get_state(slug),
            route=route,
        )
        return route

    # ──────────────────────────────────────────────────────────
    # NEXT ACTIONS
    # ──���───────────────────────────────────────────────────────

    def get_next_actions(self, slug: str) -> List[str]:
        """Return suggested next actions based on current state."""
        state = self.get_state(slug)
        guide = {
            "captured":   ["Generate brief: generate_brief()",
                           "Verify news: update_state → verified"],
            "verified":   ["Generate draft: generate_draft()",
                           "Run verifier: run_verifier()",
                           "Publish: update_state → published"],
            "published":  ["Monitor feedback: check_correction_needed()",
                           "Archive: update_state → archived",
                           "Correct: update_state → corrected"],
            "corrected":  ["Republish corrected version: update_state → published",
                           "Archive: update_state → archived"],
            "archived":   ["No further actions. Run is complete."],
        }
        return guide.get(state, ["State not recognized. Start with captured."])

    # ──────────────────────────────────────────────────────────
    # ROUTE (classification)
    # ──────────────────────────────────────────────────────────

    def decide_route(self, idea: str, source_hint: str = "") -> Dict[str, Any]:
        """Haberde tek rota vardır: VERIFIED (çok kaynaklı doğrulama)."""
        return {
            "route": "VERIFIED",
            "rationale": "Multi-source verified news.",
            "source_type": "multi-source",
        }

    # ──────────────────────────────────────────────────────────
    # ARCHIVE
    # ──────────────────────────────────────────────────────────

    def archive_run(self, slug: str, force: bool = False) -> str:
        """Move a run from active to archive."""
        state = self.get_state(slug)
        valid_pre_archive = [t for s, targets in STATE_TRANSITIONS.items()
                            if "archived" in targets for t in [s]]
        if state not in valid_pre_archive and not force:
            return (f"❌ Cannot archive {slug} in state '{state}'. "
                    f"Must be one of: {valid_pre_archive}")

        src = self.active_runs / slug
        if not src.exists():
            return f"❌ Run {slug} not found."

        dst = self.archive / slug
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(src), str(dst))

        # Update state in haber-object.md
        obj_path = dst / "haber-object.md"
        if obj_path.exists():
            try:
                obj_content = obj_path.read_text(encoding="utf-8")
                if "state:" in obj_content:
                    obj_content = re.sub(r"state:\s*\w+", "state: archived", obj_content)
                else:
                    obj_content += "\nstate: archived"
                obj_path.write_text(obj_content, encoding="utf-8")
            except (OSError, PermissionError):
                pass

        # Update cache
        if slug in self._state_cache:
            self._state_cache[slug].state = "archived"
            self._save_state_cache()

        return f"✅ Run {slug} archived."
