from __future__ import annotations

import unittest

from utils.scoring import (
    WEIGHTS,
    calculate_score,
    get_level,
    get_missing_recommendations,
    points_to_next_level,
)


class ScoringTests(unittest.TestCase):
    def test_empty_task_has_zero_score_and_all_recommendations(self) -> None:
        self.assertEqual(calculate_score({}), 0)
        self.assertEqual(len(get_missing_recommendations({})), len(WEIGHTS))

    def test_complete_task_has_one_hundred_points(self) -> None:
        task = {field: "Достаточно подробное значение" for field in WEIGHTS}
        self.assertEqual(calculate_score(task), 100)
        self.assertEqual(get_missing_recommendations(task), [])

    def test_readiness_levels_have_stable_boundaries(self) -> None:
        cases = {
            0: "Нужно уточнить",
            39: "Нужно уточнить",
            40: "Можно брать в работу",
            69: "Можно брать в работу",
            70: "Хорошо подготовлена",
            89: "Хорошо подготовлена",
            90: "Полностью готова",
            100: "Полностью готова",
        }
        for score, expected in cases.items():
            with self.subTest(score=score):
                self.assertEqual(get_level(score), expected)

    def test_next_level_hint_is_explainable(self) -> None:
        self.assertEqual(points_to_next_level(60)["points"], 10)
        self.assertEqual(points_to_next_level(80)["points"], 10)
        self.assertEqual(points_to_next_level(100)["points"], 0)


if __name__ == "__main__":
    unittest.main()
