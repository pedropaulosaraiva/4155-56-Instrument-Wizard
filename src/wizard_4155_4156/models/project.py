"""
models/project.py
-----------------
Pure data model for recent-project persistence.
No Qt imports — this layer must remain framework-agnostic.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# ── Relative-time formatting ─────────────────────────────────────────────────
# Recent-project rows show "2 hours ago" rather than a raw timestamp; the
# absolute date stays available as the row tooltip.

_MINUTE = 60
_HOUR = 60 * _MINUTE
_DAY = 24 * _HOUR
_RELATIVE_LIMIT_DAYS = 7  # beyond this an absolute date is clearer


def format_relative_time(
    when: datetime, now: Optional[datetime] = None
) -> str:
    """Human-readable age of *when* ("Just now", "3 hours ago", "Yesterday").

    Falls back to an absolute ``dd/mm/yyyy`` date past
    ``_RELATIVE_LIMIT_DAYS``, and for any timestamp in the future.
    """
    reference = now or datetime.now()
    seconds = (reference - when).total_seconds()
    days = int(seconds // _DAY)

    if seconds < 0 or days > _RELATIVE_LIMIT_DAYS:
        return when.strftime("%d/%m/%Y")
    if seconds < _MINUTE:
        return "Just now"
    if seconds < _HOUR:
        minutes = int(seconds // _MINUTE)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    if seconds < _DAY:
        hours = int(seconds // _HOUR)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    if days == 1:
        return "Yesterday"
    return f"{days} days ago"


class ProjectData:
    """Immutable value object representing a recent project entry."""

    __slots__ = ("name", "path", "last_modified", "thumbnail")

    def __init__(
        self,
        name: str,
        path: str,
        last_modified: datetime,
        thumbnail: Optional[str] = None,
    ) -> None:
        self.name = name
        self.path = path
        self.last_modified = last_modified
        self.thumbnail = thumbnail

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "last_modified": self.last_modified.isoformat(),
            "thumbnail": self.thumbnail,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectData":
        return cls(
            name=data["name"],
            path=data["path"],
            last_modified=datetime.fromisoformat(data["last_modified"]),
            thumbnail=data.get("thumbnail"),
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"ProjectData(name={self.name!r}, path={self.path!r})"


class RecentProjectsManager:
    """
    Persists up to *max_recent* project entries to
    ``~/.wizard4155/recent_projects.json``.

    Responsibilities:
        - Load / save the project list to disk.
        - Enforce the maximum-entry limit.
        - Deduplicate entries by path (most-recent bubbles to top).

    This class owns no Qt objects and carries no UI state.
    The presenter layer is responsible for refreshing the view after
    mutations.
    """

    _CONFIG_DIR = Path.home() / ".wizard4155"
    _CONFIG_FILE = "recent_projects.json"

    def __init__(self, max_recent: int = 30) -> None:
        self.max_recent = max_recent
        self._projects: List[ProjectData] = []
        self._config_path = self._CONFIG_DIR / self._CONFIG_FILE
        self._load()

    # ── Public API ───────────────────────────────────────────────────────────

    def add_project(
        self, path: str, name: Optional[str] = None
    ) -> ProjectData:
        """
        Insert or promote a project to the top of the list.
        Returns the resulting ProjectData entry.
        """
        resolved = str(Path(path).resolve())
        effective_name = name or Path(resolved).stem
        self._projects = [p for p in self._projects if p.path != resolved]
        entry = ProjectData(
            name=effective_name,
            path=resolved,
            last_modified=datetime.now(),
        )
        self._projects.insert(0, entry)
        self._projects = self._projects[: self.max_recent]
        self._save()
        return entry

    def remove_project(self, path: str) -> None:
        resolved = str(Path(path).resolve())
        self._projects = [p for p in self._projects if p.path != resolved]
        self._save()

    def get_projects(self) -> List[ProjectData]:
        """Return a shallow copy of the current list."""
        return list(self._projects)

    def clear_all(self) -> None:
        self._projects.clear()
        self._save()

    # ── Private ──────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._config_path.exists():
            return
        try:
            with open(self._config_path, encoding="utf-8") as fh:
                raw = json.load(fh)
            self._projects = [
                ProjectData.from_dict(p) for p in raw.get("projects", [])
            ]
        except Exception:  # noqa: BLE001
            self._projects = []

    def _save(self) -> None:
        self._CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as fh:
            json.dump(
                {"projects": [p.to_dict() for p in self._projects]},
                fh,
                indent=2,
            )
