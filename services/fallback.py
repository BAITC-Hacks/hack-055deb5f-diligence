"""Offline fallback data for the complete Bridge demo flow.

The helpers deliberately return plain JSON-compatible objects.  They can be
used when no OpenAI key is configured, or whenever an API response is invalid.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


DEMO_DESCRIPTION = (
    "Сотрудники на производстве вручную проверяют продукцию на брак. "
    "Это занимает много времени. Хотим попробовать автоматизировать проверку "
    "с помощью AI, но пока не понимаем, какую конкретную задачу дать студентам."
)

DEMO_ANSWERS: dict[str, str] = {
    "data_and_materials": (
        "Есть около 500 анонимизированных фотографий качественной и "
        "бракованной продукции."
    ),
    "expected_result": (
        "Нужен работающий прототип, который принимает фотографию и показывает, "
        "обнаружен ли возможный дефект."
    ),
    "success_criteria": (
        "Прототип должен запускаться по инструкции, принимать тестовые "
        "изображения и показывать результат в веб-интерфейсе."
    ),
    "constraints": (
        "Срок 3 недели. Можно использовать Python и open-source библиотеки."
    ),
    "users": "Сотрудники отдела контроля качества.",
    "business_contact": (
        "Один созвон с представителем производства в неделю и ответы на "
        "вопросы по почте."
    ),
}


def fallback_questions() -> list[dict[str, Any]]:
    """Return the five required offline clarification questions."""

    return [
        {
            "id": "expected_result",
            "question": "Какой конкретный результат должны подготовить студенты?",
            "reason": "Это поможет зафиксировать понятный результат работы команды.",
            "score_value": 15,
        },
        {
            "id": "data_and_materials",
            "question": (
                "Какие данные, примеры или материалы вы готовы им предоставить?"
            ),
            "reason": "Это позволит понять, можно ли начать работу.",
            "score_value": 20,
        },
        {
            "id": "success_criteria",
            "question": "Как вы поймёте, что задача выполнена успешно?",
            "reason": "Команде нужны прозрачные критерии проверки результата.",
            "score_value": 15,
        },
        {
            "id": "constraints",
            "question": (
                "Есть ли ограничения по срокам, технологиям или доступам?"
            ),
            "reason": "Ограничения помогают предложить реалистичный план.",
            "score_value": 10,
        },
        {
            "id": "users",
            "question": "Кто будет использовать результат?",
            "reason": "Это помогает учитывать реальный сценарий использования.",
            "score_value": 10,
        },
    ]


def fallback_analysis(
    raw_description: str = "", industry: str = ""
) -> dict[str, Any]:
    """Build a safe draft analysis without inventing missing facts."""

    description = raw_description.strip()
    selected_industry = industry.strip()

    if not description:
        description = DEMO_DESCRIPTION
        selected_industry = selected_industry or "Manufacturing"
        known_facts = [
            "Сотрудники вручную проверяют продукцию на брак.",
            "Ручная проверка занимает много времени.",
            "Компания хочет попробовать автоматизировать проверку с помощью AI.",
        ]
        summary = (
            "Компания хочет исследовать автоматизацию визуального контроля "
            "брака на производстве с помощью AI."
        )
    else:
        known_facts = [description]
        summary = description if len(description) <= 280 else description[:277].rstrip() + "..."

    if selected_industry:
        known_facts.append(f"Отрасль: {selected_industry}.")

    return {
        "summary": summary,
        "known_facts": known_facts,
        "missing_information": [
            "Конкретный результат работы команды",
            "Доступные данные и материалы",
            "Критерии успешного выполнения",
            "Ограничения по срокам, технологиям или доступам",
            "Будущие пользователи результата",
        ],
        "questions": fallback_questions(),
    }

def _clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _read_answer(answers: Mapping[str, Any], *aliases: str) -> str:
    for alias in aliases:
        value = answers.get(alias)
        if isinstance(value, Mapping):
            value = value.get("answer")
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return ""


def _derive_title(description: str, industry: str) -> str:
    lowered = description.casefold()
    if (
        ("брак" in lowered or "дефект" in lowered)
        and ("производ" in lowered or industry.casefold() == "manufacturing")
    ):
        return "AI-контроль брака на производстве"

    first_sentence = description.split(".", 1)[0].strip()
    if first_sentence:
        return first_sentence[:77].rstrip() + ("..." if len(first_sentence) > 77 else "")
    if industry:
        return f"Практическая задача: {industry}"
    return "Практическая задача для студентов"


def _derive_tags(
    description: str, industry: str, answers: Mapping[str, Any]
) -> list[str]:
    source = " ".join(
        [description, *(_clean_text(value) for value in answers.values())]
    ).casefold()
    tags: list[str] = []

    if industry and industry.casefold() != "other":
        tags.append(industry)
    if " ai" in f" {source}" or " ии" in f" {source}":
        tags.append("AI")
    if "python" in source:
        tags.append("Python")
    if "фото" in source or "изображен" in source:
        tags.append("Изображения")
    if "веб" in source or "web" in source:
        tags.append("Web")

    # Preserve order while preventing duplicates such as industry="AI".
    unique_tags: list[str] = []
    for tag in tags:
        if tag.casefold() not in {item.casefold() for item in unique_tags}:
            unique_tags.append(tag)
    return unique_tags[:5]


def fallback_task_card(
    raw_description: str = "",
    industry: str = "",
    analysis: Mapping[str, Any] | None = None,
    answers: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an editable task card using only supplied user facts.

    Calling the helper without arguments intentionally returns the complete
    prepared manufacturing demo.  During a real flow, pass the draft and the
    user's answers; absent facts remain empty strings.
    """

    no_user_input = not raw_description.strip() and not answers
    description = raw_description.strip() or (DEMO_DESCRIPTION if no_user_input else "")
    selected_industry = industry.strip() or ("Manufacturing" if no_user_input else "")

    safe_answers: Mapping[str, Any]
    if no_user_input:
        safe_answers = DEMO_ANSWERS
    elif isinstance(answers, Mapping):
        safe_answers = answers
    else:
        safe_answers = {}

    if not description and isinstance(analysis, Mapping):
        description = _clean_text(analysis.get("summary"))

    data_and_materials = _read_answer(
        safe_answers, "data_and_materials", "data", "materials"
    )
    expected_result = _read_answer(
        safe_answers, "expected_result", "result", "outcome"
    )
    success_criteria = _read_answer(
        safe_answers, "success_criteria", "criteria", "success"
    )
    constraints = _read_answer(
        safe_answers, "constraints", "limitations", "limits"
    )
    users = _read_answer(safe_answers, "users", "user", "audience")
    business_contact = _read_answer(
        safe_answers, "business_contact", "contact", "communication"
    )

    return {
        "title": _derive_title(description, selected_industry),
        "context_and_need": description,
        "users": users,
        "data_and_materials": data_and_materials,
        "expected_result": expected_result,
        "success_criteria": success_criteria,
        "constraints": constraints,
        "business_contact": business_contact,
        "tags": _derive_tags(description, selected_industry, safe_answers),
    }


