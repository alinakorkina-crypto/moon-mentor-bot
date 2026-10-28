import json
import unittest

from reading_engine_v8 import (
    FINAL_SCHEMA_V8,
    MODEL_NAME_V8,
    SYSTEM_PROMPT_V8,
    build_prompt_v8,
    calculate_cost_v8,
    clean_stars_v8,
    generate_reading_v8,
    infer_question_route_v8,
    prepare_cards_v8,
    route_rule_v8,
    hard_safety_issues_v8,
    style_warnings_v8,
    count_words_v8,
    validate_final_v8,
)


INITIATIVE_QUESTION = "Выйдет тот, о ком я думаю постоянно, первым на контакт?"
INITIATIVE_CARDS = [
    {"name": "Колесница", "general": "Инициатива без доказательства намерения."},
    {"name": "Башня", "general": "Противоречие, нарушающее прямое движение."},
    {"name": "Звезда", "general": "Надежда без подтверждённого действия."},
]

CHOICE_QUESTION = (
    "Мы тепло общаемся, но потом он надолго пропадает. "
    "Стоит ли продолжать этот контакт?"
)
CHOICE_CARDS = [
    {"name": "Солнце", "love": "Теплота общения."},
    {"name": "Отшельник", "love": "Дистанция и паузы."},
    {"name": "Умеренность", "love": "Подходящая мера участия."},
]

VALID_INITIATIVE_TEXT = """Скорее нет: в этом сочетании движение к первому контакту встречает слишком сильную помеху. Это не означает, что общения больше не будет, но оснований ждать именно самостоятельного шага другого человека здесь мало. Общий рисунок скорее указывает на задержку, чем на скорое сообщение.

Колесница задаёт движение, однако Башня нарушает его ход, а Звезда оставляет надежду без подтверждённого действия. Вместе они показывают разрыв между импульсом к контакту и его практическим продолжением. Надежда смягчает резкость сочетания, но не устраняет главное препятствие. Поэтому итог пока сдержанный: первый шаг с другой стороны выглядит маловероятным, хотя это символическое прочтение, а не установленный факт."""

VALID_CHOICE_TEXT = """Продолжать контакт имеет смысл, если вам подходит его нынешний ритм; одной теплоты для такого выбора мало. Вы описываете приятное общение и долгие исчезновения, поэтому вопрос здесь не только в ценности разговоров, но и в том, устраивает ли вас связь между ними.

Солнце поддерживает теплоту контакта, но Отшельник добавляет дистанцию, а Умеренность связывает эти полюса через меру участия. Общий рисунок не отменяет хороших моментов, однако и не превращает их в устойчивое общение. Причины пауз из карт неизвестны. Приятные разговоры важны, но терпеть неподходящий ритм ради них не требуется; выбор зависит от того, подходит ли вам контакт целиком."""


