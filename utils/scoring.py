"""Deterministic readiness scoring for Bridge task cards.

The AI layer never participates in the score calculation.  A field earns its
full weight when it contains at least ten non-whitespace characters.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


WEIGHTS: dict[str, int] = {
    "context_and_need": 20,
    "data_and_materials": 20,
    "expected_result": 15,
    "success_criteria": 15,
    "constraints": 10,
    "users": 10,
    "business_contact": 10,
}


RECOMMENDATION_MESSAGES: dict[str, str] = {
    "context_and_need": "Добавьте контекст проблемы и объясните потребность бизнеса",
    "data_and_materials": "Добавьте доступные данные или материалы",
    "expected_result": "Опишите конкретный результат работы команды",
    "success_criteria": "Опишите измеримые критерии успеха",
    "constraints": "Укажите ограничения по срокам, технологиям или доступам",
    "users": "Укажите, кто будет использовать результат",
    "business_contact": "Укажите формат связи со специалистом компании",
}


def is_field_complete(value: Any) -> bool:
    """Return ``True`` when *value* has at least 10 meaningful characters.

    Only text values count.  This prevents accidental points for values such as
    lists, dictionaries or numbers that do not belong in the card text fields.
    """

    return isinstance(value, str) and len(value.strip()) >= 10


def calculate_score(task: Mapping[str, Any] | None) -> int:
    """Calculate the task readiness score in the inclusive range 0..100."""

    if not isinstance(task, Mapping):
        return 0

    return sum(
        points
        for field, points in WEIGHTS.items()
        if is_field_complete(task.get(field))
    )


def _normalise_score(score: Any) -> float:
    """Convert arbitrary input to a safe score without raising in the UI."""

    if isinstance(score, bool):
        return 0.0
    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        return 0.0
    if numeric_score != numeric_score:  # NaN
        return 0.0
    return max(0.0, min(100.0, numeric_score))


def get_level(score: Any) -> str:
    """Return the Russian readiness level for *score*."""

    numeric_score = _normalise_score(score)
    if numeric_score < 40:
        return "Черновик"
    if numeric_score < 70:
        return "Рабочая"
    if numeric_score < 90:
        return "Готовая"
    return "Приоритетная"


def get_missing_recommendations(
    task: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return improvements for every incomplete scoring field.

    Each result has a stable UI-friendly contract::

        {"field": "data_and_materials", "message": "...", "points": 20}
    """

    safe_task = task if isinstance(task, Mapping) else {}
    return [
        {
            "field": field,
            "message": RECOMMENDATION_MESSAGES[field],
            "points": points,
        }
        for field, points in WEIGHTS.items()
        if not is_field_complete(safe_task.get(field))
    ]


def _points_word(points: int) -> str:
    """Choose the correct Russian word form for a number of points."""

    last_two = points % 100
    last_one = points % 10
    if 11 <= last_two <= 14:
        return "баллов"
    if last_one == 1:
        return "балл"
    if 2 <= last_one <= 4:
        return "балла"
    return "баллов"


def points_to_next_level(score: Any) -> dict[str, Any]:
    """Describe how many points remain to the next showcased level.

    The product specifically highlights the thresholds ``Готовая`` (70) and
    ``Приоритетная`` (90).  For an already-priority task, ``points`` is zero
    and ``target_level`` is ``None``.
    """

    numeric_score = _normalise_score(score)
    if numeric_score < 70:
        threshold = 70
        target_level: str | None = "Готовая"
    elif numeric_score < 90:
        threshold = 90
        target_level = "Приоритетная"
    else:
        return {
            "points": 0,
            "target_level": None,
            "message": "Задача полностью готова к работе 🚀",
        }

    # Scores produced by calculate_score are integers.  ``ceil`` also keeps
    # this helper sensible if a float is supplied by a caller.
    difference = threshold - numeric_score
    points = int(difference) if difference.is_integer() else int(difference) + 1
    return {
        "points": points,
        "target_level": target_level,
        "message": (
            f'До уровня "{target_level}" осталось '
            f"{points} {_points_word(points)}"
        ),
    }
