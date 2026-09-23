from __future__ import annotations

import unittest
from unittest.mock import patch

from services.fallback import (
    fallback_analysis,
    fallback_student_explanation,
    fallback_task_card,
)
from services.openai_service import explain_task
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
        self.assertTrue(explanation["example"])
        self.assertEqual(len(explanation["first_steps"]), 3)
        self.assertGreaterEqual(len(explanation["key_terms"]), 3)

    def test_all_three_depths_follow_the_same_contract(self) -> None:
        task = fallback_task_card()
        short = fallback_student_explanation(task, depth="Коротко")
        with_examples = fallback_student_explanation(task, depth="С примерами")
        technical = fallback_student_explanation(task, depth="Технически подробно")

        self.assertEqual(short["example"], "")
        self.assertEqual(short["key_terms"], [])
        self.assertTrue(with_examples["example"])
        self.assertTrue(technical["example"])
        for explanation in (short, with_examples, technical):
            self.assertEqual(len(explanation["first_steps"]), 3)
            self.assertLessEqual(len(explanation["key_terms"]), 5)

    def test_legacy_depth_values_remain_compatible(self) -> None:
        task = fallback_task_card()
        with patch("services.openai_service.get_api_key", return_value=None):
            understandable, used_fallback = explain_task(
                task, "Новичок", "Понятно"
            )
            technical, technical_fallback = explain_task(
                task, "Engineering", "Технически"
            )

        self.assertTrue(used_fallback)
        self.assertTrue(technical_fallback)
        self.assertTrue(understandable["example"])
        self.assertEqual(len(technical["first_steps"]), 3)


if __name__ == "__main__":
    unittest.main()
