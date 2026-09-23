from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StreamlitSmokeTests(unittest.TestCase):
    def test_dashboard_and_create_page_render_without_errors(self) -> None:
        app = AppTest.from_file(str(PROJECT_ROOT / "app.py")).run(timeout=30)
        self.assertFalse(app.exception)

        create_button = next(
            button for button in app.button if button.label.endswith("Создать задачу")
        )
        create_button.click().run(timeout=30)

        self.assertFalse(app.exception)
        self.assertTrue(
            any(area.key == "draft_description" for area in app.text_area)
        )


if __name__ == "__main__":
    unittest.main()