class PromptTests(unittest.TestCase):
    def test_prompt_has_no_style_example_or_extra_instructions(self):
        import reading_engine_v8 as engine
        prompt = build_prompt_v8(INITIATIVE_QUESTION, INITIATIVE_CARDS, 'initiative')
        self.assertFalse(hasattr(engine, 'STYLE_EXAMPLES_V8'))
        self.assertFalse(hasattr(engine, 'style_example_v8'))
        self.assertNotIn('Эталон', prompt)
        self.assertNotIn('Тема:', prompt)
        self.assertIn('Смысловые опоры для трактовки:', prompt)
        self.assertNotIn('единственные допустимые', prompt)
        self.assertTrue(prompt.endswith(
            'Сохрани порядок карт.\nСвяжи их в единый ответ на вопрос.\nНе добавляй неизвестные факты.'))
        self.assertIn('Не добавляй неизвестные факты', prompt)

    def test_one_call_system_requests_ready_text(self):
        self.assertIn("В начале дай понятный вывод по сочетанию карт", SYSTEM_PROMPT_V8)
        self.assertIn("Свяжи карты в одну живую историю", SYSTEM_PROMPT_V8)
        self.assertIn("Верни только JSON-объект с полем final_text.", SYSTEM_PROMPT_V8)
        for phrase in ("скорее да", "скорее нет", "пока неясно",
                       "саму тему движения", "Итог:", "Не используй конструкции"):
            self.assertNotIn(phrase, SYSTEM_PROMPT_V8)

    def test_schema_has_only_final_text(self):
        self.assertEqual(FINAL_SCHEMA_V8["required"], ["final_text"])
        self.assertFalse(FINAL_SCHEMA_V8["additionalProperties"])

    def test_prompt_contains_question_cards_positions_and_meanings(self):
        prompt = build_prompt_v8(
            INITIATIVE_QUESTION,
            INITIATIVE_CARDS,
            "initiative",
        )
        self.assertIn(INITIATIVE_QUESTION, prompt)
        for card in INITIATIVE_CARDS:
            self.assertIn(card["name"], prompt)
            self.assertIn(card["general"], prompt)
        self.assertIn("Правило этого маршрута", prompt)

    def test_initiative_prompt_forbids_redirect_to_user(self):
        prompt = build_prompt_v8(
            INITIATIVE_QUESTION,
            INITIATIVE_CARDS,
            "initiative",
        )
        self.assertIn("Оцени, поддерживает ли сочетание первый шаг другого человека; не переноси инициативу на пользователя", prompt)

    def test_love_prompt_does_not_require_accepting_bad_rhythm(self):
        prompt = build_prompt_v8(
            CHOICE_QUESTION,
            CHOICE_CARDS,
            "personal_choice",
            "love",
        )
        self.assertIn("не советуя терпеть неудобный ритм", prompt)