def _task_text(task: Mapping[str, Any], field: str) -> str:
    return _clean_text(task.get(field)) or "В задаче это не указано"


def fallback_student_explanation(
    task: Mapping[str, Any] | None = None,
    profile: str = "Новичок",
    depth: str = "Понятно",
) -> dict[str, Any]:
    """Explain a published card offline without changing its facts."""

    safe_task: Mapping[str, Any] = (
        task if isinstance(task, Mapping) else fallback_task_card()
    )
    selected_profile = profile.strip() or "Новичок"
    selected_depth = depth.strip() or "Понятно"

    role_guidance = {
        "Новичок": (
            "Начните с контекста и ожидаемого результата, затем сверяйте идеи "
            "с доступными материалами и ограничениями."
        ),
        "AI / Data": (
            "Сфокусируйтесь на доступных данных, ожидаемом результате и способе "
            "проверки результата."
        ),
        "Business": (
            "Сфокусируйтесь на потребности, пользователях и критериях успеха."
        ),
        "Engineering": (
            "Сфокусируйтесь на ожидаемом результате, ограничениях и доступных "
            "материалах."
        ),
        "Design / Product": (
            "Сфокусируйтесь на пользователях, их контексте и форме итогового "
            "результата."
        ),
    }.get(
        selected_profile,
        "Сопоставьте ожидаемый результат с данными, ограничениями и критериями успеха.",
    )

    if selected_depth == "Коротко":
        role_guidance = role_guidance.split(".", 1)[0] + "."
    elif selected_depth == "Технически":
        role_guidance += " Не считайте отсутствующие в карточке детали требованиями."

    return {
        "core_problem": _task_text(safe_task, "context_and_need"),
        "why_it_matters": _task_text(safe_task, "context_and_need"),
        "what_team_should_do": _task_text(safe_task, "expected_result"),
        "your_role": role_guidance,
        "key_terms": [
            {
                "term": "Данные и материалы",
                "explanation": _task_text(safe_task, "data_and_materials"),
            },
            {
                "term": "Ожидаемый результат",
                "explanation": _task_text(safe_task, "expected_result"),
            },
            {
                "term": "Критерии успеха",
                "explanation": _task_text(safe_task, "success_criteria"),
            },
            {
                "term": "Ограничения",
                "explanation": _task_text(safe_task, "constraints"),
            },
        ],
        "first_steps": [
            f"Изучите контекст: {_task_text(safe_task, 'context_and_need')}",
            f"Проверьте доступные материалы: {_task_text(safe_task, 'data_and_materials')}",
            f"Сверьте результат с критериями: {_task_text(safe_task, 'success_criteria')}",
        ],
    }
