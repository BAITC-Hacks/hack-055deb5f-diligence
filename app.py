"""Bridge — Streamlit MVP для постановки бизнес-задач студентам.

Приложение намеренно не использует базу данных или отдельный backend:
постоянные данные хранятся в небольших JSON-файлах, а состояние текущего
сценария — в ``st.session_state``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import streamlit as st

from services.openai_service import (
    analyze_draft,
    explain_task,
    generate_task_card,
    get_api_key,
    get_last_error_message,
)
from utils.scoring import (
    WEIGHTS,
    calculate_score,
    get_level,
    get_missing_recommendations,
    is_field_complete,
    points_to_next_level,
)
from utils.storage import (
    load_proposals,
    load_tasks,
    save_proposals,
    save_tasks,
)


APP_TITLE = "Bridge"
BUSINESS = "Бизнес"
STUDENT = "Студент"

INDUSTRIES = [
    "IT",
    "Manufacturing",
    "Retail",
    "Finance",
    "Education",
    "Healthcare",
    "Logistics",
    "Marketing",
    "Energy",
    "Other",
]
PROFILES = ["Новичок", "AI / Data", "Business", "Engineering", "Design / Product"]
DEPTHS = ["Коротко", "Понятно", "Технически"]

CARD_FIELDS = {
    "title": "Название задачи",
    "context_and_need": "Контекст и потребность",
    "users": "Пользователи",
    "data_and_materials": "Данные и материалы",
    "expected_result": "Ожидаемый результат",
    "success_criteria": "Критерии успеха",
    "constraints": "Ограничения",
    "business_contact": "Контакт и формат взаимодействия",
}

SCORE_FIELD_LABELS = {
    key: CARD_FIELDS[key] for key in WEIGHTS
}

LEVEL_ICONS = {
    "Черновик": "⚪",
    "Рабочая": "🟡",
    "Готовая": "🟢",
    "Приоритетная": "🚀",
}

PROPOSAL_STATUS = {
    "pending": "🟡 На рассмотрении",
    "accepted": "🟢 Принято",
    "rejected": "🔴 Отклонено",
}

AI_FALLBACK_MESSAGE = (
    "AI временно недоступен. Мы включили резервный режим, поэтому вы можете "
    "продолжить демонстрацию."
)

DEMO_DRAFT = (
    "Сотрудники на производстве вручную проверяют продукцию на брак. "
    "Это занимает много времени. Хотим попробовать автоматизировать проверку "
    "с помощью AI, но пока не понимаем, какую конкретную задачу дать студентам."
)


def now_iso() -> str:
    """Вернуть UTC-время в стабильном ISO-формате."""

    return datetime.now(timezone.utc).isoformat()


def init_state() -> None:
    """Инициализировать все ключи сквозного пользовательского сценария."""

    defaults: dict[str, Any] = {
        "role": BUSINESS,
        "page": "Dashboard",
        "draft": {"industry": "Manufacturing", "raw_description": ""},
        "analysis": None,
        "clarifying_answers": {},
        "current_card": None,
        "selected_task_id": None,
        "selected_proposal_id": None,
        "selected_profile": "AI / Data",
        "selected_explanation_depth": "Понятно",
        "openai_api_key": None,
        "student_explanation": None,
        "student_explanation_context": None,
        "last_ai_fallback": False,
        "last_ai_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_styles() -> None:
    """Небольшой слой стилей без переопределения внутренней разметки Streamlit."""

    st.markdown(
        """
        <style>
            .block-container {max-width: 1120px; padding-top: 2.3rem; padding-bottom: 4rem;}
            [data-testid="stSidebar"] {border-right: 1px solid rgba(128,128,128,.18);}
            h1, h2, h3 {letter-spacing: -0.025em;}
            .bridge-kicker {color: #5b67f1; font-weight: 750; letter-spacing: .08em;}
            .bridge-muted {color: #6b7280; margin-top: -.6rem; margin-bottom: 1.4rem;}
            .bridge-tag {
                display: inline-block; padding: .18rem .58rem; margin: .12rem .18rem .12rem 0;
                border-radius: 999px; background: rgba(91,103,241,.10); color: #4d57ca;
                font-size: .80rem; font-weight: 600;
            }
            .bridge-score {font-size: 1.12rem; font-weight: 700;}
            .bridge-eyebrow {font-size: .82rem; color: #6b7280; text-transform: uppercase; letter-spacing: .05em;}
            div[data-testid="stMetric"] {
                border: 1px solid rgba(128,128,128,.18); border-radius: 16px; padding: 1rem;
            }
            div[data-testid="stForm"] {
                border: 1px solid rgba(128,128,128,.18); border-radius: 18px; padding: 1.25rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def go_to(page: str, *, task_id: str | None = None, proposal_id: str | None = None) -> None:
    """Перейти на страницу и сохранить выбранный объект."""

    st.session_state.page = page
    if task_id is not None:
        st.session_state.selected_task_id = task_id
        st.session_state.student_explanation = None
        st.session_state.student_explanation_context = None
    if proposal_id is not None:
        st.session_state.selected_proposal_id = proposal_id
    st.rerun()


def reset_create_flow() -> None:
    """Очистить только временные данные мастера создания задачи."""

    st.session_state.draft = {"industry": "Manufacturing", "raw_description": ""}
    st.session_state.analysis = None
    st.session_state.clarifying_answers = {}
    st.session_state.current_card = None
    st.session_state.last_ai_fallback = False
    st.session_state.last_ai_error = None
    transient_prefixes = ("answer_", "card_", "draft_")
    for key in list(st.session_state.keys()):
        if str(key).startswith(transient_prefixes):
            del st.session_state[key]


def load_demo_draft() -> None:
    """Подставить демонстрационный черновик до создания виджетов нового rerun."""

    st.session_state.draft = {
        "industry": "Manufacturing",
        "raw_description": DEMO_DRAFT,
    }
    st.session_state.draft_industry = "Manufacturing"
    st.session_state.draft_description = DEMO_DRAFT
    st.session_state.analysis = None
    st.session_state.clarifying_answers = {}
    st.session_state.current_card = None
    st.session_state.last_ai_fallback = False
    st.session_state.last_ai_error = None
    for key in list(st.session_state.keys()):
        if str(key).startswith(("answer_", "card_")):
            del st.session_state[key]


def render_sidebar() -> None:
    """Общая навигация, переключатель роли и безопасный ввод API-ключа."""

    st.sidebar.markdown("## BRIDGE")
    st.sidebar.caption("Из проблемы — в понятную задачу")

    if "role_switch" not in st.session_state:
        st.session_state.role_switch = st.session_state.role
    chosen_role = st.sidebar.radio(
        "Роль",
        [BUSINESS, STUDENT],
        horizontal=True,
        key="role_switch",
    )
    if chosen_role != st.session_state.role:
        st.session_state.role = chosen_role
        st.session_state.page = "Dashboard"
        st.session_state.selected_task_id = None
        st.session_state.selected_proposal_id = None
        st.rerun()

    st.sidebar.markdown("---")
    if st.session_state.role == BUSINESS:
        nav_items = [
            ("🏠 Dashboard", "Dashboard"),
            ("➕ Создать задачу", "Создать задачу"),
            ("🌐 Каталог", "Каталог"),
            ("🤝 Отклики", "Отклики"),
        ]
    else:
        nav_items = [
            ("🏠 Dashboard", "Dashboard"),
            ("🔎 Найти задачи", "Найти задачи"),
            ("📤 Мои предложения", "Мои предложения"),
        ]

    for label, page in nav_items:
        if st.sidebar.button(
            label,
            key=f"nav_{st.session_state.role}_{page}",
            use_container_width=True,
            type="primary" if st.session_state.page == page else "secondary",
        ):
            go_to(page)

    st.sidebar.markdown("---")
    api_key = get_api_key(st.session_state.openai_api_key)
    if not api_key:
        st.sidebar.caption("OpenAI API не подключён")
        entered_key = st.sidebar.text_input(
            "Вставить OpenAI API key для этой сессии",
            type="password",
            key="api_key_input",
            help="Ключ хранится только в памяти текущей сессии и не записывается в JSON.",
        )
        if entered_key:
            st.session_state.openai_api_key = entered_key.strip()
            api_key = get_api_key(st.session_state.openai_api_key)

    if api_key and not st.session_state.last_ai_fallback:
        st.sidebar.caption("🟢 OpenAI подключён")
    else:
        st.sidebar.caption("🟡 Demo mode")


def render_ai_warning() -> None:
    """Show fallback state together with a safe, actionable cause."""

    st.warning(AI_FALLBACK_MESSAGE)
    reason = st.session_state.get("last_ai_error")
    if reason:
        st.error(f"Причина: {reason}")
    else:
        st.caption("Это результат предыдущей попытки. Повторите AI-запрос, чтобы обновить его.")


def status_level(score: int) -> str:
    level = get_level(score)
    return f"{LEVEL_ICONS.get(level, '•')} {level}"


def proposal_status(status: str) -> str:
    return PROPOSAL_STATUS.get(status, "• Неизвестно")


def tags_html(tags: list[str] | None) -> str:
    safe_tags = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]
    # Теги создаются из текста пользователя/модели, поэтому HTML не вставляем.
    return " · ".join(safe_tags)


def truncate(text: Any, length: int = 170) -> str:
    value = str(text or "").strip()
    return value if len(value) <= length else f"{value[: length - 1].rstrip()}…"


def task_by_id(tasks: list[dict[str, Any]], task_id: str | None) -> dict[str, Any] | None:
    return next((task for task in tasks if str(task.get("id")) == str(task_id)), None)


def proposal_counts(proposals: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for proposal in proposals:
        task_id = str(proposal.get("task_id", ""))
        counts[task_id] = counts.get(task_id, 0) + 1
    return counts


def render_page_intro(title: str, subtitle: str | None = None) -> None:
    st.title(title)
    if subtitle:
        st.markdown(f'<p class="bridge-muted">{subtitle}</p>', unsafe_allow_html=True)


def render_task_card(task: dict[str, Any], count: int, key_prefix: str) -> None:
    """Компактная карточка для каталогов и dashboard студента."""

    score = int(task.get("score", calculate_score(task)))
    with st.container(border=True):
        top, rating = st.columns([4, 1])
        with top:
            st.subheader(str(task.get("title") or "Задача без названия"))
            st.caption(f"{task.get('industry', 'Other')} · {status_level(score)}")
        with rating:
            st.metric("Готовность", f"{score}/100")
        st.write(truncate(task.get("context_and_need") or "Описание пока не указано."))
        if task.get("tags"):
            st.caption(f"Навыки: {tags_html(task.get('tags'))}")
        action, meta = st.columns([1, 2])
        with action:
            if st.button(
                "Открыть задачу",
                key=f"{key_prefix}_open_{task.get('id')}",
                use_container_width=True,
            ):
                go_to("Детали задачи", task_id=str(task.get("id")))
        with meta:
            st.caption(f"{count} отклик(ов)")


def render_business_dashboard(tasks: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> None:
    render_page_intro(
        "Добрый день 👋",
        "Управляйте задачами и предложениями студенческих команд",
    )
    published = [task for task in tasks if task.get("published")]
    average = round(sum(int(t.get("score", calculate_score(t))) for t in tasks) / len(tasks)) if tasks else 0
    cols = st.columns(3)
    cols[0].metric("Активные задачи", len(published))
    cols[1].metric("Количество откликов", len(proposals))
    cols[2].metric("Средняя готовность", f"{average}/100")

    st.write("")
    if st.button("+ Создать новую задачу", type="primary", use_container_width=True):
        reset_create_flow()
        go_to("Создать задачу")

    counts = proposal_counts(proposals)
    st.subheader("Мои задачи")
    for task in sorted(tasks, key=lambda item: str(item.get("created_at", "")), reverse=True)[:8]:
        score = int(task.get("score", calculate_score(task)))
        with st.container(border=True):
            main, rating, responses, action = st.columns([4, 1.2, 1.2, 1.2])
            with main:
                st.markdown(f"**{task.get('title') or 'Без названия'}**")
                state = "Опубликована" if task.get("published") else "Черновик"
                st.caption(f"{task.get('industry', 'Other')} · {state}")
            rating.metric("Рейтинг", f"{score}/100")
            responses.metric("Отклики", counts.get(str(task.get("id")), 0))
            with action:
                st.caption(status_level(score))
                if task.get("published") and st.button(
                    "Открыть", key=f"business_task_{task.get('id')}", use_container_width=True
                ):
                    go_to("Детали задачи", task_id=str(task.get("id")))

    st.subheader("Последние отклики")
    if not proposals:
        st.info("Новых откликов пока нет.")
        return
    for proposal in sorted(proposals, key=lambda item: str(item.get("created_at", "")), reverse=True)[:5]:
        task = task_by_id(tasks, str(proposal.get("task_id")))
        with st.container(border=True):
            text, state, action = st.columns([4, 1.4, 1])
            with text:
                st.markdown(f"**{proposal.get('team_name', 'Команда')}** · {task.get('title') if task else 'Задача'}")
                st.caption(truncate(proposal.get("idea"), 120))
            state.caption(proposal_status(str(proposal.get("status", "pending"))))
            with action:
                if st.button("Посмотреть", key=f"latest_proposal_{proposal.get('id')}"):
                    go_to("Отклики", proposal_id=str(proposal.get("id")))


def render_student_dashboard(tasks: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> None:
    render_page_intro(
        "Найдите реальную задачу для своей команды",
        "Выберите понятную задачу, разберитесь в контексте и предложите решение.",
    )
    published = sorted(
        [task for task in tasks if task.get("published")],
        key=lambda item: str(item.get("published_at", "")),
        reverse=True,
    )
    counts = proposal_counts(proposals)
    st.subheader("Новые задачи")
    for task in published[:3]:
        render_task_card(task, counts.get(str(task.get("id")), 0), "student_dashboard")
    if st.button("Смотреть все задачи", type="primary", use_container_width=True):
        go_to("Найти задачи")

    st.subheader("Мои предложения")
    render_student_proposals(tasks, proposals, compact=True)


def render_analysis(analysis: dict[str, Any]) -> None:
    st.subheader("Что мы поняли")
    st.write(analysis.get("summary") or "Краткое описание не сформировано.")
    with st.expander("Известные факты"):
        facts = analysis.get("known_facts") or []
        if facts:
            for fact in facts:
                st.markdown(f"- {fact}")
        else:
            st.caption("В черновике пока мало фактов.")
    with st.expander("Чего пока не хватает"):
        missing = analysis.get("missing_information") or []
        if missing:
            for item in missing:
                st.markdown(f"- {item}")
        else:
            st.caption("Основные сведения уже указаны.")


def render_create_task() -> None:
    render_page_intro(
        "Опишите проблему своими словами",
        "Не нужно писать идеальное ТЗ. Расскажите, что происходит сейчас и что хотите изменить — Bridge поможет сформулировать остальное.",
    )

    draft = st.session_state.draft
    if "draft_industry" not in st.session_state:
        st.session_state.draft_industry = (
            draft.get("industry") if draft.get("industry") in INDUSTRIES else "Manufacturing"
        )
    if "draft_description" not in st.session_state:
        st.session_state.draft_description = str(draft.get("raw_description", ""))
    with st.container(border=True):
        industry = st.selectbox(
            "Отрасль",
            INDUSTRIES,
            key="draft_industry",
        )
        raw_description = st.text_area(
            "Что вы хотите решить?",
            height=180,
            placeholder=(
                "Например: сотрудники вручную проверяют продукцию на брак. Хотим попробовать "
                "автоматизировать это с помощью AI, но пока не понимаем, какую именно задачу дать студентам."
            ),
            key="draft_description",
        )
        left, right = st.columns([3, 2])
        with left:
            analyze_clicked = st.button(
                "✨ Проанализировать с AI",
                type="primary",
                use_container_width=True,
            )
        with right:
            st.button(
                "Подставить demo-текст",
                use_container_width=True,
                on_click=load_demo_draft,
            )

    st.session_state.draft = {"industry": industry, "raw_description": raw_description}

    if analyze_clicked:
        if not raw_description.strip():
            st.error("Опишите проблему — поле не может быть пустым.")
        elif len(raw_description.strip()) < 20:
            st.error("Добавьте немного деталей: желательно не менее 20 символов.")
        else:
            with st.spinner("Анализируем задачу..."):
                analysis, used_fallback = analyze_draft(
                    industry,
                    raw_description.strip(),
                    api_key=get_api_key(st.session_state.openai_api_key),
                )
            st.session_state.analysis = analysis
            st.session_state.last_ai_fallback = used_fallback
            st.session_state.last_ai_error = get_last_error_message()
            st.session_state.clarifying_answers = {}
            st.session_state.current_card = None
            for key in list(st.session_state.keys()):
                if str(key).startswith(("answer_", "card_")):
                    del st.session_state[key]
            st.rerun()

    analysis = st.session_state.analysis
    if analysis:
        if st.session_state.last_ai_fallback:
            render_ai_warning()
        render_analysis(analysis)
        render_clarifying_form(industry, raw_description, analysis)

    if st.session_state.current_card:
        st.divider()
        render_editable_card()


def render_clarifying_form(
    industry: str,
    raw_description: str,
    analysis: dict[str, Any],
) -> None:
    questions = list(analysis.get("questions") or [])[:5]
    if len(questions) < 3:
        st.error("Не удалось подготовить уточняющие вопросы. Повторите анализ.")
        return

    st.subheader("Уточним несколько вещей")
    values: dict[str, str] = {}
    with st.form("clarifying_form"):
        for index, question in enumerate(questions):
            question_id = str(question.get("id") or f"question_{index}")
            st.markdown(f"**{index + 1}. {question.get('question', 'Уточните деталь')}**")
            reason = str(question.get("reason") or "Ответ сделает задачу понятнее.")
            points = int(question.get("score_value") or 0)
            st.caption(f"{reason} · до +{points} баллов")
            values[question_id] = st.text_area(
                "Ответ",
                value=str(st.session_state.clarifying_answers.get(question_id, "")),
                key=f"answer_{question_id}_{index}",
                label_visibility="collapsed",
                height=85,
            )
        submitted = st.form_submit_button(
            "Сформировать карточку",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        st.session_state.clarifying_answers = values
        with st.spinner("Формируем карточку..."):
            card, used_fallback = generate_task_card(
                industry,
                raw_description.strip(),
                analysis,
                values,
                api_key=get_api_key(st.session_state.openai_api_key),
            )
        card["industry"] = industry
        card["raw_description"] = raw_description.strip()
        card["confirmed"] = False
        card["published"] = False
        st.session_state.current_card = card
        st.session_state.last_ai_fallback = used_fallback
        st.session_state.last_ai_error = get_last_error_message()
        for key in list(st.session_state.keys()):
            if str(key).startswith("card_"):
                del st.session_state[key]
        st.rerun()


def render_score(task: dict[str, Any], confirmed: bool) -> None:
    score = calculate_score(task)
    level = get_level(score)
    label = "Рейтинг готовности" if confirmed else "Предварительный рейтинг"
    st.markdown(f'<div class="bridge-score">{label}: {score}/100 · {status_level(score)}</div>', unsafe_allow_html=True)
    st.progress(score / 100)

    complete = [label for field, label in SCORE_FIELD_LABELS.items() if is_field_complete(task.get(field))]
    st.caption(f"Заполнено: {len(complete)} из {len(WEIGHTS)} важных разделов")
    if complete:
        with st.expander("Что уже заполнено"):
            for item in complete:
                st.markdown(f"- {item}")

    recommendations = get_missing_recommendations(task)
    if recommendations:
        st.markdown("**Как улучшить задачу**")
        for item in recommendations:
            st.write(f"**+{item['points']}** · {item['message']}")
    next_level = points_to_next_level(score)
    st.info(next_level["message"])


def render_editable_card() -> None:
    card = dict(st.session_state.current_card or {})
    published = bool(card.get("published"))
    if st.session_state.last_ai_fallback:
        render_ai_warning()

    st.subheader("Карточка задачи")
    st.caption("Все поля можно проверить и отредактировать вручную.")

    widget_values: dict[str, str] = {}
    for field, label in CARD_FIELDS.items():
        widget_key = f"card_{field}"
        if widget_key not in st.session_state:
            st.session_state[widget_key] = str(card.get(field) or "")
        if field == "title":
            widget_values[field] = st.text_input(label, key=widget_key, disabled=published)
        else:
            widget_values[field] = st.text_area(
                label,
                key=widget_key,
                height=105,
                disabled=published,
            )

    if "card_tags" not in st.session_state:
        st.session_state.card_tags = ", ".join(str(tag) for tag in card.get("tags", []) if str(tag).strip())
    tags_text = st.text_input(
        "Теги (через запятую, максимум 5)",
        key="card_tags",
        disabled=published,
    )
    tags = [item.strip() for item in tags_text.split(",") if item.strip()][:5]

    changed = any(str(card.get(field) or "") != value for field, value in widget_values.items())
    changed = changed or list(card.get("tags") or []) != tags
    if changed and card.get("confirmed") and not published:
        card["confirmed"] = False
        st.info("Карточка изменилась — подтвердите её ещё раз перед публикацией.")
    card.update(widget_values)
    card["tags"] = tags
    card["score"] = calculate_score(card)
    card["level"] = get_level(card["score"])
    st.session_state.current_card = card

    render_score(card, bool(card.get("confirmed")))

    if published:
        st.success("Задача опубликована и появилась в каталоге.")
        left, right = st.columns(2)
        if left.button("Открыть в каталоге", type="primary", use_container_width=True):
            go_to("Детали задачи", task_id=str(card.get("id")))
        right.button(
            "Создать ещё одну задачу",
            use_container_width=True,
            on_click=reset_create_flow,
        )
        return

    if not card.get("confirmed"):
        st.caption("🟡 Черновик")
        if st.button(
            "✓ Всё верно — подтвердить карточку",
            type="primary",
            use_container_width=True,
            key="confirm_card",
        ):
            if not card.get("title", "").strip():
                st.error("Добавьте название задачи перед подтверждением.")
            else:
                card["confirmed"] = True
                st.session_state.current_card = card
                st.rerun()
    else:
        st.success("🟢 Подтверждено бизнесом")
        if st.button(
            "🚀 Опубликовать для студентов",
            type="primary",
            use_container_width=True,
            key="publish_card",
        ):
            publish_current_card(card)


def publish_current_card(card: dict[str, Any]) -> None:
    tasks = load_tasks()
    task = dict(card)
    task_id = str(task.get("id") or f"task-{uuid4().hex[:10]}")
    task.update(
        {
            "id": task_id,
            "score": calculate_score(task),
            "level": get_level(calculate_score(task)),
            "confirmed": True,
            "published": True,
            "created_at": task.get("created_at") or now_iso(),
            "published_at": now_iso(),
        }
    )
    existing_index = next((i for i, item in enumerate(tasks) if str(item.get("id")) == task_id), None)
    if existing_index is None:
        tasks.append(task)
    else:
        tasks[existing_index] = task
    save_tasks(tasks)
    st.session_state.current_card = task
    st.session_state.selected_task_id = task_id
    st.rerun()


def render_catalog(tasks: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> None:
    render_page_intro(
        "Реальные задачи от компаний",
        "Найдите тему, которая подходит вашей команде.",
    )
    published = [task for task in tasks if task.get("published")]
    search = st.text_input("Поиск по названию", placeholder="Например, контроль качества")
    filter_columns = st.columns(3)
    industries = ["Все"] + sorted({str(task.get("industry", "Other")) for task in published})
    industry = filter_columns[0].selectbox("Отрасль", industries)
    level = filter_columns[1].selectbox(
        "Уровень готовности",
        ["Все", "Черновик", "Рабочая", "Готовая", "Приоритетная"],
    )
    sort_order = filter_columns[2].selectbox("Сортировка", ["По рейтингу", "Сначала новые"])

    result = published
    if search.strip():
        query = search.casefold().strip()
        result = [task for task in result if query in str(task.get("title", "")).casefold()]
    if industry != "Все":
        result = [task for task in result if task.get("industry") == industry]
    if level != "Все":
        result = [
            task
            for task in result
            if get_level(int(task.get("score", calculate_score(task)))) == level
        ]
    if sort_order == "По рейтингу":
        result.sort(key=lambda item: int(item.get("score", calculate_score(item))), reverse=True)
    else:
        result.sort(key=lambda item: str(item.get("published_at", "")), reverse=True)

    st.caption(f"Найдено задач: {len(result)}")
    counts = proposal_counts(proposals)
    if not result:
        st.info("По выбранным фильтрам задач нет.")
    for task in result:
        render_task_card(task, counts.get(str(task.get("id")), 0), "catalog")


def render_task_detail(tasks: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> None:
    task = task_by_id(tasks, st.session_state.selected_task_id)
    if not task or not task.get("published"):
        st.error("Задача не найдена или ещё не опубликована.")
        if st.button("Вернуться в каталог"):
            go_to("Найти задачи" if st.session_state.role == STUDENT else "Каталог")
        return

    score = int(task.get("score", calculate_score(task)))
    st.caption(f"{task.get('industry', 'Other')} · {status_level(score)}")
    st.title(str(task.get("title") or "Задача"))
    metric_columns = st.columns(3)
    metric_columns[0].metric("Готовность", f"{score}/100")
    metric_columns[1].metric("Уровень", get_level(score))
    metric_columns[2].metric(
        "Отклики",
        sum(1 for proposal in proposals if str(proposal.get("task_id")) == str(task.get("id"))),
    )
    st.progress(score / 100)

    detail_fields = [
        ("Контекст и потребность", "context_and_need"),
        ("Для кого", "users"),
        ("Доступные данные", "data_and_materials"),
        ("Что нужно получить", "expected_result"),
        ("Критерии успеха", "success_criteria"),
        ("Ограничения", "constraints"),
        ("Формат взаимодействия", "business_contact"),
    ]
    for label, field in detail_fields:
        st.markdown(f"#### {label}")
        st.write(task.get(field) or "В задаче это не указано.")
    if task.get("tags"):
        st.caption(f"Теги: {tags_html(task.get('tags'))}")

    if st.session_state.role == STUDENT:
        render_student_ai(task)
        render_proposal_form(task)


def render_student_ai(task: dict[str, Any]) -> None:
    st.divider()
    with st.container(border=True):
        st.subheader("Не знакомы с этой отраслью?")
        st.write("Bridge объяснит контекст под ваш профиль, не меняя факты исходной задачи.")
        col_profile, col_depth = st.columns(2)
        profile = col_profile.selectbox(
            "Ваш профиль",
            PROFILES,
            index=PROFILES.index(st.session_state.selected_profile)
            if st.session_state.selected_profile in PROFILES
            else 0,
            key=f"profile_{task.get('id')}",
        )
        depth = col_depth.selectbox(
            "Глубина объяснения",
            DEPTHS,
            index=DEPTHS.index(st.session_state.selected_explanation_depth)
            if st.session_state.selected_explanation_depth in DEPTHS
            else 1,
            key=f"depth_{task.get('id')}",
        )
        st.session_state.selected_profile = profile
        st.session_state.selected_explanation_depth = depth
        if st.button(
            "✨ Объяснить мне задачу",
            type="primary",
            use_container_width=True,
            key=f"explain_{task.get('id')}",
        ):
            with st.spinner("Адаптируем объяснение..."):
                explanation, used_fallback = explain_task(
                    task,
                    profile,
                    depth,
                    api_key=get_api_key(st.session_state.openai_api_key),
                )
            st.session_state.student_explanation = explanation
            st.session_state.student_explanation_context = (
                str(task.get("id")),
                profile,
                depth,
                used_fallback,
            )
            st.session_state.last_ai_fallback = used_fallback
            st.session_state.last_ai_error = get_last_error_message()
            st.rerun()

    context = st.session_state.student_explanation_context
    explanation = st.session_state.student_explanation
    if explanation and context and context[:3] == (str(task.get("id")), profile, depth):
        if context[3]:
            render_ai_warning()
        st.subheader("Задача простыми словами")
        explanation_fields = [
            ("В чём основная проблема", "core_problem"),
            ("Почему это важно", "why_it_matters"),
            ("Что предстоит сделать команде", "what_team_should_do"),
            ("Ваша роль", "your_role"),
        ]
        for label, field in explanation_fields:
            st.markdown(f"**{label}**")
            st.write(explanation.get(field) or "В задаче это не указано.")
        terms = explanation.get("key_terms") or []
        if terms:
            with st.expander("Ключевые термины"):
                for term in terms[:5]:
                    st.markdown(f"**{term.get('term', 'Термин')}** — {term.get('explanation', '')}")
        first_steps = explanation.get("first_steps") or []
        if first_steps:
            st.markdown("**Первые шаги**")
            for index, step in enumerate(first_steps, 1):
                st.write(f"{index}. {step}")


def valid_http_url(value: str) -> bool:
    if not value.strip():
        return True
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def render_proposal_form(task: dict[str, Any]) -> None:
    st.divider()
    task_id = str(task.get("id"))
    visible_key = f"proposal_form_visible_{task_id}"
    if visible_key not in st.session_state:
        st.session_state[visible_key] = False
    if not st.session_state[visible_key]:
        if st.button(
            "Предложить решение",
            type="primary",
            use_container_width=True,
            key=f"show_proposal_form_{task_id}",
        ):
            st.session_state[visible_key] = True
            st.rerun()
        return

    st.subheader("Предложить решение")
    with st.form(f"proposal_form_{task.get('id')}"):
        team_name = st.text_input("Название команды *")
        idea = st.text_area("Идея решения *", height=120)
        plan = st.text_area("Короткий план *", height=120)
        deadline = st.text_input("Предполагаемый срок *", placeholder="Например, 3 недели")
        prototype_url = st.text_input("Ссылка на прототип", placeholder="https://...")
        submitted = st.form_submit_button(
            "Отправить предложение",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not all(value.strip() for value in [team_name, idea, plan, deadline]):
            st.error("Заполните все обязательные поля, отмеченные звёздочкой.")
        elif not valid_http_url(prototype_url):
            st.error("Ссылка должна начинаться с http:// или https://.")
        else:
            proposals = load_proposals()
            proposals.append(
                {
                    "id": f"proposal-{uuid4().hex[:10]}",
                    "task_id": str(task.get("id")),
                    "team_name": team_name.strip(),
                    "idea": idea.strip(),
                    "plan": plan.strip(),
                    "deadline": deadline.strip(),
                    "prototype_url": prototype_url.strip(),
                    "status": "pending",
                    "created_at": now_iso(),
                }
            )
            save_proposals(proposals)
            st.success("Предложение отправлено бизнесу.")


def render_student_proposals(
    tasks: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    *,
    compact: bool = False,
) -> None:
    if not compact:
        render_page_intro(
            "Мои предложения",
            "В демо-режиме здесь показаны предложения всех команд.",
        )
    if not proposals:
        st.info("Вы ещё не отправляли предложений.")
        return
    limit = 3 if compact else len(proposals)
    for proposal in sorted(proposals, key=lambda item: str(item.get("created_at", "")), reverse=True)[:limit]:
        task = task_by_id(tasks, str(proposal.get("task_id")))
        with st.container(border=True):
            st.markdown(f"**{proposal.get('team_name', 'Команда')}**")
            st.caption(f"{task.get('title') if task else 'Задача недоступна'} · {proposal_status(str(proposal.get('status', 'pending')))}")
            st.write(truncate(proposal.get("idea"), 180))
            if not compact and task and st.button(
                "Открыть задачу",
                key=f"student_proposal_task_{proposal.get('id')}",
            ):
                go_to("Детали задачи", task_id=str(task.get("id")))


def render_business_proposals(tasks: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> None:
    render_page_intro(
        "Отклики команд",
        "Решение всегда принимает представитель бизнеса вручную.",
    )
    labels = {
        "Все": None,
        "На рассмотрении": "pending",
        "Принятые": "accepted",
        "Отклонённые": "rejected",
    }
    chosen = st.selectbox("Фильтр", list(labels))
    expected = labels[chosen]
    filtered = [proposal for proposal in proposals if expected is None or proposal.get("status") == expected]

    selected_id = st.session_state.selected_proposal_id
    if selected_id:
        filtered.sort(key=lambda item: str(item.get("id")) == str(selected_id), reverse=True)

    if not filtered:
        st.info("В этой категории откликов пока нет.")
        return
    for proposal in filtered:
        task = task_by_id(tasks, str(proposal.get("task_id")))
        with st.container(border=True):
            st.subheader(str(proposal.get("team_name") or "Команда"))
            st.caption(f"{task.get('title') if task else 'Задача недоступна'} · {proposal_status(str(proposal.get('status', 'pending')))}")
            st.markdown("**Идея**")
            st.write(proposal.get("idea") or "Не указано")
            with st.expander("План и детали", expanded=str(proposal.get("id")) == str(selected_id)):
                st.markdown("**План**")
                st.write(proposal.get("plan") or "Не указано")
                st.markdown("**Срок**")
                st.write(proposal.get("deadline") or "Не указано")
                url = str(proposal.get("prototype_url") or "").strip()
                if url and valid_http_url(url):
                    st.link_button("Открыть прототип", url)
                elif url:
                    st.caption("Ссылка на прототип имеет неверный формат.")
                else:
                    st.caption("Ссылка на прототип не добавлена.")
            if proposal.get("status") == "pending":
                accept, reject = st.columns(2)
                if accept.button(
                    "✓ Принять",
                    type="primary",
                    use_container_width=True,
                    key=f"accept_{proposal.get('id')}",
                ):
                    update_proposal_status(str(proposal.get("id")), "accepted")
                if reject.button(
                    "Отклонить",
                    use_container_width=True,
                    key=f"reject_{proposal.get('id')}",
                ):
                    update_proposal_status(str(proposal.get("id")), "rejected")


def update_proposal_status(proposal_id: str, status: str) -> None:
    proposals = load_proposals()
    for proposal in proposals:
        if str(proposal.get("id")) == proposal_id:
            proposal["status"] = status
            proposal["updated_at"] = now_iso()
            break
    save_proposals(proposals)
    st.session_state.selected_proposal_id = proposal_id
    st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Bridge — задачи бизнеса для студентов",
        page_icon="🌉",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()
    apply_styles()
    render_sidebar()

    tasks = load_tasks()
    proposals = load_proposals()
    role = st.session_state.role
    page = st.session_state.page

    if page == "Детали задачи":
        render_task_detail(tasks, proposals)
    elif role == BUSINESS:
        if page == "Создать задачу":
            render_create_task()
        elif page == "Каталог":
            render_catalog(tasks, proposals)
        elif page == "Отклики":
            render_business_proposals(tasks, proposals)
        else:
            render_business_dashboard(tasks, proposals)
    else:
        if page == "Найти задачи":
            render_catalog(tasks, proposals)
        elif page == "Мои предложения":
            render_student_proposals(tasks, proposals)
        else:
            render_student_dashboard(tasks, proposals)


if __name__ == "__main__":
    main()