class ValidationTests(unittest.TestCase):
    def test_one_to_three_paragraphs_are_allowed_four_rejected(self):
        for count in (1, 2, 3, 4):
            with self.subTest(count=count):
                blocks = ['Колесница Башня Звезда ' + ' '.join(['слово'] * 15)]
                blocks.extend([' '.join(['слово'] * 18)] * (count - 1))
                if count == 1:
                    blocks[0] += ' ' + ' '.join(['слово'] * 40)
                text = '\n\n'.join(blocks)
                issues, _ = validate_final_v8(
                    {'final_text': text}, question=INITIATIVE_QUESTION,
                    cards=INITIATIVE_CARDS, route='initiative')
                self.assertEqual(any(i.startswith('paragraph_count:') for i in issues), count == 4)

    def test_cliches_produce_style_warnings_without_rejection(self):
        cases = (
            ('саму тему движения', 'cliche_movement_topic'),
            ('прямое развитие импульса', 'cliche_impulse_development'),
            ('состоявшийся практический шаг', 'cliche_practical_step'),
            ('возможность остаётся открытой', 'cliche_open_possibility'),
            ('нельзя считать подтверждённой', 'cliche_unconfirmed'),
            ('по символике сочетания нельзя уверенно сказать', 'cliche_symbolic_uncertainty'),
            ('Итог:', 'service_conclusion_label'),
        )
        for phrase, label in cases:
            with self.subTest(label=label):
                text = VALID_INITIATIVE_TEXT + ' ' + phrase.upper() + '.'
                issues, warnings = validate_final_v8(
                    {'final_text': text}, question=INITIATIVE_QUESTION,
                    cards=INITIATIVE_CARDS, route='initiative')
                self.assertEqual(issues, [])
                self.assertIn(label, warnings)

    def test_probability_word_repetition_including_inflections_and_synonyms(self):
        for text in ('Возможность есть, но возможности мало.',
                     'Потенциал сменяется потенциалом.',
                     'Вероятность зависит от вероятности.',
                     'Возможность, потенциал, вероятность.'):
            with self.subTest(text=text):
                self.assertIn('repeated_probability_words',
                              style_warnings_v8(text, INITIATIVE_QUESTION))
        for text in ('Возможность есть.', 'Потенциал есть.', 'Вероятность мала.',
                     'Скорее нет, пока движение остановлено.'):
            with self.subTest(text=text):
                self.assertNotIn('repeated_probability_words',
                                 style_warnings_v8(text, INITIATIVE_QUESTION))

    def test_three_paragraphs_are_not_a_hard_error(self):
        text = VALID_INITIATIVE_TEXT.replace('Поэтому итог', '\n\nПоэтому итог')
        issues, warnings = validate_final_v8(
            {'final_text': text}, question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS, route='initiative')
        self.assertEqual(issues, [])
        self.assertIn('preferred_paragraph_count:3', warnings)

    def test_zero_or_one_question_anywhere_is_allowed(self):
        for text in (VALID_INITIATIVE_TEXT,
                     'Что даёт сочетание? ' + VALID_INITIATIVE_TEXT):
            with self.subTest(question_count=text.count('?')):
                issues, _ = validate_final_v8(
                    {'final_text': text}, question=INITIATIVE_QUESTION,
                    cards=INITIATIVE_CARDS, route='initiative')
                self.assertEqual(issues, [])

    def test_word_count_boundaries(self):
        for count in (54, 55, 69, 70, 130, 131, 180, 181):
            with self.subTest(count=count):
                text = 'Колесница Башня Звезда\n\n' + ' '.join(['слово'] * (count - 3))
                self.assertEqual(count_words_v8(text), count)
                issues, warnings = validate_final_v8(
                    {'final_text': text}, question=INITIATIVE_QUESTION,
                    cards=INITIATIVE_CARDS, route='initiative')
                self.assertEqual(any(i.startswith('extreme_word_count:') for i in issues),
                                 count < 55 or count > 180)
                self.assertEqual(any(w.startswith('preferred_word_count:') for w in warnings),
                                 count < 70 or count > 130)

    def test_two_paragraphs_preferred_three_remain_allowed(self):
        for count in (1, 2, 3, 4):
            with self.subTest(count=count):
                text = '\n\n'.join([' '.join(['слово'] * 30)] * count)
                warnings = style_warnings_v8(text, INITIATIVE_QUESTION)
                self.assertEqual(any(w.startswith('preferred_paragraph_count:') for w in warnings),
                                 count != 2)

    def test_diagnosis_manipulation_and_guarantees_remain_rejected(self):
        for text, label in (('У вас травма.', 'diagnosis'),
                            ('Вызови ревность.', 'manipulation'),
                            ('Карты гарантируют результат.', 'guarantee')):
            with self.subTest(label=label):
                self.assertIn('unsafe:' + label, hard_safety_issues_v8(text))

    def test_valid_initiative_text_passes(self):
        issues, warnings = validate_final_v8(
            {"final_text": VALID_INITIATIVE_TEXT},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertEqual(issues, [])
        self.assertEqual(warnings, [])

    def test_valid_choice_text_passes(self):
        issues, warnings = validate_final_v8(
            {"final_text": VALID_CHOICE_TEXT},
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
            route="personal_choice",
        )
        self.assertEqual(issues, [])
        self.assertEqual(warnings, [])

    def test_missing_card_is_rejected(self):
        text = VALID_INITIATIVE_TEXT.replace("Звезда", "последняя карта")
        issues, _ = validate_final_v8(
            {"final_text": text},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("final_missing_cards:Звезда", issues)

    def test_two_questions_are_rejected(self):
        text = VALID_CHOICE_TEXT + " Что важно? Что дальше?"
        issues, _ = validate_final_v8(
            {"final_text": text},
            question=CHOICE_QUESTION,
            cards=CHOICE_CARDS,
            route="personal_choice",
        )
        self.assertIn("question_count:2", issues)

    def test_user_initiative_shift_is_rejected(self):
        text = VALID_INITIATIVE_TEXT + " Возможна ваша собственная инициатива."
        issues, _ = validate_final_v8(
            {"final_text": text},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("initiative_shift_to_user", issues)

    def test_mind_reading_is_rejected(self):
        self.assertIn("unsafe:mind_reading", hard_safety_issues_v8("Он хочет написать первым."))

    def test_certain_future_is_rejected(self):
        self.assertIn("unsafe:certain_future", hard_safety_issues_v8("Он обязательно выйдет на связь."))

    def test_probability_language_is_allowed(self):
        self.assertEqual(
            hard_safety_issues_v8("Возможно, человек выйдет на связь, но карты этого не гарантируют."),
            [],
        )

    def test_unexpected_field_is_rejected(self):
        issues, _ = validate_final_v8(
            {"final_text": VALID_INITIATIVE_TEXT, "analysis": "hidden"},
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            route="initiative",
        )
        self.assertIn("unexpected_fields:analysis", issues)

    def test_cleanup_removes_only_markdown_stars(self):
        source = "**Колесница** сохраняет текст, а *Звезда* — надежду."
        self.assertEqual(
            clean_stars_v8(source),
            "Колесница сохраняет текст, а Звезда — надежду.",
        )


EXPECTED_POSITIONS = {'initiative': ('Какой импульс или ожидание связано с возможностью контакта', 'Что делает эту возможность неясной или противоречивой', 'На какой внутренний или проверяемый ориентир переносится фокус'), 'personal_choice': ('Что делает рассматриваемый вариант привлекательным или значимым', 'Главное противоречие, цена или ограничение этого варианта', 'Какой критерий помогает пользователю определить собственную позицию')}


class OpenQuestionTests(unittest.TestCase):
    CASES = (
        ("Что мне важно понять сейчас?", "general"),
        ("Что мне важно понять сейчас?", "question"),
        ("Что происходит между нами?", "love"),
        ("Что мне мешает развиваться в работе?", "career"),
    )

    def cards(self):
        return [dict(card, love=f"Отношения: опора {index}",
                     career=f"Работа: опора {index}", question="Не значение карты")
                for index, card in enumerate(INITIATIVE_CARDS)]

    def test_open_questions_preserve_topics_positions_order_and_single_call(self):
        from unittest.mock import Mock
        for question, topic in self.CASES:
            with self.subTest(topic=topic):
                cards = self.cards()
                before = json.dumps(cards, ensure_ascii=False)
                model = Mock(return_value={'payload': {'final_text': VALID_INITIATIVE_TEXT}})
                result = generate_reading_v8(question=question, cards=cards,
                                             topic=topic, model_call=model)
                self.assertEqual(result['status'], 'success')
                self.assertEqual(result['route'], 'open_question')
                self.assertEqual(result['ai_requests'], 1)
                model.assert_called_once()
                prompt = model.call_args.args[0]
                self.assertIn(question, prompt)
                positions = ('основа ситуации', 'главное напряжение', 'направление развития')
                selected_topic = 'general' if topic == 'question' else topic
                lines = []
                for position, card in zip(positions, cards):
                    line = f"- {position}: {card['name']} — {card[selected_topic]}"
                    self.assertIn(line, prompt)
                    lines.append(prompt.index(line))
                    self.assertIn(card['name'], result['text'])
                self.assertEqual(lines, sorted(lines))
                self.assertNotIn('Не значение карты', prompt)
                self.assertEqual(json.dumps(cards, ensure_ascii=False), before)
                self.assertIn('Не превращай ответ в совет', prompt)

    def test_topic_specific_rules(self):
        self.assertIn('главный смысл сочетания', route_rule_v8('open_question', 'general'))
        self.assertEqual(route_rule_v8('open_question', 'general'),
                         route_rule_v8('open_question', 'question'))
        self.assertIn('не утверждая чужие чувства и мысли как факт',
                      route_rule_v8('open_question', 'love'))
        self.assertIn('сильную сторону, риск и направление',
                      route_rule_v8('open_question', 'career'))

    def test_existing_routes_and_positions_are_unchanged(self):
        for question, route in ((INITIATIVE_QUESTION, 'initiative'),
                                (CHOICE_QUESTION, 'personal_choice'),
                                ('Стоит ли менять работу?', 'personal_choice')):
            with self.subTest(route=route, question=question):
                self.assertEqual(infer_question_route_v8(question), route)
                for topic in ('general', 'love', 'career'):
                    prepared = prepare_cards_v8(self.cards(), route, topic)
                    self.assertEqual([c["name"] for c in prepared], [c["name"] for c in self.cards()])
                    self.assertEqual([c["position"] for c in prepared], list(EXPECTED_POSITIONS[route]))

    def test_open_question_rejects_missing_cards_and_mind_reading_without_retry(self):
        from unittest.mock import Mock
        for text, issue in (
            (VALID_INITIATIVE_TEXT.replace('Звезда', 'последняя карта'), 'final_missing_cards:Звезда'),
            (VALID_INITIATIVE_TEXT + ' Он думает о вас.', 'unsafe:mind_reading'),
            (VALID_INITIATIVE_TEXT + ' Она чувствует любовь.', 'unsafe:mind_reading'),
        ):
            with self.subTest(issue=issue):
                model = Mock(return_value={'payload': {'final_text': text}})
                result = generate_reading_v8(question='Что происходит между нами?',
                    cards=self.cards(), topic='love', model_call=model)
                model.assert_called_once()
                self.assertEqual(result['status'], 'rejected')
                self.assertIsNone(result['text'])
                self.assertIn(issue, result['issues'])

    def test_open_question_errors_never_retry(self):
        from unittest.mock import Mock
        for model in (Mock(side_effect=TimeoutError('offline timeout')),
                      Mock(return_value='{'), Mock(return_value=None)):
            with self.subTest(model=model):
                result = generate_reading_v8(question='Что мне важно понять сейчас?',
                    cards=self.cards(), model_call=model)
                model.assert_called_once()
                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['ai_requests'], 1)


class CostTests(unittest.TestCase):
    def test_terra_cost_includes_cached_input_and_output(self):
        cost = calculate_cost_v8(
            {
                "input_tokens": 2000,
                "cached_input_tokens": 500,
                "output_tokens": 200,
                "reasoning_tokens": 50,
            },
            MODEL_NAME_V8,
        )
        expected = (1500 * 2.00 + 500 * 0.20 + 200 * 12.00) / 1_000_000
        self.assertAlmostEqual(cost, expected)

    def test_reasoning_is_not_double_charged(self):
        plain = calculate_cost_v8(
            {"input_tokens": 1000, "output_tokens": 300, "reasoning_tokens": 0}
        )
        reasoned = calculate_cost_v8(
            {"input_tokens": 1000, "output_tokens": 300, "reasoning_tokens": 200}
        )
        self.assertEqual(plain, reasoned)

    def test_unknown_model_has_no_estimate(self):
        self.assertIsNone(
            calculate_cost_v8({"input_tokens": 100, "output_tokens": 100}, "unknown")
        )


class OrchestrationTests(unittest.TestCase):
    def test_success_uses_exactly_one_call(self):
        calls = []

        def model_call(prompt):
            calls.append(prompt)
            return {
                "payload": {"final_text": VALID_INITIATIVE_TEXT},
                "status": "completed",
                "model": MODEL_NAME_V8,
                "usage": {"input_tokens": 1800, "output_tokens": 220},
            }

        result = generate_reading_v8(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            model_call=model_call,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["ai_requests"], 1)
        self.assertEqual(result["status"], "success")
        self.assertIsNotNone(result["diagnostics"]["cost_usd"])

    def test_json_string_reply_uses_one_call(self):
        calls = []

        def model_call(prompt):
            calls.append(prompt)
            return json.dumps({"final_text": VALID_INITIATIVE_TEXT}, ensure_ascii=False)

        result = generate_reading_v8(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            model_call=model_call,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "success")

    def test_invalid_json_errors_without_retry(self):
        calls = []

        def model_call(prompt):
            calls.append(prompt)
            return "{"

        result = generate_reading_v8(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            model_call=model_call,
        )
        self.assertEqual(len(calls), 1)
        self.assertIsNone(result["text"])
        self.assertEqual(result["stage"], "generation")

    def test_unsafe_text_is_rejected_without_retry(self):
        unsafe = VALID_INITIATIVE_TEXT + " Он хочет написать первым."
        calls = []

        def model_call(prompt):
            calls.append(prompt)
            return {"payload": {"final_text": unsafe}}

        result = generate_reading_v8(
            question=INITIATIVE_QUESTION,
            cards=INITIATIVE_CARDS,
            model_call=model_call,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "rejected")
        self.assertIsNone(result["text"])
        self.assertEqual(result["rejected_text"], unsafe)
        self.assertIn("unsafe:mind_reading", result["issues"])

    def test_open_question_uses_one_call(self):
        calls = []
        def model_call(prompt):
            calls.append(prompt)
            return {"payload": {"final_text": VALID_INITIATIVE_TEXT}}
        result = generate_reading_v8(
            question="Расскажите об этом раскладе.",
            cards=INITIATIVE_CARDS,
            model_call=model_call,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["ai_requests"], 1)
        self.assertEqual(result["route"], "open_question")
        self.assertEqual(result["status"], "success")


class ResultContractTests(unittest.TestCase):
    def generate(self, reply):
        calls = []
        def call(prompt):
            calls.append(prompt)
            return reply
        result = generate_reading_v8(question=INITIATIVE_QUESTION,
                                     cards=INITIATIVE_CARDS, model_call=call)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("used_fallback", result)
        return result

    def test_rejected_text_preserves_every_character(self):
        raw = "  **Он хочет написать первым.**\r\n\r\n" + VALID_INITIATIVE_TEXT + "  \n"
        result = self.generate({"payload": {"final_text": raw}})
        self.assertEqual(result["status"], "rejected")
        self.assertIsNone(result["text"])
        self.assertEqual(result["rejected_text"], raw)

    def test_success_preserves_formatting_except_stars(self):
        raw = "  " + VALID_INITIATIVE_TEXT.replace("Колесница", "**Колесница**").replace("\n", "\r\n") + "  \n"
        result = self.generate({"payload": {"final_text": raw}})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["text"], raw.replace("**", ""))

    def test_json_and_payload_preserve_nbsp_markdown_and_crlf(self):
        raw = "  **Он\u00a0хочет написать первым.**\r\n\r\n" + VALID_INITIATIVE_TEXT + "  "
        for reply in ({"payload": {"final_text": raw}},
                      json.dumps({"final_text": raw}, ensure_ascii=False),
                      {"text": json.dumps({"final_text": raw}, ensure_ascii=False)}):
            with self.subTest(reply_type=type(reply).__name__):
                result = self.generate(reply)
                self.assertEqual(result["rejected_text"], raw)
                self.assertIsNone(result["text"])

    def test_invalid_json_preserves_raw_response(self):
        raw = '  {"final_text": "**искусственный\u00a0ответ**'
        result = self.generate({"raw_response_text": raw, "status": "completed"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["raw_response_text"], raw)
        self.assertIsNone(result["rejected_text"])

    def test_validation_does_not_mutate_payload(self):
        raw = "  " + VALID_INITIATIVE_TEXT.replace("\n", "\\n") + "  "
        payload = {"final_text": raw}
        issues, _ = validate_final_v8(payload, question=INITIATIVE_QUESTION,
                                     cards=INITIATIVE_CARDS, route="initiative")
        self.assertEqual(issues, [])
        self.assertEqual(payload, {"final_text": raw})

    def test_style_warning_keeps_original_answer(self):
        raw = VALID_INITIATIVE_TEXT.replace("\n\n", " ")
        result = self.generate({"payload": {"final_text": raw}})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["text"], raw)
        self.assertTrue(result["warnings"])

    def test_empty_invalid_refused_and_incomplete_responses(self):
        for reply in (None, "{", {"status": "completed", "payload": None},
                      {"status": "incomplete", "payload": {"final_text": VALID_INITIATIVE_TEXT}},
                      {"status": "ERROR", "error_type": "ReadTimeout"}):
            with self.subTest(reply=reply):
                result = self.generate(reply)
                self.assertEqual(result["status"], "error")
                self.assertIsNone(result["text"])
                self.assertTrue(result["issues"])

    def test_model_exception_is_reported_without_retry(self):
        calls = []
        def call(prompt):
            calls.append(prompt)
            raise RuntimeError("not for logs")
        result = generate_reading_v8(question=INITIATIVE_QUESTION,
                                     cards=INITIATIVE_CARDS, model_call=call)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["text"])
        self.assertEqual(result["diagnostics"]["error_type"], "RuntimeError")



if __name__ == "__main__":
    unittest.main()
