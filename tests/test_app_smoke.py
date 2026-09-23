from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StreamlitSmokeTests(unittest.TestCase):
    def new_app(self) -> AppTest:
        return AppTest.from_file(str(PROJECT_ROOT / "app.py")).run(timeout=30)

    def test_onboarding_explains_both_roles(self) -> None:
        app = self.new_app()
        self.assertFalse(app.exception)
        self.assertTrue(
            any("Добро пожаловать в Bridge" in title.value for title in app.title)
        )
        labels = {button.label for button in app.button}
        self.assertIn("Создать задачу", labels)
        self.assertIn("Найти задачу", labels)

    def test_company_navigation_and_create_page_render_without_errors(self) -> None:
        app = self.new_app()

        create_button = next(
            button for button in app.button if button.label == "Создать задачу"
        )
        create_button.click().run(timeout=30)

        self.assertFalse(app.exception)
        self.assertTrue(
            any("Расскажите, что хотите улучшить" in title.value for title in app.title)
        )
        self.assertTrue(any(area.key == "draft_description" for area in app.text_area))

        next(button for button in app.button if button.label == "🏠 Главная").click().run(
            timeout=30
        )
        self.assertFalse(app.exception)
        self.assertTrue(any(title.value == "Ваши задачи" for title in app.title))

    def test_student_can_open_a_task_and_understand_next_action(self) -> None:
        app = self.new_app()
        next(button for button in app.button if button.label == "Найти задачу").click().run(
            timeout=30
        )
        self.assertFalse(app.exception)

        next(button for button in app.button if button.label == "Открыть задачу").click().run(
            timeout=30
        )
        self.assertFalse(app.exception)
        self.assertTrue(
            any("Что требуется от команды" in item.value for item in app.markdown)
        )
        self.assertTrue(
            any("Не разбираетесь в теме" in item.value for item in app.subheader)
        )

    def test_help_page_is_available_from_sidebar(self) -> None:
        app = AppTest.from_file(str(PROJECT_ROOT / "app.py")).run(timeout=30)
        next(
            button for button in app.button if button.label == "❓ Как это работает"
        ).click().run(timeout=30)
        self.assertFalse(app.exception)
        self.assertTrue(
            any(title.value == "Как работает Bridge" for title in app.title)
        )


if __name__ == "__main__":
    unittest.main()
