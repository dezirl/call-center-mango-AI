import unittest

from mango_automation import (
    _active_call_button,
    _call_failure_visible,
    _call_timer_advanced,
    _call_timer_values,
)


class MangoConnectionDetectionTests(unittest.TestCase):
    def test_static_time_in_window_is_not_a_progressing_call_timer(self):
        first = _call_timer_values("Рабочее время 10:00–20:00. Последний звонок 02:15")
        second = _call_timer_values("Рабочее время 10:00–20:00. Последний звонок 02:15")
        self.assertFalse(_call_timer_advanced(first, second))

    def test_increasing_duration_timer_confirms_progress(self):
        self.assertTrue(
            _call_timer_advanced(
                _call_timer_values("00:41"),
                _call_timer_values("00:42"),
            )
        )

    def test_duration_timer_rollover_is_parsed(self):
        self.assertTrue(
            _call_timer_advanced(
                _call_timer_values("01:59"),
                _call_timer_values("02:00"),
            )
        )

    def test_large_time_jump_does_not_confirm_call(self):
        self.assertFalse(
            _call_timer_advanced(
                _call_timer_values("10:59"),
                _call_timer_values("11:00"),
            )
        )

    def test_active_call_requires_named_call_control(self):
        self.assertTrue(_active_call_button(["Выключить микрофон"]))
        self.assertFalse(_active_call_button(["Выключить звук уведомлений"]))

    def test_failure_status_matches_complete_words(self):
        self.assertTrue(_call_failure_visible("Абонент недоступен"))
        self.assertFalse(_call_failure_visible("Недоступность сервиса проверяется"))


if __name__ == "__main__":
    unittest.main()
