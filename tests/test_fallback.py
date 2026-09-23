from __future__ import annotations

import unittest

from services.fallback import (
    fallback_analysis,
    fallback_student_explanation,
    fallback_task_card,
)
from utils.scoring import calculate_score


class FallbackFlowTests(unittest.TestCase):
    def test_analysis_returns_five_unique_questions(self) -> None:
        analysis = fallback_analysis()
        questions = analysis["questions"]
        self.assertEqual(len(questions), 5)
        self.assertEqual(len({question["id"] for question in questions}), 5)

    def test_demo_card_is_ready_for_showcase(self) -> None:
        card = fallback_task_card()
        self.assertEqual(calculate_score(card), 100)
        self.assertTrue(card["title"])
        self.assertTrue(card["tags"])

    def test_student_explanation_preserves_complete_structure(self) -> None:
        explanation = fallback_student_explanation(fallback_task_card())
        self.assertTrue(explanation["core_problem"])
        self.assertEqual(len(explanation["first_steps"]), 3)
        self.assertGreaterEqual(len(explanation["key_terms"]), 3)


if __name__ == "__main__":
    unittest.main()
