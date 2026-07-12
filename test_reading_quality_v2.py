import unittest

from reading_quality_v2 import (
    build_repair_prompt,
    count_words,
    detect_quality_issues,
    repair_answer_if_needed,
)


class ReadingQualityV2Tests(unittest.TestCase):
    def test_detects_hidden_reason_for_other_person(self):
        issues = detect_quality_issues(
            "Паузы могут быть естественной частью его ритма и потребности "
            "в личном пространстве."
        )
        self.assertIn("hidden_reason", [item["type"] for item in issues])

    def test_detects_card_presented_as_proof(self):
        issues = detect_quality_issues(
            "Карта Солнце ярко подтверждает ваши слова о тёплом общении."
        )
        self.assertIn("unsupported_certainty", [item["type"] for item in issues])

    def test_detects_markdown_emphasis(self):
        issues = detect_quality_issues("Важно *зафиксировать* условия письменно.")
        self.assertIn("markdown_emphasis", [item["type"] for item in issues])

    def test_detects_excessive_length(self):
        text = " ".join(["слово"] * 261)
        issues = detect_quality_issues(text, max_words=260)
        self.assertIn("too_long", [item["type"] for item in issues])

    def test_clean_answer_has_no_issue(self):
        text = (
            "Вы сообщили, что общение бывает тёплым, но затем следуют долгие паузы. "
            "Солнце символически выделяет ценность контакта, а Отшельник — дистанцию. "
            "Оцените, подходит ли вам такой ритм."
        )
        self.assertEqual(detect_quality_issues(text), [])

    def test_repair_prompt_contains_question_and_issue(self):
        issues = detect_quality_issues(
            "Карта Солнце подтверждает, что тепло искреннее."
        )
        prompt = build_repair_prompt(
            "Карта Солнце подтверждает, что тепло искреннее.",
            issues,
            user_question="Стоит ли продолжать контакт?",
        )
        self.assertIn("Стоит ли продолжать контакт?", prompt)
        self.assertIn("unsupported_certainty", prompt)
        self.assertIn("Карты дают символический ракурс", prompt)

    def test_clean_answer_does_not_call_ai(self):
        calls = []

        def fake_ai(prompt):
            calls.append(prompt)
            return "Не должно вызываться"

        answer = "Солнце символически выделяет тепло, указанное в вашем вопросе."
        result, issues, repaired = repair_answer_if_needed(
            answer,
            user_question="Продолжать контакт?",
            ai_call=fake_ai,
        )
        self.assertEqual(result, answer)
        self.assertEqual(issues, [])
        self.assertFalse(repaired)
        self.assertEqual(calls, [])

    def test_problem_answer_calls_ai_once(self):
        calls = []

        def fake_ai(prompt):
            calls.append(prompt)
            return "Исправленный ответ."

        result, issues, repaired = repair_answer_if_needed(
            "Карта Солнце подтверждает искреннее тепло.",
            user_question="Продолжать контакт?",
            ai_call=fake_ai,
        )
        self.assertEqual(result, "Исправленный ответ.")
        self.assertTrue(issues)
        self.assertTrue(repaired)
        self.assertEqual(len(calls), 1)

    def test_count_words_handles_russian_text(self):
        self.assertEqual(count_words("Один короткий ответ — без повторов."), 6)


if __name__ == "__main__":
    unittest.main()
