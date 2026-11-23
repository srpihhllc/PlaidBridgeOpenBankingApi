from __future__ import annotations



from typing import Any, cast





class ProgramDesignEngine:

    """

    Assess whether a proposed grant program is clearly designed,

    measurable, feasible, and aligned with the applicant's project.

    """



    REQUIRED_SECTIONS = ("summary", "need", "activities", "outcomes")



    def assess(self, project: Any) -> dict[str, Any]:

        data = self._to_mapping(project)

        sections = data.get("proposal_sections") or {}

        present = [s for s in self.REQUIRED_SECTIONS if sections.get(s)]

        missing = [s for s in self.REQUIRED_SECTIONS if not sections.get(s)]

        score = round((len(present) / len(self.REQUIRED_SECTIONS)) * 100.0, 1)

        return {

            "score": score,

            "present_sections": present,

            "missing_sections": missing,

            "feasible": len(missing) == 0,

        }



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

