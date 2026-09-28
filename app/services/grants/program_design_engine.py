
"""

program_design_engine.py



Grant program design assessment engine.

"""



from __future__ import annotations



from typing import Any





class ProgramDesignEngine:

    """

    Assess whether a proposed grant program is clearly designed,

    measurable, feasible, and aligned with the applicant's project.

    """



    def assess(self, project: Any) -> dict[str, Any]:

        """

        Return a structured program-design assessment.



        The engine does not invent missing project information. Missing

        design elements are reported for human review.

        """

        missing: list[str] = []



        if project is None:

            return {

                "status": "incomplete",

                "score": 0,

                "strengths": [],

                "gaps": ["project"],

                "recommendations": [

                    "Provide a GrantProject before assessing program design."

                ],

            }



        project_data = self._to_mapping(project)



        required_fields = {

            "program_name": "program name",

            "problem_statement": "problem statement",

            "target_population": "target population",

            "activities": "program activities",

            "objectives": "program objectives",

            "timeline": "implementation timeline",

            "outcomes": "expected outcomes",

        }



        for field_name, display_name in required_fields.items():

            value = project_data.get(field_name)



            if value is None or value == "" or value == [] or value == {}:

                missing.append(display_name)



        total_fields = len(required_fields)

        completed_fields = total_fields - len(missing)

        score = round((completed_fields / total_fields) * 100)



        if score == 100:

            status = "ready"

        elif score >= 75:

            status = "needs_review"

        else:

            status = "incomplete"



        strengths = [

            f"{completed_fields} of {total_fields} core design elements provided."

        ]



        recommendations = [

            f"Define the {item}."

            for item in missing

        ]



        return {

            "status": status,

            "score": score,

            "strengths": strengths,

            "gaps": missing,

            "recommendations": recommendations,

        }



    @staticmethod

    def _to_mapping(project: Any) -> dict[str, Any]:

        """Convert a dataclass, mapping, or object into a dictionary."""

        if isinstance(project, dict):

            return project



        if hasattr(project, "model_dump"):

            return project.model_dump()



        if hasattr(project, "to_dict"):

            return project.to_dict()



        if hasattr(project, "__dict__"):

            return vars(project)



        return {}

