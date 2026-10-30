from __future__ import annotations

from typing import Any, cast


class ProgramDesignEngine:
    """
    Assess whether a proposed grant program is clearly designed,
    measurable, feasible, and aligned with the applicant's project.
    """

    # ... [ existing code for assess() ] ...

    @staticmethod
    def _to_mapping(project: Any) -> dict[str, Any]:
        """Convert a dataclass, mapping, or object into a dictionary."""
        if isinstance(project, dict):
            return dict(project)

        if hasattr(project, "model_dump"):
            return cast(dict[str, Any], project.model_dump())

        if hasattr(project, "to_dict"):
            return cast(dict[str, Any], project.to_dict())

        if hasattr(project, "__dict__"):
            return dict(vars(project))

        return {}