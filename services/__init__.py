"""Service-layer exports for Bridge."""

from .fallback import (
    DEMO_ANSWERS,
    DEMO_DESCRIPTION,
    fallback_analysis,
    fallback_questions,
    fallback_student_explanation,
    fallback_task_card,
)

__all__ = [
    "DEMO_DESCRIPTION",
    "DEMO_ANSWERS",
    "fallback_questions",
    "fallback_analysis",
    "fallback_task_card",
    "fallback_student_explanation",
]
