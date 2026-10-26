import os
import unittest

os.environ.setdefault("VOICEBRIDGE_DISABLE_STARTUP_WARMUPS", "1")

import app as voicebridge


class SileroProsodyTests(unittest.TestCase):
    def test_greeting_identifies_the_hr_assistant_and_asks_relevance_directly(self):
        greeting = voicebridge._candidate_greeting("Испаняркасанов")
        self.assertEqual(greeting, "Добрый день! Это Испаняркасанов?")
        self.assertNotIn("Меня зовут", greeting)
        self.assertEqual(
            voicebridge.MANGO_GREETING_AFTER_NAME,
            "Я ассистент HR-менеджера Яны из компании «Лекс-Торг». "
            "Звоню по поводу вакансии. Подскажите, актуален ли вам сейчас поиск работы?",
        )
        self.assertEqual(
            voicebridge._silero_question_focus(voicebridge._prepare_silero_text(greeting)),
            "Добрый день! Это *Испаняркасанов*?",
        )

        prepared = voicebridge._prepare_silero_text(greeting)
        self.assertEqual(
            voicebridge._silero_type_for_segment(prepared),
            "st|general_q",
        )

    def test_each_question_in_a_compound_chunk_gets_its_own_type(self):
        self.assertEqual(
            voicebridge._silero_type_for_segment(
                "Добрый день. Как вас зовут? Вы учитесь очно или заочно?"
            ),
            "st|wh_q|alternative_q",
        )

    def test_non_question_chunk_leaves_silero_auto_classification_enabled(self):
        self.assertIsNone(voicebridge._silero_type_for_segment("Добрый день. Я звоню по работе."))

    def test_russian_questions_get_a_single_semantic_focus_marker(self):
        cases = {
            "Подскажите, актуально?":
                "Подскажите, *актуально*?",
            "У вас есть ноутбук или компьютер для удалённой работы?":
                "У вас есть ноутбук или *компьютер* для удалённой работы?",
            "Уточните, пожалуйста, в какое время вам удобно?":
                "Уточните, пожалуйста, в какое *время* вам удобно?",
            "Записать вас на собеседование на пятнадцать часов по московскому времени?":
                "*Записать* вас на собеседование на пятнадцать часов по московскому времени?",
            "Записать вас на это время?":
                "*Записать* вас на это время?",
            "Подтвердить запись?": "*Подтвердить* запись?",
            "Сможете подключиться?": "*Сможете* подключиться?",
            "Поняла, а вам сейчас самим актуален поиск работы?":
                "Поняла, а вам сейчас самим *актуален* поиск работы?",
            "Уточните ваш возраст и город проживания?":
                "Уточните ваш возраст и *город* проживания?",
            "Верно?": "*Верно*?",
            "Вы сегодня хотите прийти на собеседование? Верно?":
                "Вы сегодня *хотите* прийти на собеседование? *Верно*?",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(voicebridge._silero_question_focus(source), expected)

    def test_question_focus_survives_silero_text_normalization(self):
        prepared = voicebridge._prepare_silero_text("Вы *согласны* продолжить разговор?")
        self.assertEqual(prepared, "Вы *согласны* продолжить разговор?")
        self.assertEqual(
            voicebridge._silero_question_focus(prepared),
            prepared,
            "Explicitly marked focus must not be moved or duplicated.",
        )

    def test_every_question_in_a_multi_question_line_gets_its_own_focus(self):
        self.assertEqual(
            voicebridge._silero_question_focus(
                "В какие часы проходят занятия? Они будут пересекаться с рабочим графиком?"
            ),
            "В какие *часы* проходят занятия? Они будут *пересекаться* с рабочим графиком?",
        )


if __name__ == "__main__":
    unittest.main()
