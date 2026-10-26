import os
import unittest
from unittest.mock import patch

os.environ.setdefault("VOICEBRIDGE_DISABLE_STARTUP_WARMUPS", "1")

import app as voicebridge


class DialogueScenarioTests(unittest.TestCase):
    def setUp(self):
        self.candidate = voicebridge._new_candidate_record("")

    def turn(self, stage, transcript, history=None):
        return voicebridge.MangoCallService._script_candidate_reply(
            stage,
            transcript,
            self.candidate,
            history or [],
            {},
        )

    def test_dialogue_starts_with_jana_and_relevance_question(self):
        self.assertIn("ассистент HR-менеджера Яны", voicebridge.MANGO_GREETING)
        self.assertNotIn("Меня зовут Яна", voicebridge.MANGO_GREETING)
        self.assertIn("актуален", voicebridge.MANGO_GREETING.lower())
        self.assertNotIn("согласны", voicebridge.MANGO_GREETING.lower())
        reply, stage, hangup = self.turn("relevance", "Да, актуально")
        self.assertEqual((stage, hangup), ("age_city", False))
        self.assertTrue(self.candidate["consent_to_continue"])
        self.assertEqual(reply, voicebridge.MANGO_INTERESTED_WITH_AGE)

    def test_relevance_refusal_ends_without_collecting_candidate_turns(self):
        reply, stage, hangup = self.turn("relevance", "Нет, не актуально")
        self.assertEqual((stage, hangup), ("finished", True))
        self.assertEqual(self.candidate["result"], "declined_at_opening")
        self.assertEqual(self.candidate["turns"], [])

    def test_candidate_report_contains_the_full_name(self):
        self.candidate["name"] = "Иванов Иван Иванович"
        report = voicebridge._refresh_candidate_report(self.candidate)
        self.assertIn("ФИО: Иванов Иван Иванович", report)

    def test_candidate_report_omits_unprovided_fields_but_keeps_explicit_answers(self):
        self.candidate.update({
            "age_city": "Мне двадцать два, живу в Казани",
            "computer": "есть",
            "citizenship": "не указано",
            "employment": "Не учусь и не работаю",
        })
        report = voicebridge._refresh_candidate_report(self.candidate)
        self.assertIn("Возраст и город: 22, Казани", report)
        self.assertIn("Компьютер или ноутбук: есть", report)
        self.assertIn("Учёба и работа: учёба: нет; работа: нет", report)
        self.assertNotIn("не указано", report.lower())
        self.assertNotIn("Гражданство РФ:", report)
        self.assertNotIn("Формат учёбы:", report)
        self.assertNotIn("Собеседование:", report)

    def test_candidate_report_preserves_normalized_city(self):
        self.candidate["age_city"] = "22, Казани"
        report = voicebridge._refresh_candidate_report(self.candidate)
        self.assertIn("Возраст и город: 22, Казани", report)

    def test_personalized_greeting_confirms_candidate_name(self):
        greeting = voicebridge._candidate_greeting("Иванов Иван Иванович")
        self.assertEqual(greeting, "Добрый день! Это Иванов Иван Иванович?")
        reply, stage, hangup = self.turn("name_confirm", "Да, это я")
        self.assertEqual((stage, hangup), ("relevance", False))
        self.assertIn("ассистент HR-менеджера Яны", reply)
        self.assertEqual(voicebridge._candidate_greeting(""), voicebridge.MANGO_GREETING)

    def test_wrong_named_recipient_is_asked_about_their_own_interest(self):
        self.candidate["name"] = "Иванов Иван Иванович"
        reply, stage, hangup = self.turn("name_confirm", "Нет, это не я")
        self.assertEqual((stage, hangup), ("alternate_candidate_interest", False))
        self.assertIn("вам самим", reply.lower())
        self.assertEqual(self.candidate["name"], "")
        reply, stage, hangup = self.turn("alternate_candidate_interest", "Да, актуально")
        self.assertEqual((stage, hangup), ("alternate_candidate_name", False))
        self.assertIn("обращаться", reply.lower())
        reply, stage, hangup = self.turn("alternate_candidate_name", "Мария")
        self.assertEqual((stage, hangup), ("relevance", False))
        self.assertEqual(self.candidate["name"], "Мария")

    def test_affirmative_after_conditions_repeat_advances_without_reasking(self):
        self.candidate.update({
            "consent_to_continue": True,
            "conditions_spoken": True,
            "age_city": "22, Казань",
            "computer": "есть",
            "citizenship": "да",
            "employment": "нет",
        })
        repeated_line = voicebridge.MANGO_JOB_CONDITIONS
        reply, stage, hangup = self.turn(
            "conditions",
            "Я рассматриваю",
            [{"role": "Яна", "text": repeated_line}],
        )
        self.assertEqual((stage, hangup), ("zoom", False))
        self.assertEqual(reply, voicebridge.MANGO_ZOOM)
        self.assertNotEqual(reply, voicebridge.MANGO_JOB_CONDITIONS)

    def test_telegram_recipients_are_numeric_and_deduplicated(self):
        self.assertEqual(
            voicebridge._telegram_chat_ids("123456789, -1001234567890 123456789"),
            ["123456789", "-1001234567890"],
        )
        with self.assertRaises(ValueError):
            voicebridge._telegram_chat_ids("123456789, @username")

    def test_telegram_report_sends_to_each_configured_chat(self):
        class Response:
            ok = True

            @staticmethod
            def json():
                return {"ok": True}

        with patch.object(voicebridge.requests, "post", return_value=Response()) as post:
            failures = voicebridge._send_telegram_messages(
                "123:secret",
                ["111", "222"],
                "Статус звонка",
            )
        self.assertEqual(failures, [])
        self.assertEqual(post.call_count, 2)

    def test_test_dialog_report_is_sent_to_telegram_with_candidate_fields(self):
        candidate = voicebridge._new_candidate_record("+79990000000", "Иванов Иван")
        candidate.update({
            "consent_to_continue": True,
            "result": "qualified",
            "scheduled_at": "2030-10-02T12:00:00+03:00",
            "scheduled_event_id": "test-event-1",
        })
        candidate["age_city"] = "Мне двадцать два, живу в Казани"
        voicebridge._record_candidate_turn(candidate, "age_city", "Мне двадцать два, живу в Казани")
        with patch.object(voicebridge, "_send_telegram_messages", return_value=[]) as send:
            result = voicebridge.send_dialog_test_report({
                "candidate": candidate,
                "bot_token": "123:token",
                "chat_ids": "111, 222",
            })
        self.assertTrue(result["ok"])
        self.assertEqual(result["recipients"], 2)
        self.assertIn("ФИО: Иванов Иван", result["report"])
        self.assertIn("Возраст и город: 22, Казани", result["report"])
        self.assertNotIn("Результат:", result["report"])
        send.assert_called_once_with("123:token", ["111", "222"], result["report"])

    def test_test_dialog_report_is_rejected_until_candidate_agrees_and_books(self):
        candidate = voicebridge._new_candidate_record("+79990000000", "Иванов Иван")
        voicebridge._record_candidate_turn(candidate, "age_city", "Мне двадцать два, живу в Казани")
        with patch.object(voicebridge, "_send_telegram_messages") as send:
            with self.assertRaises(voicebridge.HTTPException) as error:
                voicebridge.send_dialog_test_report({
                    "candidate": candidate,
                    "bot_token": "123:token",
                    "chat_ids": "111",
                })
        self.assertEqual(error.exception.status_code, 409)
        send.assert_not_called()

    def test_candidate_report_never_includes_a_qualified_result_line(self):
        candidate = voicebridge._new_candidate_record("+79990000000", "Иванов Иван")
        candidate["result"] = "qualified"
        candidate["scheduled_at"] = "2030-10-02T12:00:00+03:00"
        report = voicebridge._refresh_candidate_report(candidate)
        self.assertIn("Собеседование:", report)
        self.assertNotIn("Результат:", report)

    def test_appointment_sms_has_confirmed_time_and_telegram_contact(self):
        scheduled = voicebridge.datetime.combine(
            voicebridge.calendar_service.today() + voicebridge.timedelta(days=1),
            voicebridge.datetime_time(16, 20),
            voicebridge.calendar_service.tz,
        )
        message = voicebridge.MangoCallService._appointment_sms({"scheduled_at": scheduled.isoformat()})
        self.assertIn("Zoom", message)
        self.assertIn("@xxhr1", message)
        self.assertIn("по московскому времени", message)

    def test_telegram_username_repeat_only_repeats_and_spells_the_handle(self):
        reply = voicebridge.MangoCallService._script_objection_reply(
            "Я не понял никнейм, можете повторить?"
        )
        self.assertIsNotNone(reply)
        self.assertIn("икс", reply.lower())
        self.assertIn("эйч", reply.lower())
        self.assertIn("ар", reply.lower())
        self.assertNotIn("после того как найдёте", reply.lower())
        self.assertNotIn("подробности", reply.lower())

    def test_telegram_explains_case_and_latin_letter_names_without_repeating_the_call_script(self):
        cases = (
            ("В нике писать большими или маленькими буквами?", "регистр", "не русская эн"),
            ("Буква R — это русская или английская?", "английская ар", "не русская эр"),
            ("H как какая буква?", "английская эйч", "не русская эн"),
        )
        for question, expected, clarification in cases:
            with self.subTest(question=question):
                reply = voicebridge.MangoCallService._script_objection_reply(question)
                self.assertIn(expected, reply.lower())
                self.assertIn(clarification, reply.lower())
                self.assertNotIn("заработная плата", reply.lower())
        reply, stage, hangup = voicebridge.MangoCallService._telegram_stage_reply(
            "telegram_handle",
            "R, как какая?",
            self.candidate,
        )
        self.assertEqual((stage, hangup), ("telegram_handle", False))
        self.assertIn("английская ар", reply.lower())
        self.assertIn("удалось найти аккаунт", reply.lower())

    def test_zoom_invitation_always_says_duration_before_asking_to_join(self):
        duration = voicebridge.MANGO_ZOOM.lower().index("десять-пятнадцать минут")
        invitation = voicebridge.MANGO_ZOOM.lower().index("сможете подключиться")
        self.assertLess(duration, invitation)

    def test_targeted_salary_repeat_uses_selected_llm_reply_and_does_not_recite_vacancy(self):
        config = {
            "llm_base_url": "https://api.openai.com/v1",
            "llm_api_key": "test-key",
            "llm_model": "test-model",
        }
        model_reply = "В первый месяц в среднем около ста десяти тысяч рублей."
        with patch.object(
            voicebridge.llm_service,
            "chat",
            return_value={"text": (
                '{"intent":"other_question","answer_slot":"","normalized_answer":"",'
                f'"short_reply":"{model_reply}"' + "}"
            )},
        ) as chat:
            intent = voicebridge.call_service._classify_candidate_intent(
                "conditions",
                "Ещё раз, какая средняя заработная плата?",
                [{"role": "Яна", "text": voicebridge.MANGO_JOB_CONDITIONS}],
                config,
            )
        chat.assert_called_once()
        self.assertEqual(intent["short_reply"], model_reply)
        reply, stage, hangup = voicebridge.MangoCallService._script_candidate_reply(
            "conditions",
            "Ещё раз, какая средняя заработная плата?",
            self.candidate,
            [{"role": "Яна", "text": voicebridge.MANGO_JOB_CONDITIONS}],
            intent,
        )
        self.assertEqual((stage, hangup), ("conditions", False))
        self.assertIn("в первый месяц", reply.lower())
        self.assertNotIn("пять на два", reply.lower())
        self.assertNotIn("трудоустройство", reply.lower())

    def test_interview_reminder_is_scheduled_ten_minutes_before_and_deduplicated(self):
        now = voicebridge.calendar_service.now()
        start = now + voicebridge.timedelta(minutes=25)
        candidate = {
            "call_id": "reminder-test",
            "scheduled_event_id": "event-reminder-test",
            "scheduled_at": start.isoformat(timespec="minutes"),
            "name": "Иванов Иван Иванович",
            "number": "+79990000000",
        }
        service = voicebridge.InterviewReminderService(voicebridge.calendar_service)
        with patch.object(voicebridge.calendar_service, "now", return_value=now), patch.object(
            voicebridge, "Timer"
        ) as timer_factory:
            self.assertTrue(service.schedule(candidate, {
                "telegram_bot_token": "123:token",
                "telegram_chat_ids": "111",
            }))
            stored_start = voicebridge.datetime.fromisoformat(candidate["scheduled_at"])
            expected_delay = (stored_start - now).total_seconds() - 10 * 60
            self.assertAlmostEqual(timer_factory.call_args.args[0], expected_delay, delta=0.01)
            self.assertTrue(service.schedule(candidate, {
                "telegram_bot_token": "123:token",
                "telegram_chat_ids": "111",
            }))
            timer_factory.assert_called_once()
            timer_factory.return_value.start.assert_called_once()

    def test_interview_reminder_names_candidate_and_appointment(self):
        now = voicebridge.calendar_service.now()
        start = now + voicebridge.timedelta(minutes=10)
        message = voicebridge.InterviewReminderService._message(
            {"name": "Иванов Иван", "number": "+79990000000"}, start, now
        )
        self.assertIn("Иванов Иван", message)
        self.assertIn("+79990000000", message)
        self.assertIn(start.strftime("%H:%M"), message)
        self.assertIn("через 10 минут", message)

    def test_candidate_can_cancel_scheduling_before_booking(self):
        reply, stage, hangup = self.turn("schedule", "Я передумал, не хочу записываться")
        self.assertEqual((stage, hangup), ("finished", True))
        self.assertEqual(self.candidate["result"], "declined_scheduling")
        self.assertIn("отменяю", reply.lower())

    def test_candidate_can_cancel_after_booking_and_slot_is_released(self):
        self.candidate["scheduled_at"] = "2030-10-02T12:00:00+03:00"
        self.candidate["scheduled_event_id"] = "event-test"
        with patch.object(voicebridge.calendar_service, "delete", return_value={} ) as delete:
            reply, stage, hangup = self.turn("telegram", "Я передумала, не хочу идти на собеседование")
        self.assertEqual((stage, hangup), ("finished", True))
        self.assertEqual(self.candidate["result"], "declined_scheduled")
        delete.assert_called_once_with("event-test")

    def test_rejected_earlier_slot_searches_after_requested_time(self):
        day = voicebridge.calendar_service.today()
        starts = [
            ("10:40", "earlier"),
            ("11:20", "next"),
            ("11:40", "later"),
        ]
        slots = [
            {
                "start": voicebridge.datetime.combine(
                    day,
                    voicebridge.datetime.strptime(clock, "%H:%M").time(),
                    voicebridge.calendar_service.tz,
                ).isoformat(timespec="minutes"),
                "time": clock,
            }
            for clock, _ in starts
        ]
        self.candidate["schedule_request"] = "к одиннадцати"
        self.candidate["offered_slots"] = [slots[0]["start"]]
        with patch.object(voicebridge.calendar_service, "available_slots", return_value=slots), patch.object(
            voicebridge.calendar_service,
            "offer_text",
            return_value="Предлагаю ближайшее время после одиннадцати.",
        ):
            reply, stage, hangup = self.turn("schedule", "Нет, десять сорок тоже неудобно")
        self.assertEqual((stage, hangup), ("schedule", False))
        self.assertEqual(reply, "Предлагаю ближайшее время после одиннадцати.")
        self.assertEqual(self.candidate["offered_slots"], [slots[1]["start"]])

    def test_age_and_city_are_compactly_extracted_without_age_screening(self):
        value = voicebridge._extract_candidate_age_city("Мне тридцать один год, живу в Санкт-Петербурге")
        self.assertEqual(value, "31, Санкт-Петербург")
        reply, stage, hangup = self.turn("age_city", "Мне 31 год, живу в Санкт-Петербурге")
        self.assertEqual(stage, "computer")
        self.assertFalse(hangup)
        self.assertEqual(self.candidate["result"], "in_progress")

    def test_mobile_only_is_not_mistaken_for_a_computer(self):
        for phrase in ("У меня только телефон", "Есть только планшет", "Пользуюсь только айпадом"):
            with self.subTest(phrase=phrase):
                self.candidate = voicebridge._new_candidate_record("")
                _reply, stage, hangup = self.turn("computer", phrase)
                self.assertEqual(stage, "finished")
                self.assertTrue(hangup)
                self.assertEqual(self.candidate["result"], "declined_no_device")
                voicebridge._refresh_candidate_report(self.candidate)
                self.assertIn("Компьютер или ноутбук: нет", self.candidate["report"])

    def test_computer_or_laptop_counts_even_with_other_device_negated(self):
        for phrase in (
            "Есть ноутбук",
            "У меня компьютер",
            "Да, есть",
            "Да, конечно, есть",
            "Есть, конечно",
            "Компьютера нет, но ноутбук есть",
            "Да, компьютер есть, а телефона нет",
        ):
            with self.subTest(phrase=phrase):
                self.candidate = voicebridge._new_candidate_record("")
                _reply, stage, hangup = self.turn("computer", phrase)
                self.assertEqual(stage, "citizenship")
                self.assertFalse(hangup)
                self.assertEqual(self.candidate["computer"], "есть")

    def test_unclear_device_answer_repeats_only_the_current_question(self):
        reply, stage, hangup = self.turn("computer", "Иногда беру телефон с собой")
        self.assertEqual(stage, "computer")
        self.assertFalse(hangup)
        self.assertEqual(reply, voicebridge.MANGO_COMPUTER)

    def test_mixed_study_and_work_is_preserved_as_separate_facts(self):
        self.candidate = voicebridge._new_candidate_record("")
        _reply, stage, _hangup = self.turn("employment", "Не учусь, но сейчас работаю")
        self.assertEqual(stage, "work_details")
        report = voicebridge._refresh_candidate_report(self.candidate)
        self.assertIn("Учёба и работа: учёба: нет; работа: есть", report)

        self.candidate = voicebridge._new_candidate_record("")
        _reply, stage, _hangup = self.turn("employment", "Учусь заочно и параллельно работаю")
        self.assertEqual(stage, "study_schedule")
        report = voicebridge._refresh_candidate_report(self.candidate)
        self.assertIn("Учёба и работа: учёба: есть; работа: есть", report)
        self.assertIn("Формат учёбы: заочно", report)

    def test_finished_education_is_not_reported_as_current_study(self):
        self.candidate = voicebridge._new_candidate_record("")
        _reply, stage, _hangup = self.turn(
            "employment",
            "Учёбу уже закончил, сейчас работаю",
        )
        self.assertEqual(stage, "work_details")
        report = voicebridge._refresh_candidate_report(self.candidate)
        self.assertIn("Учёба и работа: учёба: нет; работа: есть", report)

        self.candidate = voicebridge._new_candidate_record("")
        _reply, stage, _hangup = self.turn(
            "employment",
            "Университет окончил, но сейчас учусь заочно",
        )
        self.assertEqual(stage, "study_schedule")
        self.assertIn("Учёба и работа: учёба: есть", voicebridge._refresh_candidate_report(self.candidate))

    def test_non_overlap_answer_does_not_cause_false_rejection(self):
        self.candidate["has_work"] = False
        reply, stage, hangup = self.turn("study_schedule", "Нет, пары с работой не пересекаются")
        self.assertFalse(hangup)
        self.assertNotEqual(stage, "finished")
        self.assertNotEqual(self.candidate["result"], "declined_study_schedule")

    def test_explicit_schedule_overlap_is_rejected(self):
        reply, stage, hangup = self.turn("study_schedule", "Пары с двенадцати до пятнадцати, они будут пересекаться")
        self.assertEqual(stage, "finished")
        self.assertTrue(hangup)
        self.assertEqual(self.candidate["result"], "declined_study_schedule")

    def test_study_outside_work_hours_continues_without_false_rejection(self):
        self.candidate["has_work"] = False
        _reply, stage, hangup = self.turn(
            "study_schedule",
            "Учусь очно, пары с восьми до девяти утра, к работе не пересекаются",
        )
        self.assertFalse(hangup)
        self.assertNotEqual(stage, "finished")
        self.assertNotEqual(self.candidate["result"], "declined_study_schedule")

    def test_refusal_and_end_call_happen_only_on_the_relevant_turn(self):
        reply, stage, hangup = self.turn("relevance", "Нет, работа уже не актуальна")
        self.assertEqual(stage, "finished")
        self.assertTrue(hangup)
        self.assertEqual(self.candidate["result"], "declined_at_opening")

        self.candidate = voicebridge._new_candidate_record("")
        _reply, stage, hangup = self.turn("conditions", "Нет, такие условия мне не подходят")
        self.assertEqual(stage, "conditions_followup")
        self.assertFalse(hangup)
        _reply, stage, hangup = self.turn("conditions_followup", "Не подходит график и зарплата")
        self.assertEqual(stage, "finished")
        self.assertTrue(hangup)

        self.candidate = voicebridge._new_candidate_record("")
        _reply, stage, hangup = self.turn("zoom", "Нет, к Zoom подключиться не смогу")
        self.assertEqual(stage, "finished")
        self.assertTrue(hangup)
        self.assertEqual(self.candidate["result"], "declined_zoom")

    def test_telegram_acceptance_finishes_and_marks_candidate_qualified(self):
        reply, stage, hangup = self.turn("telegram", "Да, смогу найти")
        self.assertEqual(stage, "telegram_permission")
        self.assertFalse(hangup)
        self.assertIn("когда можно продиктовать", reply.lower())

        reply, stage, hangup = self.turn("telegram_permission", "Сейчас можно")
        self.assertEqual(stage, "telegram_handle")
        self.assertFalse(hangup)
        self.assertIn("первая буква", reply.lower())

        reply, stage, hangup = self.turn("telegram_handle", "Да, нашла")
        self.assertEqual(stage, "telegram_send")
        self.assertFalse(hangup)
        self.assertIn("отправьте", reply.lower())

        reply, stage, hangup = self.turn("telegram_send", "Отправила сообщение")
        self.assertEqual(stage, "finished")
        self.assertTrue(hangup)
        self.assertEqual(self.candidate["result"], "qualified")
        self.assertIn("до скорой встречи", reply.lower())

    def test_telegram_no_and_repeat_replay_only_the_spelling_and_keep_call_open(self):
        for transcript in ("Нет, не нашла", "Не расслышала, повторите никнейм"):
            with self.subTest(transcript=transcript):
                reply, stage, hangup = self.turn("telegram_handle", transcript)
                self.assertEqual(stage, "telegram_handle")
                self.assertFalse(hangup)
                self.assertIn("первая буква", reply.lower())
                self.assertNotIn("подробности", reply.lower())

    def test_zoom_refusal_does_not_advance_to_time_selection(self):
        for transcript in ("Нет", "Нет, не надо", "Не хочу подключаться", "Не смогу участвовать"):
            with self.subTest(transcript=transcript):
                self.candidate = voicebridge._new_candidate_record("")
                reply, stage, hangup = self.turn("zoom", transcript)
                self.assertEqual(stage, "finished")
                self.assertTrue(hangup)
                self.assertNotIn("время", reply.lower())

    def test_schedule_availability_question_refreshes_calendar_instead_of_repeating_preference(self):
        self.candidate["schedule_request"] = "Можно к трём?"
        with patch.object(
            voicebridge.MangoCallService,
            "_schedule_offer_for_candidate",
            return_value=("Сегодня есть свободное окно на пятнадцать часов. Записать вас?", []),
        ) as offer:
            reply, stage, hangup = self.turn("schedule", "На какое время свободно?")
        self.assertEqual((stage, hangup), ("schedule", False))
        self.assertEqual(reply, "Сегодня есть свободное окно на пятнадцать часов. Записать вас?")
        self.assertEqual(self.candidate["schedule_request"], "")
        offer.assert_called_once_with(self.candidate)

    def test_required_notice_is_rejected_but_no_notice_continues(self):
        reply, stage, hangup = self.turn("work_details", "Полная занятость, потребуется отработка месяц")
        self.assertEqual(stage, "finished")
        self.assertTrue(hangup)
        self.assertEqual(self.candidate["result"], "declined_notice")

        self.candidate = voicebridge._new_candidate_record("")
        _reply, stage, hangup = self.turn("work_details", "Полная занятость, отработка не потребуется")
        self.assertEqual(stage, "conditions")
        self.assertFalse(hangup)

    def test_company_question_is_answered_without_advancing_stage(self):
        reply, stage, hangup = self.turn("age_city", "А из какой компании вы звоните?")
        self.assertEqual(stage, "age_city")
        self.assertFalse(hangup)
        self.assertIn("Лекс-Торг", reply)
        self.assertNotIn("уточните ваш возраст", reply.lower())

    def test_repeat_replays_last_assistant_line_without_prefix(self):
        last_line = "У вас есть ноутбук или компьютер для удалённой работы?"
        history = [{"role": "assistant", "text": last_line}]
        reply, stage, hangup = self.turn("computer", "Не расслышал, повторите", history)
        self.assertEqual(reply, last_line)
        self.assertEqual(stage, "computer")
        self.assertFalse(hangup)

    def test_grounded_company_question_keeps_every_active_stage(self):
        stages = (
            "relevance", "age_city", "computer", "citizenship", "employment",
            "study_format", "study_schedule", "work_details", "conditions",
            "zoom", "telegram",
        )
        for stage in stages:
            with self.subTest(stage=stage):
                self.candidate = voicebridge._new_candidate_record("")
                reply, next_stage, hangup = self.turn(stage, "Из какой компании вы звоните?")
                self.assertEqual(next_stage, stage)
                self.assertFalse(hangup)
                self.assertIn("Лекс-Торг", reply)

    def test_llm_answer_slot_saves_candidate_answer_before_question(self):
        cases = (
            ("age_city", "Мне двадцать два, Санкт-Петербург. Из какой компании?", "22, Санкт-Петербург", "computer"),
            ("computer", "Да, есть. Из какой компании?", "есть", "citizenship"),
            ("employment", "Не учусь и не работаю. Из какой компании?", "учёба: нет; работа: нет", "conditions"),
            ("study_format", "Заочно. Из какой компании?", "заочно", "study_schedule"),
            ("study_schedule", "Пары после работы, не пересекаются. Из какой компании?", "пары после работы, не пересекаются", "conditions"),
            ("work_details", "Отработка не потребуется. Из какой компании?", "отработка не потребуется", "conditions"),
        )
        for stage, transcript, normalized, expected_stage in cases:
            with self.subTest(stage=stage):
                self.candidate = voicebridge._new_candidate_record("")
                self.candidate.update({
                    "age_city": "22, Санкт-Петербург",
                    "computer": "есть",
                    "citizenship": "РФ",
                    "employment": "не учусь и не работаю",
                    "study_schedule": "пары после работы",
                })
                intent = {
                    "intent": "company_question",
                    "answer_slot": stage,
                    "normalized_answer": normalized,
                    "short_reply": "Я звоню из компании «Лекс-Торг».",
                }
                reply, next_stage, hangup = voicebridge.MangoCallService._script_candidate_reply(
                    stage, transcript, self.candidate, [], intent
                )
                self.assertEqual(next_stage, expected_stage)
                self.assertFalse(hangup)
                self.assertIn("Лекс-Торг", reply)

    def test_answer_plus_question_survives_without_a_usable_llm_result(self):
        cases = (
            ("age_city", "Мне двадцать два, живу в Санкт-Петербурге. Из какой компании?", "computer", "22, Санкт-Петербург"),
            ("computer", "Да, есть ноутбук. Из какой компании?", "citizenship", "есть"),
            ("employment", "Не учусь и не работаю. Что за работа?", "conditions", None),
            ("study_format", "Заочно. Какой график работы?", "study_schedule", "заочно"),
            ("work_details", "Отработка не потребуется. Из какой компании?", "zoom", "Отработка не потребуется."),
            ("conditions", "Да, условия подходят. Из какой компании?", "zoom", None),
        )
        for stage, transcript, expected_stage, expected_fact in cases:
            with self.subTest(stage=stage):
                self.candidate = voicebridge._new_candidate_record("")
                self.candidate.update({
                    "age_city": "22, Санкт-Петербург",
                    "computer": "есть",
                    "citizenship": "РФ",
                    "employment": "Не учусь и не работаю",
                    "conditions_spoken": True,
                })
                if stage == "employment":
                    self.candidate["conditions_spoken"] = False
                reply, next_stage, hangup = self.turn(stage, transcript)
                self.assertEqual(next_stage, expected_stage)
                self.assertFalse(hangup)
                expected_answer = "График" if stage == "study_format" else "Лекс-Торг"
                self.assertIn(expected_answer, reply)
                if expected_fact:
                    self.assertEqual(self.candidate[{
                        "age_city": "age_city", "computer": "computer", "study_format": "study_format",
                        "work_details": "work_details",
                    }[stage]], expected_fact)

    def test_yes_and_tomorrow_at_zoom_enters_schedule_persuasion(self):
        reply, stage, hangup = self.turn("zoom", "Да, смогу. Можно завтра?")
        self.assertEqual(stage, "schedule")
        self.assertFalse(hangup)
        self.assertTrue(self.candidate["schedule_today_prompted"])
        self.assertIn("сегодня", reply.lower())

    def test_second_tomorrow_request_offers_tomorrow_without_more_persuasion(self):
        self.candidate["schedule_today_prompted"] = True
        with patch.object(
            voicebridge.MangoCallService,
            "_schedule_offer_for_candidate",
            return_value=("Завтра есть свободное время. Подтвердить запись?", []),
        ) as offer:
            reply, stage, hangup = self.turn("schedule", "Сегодня не могу, давайте завтра")
        self.assertEqual(stage, "schedule")
        self.assertFalse(hangup)
        self.assertIn("завтра", reply.lower())
        self.assertEqual(offer.call_args.kwargs["day"], voicebridge.calendar_service.today() + voicebridge.timedelta(days=1))

    def test_time_named_after_today_persuasion_is_kept_for_tomorrow(self):
        self.candidate["schedule_today_prompted"] = True
        self.candidate["schedule_day_preference"] = "tomorrow"
        self.candidate["schedule_request"] = "Можно завтра?"
        self.candidate["offered_slots"] = [
            voicebridge.datetime.combine(
                voicebridge.calendar_service.today(),
                voicebridge.datetime_time(14, 0),
                voicebridge.calendar_service.tz,
            ).isoformat(timespec="minutes")
        ]
        with patch.object(
            voicebridge.MangoCallService,
            "_schedule_offer_for_candidate",
            return_value=("Завтра в семнадцать часов есть окно. Подтвердить запись?", []),
        ) as offer:
            reply, stage, hangup = self.turn("schedule", "Честно, неудобно, есть в пять")
        self.assertEqual((stage, hangup), ("schedule", False))
        self.assertIn("семнадцать", reply.lower())
        self.assertEqual(offer.call_args.kwargs["day"], voicebridge.calendar_service.today() + voicebridge.timedelta(days=1))
        self.assertEqual(self.candidate["schedule_request"], "Честно, неудобно, есть в пять")

    def test_change_to_later_slot_stays_in_schedule_and_does_not_book_early(self):
        self.candidate["offered_slots"] = ["2026-10-02T14:00:00+03:00"]
        with patch.object(
            voicebridge.MangoCallService,
            "_schedule_offer_for_candidate",
            return_value=("Ближайшее более позднее окно — пятнадцать часов.", []),
        ) as offer:
            reply, stage, hangup = self.turn("schedule", "Нет, можно чуть позже?")
        self.assertEqual(stage, "schedule")
        self.assertFalse(hangup)
        self.assertIn("позднее", reply.lower())
        offer.assert_called_once()
        self.assertEqual(
            offer.call_args.kwargs["after_start"],
            "2026-10-02T14:00:00+03:00",
        )
        self.assertNotIn("scheduled_at", self.candidate)

    def test_named_time_preference_wins_over_llm_generic_acceptance(self):
        earlier = "2026-10-02T17:00:00+03:00"
        self.candidate["offered_slots"] = [earlier]
        with patch.object(
            voicebridge.MangoCallService,
            "_schedule_offer_for_candidate",
            return_value=("На восемнадцать часов есть окно. Подтвердить запись?", []),
        ) as offer, patch.object(voicebridge.calendar_service, "reserve") as reserve:
            reply, stage, hangup = voicebridge.MangoCallService._script_candidate_reply(
                "schedule",
                "А можно к шести?",
                self.candidate,
                [],
                {"intent": "answer", "answer_slot": "schedule", "normalized_answer": "да"},
            )
        self.assertEqual((stage, hangup), ("schedule", False))
        self.assertIn("восемнадцать", reply.lower())
        self.assertEqual(self.candidate["schedule_request"], "А можно к шести?")
        self.assertEqual(offer.call_args.kwargs["exclude"], {earlier})
        reserve.assert_not_called()

    def test_candidate_can_change_booked_time_without_special_reschedule_words(self):
        self.candidate["scheduled_at"] = "2026-10-02T17:00:00+03:00"
        self.candidate["scheduled_event_id"] = "booked-event"
        with patch.object(voicebridge.calendar_service, "delete") as delete, patch.object(
            voicebridge.MangoCallService,
            "_schedule_offer_for_candidate",
            return_value=("На восемнадцать часов есть окно. Подтвердить запись?", []),
        ) as offer:
            reply, stage, hangup = self.turn("telegram", "А можно к шести?")
        self.assertEqual((stage, hangup), ("schedule", False))
        self.assertIn("восемнадцать", reply.lower())
        self.assertNotIn("scheduled_at", self.candidate)
        delete.assert_called_once_with("booked-event")
        offer.assert_called_once()

    def test_spoken_time_variants_map_to_moscow_hours(self):
        cases = {
            "к часу": 13 * 60,
            "в час": 13 * 60,
            "к одному часу": 13 * 60,
            "к двум": 14 * 60,
            "около двух часов": 14 * 60,
            "к трём часам": 15 * 60,
            "к трём": 15 * 60,
            "завтра к трём можно?": 15 * 60,
            "а завтра к трём будет удобно?": 15 * 60,
            "на четыре": 16 * 60,
            "к пяти": 17 * 60,
            "на шесть": 18 * 60,
            "не в пять, а можно к шести?": 18 * 60,
            "17:00 не подходит, можно к шести?": 18 * 60,
            "к 18": 18 * 60,
            "на четырнадцать часов": 14 * 60,
            "к семнадцати": 17 * 60,
            "в районе пяти": 17 * 60,
            "ближе к семи": 19 * 60,
            "после шести": 18 * 60,
            "в 10 вечера": 22 * 60,
            "в шесть утра": 6 * 60,
            "в 18:20": 18 * 60 + 20,
            "к половине шестого": 17 * 60 + 30,
            "на половину седьмого": 18 * 60 + 30,
            "после обеда": 14 * 60,
            "вечером": 18 * 60,
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    voicebridge.MangoCallService._requested_time_minutes(phrase),
                    expected,
                )

    def test_repeat_during_scheduling_replays_current_offer(self):
        last_line = "Сегодня есть окно на четырнадцать часов. Записать вас?"
        self.candidate["offered_slots"] = ["2026-10-02T14:00:00+03:00"]
        reply, stage, hangup = self.turn(
            "schedule",
            "Не расслышала, повторите, пожалуйста",
            [{"role": "assistant", "text": last_line}],
        )
        self.assertEqual(reply, last_line)
        self.assertEqual(stage, "schedule")
        self.assertFalse(hangup)
        self.assertNotIn("scheduled_at", self.candidate)

    def test_schedule_faq_preserves_the_offered_slot_and_stage(self):
        self.candidate["offered_slots"] = ["2026-10-02T14:00:00+03:00"]
        for question, expected in (
            ("А какой оклад?", "оклад"),
            ("Какой график работы?", "пять на два"),
            ("Что за должность?", "советник"),
        ):
            with self.subTest(question=question):
                reply, stage, hangup = self.turn("schedule", question)
                self.assertEqual(stage, "schedule")
                self.assertFalse(hangup)
                self.assertIn(expected, reply.lower())
                self.assertIn("четырнадцать", reply.lower())
                self.assertEqual(self.candidate["offered_slots"], ["2026-10-02T14:00:00+03:00"])
                self.assertNotIn("scheduled_at", self.candidate)

    def test_combined_time_preference_and_salary_question_keeps_both(self):
        self.candidate["offered_slots"] = ["2026-10-02T14:00:00+03:00"]
        with patch.object(
            voicebridge.MangoCallService,
            "_schedule_offer_for_candidate",
            return_value=("На восемнадцать часов есть окно. Подтвердить запись?", []),
        ) as offer:
            reply, stage, hangup = self.turn(
                "schedule",
                "Можно к шести? И какой оклад?",
            )
        self.assertEqual(stage, "schedule")
        self.assertFalse(hangup)
        self.assertIn("оклад", reply.lower())
        self.assertIn("восемнадцать", reply.lower())
        self.assertEqual(self.candidate["schedule_request"], "Можно к шести? И какой оклад?")
        self.assertEqual(offer.call_args.kwargs["exclude"], {"2026-10-02T14:00:00+03:00"})
        self.assertNotIn("scheduled_at", self.candidate)

    def test_asking_if_proposed_time_is_possible_does_not_book_it(self):
        offered = "2026-10-02T14:00:00+03:00"
        self.candidate["offered_slots"] = [offered]
        with patch.object(voicebridge.calendar_service, "reserve") as reserve:
            reply, stage, hangup = self.turn("schedule", "Можно на четырнадцать часов?")
        self.assertEqual(stage, "schedule")
        self.assertFalse(hangup)
        self.assertIn("подтвердить", reply.lower())
        reserve.assert_not_called()
        self.assertNotIn("scheduled_at", self.candidate)

    def test_explicit_slot_confirmation_books_and_says_the_time(self):
        offered = "2026-10-02T14:00:00+03:00"
        self.candidate["offered_slots"] = [offered]
        with patch.object(
            voicebridge.calendar_service,
            "reserve",
            return_value={"start": offered, "id": "test-event"},
        ) as reserve:
            reply, stage, hangup = self.turn("schedule", "Да, на четырнадцать записывайте")
        self.assertEqual(stage, "telegram")
        self.assertFalse(hangup)
        self.assertIn("четырнадцать", reply.lower())
        self.assertEqual(self.candidate["scheduled_at"], offered)
        reserve.assert_called_once()

    def test_schedule_time_status_understands_natural_wording(self):
        self.candidate["offered_slots"] = ["2026-10-02T14:00:00+03:00"]
        for question in (
            "А во сколько у меня встреча?",
            "Когда собеседование?",
            "Когда созвон?",
            "Когда встречаемся?",
            "Напомните время, пожалуйста",
            "На когда меня записали?",
        ):
            with self.subTest(question=question):
                reply, stage, hangup = self.turn("schedule", question)
                self.assertEqual(stage, "schedule")
                self.assertFalse(hangup)
                self.assertIn("четырнадцать", reply.lower())

    def test_time_preference_offers_nearest_available_slot(self):
        slots = [
            {"start": "2026-10-02T15:00:00+03:00", "time": "15:00"},
            {"start": "2026-10-02T16:20:00+03:00", "time": "16:20"},
            {"start": "2026-10-02T17:00:00+03:00", "time": "17:00"},
        ]
        self.candidate["schedule_request"] = "Можно к четырём?"
        with patch.object(voicebridge.calendar_service, "available_slots", return_value=slots):
            reply, offered = voicebridge.MangoCallService._schedule_offer_for_candidate(
                self.candidate,
                day=voicebridge.date(2026, 10, 2),
            )
        self.assertEqual([slot["start"] for slot in offered], ["2026-10-02T16:20:00+03:00"])
        self.assertEqual(self.candidate["offered_slots"], ["2026-10-02T16:20:00+03:00"])
        self.assertIn("шестнадцать", reply.lower())

    def test_exact_requested_free_time_is_not_reported_as_busy(self):
        slot = {"start": "2026-10-02T15:00:00+03:00", "time": "15:00"}
        self.candidate["schedule_request"] = "Можно к трём?"
        with patch.object(voicebridge.calendar_service, "available_slots", return_value=[slot]):
            reply, offered = voicebridge.MangoCallService._schedule_offer_for_candidate(
                self.candidate,
                day=voicebridge.date(2026, 10, 2),
            )
        self.assertEqual([item["start"] for item in offered], [slot["start"]])
        self.assertIn("есть свободное окно", reply.lower())
        self.assertNotIn("занято", reply.lower())
        self.assertIn("пятнадцать", reply.lower())

    def test_spoken_hour_matches_an_already_offered_exact_slot(self):
        offered = ["2026-10-02T15:00:00+03:00"]
        self.assertEqual(
            voicebridge.MangoCallService._schedule_slot_from_text("Можно к трём?", offered),
            offered[0],
        )
        self.candidate["offered_slots"] = offered
        with patch.object(voicebridge.calendar_service, "reserve") as reserve:
            reply, stage, hangup = self.turn("schedule", "Можно к трём?")
        self.assertEqual((stage, hangup), ("schedule", False))
        self.assertIn("пятнадцать", reply.lower())
        self.assertIn("подтвердить", reply.lower())
        reserve.assert_not_called()

    def test_tomorrow_exact_free_time_is_checked_against_tomorrow_calendar(self):
        tomorrow = voicebridge.calendar_service.today() + voicebridge.timedelta(days=1)
        slot = {
            "start": voicebridge.datetime.combine(
                tomorrow,
                voicebridge.datetime_time(15, 0),
                voicebridge.calendar_service.tz,
            ).isoformat(timespec="minutes"),
            "time": "15:00",
        }
        self.candidate.update({
            "schedule_today_prompted": True,
            "schedule_day_preference": "tomorrow",
            "schedule_request": "завтра к трём",
        })
        with patch.object(voicebridge.calendar_service, "available_slots", return_value=[slot]) as available:
            reply, offered = voicebridge.MangoCallService._schedule_offer_for_candidate(
                self.candidate,
                day=tomorrow,
            )
        self.assertEqual(available.call_args.args[0], tomorrow.isoformat())
        self.assertEqual([item["start"] for item in offered], [slot["start"]])
        self.assertIn("завтра", reply.lower())
        self.assertIn("есть свободное окно", reply.lower())
        self.assertNotIn("занято", reply.lower())

    def test_tomorrow_time_followed_by_conversational_words_selects_matching_window(self):
        tomorrow = voicebridge.calendar_service.today() + voicebridge.timedelta(days=1)
        slots = [
            {
                "start": voicebridge.datetime.combine(
                    tomorrow,
                    voicebridge.datetime_time(hour, 0),
                    voicebridge.calendar_service.tz,
                ).isoformat(timespec="minutes"),
                "time": f"{hour:02d}:00",
            }
            for hour in (10, 15, 16)
        ]
        self.candidate["schedule_request"] = "Завтра к трём можно?"
        with patch.object(voicebridge.calendar_service, "available_slots", return_value=slots):
            reply, offered = voicebridge.MangoCallService._schedule_offer_for_candidate(
                self.candidate,
                day=tomorrow,
            )
        self.assertEqual([item["time"] for item in offered], ["15:00"])
        self.assertIn("есть свободное окно", reply.lower())
        self.assertNotIn("занято", reply.lower())

    def test_dynamic_model_cannot_send_json_or_corrupted_markup_to_tts(self):
        with patch.object(
            voicebridge.llm_service,
            "chat",
            return_value={"text": '{",зыу.зз заняз,з завз?'},
        ):
            reply = voicebridge.call_service._dynamic_candidate_reply(
                "age_city",
                "А из какой компании вы звоните?",
                voicebridge.MANGO_GENERIC_CLARIFICATION,
                self.candidate,
                [],
                {"llm_base_url": voicebridge.LOCAL_LLM_BASE_URL},
            )
        self.assertEqual(reply, "")

    def test_known_question_does_not_trigger_second_model_rewrite(self):
        self.assertFalse(voicebridge.MangoCallService._dynamic_reply_needed(
            "conditions", "Какой график работы?", "График пять на два, с десяти до двадцати."
        ))

    def test_deterministic_schedule_turns_skip_slow_llm_classification(self):
        config = {
            "llm_base_url": "http://127.0.0.1:34200/v1",
            "llm_api_key": "local-test",
            "llm_model": "Qwen3-1.7B-Q4_K_M.gguf",
        }
        for stage, transcript in (
            ("schedule", "Нет, это время не подходит, давайте чуть позже"),
            ("zoom", "Да, смогу. Можно завтра?"),
            ("conditions", "Да, условия подходят, когда ближайшее собеседование?"),
        ):
            with self.subTest(stage=stage), patch.object(
                voicebridge.llm_service,
                "chat",
                side_effect=AssertionError("deterministic turn must not wait for Qwen"),
            ):
                result = voicebridge.call_service._classify_candidate_intent(
                    stage, transcript, [], config
                )
                self.assertEqual(result, {})

    def test_dialog_turn_api_keeps_zoom_and_tomorrow_context_together(self):
        result = voicebridge.process_dialog_turn({
            "stage": "zoom",
            "transcript": "Да, смогу. Только сегодня занята, можно завтра?",
            "candidate": voicebridge._new_candidate_record(""),
            "history": [{
                "role": "Яна",
                "text": "Сможете подключиться к Zoom?",
            }],
            "config": {"llm_base_url": voicebridge.LOCAL_LLM_BASE_URL},
        })
        self.assertEqual(result["nextStage"], "schedule")
        self.assertFalse(result["ends"])
        self.assertTrue(result["candidate"]["schedule_today_prompted"])
        self.assertIn("сегодня", result["reply"].lower())

    def test_complete_basic_dialogue_keeps_the_required_stage_order(self):
        route = (
            ("relevance", "Да, актуально", "age_city"),
            ("age_city", "Мне двадцать два, живу в Санкт-Петербурге", "computer"),
            ("computer", "Да, есть", "citizenship"),
            ("citizenship", "Да, гражданин России", "employment"),
            ("employment", "Не учусь и сейчас не работаю", "conditions"),
            ("conditions", "Да, условия подходят", "zoom"),
        )
        for current_stage, transcript, expected_stage in route:
            with self.subTest(current_stage=current_stage):
                reply, next_stage, hangup = self.turn(current_stage, transcript)
                self.assertEqual(next_stage, expected_stage)
                self.assertFalse(hangup)
                self.assertTrue(reply)
        self.assertEqual(self.candidate["age_city"], "22, Санкт-Петербург")
        self.assertEqual(self.candidate["computer"], "есть")
        self.assertEqual(self.candidate["citizenship"], "Да, гражданин России")

    def test_accepted_zoom_time_is_confirmed_before_telegram(self):
        slot = "2026-10-02T14:20:00+03:00"
        self.candidate["offered_slots"] = [slot]
        with patch.object(
            voicebridge.calendar_service,
            "reserve",
            return_value={"start": slot, "id": "test-event"},
        ):
            reply, stage, hangup = self.turn("schedule", "Да, подтверждаю")
        self.assertEqual(stage, "telegram")
        self.assertFalse(hangup)
        self.assertEqual(self.candidate["scheduled_at"], slot)
        self.assertIn("четырнадцать двадцать", reply.lower())
        self.assertIn("телеграм", reply.lower())
        status_reply, status_stage, status_hangup = self.turn("telegram", "На какое время я записан?")
        self.assertEqual(status_stage, "telegram")
        self.assertFalse(status_hangup)
        self.assertIn("четырнадцать двадцать", status_reply.lower())


if __name__ == "__main__":
    unittest.main()
