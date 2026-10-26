from __future__ import annotations

import atexit
import base64
import gc
import hashlib
import io
import json
import logging
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unicodedata
import warnings
import wave
import uuid
from collections import deque
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from threading import Event, RLock, Thread, Timer
from typing import Any
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.10+ normally provides zoneinfo
    ZoneInfo = None

# Set BLAS/OpenMP defaults before importing the local audio/runtime helpers.
_CPU_THREADS = max(1, (os.cpu_count() or 2) - 1)
os.environ.setdefault("OMP_NUM_THREADS", str(_CPU_THREADS))
os.environ.setdefault("MKL_NUM_THREADS", str(_CPU_THREADS))

import requests
try:
    import torch
except ImportError:  # The TTS runtime is external; PyTorch is optional here.
    torch = None


def _load_local_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_local_env()
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

try:
    import psutil
except ImportError:  # pragma: no cover - setup installs psutil with the app
    psutil = None

_LLM_CPU_THREADS = max(
    1,
    min(8, (psutil.cpu_count(logical=False) if psutil else None) or _CPU_THREADS),
)


if getattr(sys, "frozen", False):
    # A PyInstaller sidecar must keep user data outside its temporary unpack
    # directory, which can be removed as soon as the process exits.
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    BASE_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "VoiceBridge"
else:
    RESOURCE_DIR = Path(__file__).resolve().parent
    BASE_DIR = RESOURCE_DIR
STATIC_DIR = RESOURCE_DIR / "static"
VOICE_DIR = BASE_DIR / "voices"
AUDIO_DIR = BASE_DIR / "audio_uploads"
OUTPUT_DIR = BASE_DIR / "generated_audio"
VPN_DIR = BASE_DIR / "vpn"
RVC_DIR = BASE_DIR / "rvc"
RVC_RUNTIME_DIR = RESOURCE_DIR / "rvc-runtime"
RVC_SCRIPT_PATH = RVC_RUNTIME_DIR / "infer_cli.py"
RVC_CONFIG_FILE = RVC_DIR / "config.json"
RVC_MODEL_PATH = RVC_DIR / "model.pth"
RVC_INDEX_PATH = RVC_DIR / "model.index"
ACTIVE_AUDIO_META = AUDIO_DIR / "active_input.json"
TTS_DEVICE_FILE = BASE_DIR / "tts_device.json"
AUDIO_ROUTING_FILE = BASE_DIR / "audio_routing.json"
CALL_SETTINGS_FILE = BASE_DIR / "call_settings.json"
VISION_STATE_FILE = BASE_DIR / "vision_inbox.json"
CANDIDATE_RECORDS_FILE = BASE_DIR / "candidate_records.json"
INTERVIEW_CALENDAR_FILE = BASE_DIR / "interview_calendar.json"
SCRIPT_AUDIO_CACHE_DIR = BASE_DIR / "script_audio_cache"
VISION_DEFAULT_PROMPT = (
    "Найди на изображении всех людей, у которых указан полный номер телефона. "
    "Для каждого человека определи только его ФИО и относящийся к нему номер. "
    "Не добавляй города, организации, должности и людей без полного номера."
)
MANGO_GREETING = (
    "Добрый день! Я ассистент HR-менеджера Яны из компании «Лекс-Торг». "
    "Звоню по поводу вакансии. Подскажите, актуален ли вам сейчас поиск работы?"
)
MANGO_GREETING_WITH_NAME = (
    "Добрый день! Это {name}?"
)
MANGO_GREETING_AFTER_NAME = (
    "Я ассистент HR-менеджера Яны из компании «Лекс-Торг». "
    "Звоню по поводу вакансии. Подскажите, актуален ли вам сейчас поиск работы?"
)
MANGO_WRONG_RECIPIENT = "Поняла, извините за беспокойство. Всего доброго."
MANGO_ALTERNATE_CANDIDATE_ASK = "Поняла. А вам самим сейчас актуален поиск работы?"
MANGO_ALTERNATE_CANDIDATE_NAME = "Как я могу к вам обращаться?"
MANGO_GOODBYE = "Поняла, спасибо за ответ. Всего доброго."
MANGO_REJECT_NOTICE = (
    "Спасибо за информацию. К сожалению, мы не сможем продолжить по этой вакансии, "
    "если при увольнении потребуется обязательная отработка. Желаю удачи в поиске работы. "
    "Всего доброго."
)
MANGO_REJECT_DEVICE = (
    "Спасибо за информацию. К сожалению, для этой удалённой работы нужен компьютер или ноутбук. "
    "Желаю удачи в поиске работы. Всего доброго."
)
MANGO_REJECT_STUDY = (
    "Спасибо за информацию. К сожалению, рабочий график пересекается с вашим расписанием учёбы, "
    "поэтому сейчас мы не сможем продолжить. Желаю удачи в поиске работы. Всего доброго."
)
MANGO_RELEVANCE_REPROMPT = "Подскажите, актуально?"
MANGO_INTERESTED_OPENING = "Отлично! Позвольте уточнить несколько моментов."
MANGO_AGE_CITY = "Уточните ваш возраст и город проживания?"
MANGO_INTERESTED_WITH_AGE = f"{MANGO_INTERESTED_OPENING} {MANGO_AGE_CITY}"
MANGO_COMPUTER = "У вас есть ноутбук или компьютер для удалённой работы?"
MANGO_CITIZENSHIP = "Гражданство у вас Российской Федерации?"
MANGO_EMPLOYMENT = "Есть ли у вас сейчас учёба или работа?"
MANGO_STUDY_FORMAT = "Подскажите, в каком формате вы учитесь: очно, заочно или очно-заочно?"
MANGO_STUDY_SCHEDULE = (
    "Подскажите, пожалуйста, в какие часы проходят занятия или пары? "
    "Они будут пересекаться с рабочим графиком с десяти до двадцати по московскому времени?"
)
MANGO_WORK_DETAILS = "Подскажите, у вас полная занятость? Потребуется ли отработка при увольнении?"
MANGO_JOB_DESCRIPTION = (
    "Ещё раз напомню, звоню из компании «Лекс-Торг», мы рекрутинговая компания. "
    "К нам поступил запрос на должность: персональный инвестиционный советник "
    "из компании «Баланс». Эта должность подразумевает работу с клиентами. "
    "Трудоустройство по трудовому договору или договору гражданско-правового характера. "
    "Предусмотрена только полная занятость, работа полностью удалённая. "
    "График: пять на два, с десяти до двадцати по московскому времени. "
    "Средняя заработная плата от ста десяти тысяч рублей. Такие условия для себя рассматриваете?"
)
MANGO_JOB_OVERVIEW = (
    "Речь о должности персонального инвестиционного советника в компании «Баланс». "
    "Работа заключается в общении с клиентами."
)
MANGO_JOB_LATER = (
    "Сейчас расскажу об этом подробнее. Сначала уточню несколько коротких моментов, "
    "а затем перейду к условиям работы."
)
MANGO_JOB_CONDITIONS = (
    "Ещё раз напомню: звоню из компании «Лекс-Торг», мы рекрутинговая компания. "
    "К нам поступил запрос на должность: персональный инвестиционный советник "
    "из компании «Баланс». Эта должность подразумевает работу с клиентами. "
    "Трудоустройство по трудовому договору или договору гражданско-правового характера. "
    "Предусмотрена полная занятость, работа полностью удалённая. "
    "График: пять на два, с десяти до двадцати по московскому времени. "
    "Средняя заработная плата от ста десяти тысяч рублей. Такие условия для себя рассматриваете?"
)
MANGO_JOB_INTRO = "Тогда я коротко введу вас в курс дела. " + MANGO_JOB_CONDITIONS
MANGO_JOB_OVERVIEW_FOLLOWUP = MANGO_JOB_OVERVIEW + " Рассказать подробнее?"
MANGO_NOT_SUITABLE = "Подскажите, что именно вам не подходит?"
MANGO_FOREIGN_ANSWER = "Да, можно работать из-за границы."
MANGO_SALARY_ANSWER = (
    "Заработная плата складывается из фиксированного оклада и неограниченного процента. "
    "В среднем в первый месяц около ста десяти тысяч рублей. Подробнее могу рассказать уже на собеседовании."
)
MANGO_CITIZENSHIP_ANSWER = "Нет, обязательно быть гражданином Российской Федерации не нужно."
MANGO_COMPUTER_ANSWER = "Да, обязательно работать с компьютера или ноутбука."
MANGO_ZOOM_CAMERA_ANSWER = (
    "Да, нужны будут камера и микрофон. Можете не переживать, это всё конфиденциально и между нами."
)
MANGO_DEEP_ANSWER = (
    "Подробные детали обсуждаются на собеседовании. Оно занимает около десяти минут, "
    "и на него можно зайти с компьютера или телефона."
)
MANGO_GENERIC_CLARIFICATION = (
    "Уточню этот вопрос и отвечу точнее. А пока продолжим с того места, "
    "на котором остановились."
)
MANGO_NAME_ANSWER = "Я ассистент HR-менеджера Яны из компании «Лекс-Торг»."
MANGO_SCHEDULE_REPROMPT = "На какое время вам сегодня будет удобно?"
MANGO_STAGE_REPROMPTS = {
    "relevance": "Подскажите, пожалуйста, работа для вас сейчас актуальна?",
    "age_city": "Уточните, пожалуйста, ваш возраст и город проживания.",
    "computer": "Уточните, пожалуйста: у вас есть компьютер или ноутбук для удалённой работы?",
    "citizenship": "Уточните, пожалуйста: вы гражданин или гражданка Российской Федерации?",
    "employment": "Уточните, пожалуйста: есть ли сейчас учёба или работа?",
    "study_format": "Уточните, пожалуйста, вы учитесь очно, заочно или очно-заочно?",
    "study_schedule": MANGO_STUDY_SCHEDULE,
    "work_details": "Уточните, пожалуйста: занятость полная или частичная, и потребуется ли отработка?",
    "conditions": "Подскажите, пожалуйста, вы рассматриваете такие условия работы?",
    "conditions_before_details": "Подскажите, пожалуйста, такие условия работы вам подходят?",
    "conditions_resume_age_city": "Подскажите, пожалуйста, такие условия работы вам подходят?",
    "conditions_resume_computer": "Подскажите, пожалуйста, такие условия работы вам подходят?",
    "conditions_followup": "Подскажите, пожалуйста, что именно не подходит по условиям?",
    "zoom": "Подскажите, пожалуйста, сможете подключиться к онлайн-собеседованию в зум?",
    "telegram": "Сможете сейчас найти мой аккаунт в телеграме?",
    "telegram_permission": "Скажите, пожалуйста, когда можно продиктовать никнейм?",
    "telegram_handle": "Удалось найти аккаунт?",
    "telegram_send": "Отправьте мне любое сообщение в телеграме и скажите, когда отправите.",
    "schedule": MANGO_SCHEDULE_REPROMPT,
}
MANGO_ZOOM = (
    "Спасибо! Тогда я предлагаю перейти на следующий этап — онлайн-собеседование в зум. "
    "Само собеседование займёт всего десять-пятнадцать минут. Я расскажу об обязанностях и условиях. "
    "Сможете подключиться?"
)
MANGO_TELEGRAM = "Сможете сейчас найти мой аккаунт в телеграме?"
MANGO_TELEGRAM_PERMISSION = "Скажите, пожалуйста, когда можно продиктовать никнейм?"
MANGO_TELEGRAM_HANDLE = (
    "Никнейм по буквам. Первая буква — икс. Вторая буква — икс. "
    "Третья буква — эйч. Четвёртая буква — ар. Цифра — один. "
    "Удалось найти аккаунт?"
)
MANGO_TELEGRAM_FOUND = "Удалось найти аккаунт?"
MANGO_TELEGRAM_SEND = (
    "Отлично. Отправьте мне любое сообщение в телеграме, чтобы я могла связаться с вами. "
    "Скажите, когда отправите."
)
MANGO_SCHEDULE_OFFER = "Подскажите, пожалуйста, вам удобно пройти онлайн-собеседование сегодня? Могу предложить свободное время по Москве."
MANGO_SCHEDULE_REPROMPT = "На какое время вам сегодня будет удобно?"
MANGO_SCHEDULE_TIME_ASK = "Понимаю. А в какое время вам будет удобно пройти собеседование?"
MANGO_SCHEDULE_TODAY_PERSUADE = (
    "Понимаю. Собеседование займёт всего десять-пятнадцать минут. "
    "Подключиться к Zoom можно с компьютера или телефона, я коротко расскажу об обязанностях и отвечу на вопросы. "
    "Если получится пройти его сегодня, это было бы удобно. Какое время сегодня вам подойдёт?"
)
MANGO_SCHEDULE_CONFIRM = "Отлично, записала вас на онлайн-собеседование."
MANGO_SCHEDULE_UNAVAILABLE = "На сегодня свободных слотов не осталось. Давайте подберём другое время."
MANGO_FINAL = "Спасибо за уделённое время, до скорой встречи!"
MANGO_NO_RESPONSE_TIMEOUT_SECONDS = 2.5
MANGO_HEARING_CHECK_TIMEOUT_SECONDS = 3.0
MANGO_HEARING_CHECK_TEXT = "Алло?"
AUTOANSWER_PHRASES = (
    "автоответчик",
    "оставьте сообщение",
    "оставить сообщение",
    "после сигнала",
    "после звукового сигнала",
    "запишите сообщение",
    "голосовое меню",
    "нажмите цифру",
    "нажмите один",
    "ваш звонок очень важен",
    "абонент временно недоступен",
    "абонент не может ответить",
    "перезвонит позже",
    "после гудка",
    "я передам",
    "сейчас передам",
    "передам информацию",
    "я это сделаю",
    "вас слушает автоответчик",
)
AUTOANSWER_SOFT_MARKERS = (
    "оставьте",
    "оставить",
    "передам",
    "скоро передам",
    "записала",
    "записано",
    "опять эта пауза",
    "после звонка",
    "я тут жду",
    "услышала",
    "голосовое сообщение",
    "позже передам",
    "абонент",
    "вне зоны",
    "не в сети",
    "выключен",
)
MANGO_ROLE_PROTOCOL = (
    "КРИТИЧЕСКОЕ ПРАВИЛО РОЛЕЙ: [ИИ-АССИСТЕНТ] — уже произнесённые реплики ИИ-ассистента HR, "
    "[СОБЕСЕДНИК] — реальные слова кандидата. Последняя реплика [СОБЕСЕДНИК] "
    "является входом пользователя и требует ответа. Реплики [ИИ-АССИСТЕНТ] — это контекст, "
    "а не новые слова кандидата. Не отвечай на собственные реплики и не приписывай "
    "слова ассистента собеседнику."
)
MANGO_CALL_SYSTEM_PROMPT = (
    "Ты — ИИ-ассистент HR-менеджера Яны из компании «Лекс-Торг». Не представляйся Яной. Начальное приветствие "
    "с вопросом об актуальности вакансии уже произнесено приложением. "
    "В истории разговора [ИИ-АССИСТЕНТ] означает уже сказанные реплики ассистента, "
    "а [СОБЕСЕДНИК] — реальные слова кандидата. Никогда не принимай реплики ассистента "
    "за слова кандидата. Отвечай только следующей короткой репликой ассистента, без пояснений, "
    "меток, списков и рассуждений. Используй только русский текст и слова вместо цифр и "
    "английских сокращений: говори «эйч ар», «зум», «телеграм», «пять на два», "
    "«с десяти до двадцати», «сто десять тысяч рублей», «трудовой договор или договор "
    "гражданско-правового характера», «общество с ограниченной ответственностью «Баланс»». "
    "Не используй символы, которые нужно читать вслух: слеши, цифровые номера, латинские "
    "аббревиатуры и markdown. Никогда не придумывай сведения о вакансии или кандидате.\n\n"
    "Сценарий:\n"
    "1. После ответа об актуальности вакансии, если кандидат отвечает положительно, скажи: "
    "«Отлично! Позвольте уточнить несколько моментов.» "
    "Затем задавай вопросы по одному: возраст и город проживания; есть ли ноутбук или компьютер "
    "для удалённой работы; гражданство Российской Федерации; есть ли сейчас учёба или работа. "
    "Если есть очная учёба, вежливо заверши разговор. Если есть работа, уточни, готов ли кандидат "
    "уволиться и нужна ли отработка.\n"
    "2. Если кандидат сразу спрашивает, что за работа, сначала коротко скажи: «Ещё раз напомню, "
    "я звоню из компании «Лекс-Торг». Мы рекрутинговая компания. К нам поступил запрос на должность "
    "персонального инвестиционного советника из компании «Баланс». Работа заключается в работе с "
    "клиентами. Трудоустройство по трудовому договору или договору гражданско-правового характера. "
    "Только полная занятость и полностью удалённая работа. График пять на два, с десяти до двадцати "
    "по московскому времени. Средняя заработная плата от ста десяти тысяч рублей. Такие условия "
    "вам подходят?» Затем продолжай с вопросами из пункта два.\n"
    "3. После положительных ответов на вопросы о кандидате скажи: «Тогда я коротко введу вас в "
    "курс дела». Озвучь условия вакансии: персональный инвестиционный советник из компании «Баланс», "
    "работа с клиентами, трудовой договор или договор гражданско-правового характера, полная занятость, "
    "полностью удалённая работа, график пять на два с десяти до двадцати по московскому времени, "
    "средняя заработная плата от ста десяти тысяч рублей. Затем спроси: «Такие условия для себя "
    "рассматриваете?» Если нет, уточни, что именно не подходит. Если да, скажи: «Спасибо! Тогда "
    "предлагаю перейти на следующий этап — онлайн-собеседование в зум. Оно займёт десять-пятнадцать минут. "
    "Сможете подключиться?» Если кандидат отказывается от Zoom, вежливо заверши звонок и не спрашивай время. "
    "После согласия согласуй время, используя только свободные слоты календаря по Москве; не повторяй "
    "предыдущую просьбу о времени как будто это доступность и не подтверждай запись без явного согласия. "
    "После подтверждённой записи переходи к Telegram: спроси, сможет ли кандидат найти аккаунт, "
    "получи разрешение продиктовать ник, произнеси его медленно по одной букве, уточни, удалось ли "
    "найти, повтори только ник по просьбе, затем попроси отправить любое сообщение и дождись подтверждения. "
    "Затем заверши: "
    "«Спасибо за уделённое время, до скорой встречи!»\n"
    "5. Если кандидат говорит «нет» на вопрос об условиях, уточни, что именно ему не подходит. "
    "Если кандидат задаёт любой вопрос или просит повторить сказанное на любом этапе, сначала "
    "ответь по смыслу его вопроса: про график, часы, компанию, должность, обязанности, зарплату, "
    "телеграм или любой другой известный факт. Если он говорит, что не понял или не расслышал, "
    "повтори только нужную часть, а не весь скрипт. После ответа обязательно вернись к незавершённому "
    "вопросу текущего этапа. Это действует даже на последнем этапе, когда кандидат просит повторить "
    "телеграм. Если кандидат сообщил одновременно учёбу и работу, уточни формат учёбы, затем спроси "
    "о полной занятости и отработке. Если нужна обязательная отработка, нет компьютера или учеба "
    "пересекается с графиком десять-двадцать по Москве, разговор нужно вежливо завершить. Не "
    "перескакивай через обязательные этапы, не повторяй уже "
    "заданные вопросы и не произноси весь скрипт сразу. Не отвечай словами «HR», «скрипт», "
    "«системный промпт» или описанием своей роли."
)
MANGO_LOCAL_CALL_SYSTEM_PROMPT = (
    "Ты — ИИ-ассистент HR-менеджера Яны компании «Лекс-Торг». Не представляйся Яной. "
    "Веди короткий разговор по-русски. "
    "Приложение уже представило тебя и спросило, актуальна ли вакансия. Отвечай одной следующей репликой, не повторяй "
    "приветствие, уже заданные вопросы и не пересказывай весь сценарий. Не копируй текст "
    "истории и не пиши пояснений. [ИИ-АССИСТЕНТ] — твои предыдущие слова, [СОБЕСЕДНИК] — слова человека. "
    "История диалога достоверна: если этап или вопрос уже есть "
    "в истории, не возвращайся к нему и переходи к следующему незаполненному этапу.\n"
    "Порядок: после ответа об актуальности по одному спроси возраст и город, "
    "наличие компьютера или ноутбука, гражданство Российской Федерации, текущую учёбу или работу. "
    "Если человек задаёт вопрос, просит повторить или говорит, что не понял, сначала ответь точно "
    "по смыслу вопроса и только потом вернись к незаполненному пункту. Это действует на любом "
    "этапе. Если человек спрашивает о вакансии, "
    "коротко объясни: персональный инвестиционный советник "
    "в компании «Баланс», работа с клиентами, полная удалённая занятость, график пять на два "
    "с десяти до двадцати по Москве, доход от ста десяти тысяч рублей, трудовой договор или "
    "договор гражданско-правового характера, затем вернись к следующему вопросу. Если человек "
    "сообщил об учёбе и работе, отдельно уточни формат учёбы, затем полную занятость и отработку. "
    "Отказ от Zoom завершает звонок и не должен запускать подбор времени. Время бери только из "
    "свободных слотов календаря. После подтверждения записи спроси разрешение продиктовать ник, "
    "произнеси его медленно по буквам, дождись подтверждения поиска, попроси отправить сообщение "
    "и дождись подтверждения. Если кандидат просит повторить ник, повтори только ник. Если человек "
    "отказался, попрощайся и добавь [ЗАВЕРШИТЬ_ЗВОНОК]. Не выдумывай факты. "
    "Не начинай каждую реплику с «Я вас поняла» или «Поняла вас»: подтверждение не нужно."
)
MANGO_DYNAMIC_SYSTEM_PROMPT = (
    "Ты — ИИ-ассистент HR в текущем звонке. Отвечай только одной "
    "короткой естественной репликой по-русски, без анализа, JSON, markdown и служебных меток. "
    "В истории [ИИ-АССИСТЕНТ] — реплики ассистента, [СОБЕСЕДНИК] — реплики кандидата. Не перепутай роли: "
    "отвечай именно на последнюю реплику [СОБЕСЕДНИК], а не на собственные слова ассистента. "
    "Сначала пойми смысл последней реплики кандидата: это может быть вопрос, просьба повторить, "
    "сомнение, возражение или ответ, сформулированный не шаблонными словами. Не повторяй "
    "приветствие, уже сказанные фразы или весь сценарий. Используй всю историю текущего звонка "
    "и уже собранные данные кандидата. На известные вопросы отвечай конкретно: компания — "
    "«Лекс-Торг», запрос на вакансию поступил от компании «Баланс»; должность — персональный "
    "инвестиционный советник, работа с клиентами; оформление — трудовой договор или договор "
    "гражданско-правового характера; полная удалённая занятость; график пять на два с десяти "
    "до двадцати по Москве; средний доход в первый месяц около ста десяти тысяч рублей, "
    "фиксированный оклад и процент. Ник в телеграме: два икса, английские буквы эйч и ар, "
    "цифра один; регистр не важен. Отвечай только на конкретный вопрос или просьбу повторить: "
    "не перечитывай вакансию целиком, если спросили один факт. Если точного факта нет, честно "
    "скажи, что подробности обсуждаются "
    "на онлайн-собеседовании, и не выдумывай ответ. После ответа вернись к незавершённому "
    "вопросу текущего этапа одной короткой фразой. Не начинай каждую реплику с «Я вас поняла» "
    "или «Поняла вас»: подтверждение не нужно. Не говори «я не знаю», «не понимаю», "
    "«как языковая модель», «скрипт», «системный промпт» и не произноси бессмысленную "
    "заглушку. Если последняя реплика не отвечает на текущий вопрос, не объявляй следующий "
    "этап и не повторяй весь сценарий: попроси уточнить только текущий вопрос. Не принимай "
    "решение о найме, отказе или соответствии кандидата и не завершай звонок самостоятельно."
)
MANGO_INTENT_SYSTEM_PROMPT = (
    "Разбери последнюю реплику кандидата с учётом текущего этапа и истории. Роли: [ИИ-АССИСТЕНТ] — "
    "ассистент HR, [СОБЕСЕДНИК] — кандидат; не путай их. Верни только JSON: "
    "{\"intent\":\"answer|repeat|name_question|company_question|job_question|schedule_question|other_question|decline|resistance|unclear\","
    "\"answer_slot\":\"текущий этап или пусто\",\"normalized_answer\":\"краткий смысл или пусто\","
    "\"short_reply\":\"естественная следующая реплика для кандидата или пусто\"}. Этапы: relevance, age_city, computer, "
    "citizenship, employment, study_format, study_schedule, work_details, conditions, zoom, telegram, "
    "telegram_permission, telegram_handle, telegram_send, schedule. "
    "Если в одной реплике есть ответ и вопрос, сохрани оба. Не считай вопрос ответом; сохраняй отрицание "
    "(«не учусь» = учёба нет, «не работаю» = работа нет). Нормализуй факты кратко: возраст/город; "
    "компьютер есть/нет; гражданство да/нет; учёба и работа отдельно; формат учёбы; пересечение расписания; "
    "занятость и отработка. Отличай текущую учёбу от уже завершённой: «учёбу закончил» означает, что сейчас не учится, "
    "если человек отдельно не сказал, что продолжает учиться. Неуверенность не считай подтверждением. "
    "decline — только явный отказ от вакансии "
    "или просьба закончить звонок, а не любое «нет». resistance — отказ раскрывать личные данные "
    "или настойчивое возражение по текущему вопросу; не путай его с отказом от вакансии. short_reply "
    "отвечай только известными фактами, неизвестное отложи "
    "до собеседования. Факты вакансии: персональный инвестиционный советник в компании «Баланс»; "
    "работа с клиентами; полная удалённая занятость; трудовой договор или договор гражданско-правового "
    "характера; график пять на два с десяти до двадцати по Москве; средний доход в первый месяц около "
    "ста десяти тысяч рублей из фиксированного оклада и процента. Телеграм-ник: два икса, английские "
    "буквы эйч и ар, цифра один; регистр букв не важен. Отвечай только на конкретно спрошенную часть. "
    "Если спрашивают только зарплату, не пересказывай должность, график и оформление. Если просят "
    "повторить отдельную деталь, повтори только её. Не повторяй весь сценарий и не добавляй "
    "«Конечно, повторю». Если кандидат не хочет сообщать точный адрес или личные данные, не дави: "
    "объясни, что для первичного отбора достаточно города, предложи пропустить вопрос и коротко "
    "расскажи о вакансии, затем спроси, хочет ли он услышать условия. Если он повторно явно "
    "отказывается продолжать, уважительно заверши звонок. Для нестандартной реплики подготовь "
    "естественный короткий ответ, который учитывает контекст и возвращает разговор к текущему "
    "этапу. Не выдумывай факты и не решай за кандидата, подходит ли он."
)
INDEX_FILE = STATIC_DIR / "index.html"
DEFAULT_TTS_CACHE_DIR = Path(os.getenv("LOCALAPPDATA", str(BASE_DIR))) / "VoiceBridge" / "silero_models"
TTS_CACHE_DIR = Path(os.getenv("VOICEBRIDGE_TTS_CACHE", str(DEFAULT_TTS_CACHE_DIR))).expanduser()
GIGAAM_CACHE_DIR = Path(
    os.getenv("VOICEBRIDGE_GIGAAM_CACHE", str(BASE_DIR / "gigaam-v2-onnx"))
).expanduser()
GIGAAM_BUNDLED_DIR = RESOURCE_DIR / "gigaam-v2-onnx"
QWEN_BUNDLED_DIR = RESOURCE_DIR / "qwen3-1.7b"
if not QWEN_BUNDLED_DIR.exists() and (RESOURCE_DIR / "models" / "qwen3-1.7b").exists():
    QWEN_BUNDLED_DIR = RESOURCE_DIR / "models" / "qwen3-1.7b"

# Keep old relative cache settings away from the Cyrillic project directory.
if not TTS_CACHE_DIR.is_absolute():
    TTS_CACHE_DIR = DEFAULT_TTS_CACHE_DIR
if not GIGAAM_CACHE_DIR.is_absolute():
    GIGAAM_CACHE_DIR = BASE_DIR / "gigaam-v2-onnx"

# Let ONNX Runtime find the CUDA/cuDNN DLLs bundled with PyTorch in a
# PyInstaller portable build.
def _prepare_cuda_dll_paths() -> None:
    candidates: list[Path] = []
    if torch is not None:
        try:
            candidates.append(Path(torch.__file__).resolve().parent / "lib")
        except (AttributeError, OSError):
            pass
    candidates.extend([
        RESOURCE_DIR / "torch" / "lib",
        RESOURCE_DIR / "qwen3-1.7b" / "cuda",
        RESOURCE_DIR / "models" / "qwen3-1.7b" / "cuda",
    ])
    seen: set[str] = set()
    for candidate in candidates:
        try:
            path = candidate.resolve()
        except OSError:
            continue
        key = os.path.normcase(str(path))
        if key in seen or not path.is_dir():
            continue
        seen.add(key)
        os.environ["PATH"] = str(path) + os.pathsep + os.environ.get("PATH", "")
        if os.name == "nt" and hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(str(path))
            except OSError:
                pass


_prepare_cuda_dll_paths()

# Keep the optional Xet downloader out of the portable runtime.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

if torch is not None:
    try:
        torch.set_num_threads(int(os.getenv("VOICEBRIDGE_TORCH_THREADS", str(_CPU_THREADS))))
        torch.set_num_interop_threads(max(1, min(4, _CPU_THREADS // 2)))
    except RuntimeError:
        pass
    if hasattr(torch, "set_float32_matmul_precision"):
        torch.set_float32_matmul_precision("high")
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.backends.cudnn.benchmark = True

# Keep the server log actionable when an optional runtime emits deprecation notices.
warnings.filterwarnings("ignore", message=r".*deprecated.*", category=FutureWarning)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

DEFAULT_TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "ru")
DEFAULT_LANGUAGE = os.getenv("GROQ_STT_LANGUAGE", "auto")
DEFAULT_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
LOCAL_STT_MODEL = "gigaam-v2-ctc"
GIGAAM_STT_QUANTIZATION = os.getenv("GIGAAM_STT_QUANTIZATION", "int8")
LOCAL_LLM_BASE_URL = "local://qwen3-1.7b"
LOCAL_LLM_MODEL = "Qwen3-1.7B-Q4_K_M.gguf"
LOCAL_LLM_REASONING_BUDGET = max(32, int(os.getenv("LOCAL_LLM_REASONING_BUDGET", "96")))
LOCAL_LLM_CALL_MAX_TOKENS = max(64, int(os.getenv("VOICEBRIDGE_CALL_MAX_TOKENS", "96")))
LOCAL_LLM_INTENT_MAX_TOKENS = max(64, int(os.getenv("VOICEBRIDGE_INTENT_MAX_TOKENS", "144")))
LOCAL_LLM_TEMPERATURE = float(os.getenv("LOCAL_LLM_TEMPERATURE", "0.7"))
DEFAULT_LLM_BASE_URL = os.getenv("OPENAI_COMPAT_BASE_URL", LOCAL_LLM_BASE_URL).rstrip("/")
DEFAULT_LLM_MODEL = os.getenv("OPENAI_COMPAT_MODEL", LOCAL_LLM_MODEL)
DEFAULT_SYSTEM_PROMPT = os.getenv("VOICE_BRIDGE_SYSTEM_PROMPT", MANGO_CALL_SYSTEM_PROMPT)
DEFAULT_RVC_COMMAND = os.getenv(
    "RVC_CMD_TEMPLATE",
    '{rvc_command} --model "{model_path}" --input "{input_wav}" '
    '--output "{output_wav}" --index "{index_path}" --index-rate 0.75 --f0-method pm --overwrite',
)
GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
STT_MODELS = ["whisper-large-v3-turbo", "whisper-large-v3"]
STT_MODELS.append(LOCAL_STT_MODEL)
SILERO_TTS_LANGUAGES = ["ru", "en"]
SILERO_TTS_LANGUAGE_NAMES = {"ru": "Русский", "en": "English"}
SILERO_TTS_MODEL_IDS = {"ru": "v5_5_ru", "en": "v3_en"}
SILERO_TTS_SPEAKERS = {
    "ru": ["aidar", "baya", "kseniya", "xenia", "eugene"],
    "en": ["en_0"],
}
SILERO_TTS_SPEAKER_NAMES = {
    "aidar": "Aidar", "baya": "Baya", "kseniya": "Kseniya",
    "xenia": "Xenia", "eugene": "Eugene", "en_0": "English 0",
}
DEFAULT_SILERO_TTS_MODEL = "silero-v5.5"
DEFAULT_SILERO_SPEAKER = os.getenv("SILERO_TTS_SPEAKER", "xenia")
VAD_THRESHOLD = min(max(float(os.getenv("VOICEBRIDGE_VAD_THRESHOLD", "0.68")), 0.5), 0.95)
VAD_MIN_SPEECH_SECONDS = min(
    max(float(os.getenv("VOICEBRIDGE_VAD_MIN_SPEECH_SECONDS", "0.18")), 0.08),
    0.8,
)
VAD_INTERRUPT_THRESHOLD = min(
    max(float(os.getenv("VOICEBRIDGE_VAD_INTERRUPT_THRESHOLD", "0.82")), 0.65),
    0.98,
)
VAD_INTERRUPT_MIN_SPEECH_SECONDS = min(
    max(float(os.getenv("VOICEBRIDGE_VAD_INTERRUPT_MIN_SPEECH_SECONDS", "0.14")), 0.10),
    1.0,
)
# A pause of about three quarters of a second is enough to finish most phone
# phrases without adding a full second of dead air before STT starts.
MANGO_SILENCE_SECONDS = min(
    max(float(os.getenv("VOICEBRIDGE_SILENCE_SECONDS", "0.75")), 0.55),
    1.5,
)
MANGO_INTERRUPT_SILENCE_SECONDS = min(
    max(float(os.getenv("VOICEBRIDGE_INTERRUPT_SILENCE_SECONDS", "0.7")), 0.55),
    1.5,
)
VOICE_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
AUDIO_EXTENSIONS = VOICE_EXTENSIONS | {".webm", ".opus", ".aac"}
STORAGE_DIRS = {
    "voices": VOICE_DIR,
    "audio": AUDIO_DIR,
    "outputs": OUTPUT_DIR,
    "model_cache": TTS_CACHE_DIR,
    "rvc": RVC_DIR,
}

# The endpoint is copied from the user's existing ai helper VPN integration.
# Environment variables remain available so the app can be moved without editing code.
VPN_PROXY_PORT = 41809
VPN_SERVER = os.getenv("VOICEBRIDGE_VPN_SERVER", "connect.echocloud.space:16770")
VPN_AUTH = os.getenv("VOICEBRIDGE_VPN_AUTH", "dasfs0a488ynkt1q")
VPN_SNI = os.getenv("VOICEBRIDGE_VPN_SNI", "connect.echocloud.space")
VPN_OBFS_PASSWORD = os.getenv("VOICEBRIDGE_VPN_OBFS_PASSWORD", "e0tsxwwokzssaf2h")
VPN_DOWNLOAD_URLS = (
    "https://github.com/HyNetworks/hysteria/releases/latest/download/hysteria-windows-amd64.exe",
    "https://github.com/apernet/hysteria/releases/latest/download/hysteria-windows-amd64.exe",
)

app = FastAPI(title="Voice Bridge", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(tauri://localhost|https?://tauri\.localhost|https?://(localhost|127\.0\.0\.1)(:\d+)?)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _normalize_text(value: str) -> str:
    return (value or "").strip()


def _is_assistant_history_role(role: object) -> bool:
    """Treat UI labels and OpenAI role names as assistant messages."""
    lowered = _normalize_text(str(role)).lower()
    return lowered in {"яна", "assistant", "ассистент", "ии-ассистент hr", "ии-ассистент", "jana"}


def _llm_history_label(role: object) -> str:
    """Make the speaker explicit inside message content for every provider."""
    return "[ИИ-АССИСТЕНТ]" if _is_assistant_history_role(role) else "[СОБЕСЕДНИК]"


def _is_voice_history(history: list[dict[str, str]] | None) -> bool:
    if not history:
        return False
    voice_roles = {"яна", "собеседник", "кандидат", "candidate", "jana", "ии-ассистент hr", "ии-ассистент"}
    return any(
        _normalize_text(str(item.get("role", ""))).lower() in voice_roles
        for item in history
        if isinstance(item, dict)
    )


def _candidate_greeting(name: str = "") -> str:
    clean_name = re.sub(r"\s+", " ", _normalize_text(str(name))).strip(" ,.;:-")
    if not clean_name or clean_name.lower() in {"без имени", "не указано", "кандидат"}:
        return MANGO_GREETING
    return MANGO_GREETING_WITH_NAME.format(name=clean_name)


def _new_candidate_record(number: str, name: str = "") -> dict[str, Any]:
    call_id = uuid.uuid4().hex
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "call_id": call_id,
        "number": number,
        "name": _normalize_text(name),
        "age_city": "",
        "computer": "",
        "citizenship": "",
        "employment": "",
        "study_format": "",
        "study_schedule": "",
        "work_details": "",
        "conditions_spoken": False,
        "objection": "",
        "autoanswer_text": "",
        "review_flags": [],
        "turns": [],
        "report": "",
        "result": "in_progress",
        # The conversation starts immediately after the greeting. Keep this
        # legacy field true for existing reporting/Telegram gates.
        "consent_to_continue": True,
        "schedule_today_refusal_count": 0,
        "stage": "relevance",
        "startedAt": now,
        "updatedAt": now,
    }


def _add_candidate_review_flag(candidate: dict[str, Any], flag: str) -> None:
    flags = candidate.setdefault("review_flags", [])
    if not isinstance(flags, list):
        flags = []
        candidate["review_flags"] = flags
    if flag not in flags:
        flags.append(flag)


def _extract_candidate_age_city(value: str) -> str:
    """Reduce a spoken age/location answer to `age, city` for the report."""
    text = _normalize_text(value)
    lowered = text.lower()
    age = ""
    numeric_age = re.search(r"\b(?:1[6-9]|[2-9]\d)\b", lowered)
    if numeric_age:
        age = numeric_age.group(0)
    else:
        tens = {
            "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19,
            "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
            "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
        }
        units = {"один": 1, "два": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9}
        for word, number in tens.items():
            if re.search(rf"\b{word}\b", lowered):
                unit = next((unit_value for unit_word, unit_value in units.items() if re.search(rf"\b{unit_word}\b", lowered)), 0)
                age = str(number + unit)
                break
    city = ""
    city_match = re.search(
        r"(?:живу|проживаю|нахожусь|из|город|место проживания)\s*(?:в|:)?\s*([^,.!?;]+)",
        text,
        flags=re.IGNORECASE,
    )
    if city_match:
        city = re.sub(r"\s+", " ", city_match.group(1)).strip(" -")
    if not city:
        known_city = re.search(r"\b(санкт\s*-?\s*петербург\w*|москв\w*)\b", lowered)
        if known_city:
            city = known_city.group(1)
    if city:
        city_lower = city.lower().replace("ё", "е")
        if re.match(r"санкт\s*-?\s*петербург", city_lower):
            city = "Санкт-Петербург"
        elif city_lower.startswith("москв"):
            city = "Москва"
        elif city != "Санкт-Петербург":
            city = city[:1].upper() + city[1:]
    return ", ".join(part for part in (age, city) if part)


def _computer_access_status(value: str) -> bool | None:
    """Return whether a candidate has a PC/laptop; mobile-only is not enough."""
    text = re.sub(r"\s+", " ", _normalize_text(value).lower()).strip()
    if not text:
        return None
    computer = r"(?:компьютер\w*|комп\w*|пк|ноутбук\w*|ноут\w*|лэптоп\w*)"
    positive = bool(re.search(
        rf"(?:\b(?:есть|имеется|имею|пользуюсь)\b.{{0,24}}\b{computer}\b|"
        rf"\b{computer}\b.{{0,12}}\b(?:есть|имеется)\b|у меня\s+{computer}\b)",
        text,
    ))
    if positive:
        return True
    negative = bool(re.search(
        rf"(?:\b(?:нет|нету|без|отсутствует)\b.{{0,24}}\b{computer}\b|"
        rf"\b{computer}\b.{{0,12}}\b(?:нет|нету|отсутствует)\b|"
        rf"не\s+имею.{{0,16}}\b{computer}\b)",
        text,
    ))
    if negative:
        return False
    mobile_only = bool(re.search(
        r"\b(?:только|лишь)\b.{0,20}\b(?:телефон\w*|смартфон\w*|планшет\w*|айпад\w*|ipad\w*)\b|"
        r"\b(?:телефон\w*|смартфон\w*|планшет\w*|айпад\w*|ipad\w*)\b.{0,20}\b(?:только|лишь)\b",
        text,
    ))
    if mobile_only:
        return False
    if re.fullmatch(
        r"(?:(?:да|ага|угу|конечно)[\s,]*)*(?:есть|имеется|имею)"
        r"(?:[\s,]*(?:да|конечно))*[.! ]*",
        text,
    ):
        return True
    if re.fullmatch(r"(?:да|ага|угу|есть|имеется|имею|конечно)[.! ]*", text):
        return True
    if re.fullmatch(r"(?:нет|нету|неа|отсутствует)[.! ]*", text):
        return False
    if re.search(rf"\b{computer}\b", text):
        return True
    return None


def _candidate_currently_studies(value: str) -> bool:
    lowered = _normalize_text(value).lower()
    if not re.search(r"уч[её]б|учусь|университет|колледж|студент|обуча", lowered):
        return False
    explicitly_not_studying = bool(re.search(
        r"(?:нет|нету|без)\s+(?:сейчас\s+)?(?:уч[её]б\w*|университет\w*|колледж\w*|студент\w*)|"
        r"\bне\s+(?:учусь|учится|учиться|обучаюсь|обучается|студент\w*|занимаюсь)\b|"
        r"уч[её]б\w*[\s:,-]+(?:нет|не было|отсутствует)|"
        r"(?:раньше|ранее|уже)\s+(?:учил\w*|обучал\w*)|"
        r"(?:закончил\w*|окончил\w*|завершил\w*|бросил\w*).{0,30}(?:уч[её]б\w*|обучени\w*|университет\w*|колледж\w*)|"
        r"(?:уч[её]б\w*|обучени\w*|университет\w*|колледж\w*).{0,30}(?:закончил\w*|окончил\w*|завершил\w*|бросил\w*)",
        lowered,
    ))
    current_study = bool(re.search(
        r"(?<!не )\b(?:учусь|учится|обучаюсь|обучается|прохожу обучение|сейчас студент\w*|я студент\w*)\b|"
        r"(?:уч[её]б\w*|обучени\w*).{0,24}\b(?:сейчас|ид[её]т|проходит|очно|заочно|вечерн\w*|дистанцион\w*)\b",
        lowered,
    ))
    if current_study and (
        not explicitly_not_studying
        or bool(re.search(r"(?:но|а|зато|сейчас).{0,24}(?<!не )\b(?:учусь|учится|обучаюсь|обучается|студент\w*)\b", lowered))
    ):
        return True
    if explicitly_not_studying:
        return False
    # Past-tense-only answers such as «учился раньше, сейчас работаю» must not
    # be reported as current education.
    if re.search(r"\b(?:учился|училась|учились|обучался|обучалась|обучались)\b", lowered):
        return False
    return True


_CANDIDATE_OUTCOMES = {
    "autoanswer_detected": "автоответчик",
    "no_human_answer": "абонент недоступен",
    "no_response": "не ответил после вопроса",
    "call_busy": "линия занята",
    "call_no_answer": "не ответил на звонок",
    "remote_hangup": "собеседник завершил звонок",
    "declined_at_opening": "отказался от вакансии",
    "declined_conditions": "не подошли условия",
    "declined_notice": "нужна обязательная отработка",
    "declined_study_schedule": "график пересекается с учёбой",
    "declined_no_device": "нет компьютера или ноутбука",
    "declined_zoom": "отказался от собеседования",
    "declined_telegram": "отказался продолжать в Telegram",
    "declined_scheduling": "отказался подбирать время собеседования",
    "declined_by_candidate": "отказался продолжать разговор",
    "declined_scheduled": "отменил собеседование",
    "wrong_recipient": "ответил другой человек",
    "qualified": "прошёл первичный опрос",
}


def _candidate_status_line(candidate: dict[str, Any]) -> str:
    name = _normalize_text(str(candidate.get("name", "")))
    if not name:
        name = _normalize_text(str(candidate.get("number", ""))) or "Абонент"
    outcome = _CANDIDATE_OUTCOMES.get(str(candidate.get("result", "")), "звонок завершён")
    return f"{name}: {outcome}"


def _refresh_candidate_report(candidate: dict[str, Any]) -> str:
    """Build a short field report; raw turns remain stored separately."""
    def short_value(key: str, value: str) -> str:
        text = _normalize_text(value)
        lowered = text.lower()
        if not text:
            return ""
        if key == "age_city":
            if re.match(r"^\d{1,3},\s*\S", text):
                return re.sub(r"\s+", " ", text)[:80]
            return _extract_candidate_age_city(text) or re.sub(r"\s+", " ", text)[:80]
        if key == "computer":
            access = _computer_access_status(text)
            if access is not None:
                return "есть" if access else "нет"
        if key == "citizenship":
            if re.search(r"не\s+(?:граждан|имею гражданств)|гражданств\w*\s+нет", lowered):
                return "нет"
            if re.search(
                r"\b(?:гражданин|гражданка)\b|"
                r"гражданств\w*\s+(?:рф|росси\w*)?\s*(?:есть|да)|"
                r"(?:рф|росси\w*)\s+(?:гражданств\w*|гражданин\w*)",
                lowered,
            ):
                return "да"
        if key == "employment":
            has_study = _candidate_currently_studies(lowered)
            has_work = bool(re.search(r"работ|занят|трудоустро|служб", lowered))
            has_work = has_work and not bool(re.search(
                r"(?:нет|нету|без)\s+(?:сейчас\s+)?(?:уч[её]б\w*\s+и\s+)?работ\w*|"
                r"\bне\s+(?:работаю|работает|работать|трудоустроен|трудоустроена)\b|"
                r"работ\w*[\s:,-]+(?:нет|не\s+имею|отсутств\w*)",
                lowered,
            ))
            parts = []
            if re.search(r"уч[её]б|учусь|университет|колледж|студент", lowered):
                parts.append(f"учёба: {'есть' if has_study else 'нет'}")
            if re.search(r"работ|занят|трудоустро|служб", lowered):
                parts.append(f"работа: {'есть' if has_work else 'нет'}")
            if parts:
                return "; ".join(parts)
        if key == "study_format":
            if re.search(r"очно\s*[- ]\s*заоч\w*|заочно\s*[- ]\s*очн\w*", lowered):
                return "очно-заочно"
            if re.search(r"\bзаоч\w*", lowered):
                return "заочно"
            if re.search(r"\bочн\w*|\bдневн\w*", lowered):
                return "очно"
        if key == "study_schedule":
            if re.search(r"не\s+(?:пересека|совпада)|не будет пересек", lowered):
                return "не пересекается с работой"
            if re.search(r"пересека|совпада", lowered):
                return "пересекается с работой"
            if re.search(r"вечер", lowered):
                return "вечером"
            if re.search(r"утр", lowered):
                return "утром"
            if re.search(r"дн", lowered):
                return "днём"
        if key == "work_details":
            parts = []
            if re.search(r"пол(?:ная|ную)\s+занят|полный день", lowered):
                parts.append("полная занятость")
            elif re.search(r"частич|непол", lowered):
                parts.append("неполная занятость")
            if re.search(r"отработ", lowered):
                parts.append(
                    "отработка: нет"
                    if re.search(r"\b(?:не|нет|не потребуется|не нужна)\b", lowered)
                    else "отработка: да"
                )
            time_match = re.search(
                r"с\s+(\d{1,2}(?::\d{2})?)\s*(?:до|по)\s+(\d{1,2}(?::\d{2})?)",
                lowered,
            )
            if time_match:
                parts.append(f"время: {time_match.group(1)}–{time_match.group(2)}")
            if parts:
                return "; ".join(parts)
        if key == "scheduled_at":
            try:
                scheduled = datetime.fromisoformat(text).astimezone(calendar_service.tz)
                return scheduled.strftime("%d.%m.%Y %H:%M по Москве")
            except ValueError:
                return text[:80]
        if key == "objection":
            return re.sub(r"\s+", " ", text)[:140]
        return re.sub(r"\s+", " ", text)[:120]

    labels = (
        ("age_city", "Возраст и город"),
        ("computer", "Компьютер или ноутбук"),
        ("citizenship", "Гражданство РФ"),
        ("employment", "Учёба и работа"),
        ("study_format", "Формат учёбы"),
        ("study_schedule", "Время учёбы"),
        ("work_details", "Занятость и отработка"),
        ("scheduled_at", "Собеседование"),
        ("objection", "Возражение"),
    )
    lines = ["Краткий отчёт кандидата"]
    if candidate.get("name"):
        lines.append(f"ФИО: {candidate['name']}")
    if candidate.get("number"):
        lines.append(f"Номер: {candidate['number']}")
    unknown_values = {
        "не указано", "не указана", "не указан", "неизвестно",
        "не сообщено", "нет данных", "n/a", "unknown",
    }
    for key, label in labels:
        raw_value = str(candidate.get(key, ""))
        value = short_value(key, raw_value)
        if not value or _normalize_text(value).casefold() in unknown_values:
            continue
        lines.append(f"{label}: {value}")
    if candidate.get("result") in _CANDIDATE_OUTCOMES:
        lines.append(_candidate_status_line(candidate))
    flags = candidate.get("review_flags")
    if isinstance(flags, list) and flags:
        lines.append("Проверить вручную: " + "; ".join(str(flag) for flag in flags))
    candidate["report"] = "\n".join(lines)
    return candidate["report"]


def _record_candidate_turn(candidate: dict[str, Any], stage: str, transcript: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    candidate["updatedAt"] = now
    candidate["stage"] = stage
    turns = candidate.setdefault("turns", [])
    if isinstance(turns, list):
        turns.append({"role": "candidate", "stage": stage, "text": transcript, "at": now})
        del turns[:-100]
    _refresh_candidate_report(candidate)


def _telegram_chat_ids(value: str) -> list[str]:
    ids = [item.strip() for item in re.split(r"[,;\s]+", value or "") if item.strip()]
    if any(not re.fullmatch(r"-?\d{1,24}", item) or item == "0" for item in ids):
        raise ValueError("Telegram chat ID должны быть числовыми; несколько ID разделяй запятыми.")
    return list(dict.fromkeys(ids))


def _send_telegram_messages(token: str, chat_ids: list[str], message: str) -> list[str]:
    """Send an opt-in status/report; never include candidate data before consent."""
    failures: list[str] = []
    if not token or not chat_ids or not message:
        return ["Укажи токен Telegram-бота, chat ID и текст сообщения."]
    if len(message) > 4000:
        message = message[:3980] + "…"
    for chat_id in chat_ids:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
                timeout=8,
            )
            payload = response.json()
            if not response.ok or not payload.get("ok"):
                failures.append(f"Не удалось отправить уведомление для chat ID {chat_id}.")
        except Exception:  # noqa: BLE001
            failures.append(f"Не удалось связаться с Telegram для chat ID {chat_id}.")
    return failures


def _save_candidate_record(record: dict[str, Any]) -> None:
    """Keep completed call answers in user data without blocking the call loop."""
    try:
        CANDIDATE_RECORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing: list[Any] = []
        if CANDIDATE_RECORDS_FILE.exists():
            try:
                payload = json.loads(CANDIDATE_RECORDS_FILE.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    existing = payload
            except (OSError, ValueError):
                logging.warning("Candidate records file is unreadable; starting a new list.")
        record_id = _normalize_text(str(record.get("call_id", "")))
        replaced = False
        if record_id:
            for index, item in enumerate(existing):
                if isinstance(item, dict) and _normalize_text(str(item.get("call_id", ""))) == record_id:
                    existing[index] = record
                    replaced = True
                    break
        if not replaced:
            existing.append(record)
        existing = existing[-500:]
        temporary = CANDIDATE_RECORDS_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(CANDIDATE_RECORDS_FILE)
    except OSError:
        logging.exception("Could not persist candidate record")


def _delete_candidate_record(call_id: str) -> None:
    """Remove a candidate record when they withdraw from the conversation."""
    record_id = _normalize_text(call_id)
    if not record_id or not CANDIDATE_RECORDS_FILE.exists():
        return
    try:
        payload = json.loads(CANDIDATE_RECORDS_FILE.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return
        retained = [
            item for item in payload
            if not isinstance(item, dict)
            or _normalize_text(str(item.get("call_id", ""))) != record_id
        ]
        temporary = CANDIDATE_RECORDS_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(retained, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(CANDIDATE_RECORDS_FILE)
    except (OSError, ValueError):
        logging.exception("Could not remove withdrawn candidate record")


def _parse_chat_history(value: str) -> list[dict[str, str]]:
    if not value:
        return []
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    history: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = _normalize_text(str(item.get("text", "")))
        role = _normalize_text(str(item.get("role", "")))
        if text and role in {"Яна", "ИИ-ассистент HR", "Собеседник", "assistant", "user"}:
            history.append({"role": role, "text": text})
    return history


def _local_qwen_turn_hint(history: list[dict[str, str]] | None, transcript: str) -> str:
    """Give the tiny local model the next script step without hiding the reply."""
    if not history:
        return transcript
    lowered = _normalize_text(transcript).lower()
    if re.search(r"что за работа|расскажите о работе|какая работа|ваканс", lowered):
        hint = "Кандидат спрашивает о вакансии: кратко ответь по условиям вакансии и вернись к текущему вопросу."
    else:
        assistant_lines = [
            _normalize_text(str(item.get("text", "")))
            for item in history
            if _is_assistant_history_role(item.get("role")) and item.get("text")
        ]
        last = assistant_lines[-1].lower() if assistant_lines else ""
        if "возраст" in last and "город" in last:
            hint = "Возраст и город уже спросили. Следующий единственный вопрос: есть ли у кандидата компьютер или ноутбук для удалённой работы?"
        elif "компьютер" in last or "ноутбук" in last:
            hint = "Наличие компьютера уже спросили. Следующий единственный вопрос: гражданство кандидата — Российская Федерация или нет?"
        elif "гражданств" in last:
            hint = "Гражданство уже спросили. Следующий единственный вопрос: есть ли сейчас учёба или работа?"
        elif "есть ли сейчас учёба или работа" in last:
            hint = "Вопросы о кандидате пройдены. Перейди к следующему незавершённому блоку сценария, не повторяй вопросы."
        elif "в каком формате вы учитесь" in last:
            hint = "Уточни только формат учёбы, не возвращайся к началу разговора."
        elif "полная занятость" in last or "потребуется ли отработка" in last:
            hint = "Уточни только занятость и отработку, не зачитывай вакансию заново."
        else:
            hint = "Определи смысл последней реплики по истории и задай только следующий уместный вопрос."
    return f"{transcript}\n\nСлужебная подсказка для выбора следующего шага: {hint}"


def _prepare_silero_text(value: str) -> str:
    """Convert typographic/unsupported characters before Silero tokenization."""
    replacements = {
        "—": ", ",
        "–": ", ",
        "‑": "-",
        "…": "...",
        "«": '"',
        "»": '"',
        "„": '"',
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
        " ": " ",
    }
    text = unicodedata.normalize("NFKC", _normalize_text(value))
    text = re.sub(r"\bxxhr1\b", "икс икс эйч ар один", text, flags=re.IGNORECASE)
    text = re.sub(r"\bH\s*R\b", "эйч ар", text, flags=re.IGNORECASE)
    text = re.sub(r"\bООО\b", "общество с ограниченной ответственностью", text, flags=re.IGNORECASE)
    text = re.sub(r"\bГПХ\b", "гражданско правового характера", text, flags=re.IGNORECASE)
    text = re.sub(r"\bТК\b", "трудовой договор", text, flags=re.IGNORECASE)
    text = re.sub(r"\bZoom\b", "зум", text, flags=re.IGNORECASE)
    text = re.sub(r"\bTelegram\b", "телеграм", text, flags=re.IGNORECASE)
    text = re.sub(r"\b5\s*/\s*2\b", "пять на два", text)
    text = re.sub(r"\b10\s*:\s*00\b", "десять часов", text)
    text = re.sub(r"\b20\s*:\s*00\b", "двадцать часов", text)
    text = re.sub(r"\b110[.\s]?000\b", "сто десять тысяч", text)
    for source, target in replacements.items():
        text = text.replace(source, target)

    allowed_punctuation = set(".,!?;:()[]'\"/-+*")
    cleaned = []
    for char in text:
        if char.isalnum() or char.isspace() or char in allowed_punctuation:
            cleaned.append(char)
        else:
            cleaned.append(" ")
    return re.sub(r"\s+", " ", "".join(cleaned)).strip()


def _split_silero_text(value: str, max_chars: int = 700) -> list[str]:
    """Keep Silero's internal positional sequence below its 5000-step limit."""
    text = value.strip()
    if len(text) <= max_chars:
        return [text] if text else []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""

    def append_piece(piece: str) -> None:
        nonlocal current
        piece = piece.strip()
        if not piece:
            return
        candidate = f"{current} {piece}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            return
        if current:
            chunks.append(current)
            current = ""
        if len(piece) <= max_chars:
            current = piece
            return
        words = piece.split()
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = word
            else:
                current = candidate

    for sentence in sentences:
        append_piece(sentence)
    if current:
        chunks.append(current)
    return chunks


def _cyrillic_count(value: str) -> int:
    return sum("\u0400" <= char <= "\u04ff" for char in value)


def _latin_count(value: str) -> int:
    return sum(("a" <= char.lower() <= "z") for char in value)


def _silero_fallback_language(value: str, language: str) -> str:
    """Choose the other bundled Silero model for a pure foreign-script segment."""
    if language == "ru" and _cyrillic_count(value) == 0 and _latin_count(value) > 0:
        return "en"
    if language == "en" and _latin_count(value) == 0 and _cyrillic_count(value) > 0:
        return "ru"
    return language


def _silero_type_for_segment(value: str) -> str | None:
    """Pass Silero a prosody type for every sentence in the synthesized chunk."""
    sentences = re.split(r"(?<=[.!?])\s+", value.strip())
    types: list[str] = []
    has_question = False
    for sentence in sentences:
        text = re.sub(r"\s+", " ", sentence.strip().lower())
        # The packaged Silero classifier has an explicit tag-question class;
        # use it for confirmation questions such as "Это имя, верно?".
        question_text = text.rstrip(" \t\"'»")
        if not question_text.endswith("?"):
            types.append("st")
            continue

        has_question = True
        if re.search(r",\s*(?:верно|правильно|так|не так ли)\s*\?$", question_text):
            types.append("tag_q")
        elif re.search(r"\bили\b", question_text):
            types.append("alternative_q")
        elif re.match(
            r"^(?:а\s+)?(?:кто|что|где|куда|откуда|когда|почему|зачем|как|"
            r"какой|какая|какие|какое|сколько|чей|чья|чьи)\b",
            question_text,
        ):
            types.append("wh_q")
        else:
            types.append("general_q")
    return "|".join(types) if has_question else None


def _silero_mark_question_focus(value: str) -> str:
    """Mark one question's semantic nucleus for Silero v5 prosody."""
    if "?" not in value or "*" in value:
        return value

    words = list(re.finditer(r"[\w-]+", value, flags=re.UNICODE))
    if not words:
        return value
    lower = value.lower()

    focus = None
    ignored = {
        "а", "вы", "вас", "вам", "ваш", "ваша", "ваше", "ваши", "у", "в", "на", "по",
        "для", "с", "со", "к", "и", "или", "ли", "же", "бы", "то", "это", "мне", "меня",
        "мы", "я", "сейчас", "пожалуйста", "именно", "примерно", "вообще", "уже", "там",
        "будет",
    }

    def word_at(match: re.Match[str], group: int = 0) -> re.Match[str] | None:
        start = match.start(group)
        return next((word for word in words if word.start() == start), None)

    # In booking confirmations the intended question is whether the person
    # agrees to be booked, not the time being offered.
    booking = re.search(r"\b(записать)\s+(?:ли\s+)?вас\b", lower)
    if booking:
        focus = word_at(booking, 1)
    if focus is None:
        confirmation = re.search(r"\b(подтвердить)\s+запис\w*\b", lower)
        if confirmation:
            focus = word_at(confirmation, 1)
    if focus is None:
        relevance = re.search(r"\b(актуал\w*)\b", lower)
        if relevance:
            focus = word_at(relevance, 1)

    # A tag such as "верно?" is itself the confirmation question's focus.
    if focus is None:
        tag = re.search(r"\b(верно|правильно)\s*\?$", lower)
        if tag:
            focus = word_at(tag, 1)
        elif re.search(r"\bне\s+так\s+ли\s*\?$", lower):
            tag = re.search(r"\b(так)\s+ли\s*\?$", lower)
            focus = word_at(tag, 1) if tag else None

    if focus is None:
        # In open questions, accent the requested fact rather than the
        # sentence-final verb or a function word after the question word.
        wh = re.search(
            r"\b(кто|что|где|куда|откуда|когда|почему|зачем|как|какой|какая|какие|"
            r"какое|каком|какую|каких|сколько|чей|чья|чьи)\b",
            lower,
        )
        if wh:
            if wh.group(1) == "что" and re.match(r"\s+за\b", lower[wh.end():]):
                after_za = re.search(r"\bза\s+([\w-]+)", lower[wh.end():])
                if after_za:
                    offset = wh.end() + after_za.start(1)
                    focus = next((word for word in words if word.start() == offset), None)
            if focus is None:
                focus = next(
                    (
                        word for word in words
                        if word.start() >= wh.end() and word.group().lower() not in ignored
                    ),
                    None,
                )

    if focus is None:
        # For alternatives, the second offered choice carries the contrastive
        # accent ("ноутбук или *компьютер*", "очно или *заочно*").
        conjunction = re.search(r"\bили\b", lower)
        if conjunction:
            focus = next((word for word in words if word.start() >= conjunction.end()), None)

    if focus is None:
        # Yes/no questions usually put their nucleus on the predicate, not on
        # a trailing complement such as "разговор" or "собеседование".
        predicate = re.search(
            r"\b(согласн\w*|актуал\w*|рассматрива\w*|подход\w*|сможете|смогли|"
            r"хотите|хотели|можете|могли|удобн\w*|пересек\w*|будет|"
            r"занятост\w*|отработ\w*|потребу\w*)\b",
            lower,
        )
        if predicate:
            focus = word_at(predicate, 1)

    if focus is None:
        # "город проживания" is one requested detail; stress its head noun.
        city = re.search(r"\b(город)\s+прожив[\w-]*", lower)
        if city:
            focus = word_at(city, 1)

    if focus is None:
        candidates = [word for word in words if word.group().lower() not in ignored]
        if candidates:
            focus = candidates[-1]

    if focus is None:
        return value
    return f"{value[:focus.start()]}*{focus.group()}*{value[focus.end():]}"


def _silero_question_focus(value: str) -> str:
    """Mark each unannotated Russian question independently in a TTS chunk."""
    parts = re.split(r"(?<=[.!?])(\s+)", value)
    return "".join(
        part if not part or part.isspace() else _silero_mark_question_focus(part)
        for part in parts
    )


def _repair_mojibake(value: str) -> str:
    """Repair common UTF-8-as-Windows-1252 text from non-standard LLM APIs."""
    if not isinstance(value, str) or not value:
        return value

    original = value
    best = value
    best_score = 0
    for _ in range(2):
        candidates: list[str] = []
        for encoding in ("latin1", "cp1252"):
            try:
                candidates.append(best.encode(encoding).decode("utf-8"))
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue

        for candidate in candidates:
            score = (_cyrillic_count(candidate) * 4) - sum(
                candidate.count(marker) for marker in ("Ã", "Â", "Ð", "Ñ", "â", "�")
            )
            if _cyrillic_count(candidate) > _cyrillic_count(original) and score > best_score:
                best = candidate
                best_score = score
    return best


class GigaAmSttService:
    """Lazy local Russian ASR using the int8 GigaAM v2 ONNX model."""

    def __init__(self, cache_dir: Path, bundled_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.bundled_dir = bundled_dir
        self._lock = RLock()
        self._model = None
        self._provider = "CPUExecutionProvider"
        self._warmup_thread: Thread | None = None

    def start_warmup(self) -> None:
        """Load the local ASR session before the first call needs it."""
        with self._lock:
            if self._warmup_thread and self._warmup_thread.is_alive():
                return
            self._warmup_thread = Thread(
                target=self._warmup,
                name="gigaam-stt-warmup",
                daemon=True,
            )
            self._warmup_thread.start()

    def _warmup(self) -> None:
        try:
            self._load_model()
            logging.info("GigaAM v2 CTC ONNX warmup completed.")
        except Exception as exc:  # noqa: BLE001
            # Keep startup usable; the first local STT request will retry and
            # return the real diagnostic if the model or runtime is unavailable.
            logging.warning("GigaAM v2 CTC ONNX warmup skipped: %s", exc)

    @staticmethod
    def _runtime():
        try:
            import onnxruntime as ort
        except ImportError:
            return None
        preload = getattr(ort, "preload_dlls", None)
        if preload is not None:
            try:
                preload()
            except Exception:  # noqa: BLE001
                logging.debug("ONNX Runtime CUDA DLL preload was unavailable", exc_info=True)
        return ort

    @classmethod
    def _preferred_provider(cls) -> str:
        ort = cls._runtime()
        if ort is None:
            return "CPUExecutionProvider"
        # ONNX Runtime has its own CUDA provider. Do not gate GigaAM on
        # torch.cuda.is_available() when PyTorch is absent. If a CPU-only
        # PyTorch build is present, however, avoid repeatedly probing a CUDA
        # runtime that cannot work on this machine.
        if torch is not None and not torch.cuda.is_available():
            return "CPUExecutionProvider"
        return (
            "CUDAExecutionProvider"
            if "CUDAExecutionProvider" in ort.get_available_providers()
            else "CPUExecutionProvider"
        )

    def _update_loaded_provider(self) -> None:
        """Reflect the provider actually used by the core ONNX session."""
        try:
            core = getattr(getattr(self._model, "asr", None), "_model", None)
            active = core.get_providers() if core is not None else []
            self._provider = (
                "CUDAExecutionProvider"
                if "CUDAExecutionProvider" in active
                else "CPUExecutionProvider"
            )
        except Exception:  # noqa: BLE001
            self._provider = "CPUExecutionProvider"

    def _load_model(self):
        with self._lock:
            if self._model is not None:
                return self._model

            try:
                import onnx_asr
                ort = self._runtime()
                if ort is None:
                    raise ImportError("onnxruntime is not installed")

                providers = ["CPUExecutionProvider"]
                if self._preferred_provider() == "CUDAExecutionProvider":
                    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
                    self._provider = "CUDAExecutionProvider"
                self.cache_dir.parent.mkdir(parents=True, exist_ok=True)
                model_dir = self.bundled_dir if self._bundled_model_available() else self.cache_dir
                logging.info(
                    "Loading local GigaAM v2 CTC ONNX model (%s quantization, %s, %s)...",
                    GIGAAM_STT_QUANTIZATION,
                    self._provider,
                    "bundled" if model_dir == self.bundled_dir else "cache",
                )
                session_options = ort.SessionOptions()
                session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                session_options.intra_op_num_threads = max(1, min(_CPU_THREADS, 8))
                session_options.inter_op_num_threads = 1
                # The ONNX preprocessor can run through CUDA when CUDA EP is
                # available. On CPU, NumPy is faster for this small front end.
                preprocessor_config = {
                    "max_concurrent_workers": 1,
                    "use_numpy_preprocessors": self._provider != "CUDAExecutionProvider",
                }
                if self._provider == "CUDAExecutionProvider":
                    preprocessor_config["use_conv_preprocessors"] = True
                load_options = {
                    "quantization": GIGAAM_STT_QUANTIZATION,
                    "providers": providers,
                    "sess_options": session_options,
                    "preprocessor_config": preprocessor_config,
                }
                try:
                    self._model = onnx_asr.load_model(
                        LOCAL_STT_MODEL,
                        str(model_dir),
                        **load_options,
                    )
                    self._update_loaded_provider()
                except Exception:
                    if self._provider != "CUDAExecutionProvider":
                        raise
                    logging.exception(
                        "GigaAM CUDA provider failed; retrying with CPUExecutionProvider"
                    )
                    self._provider = "CPUExecutionProvider"
                    load_options["providers"] = ["CPUExecutionProvider"]
                    load_options["preprocessor_config"] = {
                        "max_concurrent_workers": 1,
                        "use_numpy_preprocessors": True,
                    }
                    self._model = onnx_asr.load_model(
                        LOCAL_STT_MODEL,
                        str(model_dir),
                        **load_options,
                    )
                    self._update_loaded_provider()
                logging.info("GigaAM v2 CTC ONNX is ready.")
                return self._model
            except Exception as exc:  # noqa: BLE001
                logging.exception("GigaAM v2 ONNX model load failed")
                raise RuntimeError(
                    "GigaAM v2 ONNX не загрузился. Проверь интернет для первой загрузки "
                    f"модели и папку кэша {self.cache_dir}: {exc}"
                ) from exc

    def _bundled_model_available(self) -> bool:
        return all(
            (self.bundled_dir / filename).is_file()
            for filename in ("config.json", "v2_ctc.int8.onnx", "v2_vocab.txt")
        )

    @staticmethod
    def _wav_to_float32(wav_bytes: bytes):
        import numpy as np

        if wav_bytes[:4] == b"RIFF":
            with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
                channels = max(1, reader.getnchannels())
                sample_width = reader.getsampwidth()
                sample_rate = reader.getframerate()
                raw = reader.readframes(reader.getnframes())
            if sample_width != 2:
                raise ValueError("GigaAM ожидает PCM WAV 16-bit.")
            samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            if channels > 1:
                samples = samples[: len(samples) - (len(samples) % channels)]
                samples = samples.reshape(-1, channels).mean(axis=1)
            return samples, sample_rate

        # Accept common uploaded formats when libsndfile can decode them.
        # Browser recordings are normalized to WAV in app.js before this point.
        try:
            import soundfile as sf

            samples, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
            return samples.mean(axis=1), int(sample_rate)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                "Аудио не является WAV (RIFF) и не удалось декодировать его автоматически. "
                "Для записи из браузера обнови страницу и повтори распознавание."
            ) from exc

    def transcribe(self, wav_bytes: bytes) -> tuple[str, float | None]:
        if not wav_bytes:
            return "", None
        waveform, sample_rate = self._wav_to_float32(wav_bytes)
        if waveform.size == 0:
            return "", None
        model = self._load_model()
        with self._lock:
            result = model.recognize(waveform, sample_rate=sample_rate)
        text = _repair_mojibake(str(result or "").strip())
        return text, round(float(waveform.size / max(1, sample_rate)), 3)

    def info(self) -> dict[str, Any]:
        provider = self._provider if self._model is not None else self._preferred_provider()
        return {
            "id": LOCAL_STT_MODEL,
            "label": "GigaAM v2 CTC · ONNX / " + provider.replace("ExecutionProvider", ""),
            "quantization": GIGAAM_STT_QUANTIZATION,
            "cacheDir": str(self.cache_dir),
            "bundled": self._bundled_model_available(),
            "loaded": self._model is not None,
            "provider": provider,
            "availableProviders": self._available_providers(),
        }

    @staticmethod
    def _available_providers() -> list[str]:
        try:
            ort = GigaAmSttService._runtime()
            if ort is None:
                return []
            return list(ort.get_available_providers())
        except ImportError:
            return []


class HysteriaVpnService:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._process: subprocess.Popen[bytes] | None = None
        self._log_handle = None

    @property
    def binary_path(self) -> Path:
        return self.base_dir / "hysteria.exe"

    @property
    def config_path(self) -> Path:
        return self.base_dir / "hysteria-config.yaml"

    @property
    def log_path(self) -> Path:
        return self.base_dir / "hysteria.log"

    def _binary_is_valid(self) -> bool:
        try:
            if self.binary_path.stat().st_size < 1024 * 1024:
                return False
            with self.binary_path.open("rb") as binary:
                return binary.read(2) == b"MZ"
        except OSError:
            return False

    def _running_unlocked(self) -> bool:
        if self._process is None:
            return False
        if self._process.poll() is None:
            return True
        self._process = None
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None
        return False

    def is_running(self) -> bool:
        with self._lock:
            return self._running_unlocked()

    def status(self) -> dict[str, Any]:
        return {
            "running": self.is_running(),
            "available": self._binary_is_valid(),
            "port": VPN_PROXY_PORT,
            "binPath": str(self.binary_path),
            "configPath": str(self.config_path),
        }

    def _config_text(self) -> str:
        return (
            f'server: "{VPN_SERVER}"\n'
            f'auth: "{VPN_AUTH}"\n'
            "tls:\n"
            f'  sni: "{VPN_SNI}"\n'
            "  insecure: false\n"
            '  alpn:\n    - "h3"\n'
            "obfs:\n"
            "  type: salamander\n"
            "  salamander:\n"
            f'    password: "{VPN_OBFS_PASSWORD}"\n'
            "socks5:\n"
            f'  listen: "127.0.0.1:{VPN_PROXY_PORT}"\n'
        )

    def _stop_unlocked(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._stop_unlocked()
        return self.status()

    def _log_tail(self) -> str:
        try:
            text = self.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text[-1800:].strip()

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._running_unlocked():
                return self.status()

            self._stop_unlocked()
            if not self._binary_is_valid():
                raise RuntimeError(
                    "Hysteria client is not installed or is damaged. Download it again from the VPN panel."
                )

            self.config_path.write_text(self._config_text(), encoding="utf-8")
            self._log_handle = self.log_path.open("w", encoding="utf-8")
            creation_flags = 0x08000000 if os.name == "nt" else 0
            try:
                self._process = subprocess.Popen(
                    [str(self.binary_path), "client", "--config", str(self.config_path)],
                    cwd=str(self.base_dir),
                    stdout=self._log_handle,
                    stderr=subprocess.STDOUT,
                    creationflags=creation_flags,
                )
            except OSError as exc:
                self._stop_unlocked()
                raise RuntimeError(f"Could not start Hysteria client: {exc}") from exc

            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    detail = self._log_tail()
                    self._stop_unlocked()
                    raise RuntimeError(f"Hysteria client exited during startup. {detail}")
                try:
                    with socket.create_connection(("127.0.0.1", VPN_PROXY_PORT), timeout=0.15):
                        return self.status()
                except OSError:
                    time.sleep(0.2)

            detail = self._log_tail()
            self._stop_unlocked()
            raise RuntimeError(
                "Hysteria client did not open the local proxy port. "
                f"Check {self.log_path}. {detail}"
            )

    def download(self) -> dict[str, Any]:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = self.binary_path.with_suffix(".download")
        errors: list[str] = []
        try:
            headers = {
                "User-Agent": "VoiceBridge/0.3",
                "Accept": "application/octet-stream",
            }
            for url in VPN_DOWNLOAD_URLS:
                for attempt in range(3):
                    try:
                        temporary_path.unlink(missing_ok=True)
                        with requests.get(
                            url,
                            headers=headers,
                            stream=True,
                            allow_redirects=True,
                            timeout=(20, 300),
                        ) as response:
                            response.raise_for_status()
                            with temporary_path.open("wb") as output:
                                for chunk in response.iter_content(chunk_size=1024 * 1024):
                                    if chunk:
                                        output.write(chunk)
                        if not self._file_is_valid(temporary_path):
                            raise RuntimeError("сервер вернул не Windows EXE-файл")
                        os.replace(temporary_path, self.binary_path)
                        result = self.status()
                        result["message"] = "Hysteria client downloaded and verified."
                        return result
                    except (requests.RequestException, OSError, RuntimeError) as exc:
                        errors.append(f"{url} attempt {attempt + 1}: {exc}")
                        temporary_path.unlink(missing_ok=True)
                        if attempt < 2:
                            time.sleep(1.5 * (attempt + 1))
        finally:
            temporary_path.unlink(missing_ok=True)
        detail = "; ".join(errors[-4:])
        raise RuntimeError(f"Could not download a valid Hysteria client. {detail}")

    @staticmethod
    def _file_is_valid(path: Path) -> bool:
        try:
            if path.stat().st_size < 1024 * 1024:
                return False
            with path.open("rb") as binary:
                return binary.read(2) == b"MZ"
        except OSError:
            return False


vpn_service = HysteriaVpnService(VPN_DIR)


def vpn_proxy(use_vpn: bool) -> str | None:
    if not use_vpn:
        return None
    if not vpn_service.is_running():
        try:
            vpn_service.start()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=503,
                detail=f"VPN включён, но Hysteria не запустилась автоматически: {exc}",
            ) from exc
    return f"socks5h://127.0.0.1:{VPN_PROXY_PORT}"


def request_proxy_kwargs(proxy: str | None) -> dict[str, Any]:
    if not proxy:
        return {}
    return {"proxies": {"http": proxy, "https": proxy}}


def active_audio_path() -> Path | None:
    if not ACTIVE_AUDIO_META.exists():
        return None
    try:
        metadata = json.loads(ACTIVE_AUDIO_META.read_text(encoding="utf-8"))
        path = AUDIO_DIR / Path(metadata.get("storedName", "")).name
    except (OSError, ValueError, TypeError):
        return None
    return path if path.exists() else None


def active_audio_info() -> dict[str, Any]:
    path = active_audio_path()
    if path is None:
        return {"active": False, "name": "", "size": 0}
    try:
        metadata = json.loads(ACTIVE_AUDIO_META.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        metadata = {}
    return {
        "active": True,
        "name": metadata.get("name") or path.name,
        "size": path.stat().st_size,
        "contentType": metadata.get("contentType") or "application/octet-stream",
    }


def save_active_audio(filename: str, content_type: str, audio_bytes: bytes) -> dict[str, Any]:
    extension = Path(filename or "").suffix.lower() or ".webm"
    if extension not in AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Use an audio file such as WAV, MP3, OGG, M4A, or WEBM.")
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="The audio file is empty.")
    if len(audio_bytes) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="The audio file is too large.")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    for old_path in AUDIO_DIR.glob("active_input.*"):
        old_path.unlink(missing_ok=True)
    path = AUDIO_DIR / f"active_input{extension}"
    path.write_bytes(audio_bytes)
    ACTIVE_AUDIO_META.write_text(
        json.dumps(
            {"name": filename or path.name, "storedName": path.name, "contentType": content_type or ""},
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    return active_audio_info()


def delete_active_audio() -> dict[str, Any]:
    for path in AUDIO_DIR.glob("active_input.*"):
        path.unlink(missing_ok=True)
    ACTIVE_AUDIO_META.unlink(missing_ok=True)
    return active_audio_info()


def save_generated_audio(audio_bytes: bytes) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = OUTPUT_DIR / f"speech_{stamp}.wav"
    path.write_bytes(audio_bytes)
    return {"name": path.name, "path": str(path), "size": len(audio_bytes)}


def storage_info(kind: str) -> dict[str, Any]:
    path = STORAGE_DIRS[kind]
    path.mkdir(parents=True, exist_ok=True)
    files = [item for item in path.rglob("*") if item.is_file()]
    return {
        "kind": kind,
        "path": str(path),
        "fileCount": len(files),
        "size": sum(item.stat().st_size for item in files),
    }


def clear_storage_files(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for item in path.iterdir():
        if item.is_file():
            item.unlink(missing_ok=True)


def _gpu_system_stats() -> dict[str, Any]:
    """Return live NVIDIA utilization without requiring a local ML framework."""
    unavailable = {
        "available": False,
        "name": "",
        "percent": None,
        "memoryPercent": None,
        "memoryUsed": 0,
        "memoryTotal": 0,
    }
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,name",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=0.8,
            creationflags=0x08000000 if os.name == "nt" else 0,
            check=False,
        )
        values = [part.strip() for part in result.stdout.splitlines()[0].split(",", 3)]
        if len(values) == 4:
            gpu_percent = float(values[0])
            memory_used = int(float(values[1]) * 1024 * 1024)
            memory_total = int(float(values[2]) * 1024 * 1024)
            name = values[3]
        else:
            return unavailable
    except (OSError, IndexError, ValueError, RuntimeError, subprocess.SubprocessError):
        return unavailable

    return {
        "available": True,
        "name": name,
        "percent": gpu_percent,
        "memoryPercent": round((memory_used / memory_total) * 100, 1) if memory_total else None,
        "memoryUsed": memory_used,
        "memoryTotal": memory_total,
    }


def system_status() -> dict[str, Any]:
    """Small polling-friendly snapshot for the system cards in the desktop UI."""
    if psutil is not None:
        memory = psutil.virtual_memory()
        cpu_percent = float(psutil.cpu_percent(interval=0.05))
        memory_used = int(memory.used)
        memory_total = int(memory.total)
        memory_percent = float(memory.percent)
    else:
        cpu_percent = 0.0
        memory_used = 0
        memory_total = 0
        memory_percent = 0.0

    return {
        "cpu": {
            "percent": round(cpu_percent, 1),
            "threads": os.cpu_count() or 1,
        },
        "memory": {
            "percent": round(memory_percent, 1),
            "used": memory_used,
            "total": memory_total,
        },
        "gpu": _gpu_system_stats(),
        "tts": silero_tts_service.activity() if "silero_tts_service" in globals() else {
            "active": False,
            "phase": "idle",
            "progress": 0,
            "message": "Готово",
        },
    }


class LocalVoiceService:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._cuda_error = ""
        self._gpu_available = self._probe_gpu()
        self._device_mode = self._read_device_preference()

    def _probe_gpu(self) -> bool:
        cuda_build = bool(torch is not None and getattr(torch.version, "cuda", None))
        if torch is None:
            self._cuda_error = "PyTorch не установлен в bundled runtime."
            return False
        if not cuda_build:
            self._cuda_error = "В bundled runtime установлена CPU-сборка PyTorch. Пересоберите portable с CUDA."
            return False
        if not torch.cuda.is_available():
            self._cuda_error = "CUDA-runtime встроен, но NVIDIA GPU недоступен. Проверьте драйвер NVIDIA."
            return False
        try:
            result = subprocess.run(
                ["nvidia-smi", "-L"],
                capture_output=True,
                text=True,
                timeout=1.5,
                creationflags=0x08000000 if os.name == "nt" else 0,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return True
            self._cuda_error = result.stderr.strip() or "nvidia-smi не обнаружил GPU."
            return False
        except (OSError, subprocess.SubprocessError) as error:
            self._cuda_error = str(error)
            return False

    def _read_device_preference(self) -> str:
        preference = _normalize_text(os.getenv("TTS_DEVICE", ""))
        if not preference and TTS_DEVICE_FILE.exists():
            try:
                preference = _normalize_text(json.loads(TTS_DEVICE_FILE.read_text(encoding="utf-8")).get("device", ""))
            except (OSError, ValueError, TypeError):
                preference = ""
        if preference == "cpu":
            return "cpu"
        if preference == "gpu" and self._gpu_available:
            return "gpu"
        return "gpu" if self._gpu_available else "cpu"

    def device_info(self) -> dict[str, Any]:
        if self._gpu_available:
            gpu_message = "GPU / CUDA готов к работе."
        elif self._cuda_error:
            gpu_message = self._cuda_error
        elif os.name == "nt" and not shutil.which("nvidia-smi"):
            gpu_message = "NVIDIA-драйвер не найден в системе. Установите или обновите драйвер."
        else:
            gpu_message = "NVIDIA GPU не обнаружен через nvidia-smi. Проверьте драйвер NVIDIA."
        return {
            "selected": self._device_mode,
            "label": "GPU / CUDA" if self._device_mode == "gpu" else "CPU",
            "gpuAvailable": self._gpu_available,
            "cudaBuild": bool(torch is not None and getattr(torch.version, "cuda", None)),
            "cudaVersion": getattr(torch.version, "cuda", None) if torch is not None else None,
            "torchVersion": getattr(torch, "__version__", None) if torch is not None else None,
            "gpuMessage": gpu_message,
            "cudaError": self._cuda_error,
            "torchThreads": _CPU_THREADS,
            # The UI uses this compatibility field as the effective TTS
            # accelerator state. VAD is separate and intentionally stays on
            # the lightweight CPU ONNX runtime.
            "mixedPrecision": bool(self._device_mode == "gpu" and self._gpu_available),
        }

    def set_device(self, device: str) -> dict[str, Any]:
        requested = _normalize_text(device).lower()
        if requested not in {"cpu", "gpu"}:
            raise HTTPException(status_code=400, detail="Choose CPU or GPU.")
        if requested == "gpu" and not self._gpu_available:
            raise HTTPException(
                status_code=409,
                detail=self.device_info()["gpuMessage"],
            )

        changed = False
        with self._lock:
            if requested != self._device_mode:
                self._device_mode = requested
                changed = True
                TTS_DEVICE_FILE.write_text(
                    json.dumps({"device": requested}, ensure_ascii=True),
                    encoding="utf-8",
                )
                gc.collect()
        if changed and "silero_tts_service" in globals():
            silero_tts_service.reset_model()
        return self.device_info()

    def active_voice_path(self) -> Path | None:
        for extension in VOICE_EXTENSIONS:
            path = self.base_dir / f"active_reference{extension}"
            if path.exists():
                return path
        return None

    def save_reference(self, filename: str, audio_bytes: bytes) -> dict[str, Any]:
        extension = Path(filename or "").suffix.lower()
        if extension not in VOICE_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Use a WAV, MP3, FLAC, OGG, or M4A reference file.")
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="The reference voice file is empty.")
        if len(audio_bytes) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="The reference voice file is too large.")

        for old_extension in VOICE_EXTENSIONS:
            old_path = self.base_dir / f"active_reference{old_extension}"
            if old_path.exists():
                old_path.unlink()

        path = self.base_dir / f"active_reference{extension}"
        path.write_bytes(audio_bytes)
        return {"name": path.name, "path": str(path), "size": len(audio_bytes)}

    @property
    def reference_text_path(self) -> Path:
        return self.base_dir / "active_reference.txt"

    def save_reference_text(self, text: str) -> None:
        text = _normalize_text(text)
        if text:
            self.reference_text_path.write_text(text, encoding="utf-8")
        else:
            self.reference_text_path.unlink(missing_ok=True)

    def reference_text(self) -> str:
        try:
            return _normalize_text(self.reference_text_path.read_text(encoding="utf-8"))
        except OSError:
            return ""

    def clear_voice_prompt(self) -> None:
        return None

    def delete_reference(self) -> dict[str, Any]:
        for extension in VOICE_EXTENSIONS:
            (self.base_dir / f"active_reference{extension}").unlink(missing_ok=True)
        self.reference_text_path.unlink(missing_ok=True)
        return {"active": False, "name": "", "size": 0}


class RvcPostProcessor:
    """Optional RVC conversion stage for the WAV produced by Silero."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._enabled = False
        self._command_template = DEFAULT_RVC_COMMAND
        self._load_settings()

    def _load_settings(self) -> None:
        settings: dict[str, Any] = {}
        try:
            settings = json.loads(RVC_CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            pass
        env_enabled = _normalize_text(os.getenv("RVC_ENABLED", "")).lower() in {"1", "true", "yes", "on"}
        self._enabled = bool(settings.get("enabled", env_enabled))
        self._command_template = self._normalize_command_template(settings.get("command_template"))

    @staticmethod
    def _normalize_command_template(value: Any) -> str:
        command = _normalize_text(str(value or ""))
        legacy_commands = {
            "python",
            "python.exe",
            "copy /y {input_wav} {output_wav}",
            'python infer_cli.py --input_path "{input_wav}" --opt_path "{output_wav}" '
            '--model_name "{model_path}" --index_path "{index_path}"',
        }
        if (
            command.lower() in legacy_commands
            or "--input_path" in command
            or "--opt_path" in command
            or "--model_name" in command
            or "--index_path" in command
            or ("{python_cmd}" in command and "{rvc_script}" in command)
        ):
            return DEFAULT_RVC_COMMAND
        return command or DEFAULT_RVC_COMMAND

    @staticmethod
    def _embedded_command() -> str:
        """Use the bundled backend as the RVC Python runtime when frozen."""
        if getattr(sys, "frozen", False):
            return f'"{Path(sys.executable).resolve()}" --rvc-cli'
        return f'{RvcPostProcessor._python_command()} -u "{RVC_SCRIPT_PATH}"'

    @staticmethod
    def _python_command() -> str:
        """Return a runnable Python command for a standalone RVC runtime."""
        candidates: list[Path] = []
        if not getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable))
        else:
            # Reuse the project's isolated runtime when a portable build is
            # launched from the original project tree.
            for parent in Path(sys.executable).resolve().parents:
                candidates.append(parent / ".venv" / "Scripts" / "python.exe")
        candidates.extend([
            RVC_DIR / "python.exe",
            BASE_DIR / "runtime" / "python.exe",
            BASE_DIR / ".venv" / "Scripts" / "python.exe",
        ])
        for candidate in candidates:
            if candidate.is_file():
                return f'"{candidate}"'
        py_launcher = shutil.which("py")
        if py_launcher:
            return f'"{py_launcher}" -3'
        python = shutil.which("python") or shutil.which("python3")
        if python:
            return f'"{python}"'
        return "python"

    def _save_settings(self) -> None:
        RVC_CONFIG_FILE.write_text(
            json.dumps(
                {
                    "enabled": self._enabled,
                    "command_template": self._command_template,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def status(self) -> dict[str, Any]:
        with self._lock:
            has_model = RVC_MODEL_PATH.exists()
            has_index = RVC_INDEX_PATH.exists()
            command_ready = bool(self._command_template)
            builtin_cli = "{rvc_script}" in self._command_template or "{rvc_command}" in self._command_template
            cli_available = not builtin_cli or RVC_SCRIPT_PATH.is_file()
            return {
                "enabled": self._enabled,
                "configured": has_model and command_ready,
                "ready": has_model and command_ready,
                "cliAvailable": cli_available,
                "degraded": bool(self._enabled and builtin_cli and not cli_available),
                "modelPath": str(RVC_MODEL_PATH),
                "indexPath": str(RVC_INDEX_PATH) if has_index else "",
                "modelName": RVC_MODEL_PATH.name if has_model else "",
                "indexName": RVC_INDEX_PATH.name if has_index else "",
                "commandTemplate": self._command_template,
                "commandConfigured": command_ready,
                "message": self._message(has_model, has_index, command_ready, cli_available),
            }

    @staticmethod
    def _message(has_model: bool, has_index: bool, command_ready: bool, cli_available: bool) -> str:
        if not has_model:
            return "Загрузите RVC-модель .pth."
        if not command_ready:
            return "Укажите команду RVC в настройках runtime."
        if not cli_available:
            return "RVC CLI не найден; TTS продолжит работу без RVC, пока не добавлен runtime RVC."
        if not has_index:
            return "Модель сохранена; индекс .index необязателен."
        return "RVC-модель и индекс готовы."

    def set_settings(self, enabled: bool, command_template: str) -> dict[str, Any]:
        with self._lock:
            self._enabled = bool(enabled)
            self._command_template = self._normalize_command_template(command_template)
            self._save_settings()
        return self.status()

    def save_files(
        self,
        model_filename: str,
        model_bytes: bytes,
        index_filename: str = "",
        index_bytes: bytes = b"",
    ) -> dict[str, Any]:
        model_extension = Path(model_filename or "").suffix.lower()
        if model_extension != ".pth":
            raise HTTPException(status_code=400, detail="RVC-модель должна быть файлом .pth.")
        if not model_bytes:
            raise HTTPException(status_code=400, detail="RVC-модель пустая.")
        if len(model_bytes) > 2 * 1024 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="RVC-модель слишком большая.")

        index_extension = Path(index_filename or "").suffix.lower()
        if index_filename and index_extension != ".index":
            raise HTTPException(status_code=400, detail="RVC-индекс должен быть файлом .index.")
        if index_bytes and len(index_bytes) > 2 * 1024 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="RVC-индекс слишком большой.")

        with self._lock:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            RVC_MODEL_PATH.write_bytes(model_bytes)
            if index_bytes:
                RVC_INDEX_PATH.write_bytes(index_bytes)
            elif not index_filename:
                RVC_INDEX_PATH.unlink(missing_ok=True)
        return self.status()

    def delete_files(self) -> dict[str, Any]:
        with self._lock:
            RVC_MODEL_PATH.unlink(missing_ok=True)
            RVC_INDEX_PATH.unlink(missing_ok=True)
            self._enabled = False
            self._save_settings()
        return self.status()

    def convert(self, wav_bytes: bytes) -> bytes:
        with self._lock:
            status = self.status()
            if not status["enabled"]:
                return wav_bytes
            if not status["configured"]:
                raise HTTPException(status_code=409, detail=status["message"])
            command_template = self._command_template

        with tempfile.TemporaryDirectory(prefix="voicebridge-rvc-") as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.wav"
            output_path = temp_path / "output.wav"
            input_path.write_bytes(wav_bytes)
            replacements = {
                "input_wav": str(input_path),
                "output_wav": str(output_path),
                "model_path": str(RVC_MODEL_PATH),
                "index_path": str(RVC_INDEX_PATH) if RVC_INDEX_PATH.exists() else "",
                "python_cmd": self._python_command(),
                "rvc_dir": str(RVC_DIR),
                "rvc_script": str(RVC_SCRIPT_PATH),
                "rvc_command": self._embedded_command(),
            }
            try:
                command = command_template.format(**replacements)
            except KeyError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Неизвестный placeholder RVC-команды: {{{exc.args[0]}}}.",
                ) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Некорректный шаблон RVC-команды: {exc}") from exc

            uses_builtin_cli = "{rvc_script}" in command_template or "{rvc_command}" in command_template
            if uses_builtin_cli and not Path(replacements["rvc_script"]).is_file():
                logging.warning(
                    "RVC CLI не найден: %s. Пропускаю RVC и возвращаю исходный Silero WAV.",
                    replacements["rvc_script"],
                )
                return wav_bytes

            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(self.base_dir),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                    creationflags=0x08000000 if os.name == "nt" else 0,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise HTTPException(status_code=503, detail=f"RVC runtime не запустился: {exc}") from exc

            if result.returncode != 0:
                details = (result.stderr or result.stdout or "").strip()
                raise HTTPException(
                    status_code=503,
                    detail=f"RVC завершился с кодом {result.returncode}. {details[-1500:]}",
                )
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise HTTPException(status_code=503, detail="RVC не создал output_wav.")
            return output_path.read_bytes()


class AudioRoutingService:
    """Route TTS to a selected Windows output and capture WASAPI loopback."""

    def __init__(self, settings_path: Path) -> None:
        self.settings_path = settings_path
        self._lock = RLock()
        self._settings = {"output_device": "", "loopback_device": ""}
        self._last_output_route = ""
        self._last_capture_route = ""
        self._vad_lock = RLock()
        self._vad_model = None
        self._vad_warmup_thread: Thread | None = None
        self._load()

    def start_vad_warmup(self) -> None:
        with self._vad_lock:
            if self._vad_warmup_thread and self._vad_warmup_thread.is_alive():
                return
            self._vad_warmup_thread = Thread(target=self._warmup_vad, name="silero-vad-warmup", daemon=True)
            self._vad_warmup_thread.start()

    def _warmup_vad(self) -> None:
        try:
            self._load_vad()
            logging.info("Silero VAD 6.2.2 ONNX is ready.")
        except Exception:  # noqa: BLE001
            logging.exception("Silero VAD ONNX warmup failed")

    def _load_vad(self):
        with self._vad_lock:
            if self._vad_model is not None:
                return self._vad_model
            previous_threads = None
            if torch is not None:
                previous_threads = torch.get_num_threads()
            from silero_vad import load_silero_vad

            self._vad_model = load_silero_vad(onnx=True, opset_version=16)
            if previous_threads is not None:
                try:
                    torch.set_num_threads(previous_threads)
                except RuntimeError:
                    pass
            return self._vad_model

    @staticmethod
    def _to_vad_samples(raw: bytes, channels: int, source_rate: int):
        import numpy as np

        samples = np.frombuffer(raw, dtype=np.int16)
        if channels > 1:
            samples = samples[: len(samples) - (len(samples) % channels)]
            if not len(samples):
                return np.empty(0, dtype=np.float32)
            samples = samples.reshape(-1, channels).mean(axis=1)
        if source_rate == 16000:
            return (samples.astype(np.float32) / 32768.0)
        target_length = max(1, round(len(samples) * 16000 / source_rate))
        source_positions = np.linspace(0.0, 1.0, num=len(samples), endpoint=True)
        target_positions = np.linspace(0.0, 1.0, num=target_length, endpoint=True)
        return np.interp(target_positions, source_positions, samples).astype(np.float32) / 32768.0

    def _load(self) -> None:
        try:
            value = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                self._settings.update({
                    "output_device": _normalize_text(value.get("output_device", "")),
                    "loopback_device": _normalize_text(value.get("loopback_device", "")),
                })
        except (OSError, ValueError, TypeError):
            pass

    def settings(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._settings)

    def set_settings(self, output_device: str = "", loopback_device: str = "") -> dict[str, Any]:
        with self._lock:
            self._settings = {
                "output_device": _normalize_text(output_device),
                "loopback_device": _normalize_text(loopback_device),
            }
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(
                json.dumps(self._settings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return dict(self._settings)

    @staticmethod
    def _pyaudio():
        try:
            import pyaudiowpatch as pyaudio
        except ImportError as exc:
            raise RuntimeError(
                "Для аудиомаршрутизации нужен pyaudiowpatch. Запустите setup_new_pc.cmd."
            ) from exc
        return pyaudio

    @staticmethod
    def _device_name(info: dict[str, Any]) -> str:
        return str(info.get("name", "")).strip()

    @staticmethod
    def _host_api_name(audio, info: dict[str, Any]) -> str:
        try:
            host_api = audio.get_host_api_info_by_index(int(info.get("hostApi", 0)))
            return str(host_api.get("name", "")).strip()
        except (OSError, TypeError, ValueError):
            return ""

    @staticmethod
    def _device_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
        host_api = str(item.get("hostApiName", "")).lower()
        name = str(item.get("name", "")).lower()
        return (
            0 if "wasapi" in host_api else 1,
            0 if "cable input" in name else 1,
            name,
        )

    def list_devices(self) -> dict[str, Any]:
        try:
            pyaudio = self._pyaudio()
            audio = pyaudio.PyAudio()
            outputs: list[dict[str, Any]] = []
            try:
                for index in range(audio.get_device_count()):
                    info = audio.get_device_info_by_index(index)
                    if int(info.get("maxOutputChannels", 0)) > 0:
                        name = self._device_name(info)
                        outputs.append({
                            "id": str(index),
                            "name": name,
                            "sampleRate": int(float(info.get("defaultSampleRate", 48000))),
                            "channels": int(info.get("maxOutputChannels", 0)),
                            "role": "tts-cable-input" if "cable input" in name.lower() else "tts-output",
                            "hostApiName": self._host_api_name(audio, info),
                        })
                loopbacks = []
                for info in audio.get_loopback_device_info_generator():
                    name = self._device_name(info)
                    loopbacks.append({
                        "id": str(info.get("index", "")),
                        "name": name,
                        "sampleRate": int(float(info.get("defaultSampleRate", 48000))),
                        "channels": int(info.get("maxInputChannels", 0)),
                        "role": "stt-cable-loopback" if "cable input" in name.lower() else "stt-loopback",
                        "hostApiName": "Windows WASAPI",
                    })
                outputs.sort(key=self._device_sort_key)
            finally:
                audio.terminate()
            cable_names = ("cable", "vb-audio", "virtual audio", "virtual cable")
            virtual_cable = any(
                any(marker in item["name"].lower() for marker in cable_names)
                for item in outputs
            )
            settings = self.settings()
            route_warnings: list[str] = []
            if (
                "cable input" in settings["output_device"].lower()
                and "cable input" in settings["loopback_device"].lower()
            ):
                route_warnings.append(
                    "TTS и STT используют один CABLE Input: STT может услышать собственный ответ."
                )
            return {
                "available": True,
                "outputs": outputs,
                "loopbacks": loopbacks,
                "virtualCableDetected": virtual_cable,
                "routeWarnings": route_warnings,
                "error": "",
                "settings": settings,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "available": False,
                "outputs": [],
                "loopbacks": [],
                "virtualCableDetected": False,
                "routeWarnings": [],
                "error": str(exc),
                "settings": self.settings(),
            }

    @staticmethod
    def _match_device(items: list[dict[str, Any]], requested: str) -> dict[str, Any] | None:
        requested = _normalize_text(requested)
        if not requested:
            return None
        if requested.isdigit():
            for item in items:
                if item["id"] == requested:
                    return item
        requested_lower = requested.lower()
        exact = [item for item in items if item["name"].lower() == requested_lower]
        if exact:
            return sorted(exact, key=AudioRoutingService._device_sort_key)[0]
        partial = [item for item in items if requested_lower in item["name"].lower()]
        if partial:
            return sorted(partial, key=AudioRoutingService._device_sort_key)[0]
        raise RuntimeError(f"Аудиоустройство не найдено: {requested}")

    def _device_lists(self, audio) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        outputs = []
        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)
            if int(info.get("maxOutputChannels", 0)) > 0:
                name = self._device_name(info)
                outputs.append({
                    "id": str(index),
                    "name": name,
                    "sampleRate": int(float(info.get("defaultSampleRate", 48000))),
                    "channels": int(info.get("maxOutputChannels", 0)),
                    "role": "tts-cable-input" if "cable input" in name.lower() else "tts-output",
                    "hostApiName": self._host_api_name(audio, info),
                })
        loopbacks = []
        for info in audio.get_loopback_device_info_generator():
            name = self._device_name(info)
            loopbacks.append({
                "id": str(info.get("index", "")),
                "name": name,
                "sampleRate": int(float(info.get("defaultSampleRate", 48000))),
                "channels": int(info.get("maxInputChannels", 0)),
                "role": "stt-cable-loopback" if "cable input" in name.lower() else "stt-loopback",
                "hostApiName": "Windows WASAPI",
            })
        outputs.sort(key=self._device_sort_key)
        return outputs, loopbacks

    def monitor_ringback(self, requested: str, stop_event: Event, on_tone: Any) -> None:
        """Detect telephone ringback tones from short loopback buffers in RAM."""
        audio = None
        stream = None
        try:
            pyaudio = self._pyaudio()
            audio = pyaudio.PyAudio()
            _, loopbacks = self._device_lists(audio)
            selected = self._match_device(loopbacks, requested or self.settings()["loopback_device"])
            if selected is None:
                selected = next(iter(loopbacks), None)
            if selected is None:
                return
            channels = max(1, min(int(selected.get("channels", 0) or 1), 2))
            rate = int(selected.get("sampleRate", 48000) or 48000)
            frame_size = max(2048, int(rate * 0.16))
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=int(selected["id"]),
                frames_per_buffer=frame_size,
            )
            import numpy as np

            target_frequencies = np.asarray((350.0, 425.0, 440.0, 480.0), dtype=np.float32)
            while not stop_event.is_set():
                raw = stream.read(frame_size, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                if channels > 1:
                    samples = samples.reshape(-1, channels).mean(axis=1)
                if not len(samples):
                    continue
                rms = float(np.sqrt(np.mean(samples * samples)))
                if rms < 90.0:
                    continue
                windowed = samples * np.hanning(len(samples))
                spectrum = np.abs(np.fft.rfft(windowed)) ** 2
                frequencies = np.fft.rfftfreq(len(windowed), d=1.0 / rate)
                total_power = float(spectrum.sum())
                if total_power <= 0:
                    continue
                tone_bins = np.zeros(len(frequencies), dtype=bool)
                for target in target_frequencies:
                    tone_bins |= np.abs(frequencies - target) <= 18.0
                band_power = float(spectrum[tone_bins].sum())
                if band_power / total_power >= 0.48:
                    on_tone(time.monotonic())
        except Exception as exc:  # noqa: BLE001
            logging.info("Ringback audio monitor unavailable; using Mango UI state: %s", exc)
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:  # noqa: BLE001
                    pass
            if audio is not None:
                audio.terminate()

    @staticmethod
    def _resample_wav(wav_bytes: bytes, target_rate: int) -> bytes:
        """Convert the app's PCM WAV to a device-supported sample rate."""
        from array import array

        with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
            source_rate = reader.getframerate()
            raw = reader.readframes(reader.getnframes())
        if source_rate == target_rate or sample_width != 2 or not raw:
            return wav_bytes

        samples = array("h")
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if sys.byteorder != "little":
            samples.byteswap()
        source_frames = len(samples) // max(1, channels)
        if source_frames <= 0:
            return wav_bytes
        target_frames = max(1, round(source_frames * target_rate / source_rate))
        converted = array("h")
        for frame_index in range(target_frames):
            position = frame_index * (source_frames - 1) / max(1, target_frames - 1)
            left = int(position)
            right = min(left + 1, source_frames - 1)
            fraction = position - left
            for channel in range(channels):
                first = samples[left * channels + channel]
                second = samples[right * channels + channel]
                converted.append(round(first + (second - first) * fraction))
        if sys.byteorder != "little":
            converted.byteswap()
        output = io.BytesIO()
        with wave.open(output, "wb") as writer:
            writer.setnchannels(channels)
            writer.setsampwidth(sample_width)
            writer.setframerate(target_rate)
            writer.writeframes(converted.tobytes())
        return output.getvalue()

    @staticmethod
    def _convert_output_channels(wav_bytes: bytes, target_channels: int) -> bytes:
        """Normalize PCM playback to the channel layout accepted by virtual cables."""
        from array import array

        target_channels = max(1, min(2, int(target_channels or 1)))
        with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
            sample_rate = reader.getframerate()
            raw = reader.readframes(reader.getnframes())
        if channels == target_channels or sample_width != 2 or not raw:
            return wav_bytes

        samples = array("h")
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if sys.byteorder != "little":
            samples.byteswap()
        frame_count = len(samples) // max(1, channels)
        converted = array("h")
        for frame in range(frame_count):
            start = frame * channels
            values = samples[start : start + channels]
            if target_channels == 2 and channels == 1:
                converted.extend((values[0], values[0]))
            elif target_channels == 1:
                converted.append(round(sum(values) / max(1, len(values))))
            else:
                converted.extend(values[:target_channels])
        if sys.byteorder != "little":
            converted.byteswap()
        output = io.BytesIO()
        with wave.open(output, "wb") as writer:
            writer.setnchannels(target_channels)
            writer.setsampwidth(2)
            writer.setframerate(sample_rate)
            writer.writeframes(converted.tobytes())
        return output.getvalue()

    def play_wav(self, wav_bytes: bytes, requested: str = "") -> None:
        pyaudio = self._pyaudio()
        audio = pyaudio.PyAudio()
        stream = None
        try:
            outputs, _ = self._device_lists(audio)
            selected = self._match_device(outputs, requested or self.settings()["output_device"])
            route_name = selected["name"] if selected else "системное устройство по умолчанию"
            route_key = f"{selected['id'] if selected else 'default'}:{route_name}"
            if route_key != self._last_output_route:
                logging.info("TTS audio output: %s (device id %s)", route_name, selected["id"] if selected else "default")
                self._last_output_route = route_key
            target_rate = int(selected.get("sampleRate", 0)) if selected else 0
            target_channels = min(2, int(selected.get("channels", 0))) if selected else 0
            with wave.open(io.BytesIO(wav_bytes), "rb") as source_reader:
                source_rate = source_reader.getframerate()
            playback_wav = wav_bytes
            if target_rate and source_rate != target_rate:
                logging.info("Resampling audio route from %s Hz to %s Hz", source_rate, target_rate)
                playback_wav = self._resample_wav(wav_bytes, target_rate)
            if target_channels:
                playback_wav = self._convert_output_channels(playback_wav, target_channels)
            with wave.open(io.BytesIO(playback_wav), "rb") as reader:
                stream = audio.open(
                    format=audio.get_format_from_width(reader.getsampwidth()),
                    channels=reader.getnchannels(),
                    rate=reader.getframerate(),
                    output=True,
                    output_device_index=int(selected["id"]) if selected else None,
                )
                while True:
                    chunk = reader.readframes(2048)
                    if not chunk:
                        break
                    stream.write(chunk)
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            audio.terminate()

    def capture_chunk(self, seconds: float = 2.5, requested: str = "") -> bytes:
        pyaudio = self._pyaudio()
        audio = pyaudio.PyAudio()
        stream = None
        try:
            _, loopbacks = self._device_lists(audio)
            selected = self._match_device(loopbacks, requested or self.settings()["loopback_device"])
            if selected is None:
                try:
                    selected = next(iter(loopbacks))
                except StopIteration as exc:
                    raise RuntimeError("WASAPI loopback-устройства не найдены.") from exc
            route_name = selected["name"]
            route_key = f"{selected['id']}:{route_name}"
            if route_key != self._last_capture_route:
                logging.info("STT audio input: %s (loopback id %s)", route_name, selected["id"])
                self._last_capture_route = route_key
            channels = max(1, min(int(selected["channels"] or 2), 2))
            rate = int(selected["sampleRate"] or 48000)
            frames_needed = max(1, int(rate * max(0.5, min(float(seconds), 10.0))))
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=int(selected["id"]),
                frames_per_buffer=1024,
            )
            frames: list[bytes] = []
            remaining = frames_needed
            while remaining > 0:
                count = min(1024, remaining)
                frames.append(stream.read(count, exception_on_overflow=False))
                remaining -= count
            raw = b"".join(frames)
            output = io.BytesIO()
            with wave.open(output, "wb") as writer:
                writer.setnchannels(channels)
                writer.setsampwidth(2)
                writer.setframerate(rate)
                writer.writeframes(raw)
            return output.getvalue()
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            audio.terminate()

    def capture_speech(
        self,
        max_seconds: float = 60.0,
        requested: str = "",
        silence_seconds: float = 1.0,
        vad_threshold: float | None = None,
        min_speech_seconds: float | None = None,
        stop_event: Event | None = None,
        stop_before_speech_event: Event | None = None,
        speech_started_event: Event | None = None,
    ) -> bytes:
        """Capture one utterance, starting on speech and ending after a pause."""
        pyaudio = self._pyaudio()
        audio = pyaudio.PyAudio()
        stream = None
        try:
            _, loopbacks = self._device_lists(audio)
            selected = self._match_device(loopbacks, requested or self.settings()["loopback_device"])
            if selected is None:
                try:
                    selected = next(iter(loopbacks))
                except StopIteration as exc:
                    raise RuntimeError("WASAPI loopback-устройства не найдены.") from exc

            channels = max(1, min(int(selected["channels"] or 2), 2))
            rate = int(selected["sampleRate"] or 48000)
            frame_size = max(256, min(2048, int(rate * 0.032)))
            max_seconds = max(0.5, min(float(max_seconds), 60.0))
            silence_seconds = max(0.5, min(float(silence_seconds), 2.0))
            active_vad_threshold = min(
                max(float(vad_threshold if vad_threshold is not None else VAD_THRESHOLD), 0.5),
                0.99,
            )
            active_min_speech_seconds = min(
                max(float(min_speech_seconds if min_speech_seconds is not None else VAD_MIN_SPEECH_SECONDS), 0.08),
                1.2,
            )
            deadline = time.monotonic() + max_seconds
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=int(selected["id"]),
                frames_per_buffer=frame_size,
            )

            frames: list[bytes] = []
            pre_roll: deque[bytes] = deque(maxlen=max(1, int(0.4 * rate / frame_size)))
            started = False
            speech_confirmed = False
            speech_candidate_started_at = 0.0
            vad_samples = None
            vad_iterator = None
            try:
                import numpy as np
                from silero_vad import VADIterator

                vad_model = self._load_vad()
                vad_iterator = VADIterator(
                    vad_model,
                    threshold=active_vad_threshold,
                    sampling_rate=16000,
                    min_silence_duration_ms=int(silence_seconds * 1000),
                    speech_pad_ms=120,
                )
                vad_samples = np.empty(0, dtype=np.float32)
            except Exception as exc:  # noqa: BLE001
                logging.warning("Silero VAD unavailable, using RMS fallback: %s", exc)
            fallback_last_speech_at = 0.0
            fallback_noise_floor = 180.0
            fallback_speech_frames = 0
            fallback_min_speech_frames = max(3, int(round(active_min_speech_seconds * rate / frame_size)))

            while time.monotonic() < deadline:
                if stop_event is not None and stop_event.is_set():
                    break
                if (
                    not started
                    and stop_before_speech_event is not None
                    and stop_before_speech_event.is_set()
                ):
                    break
                raw = stream.read(frame_size, exception_on_overflow=False)
                if not raw:
                    continue
                pre_roll.append(raw)
                vad_event = None
                started_this_frame = False
                if vad_iterator is not None:
                    vad_samples = np.concatenate((vad_samples, self._to_vad_samples(raw, channels, rate)))
                    ended = False
                    while len(vad_samples) >= 512:
                        vad_chunk = vad_samples[:512]
                        vad_samples = vad_samples[512:]
                        vad_event = vad_iterator(torch.from_numpy(vad_chunk))
                        if vad_event:
                            if "start" in vad_event and not started:
                                started = True
                                speech_confirmed = False
                                speech_candidate_started_at = time.monotonic()
                                started_this_frame = True
                                frames.extend(pre_roll)
                                pre_roll.clear()
                            if "end" in vad_event and started:
                                if speech_confirmed:
                                    frames.append(raw)
                                    ended = True
                                else:
                                    # Very short events are usually clicks,
                                    # bumps, keyboard sounds, or cable noise.
                                    started = False
                                    speech_confirmed = False
                                    speech_candidate_started_at = 0.0
                                    frames.clear()
                                    pre_roll.clear()
                                    try:
                                        vad_iterator.reset_states()
                                    except AttributeError:
                                        pass
                                break
                    if ended:
                        break
                    if (
                        started
                        and not speech_confirmed
                        and time.monotonic() - speech_candidate_started_at >= active_min_speech_seconds
                    ):
                        speech_confirmed = True
                        if speech_started_event is not None:
                            speech_started_event.set()
                    if started and not started_this_frame:
                        frames.append(raw)
                    continue

                from array import array
                samples = array("h")
                samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
                if sys.byteorder != "little":
                    samples.byteswap()
                if not samples:
                    continue
                rms = (sum(value * value for value in samples) / len(samples)) ** 0.5
                peak = max(abs(value) for value in samples)
                threshold = max(420.0, fallback_noise_floor * 2.6)
                is_speech = rms >= threshold and peak >= 700.0
                if not started:
                    if not is_speech:
                        fallback_speech_frames = 0
                        fallback_noise_floor = min(1800.0, fallback_noise_floor * 0.96 + rms * 0.04)
                    else:
                        fallback_speech_frames += 1
                    if fallback_speech_frames >= fallback_min_speech_frames:
                        started = True
                        speech_confirmed = True
                        frames.extend(pre_roll)
                        pre_roll.clear()
                        fallback_last_speech_at = time.monotonic()
                        if speech_started_event is not None:
                            speech_started_event.set()
                else:
                    frames.append(raw)
                    if is_speech:
                        fallback_last_speech_at = time.monotonic()
                    elif time.monotonic() - fallback_last_speech_at >= silence_seconds:
                        break

            if not frames or not speech_confirmed:
                return b""
            output = io.BytesIO()
            with wave.open(output, "wb") as writer:
                writer.setnchannels(channels)
                writer.setsampwidth(2)
                writer.setframerate(rate)
                writer.writeframes(b"".join(frames))
            return output.getvalue()
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            audio.terminate()

    def play_wav_interruptible(
        self,
        wav_bytes: bytes,
        requested: str = "",
        loopback: str = "",
        max_speech_seconds: float = 60.0,
        stop_event: Event | None = None,
    ) -> bytes:
        """Play TTS while watching loopback for a new utterance that interrupts it."""
        pyaudio = self._pyaudio()
        audio = pyaudio.PyAudio()
        stream = None
        playback_finished = Event()
        speech_started = Event()
        captured: list[bytes] = []
        monitor_started = False

        def monitor_speech() -> None:
            try:
                captured.append(
                    self.capture_speech(
                        max_seconds=max_speech_seconds,
                        requested=loopback,
                        silence_seconds=MANGO_SILENCE_SECONDS,
                        vad_threshold=VAD_INTERRUPT_THRESHOLD,
                        min_speech_seconds=VAD_INTERRUPT_MIN_SPEECH_SECONDS,
                        stop_event=stop_event,
                        stop_before_speech_event=playback_finished,
                        speech_started_event=speech_started,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logging.warning("Speech interruption monitor unavailable: %s", exc)

        monitor = Thread(target=monitor_speech, name="mango-interrupt-monitor", daemon=True)
        try:
            outputs, loopbacks = self._device_lists(audio)
            selected = self._match_device(outputs, requested or self.settings()["output_device"])
            selected_loopback = self._match_device(
                loopbacks,
                loopback or self.settings()["loopback_device"],
            )
            if (
                selected
                and selected_loopback
                and "cable input" in selected["name"].lower()
                and "cable input" in selected_loopback["name"].lower()
            ):
                logging.warning(
                    "Speech interruption monitor disabled: STT loopback is the same CABLE Input as TTS output."
                )
            else:
                monitor.start()
                monitor_started = True
            target_rate = int(selected.get("sampleRate", 0)) if selected else 0
            target_channels = min(2, int(selected.get("channels", 0))) if selected else 0
            with wave.open(io.BytesIO(wav_bytes), "rb") as source_reader:
                source_rate = source_reader.getframerate()
            playback_wav = wav_bytes
            if target_rate and source_rate != target_rate:
                playback_wav = self._resample_wav(playback_wav, target_rate)
            if target_channels:
                playback_wav = self._convert_output_channels(playback_wav, target_channels)
            with wave.open(io.BytesIO(playback_wav), "rb") as reader:
                stream = audio.open(
                    format=audio.get_format_from_width(reader.getsampwidth()),
                    channels=reader.getnchannels(),
                    rate=reader.getframerate(),
                    output=True,
                    output_device_index=int(selected["id"]) if selected else None,
                )
                while True:
                    if stop_event is not None and stop_event.is_set():
                        break
                    if speech_started.is_set():
                        logging.info("TTS interrupted by detected speech.")
                        break
                    chunk = reader.readframes(2048)
                    if not chunk:
                        break
                    stream.write(chunk)
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            audio.terminate()
            playback_finished.set()
            if monitor_started:
                monitor.join(timeout=max(2.0, min(float(max_speech_seconds), 60.0) + 2.0))
        return captured[0] if captured and captured[0] else b""

    def play_test_tone(self, requested: str = "") -> None:
        """Play a short audible marker to verify the selected TTS route."""
        sample_rate = 48000
        frames = int(sample_rate * 0.65)
        raw = bytearray()
        for index in range(frames):
            envelope = min(1.0, index / 500.0, (frames - index) / 1500.0)
            sample = int(0.22 * envelope * 32767 * math.sin(2 * math.pi * 660 * index / sample_rate))
            raw.extend(sample.to_bytes(2, byteorder="little", signed=True))
        output = io.BytesIO()
        with wave.open(output, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(sample_rate)
            writer.writeframes(raw)
        self.play_wav(output.getvalue(), requested)

    @staticmethod
    def has_speech(wav_bytes: bytes, threshold: float = 420.0) -> bool:
        from array import array

        if not wav_bytes:
            return False

        with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
            raw = reader.readframes(reader.getnframes())
        samples = array("h")
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if not samples:
            return False
        if sys.byteorder != "little":
            samples.byteswap()
        stride = max(1, len(samples) // 12000)
        selected = samples[::stride]
        rms = (sum(value * value for value in selected) / len(selected)) ** 0.5
        return rms >= threshold


class MangoCallService:
    """Run the existing Mango UI methods and the live STT/LLM/TTS loop."""

    def __init__(self, audio: AudioRoutingService) -> None:
        self.audio = audio
        self._lock = RLock()
        self._stop = Event()
        self._window_ready = Event()
        self._thread: Thread | None = None
        self._warmup_thread: Thread | None = None
        self._talker = None
        self._connected = False
        self._peer_hangup = Event()
        self._local_hangup = Event()
        self._status: dict[str, Any] = {
            "running": False,
            "state": "idle",
            "message": "Звонок не запущен.",
            "number": "",
            "startedAt": None,
            "connectedAt": None,
            "callElapsedSeconds": 0.0,
            "remoteAnswered": False,
            "humanSpeechDetected": False,
            "transcript": "",
            "reply": "",
            "script_stage": "idle",
            "candidate": {},
        }
        self._warmup_thread = Thread(target=self._warmup_window, name="mango-warmup", daemon=True)
        self._warmup_thread.start()

    def _warmup_window(self) -> None:
        """Find Mango once in the background so dialing does not pay UIA startup cost."""
        try:
            from mango_automation import MangoTalker, Settings

            talker = MangoTalker(Settings())
            talker.connect()
            with self._lock:
                if not (self._thread and self._thread.is_alive()):
                    self._talker = talker
                    self._window_ready.set()
            logging.info("Mango Talker UI connection warmed up.")
        except Exception as exc:  # noqa: BLE001
            logging.debug("Mango warmup skipped: %s", exc)

    def _get_talker(self):
        from mango_automation import MangoTalker, Settings

        with self._lock:
            talker = self._talker
        if talker is not None:
            return talker
        talker = MangoTalker(Settings())
        talker.connect()
        with self._lock:
            self._talker = talker
            self._window_ready.set()
        return talker

    def _update(self, **values: Any) -> None:
        with self._lock:
            self._status.update(values)

    def status(self) -> dict[str, Any]:
        with self._lock:
            result = dict(self._status)
            result["running"] = bool(self._thread and self._thread.is_alive())
            connected_at = result.get("connectedAt")
            if connected_at:
                result["callElapsedSeconds"] = round(max(0.0, time.time() - float(connected_at)), 1)
            result["audio"] = self.audio.settings()
            return result

    def start(self, **config: Any) -> dict[str, Any]:
        number = re.sub(r"\D", "", _normalize_text(str(config.get("number", ""))))
        if len(number) < 5:
            raise HTTPException(status_code=400, detail="Номер должен содержать не менее 5 цифр.")
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise HTTPException(status_code=409, detail="Звонок уже выполняется.")
            self._stop.clear()
            self._peer_hangup.clear()
            self._local_hangup.clear()
            self._connected = False
            self._status = {
                "running": True,
                "state": "starting",
                "message": "Подключаюсь к Mango Talker…",
                "number": number,
                "startedAt": time.time(),
                "connectedAt": None,
                "callElapsedSeconds": 0.0,
                "remoteAnswered": False,
                "humanSpeechDetected": False,
                "transcript": "",
                "reply": "",
            "script_stage": "relevance",
                "candidate": _new_candidate_record(number, str(config.get("candidate_name", ""))),
            }
            self._thread = Thread(target=self._run, args=(number, config), name="mango-call", daemon=True)
            self._thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._local_hangup.set()
        self._stop.set()
        talker = self._talker
        if talker is not None and self._connected:
            try:
                talker.hang_up()
            except Exception as exc:  # noqa: BLE001
                logging.warning("Mango hang-up failed: %s", exc)
        self._update(state="stopping", message="Завершаю звонок…")
        return self.status()

    def _watch_remote_hangup(self, talker: Any) -> None:
        """Stop the audio loop when Mango shows that the other side hung up."""
        inactive_snapshots = 0
        while self._connected and not self._stop.wait(0.8):
            try:
                active = talker.call_is_active()
            except Exception as exc:  # noqa: BLE001
                logging.debug("Could not inspect Mango call state: %s", exc)
                inactive_snapshots = 0
                continue
            inactive_snapshots = 0 if active else inactive_snapshots + 1
            if inactive_snapshots >= 3 and not self._local_hangup.is_set():
                self._peer_hangup.set()
                self._stop.set()
                self._update(state="stopping", message="Собеседник завершил звонок.")
                return

    def send_sms(self, number: str, message: str) -> dict[str, Any]:
        message = _normalize_text(message)
        if not message:
            raise HTTPException(status_code=400, detail="Текст SMS не может быть пустым.")
        if len(message) > 4000:
            raise HTTPException(status_code=400, detail="Текст SMS слишком длинный.")
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise HTTPException(status_code=409, detail="Сначала заверши текущий звонок.")
        try:
            from mango_automation import MangoTalker, Settings

            talker = MangoTalker(Settings())
            self._update(state="sms", message=f"Открываю историю Mango для SMS на {number}…")
            talker.connect()
            # Keep the original Mango SMS sequence unchanged.
            talker.open_calls()
            talker.scroll_calls_to_top()
            talker.select_latest_call()
            talker.open_sms_for_selected_call()
            talker.send_sms(message)
            self._update(state="idle", message=f"SMS отправлено на {number}.")
            return {**self.status(), "smsSent": True}
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logging.exception("Mango SMS failed")
            self._update(state="error", message=str(exc))
            raise HTTPException(status_code=503, detail=f"Не удалось отправить SMS через Mango: {exc}") from exc

    @staticmethod
    def _appointment_sms(candidate: dict[str, Any]) -> str:
        scheduled = datetime.fromisoformat(str(candidate["scheduled_at"])).astimezone(calendar_service.tz)
        if scheduled.date() == calendar_service.today():
            date_words = "сегодня"
        elif scheduled.date() == calendar_service.today() + timedelta(days=1):
            date_words = "завтра"
        else:
            date_words = calendar_service._date_words(scheduled.date())
        time_words = calendar_service._time_words(scheduled.strftime("%H:%M"))
        return (
            f"Онлайн-собеседование в Zoom назначено {date_words} в {time_words} "
            "по московскому времени. Контакт HR-менеджера в телеграм: @xxhr1."
        )

    def _send_scheduled_sms(self, talker: Any, candidate: dict[str, Any]) -> bool:
        if not candidate.get("consent_to_continue") or not candidate.get("scheduled_at"):
            return False
        if candidate.get("appointment_sms_sent"):
            return True
        try:
            message = self._appointment_sms(candidate)
            talker.open_calls()
            talker.scroll_calls_to_top()
            talker.select_latest_call()
            talker.open_sms_for_selected_call()
            talker.send_sms(message)
            candidate["appointment_sms_sent"] = True
            logging.info("Appointment SMS sent through Mango to the latest called contact.")
            return True
        except Exception:  # noqa: BLE001
            logging.exception("Could not send scheduled-interview SMS through Mango")
            return False

    @staticmethod
    def _notify_telegram(config: dict[str, Any], message: str) -> bool:
        token = _normalize_text(str(config.get("telegram_bot_token", "")))
        raw_ids = _normalize_text(str(config.get("telegram_chat_ids", "")))
        if not token and not raw_ids:
            return False
        try:
            chat_ids = _telegram_chat_ids(raw_ids)
        except ValueError as exc:
            logging.warning("Telegram notification skipped: %s", exc)
            return False
        failures = _send_telegram_messages(token, chat_ids, message)
        if failures:
            logging.warning("Telegram notification failed for %d recipient(s).", len(failures))
            return False
        return True

    @staticmethod
    def _transcribe_chunk(audio_bytes: bytes, config: dict[str, Any]) -> str:
        model = _normalize_text(str(config.get("stt_model", DEFAULT_STT_MODEL))) or DEFAULT_STT_MODEL
        if model == LOCAL_STT_MODEL:
            text, _duration = gigaam_stt_service.transcribe(audio_bytes)
            return text

        token = _normalize_text(str(config.get("stt_api_key", ""))) or _normalize_text(os.getenv("GROQ_API_KEY", ""))
        if not token:
            raise RuntimeError("Укажи Groq API key в настройках.")
        language = _normalize_text(str(config.get("stt_language", "auto")))
        data: list[tuple[str, str]] = [("model", model), ("response_format", "json")]
        if language and language.lower() != "auto":
            data.append(("language", language))
        proxy = vpn_proxy(bool(config.get("use_vpn_stt", False)))
        response = requests.post(
            GROQ_STT_URL,
            headers={"Authorization": f"Bearer {token}"},
            data=data,
            files={"file": ("mango-loopback.wav", io.BytesIO(audio_bytes), "audio/wav")},
            timeout=60,
            **request_proxy_kwargs(proxy),
        )
        if not response.ok:
            raise RuntimeError(f"Groq STT вернул HTTP {response.status_code}: {response.text[:400]}")
        return _repair_mojibake(str(response.json().get("text", "")).strip())

    @staticmethod
    def _initial_decline(text: str) -> bool:
        return MangoCallService._is_decline(text)

    @staticmethod
    def _initial_greeting_only(text: str) -> bool:
        lowered = _normalize_text(text).lower()
        if not lowered:
            return False
        if re.search(r"\b(?:да|актуально|интересно|подходит|расскажите|какая работа|что за работа)\b", lowered):
            return False
        return bool(re.fullmatch(r"[\s,!.?\-]*(?:привет|здравствуйте|добрый день|добрый вечер|алло)[\s,!.?\-]*", lowered))

    @staticmethod
    def _initial_affirmative(text: str) -> bool:
        return MangoCallService._is_affirmative(text)

    @staticmethod
    def _is_job_question(text: str) -> bool:
        lowered = _normalize_text(text).lower()
        if any(marker in lowered for marker in (
            "что за работа", "какая работа", "расскажите о работе",
            "что нужно делать", "обязанност", "ваканс",
            "какие условия", "условия работы", "расскажите об условиях",
        )):
            return True
        return bool(re.search(r"(?:расскажите|уточните|какие|что за|подробнее).*услов", lowered))

    @staticmethod
    def _is_repeat_request(text: str) -> bool:
        """Recognize a request to repeat the last Jana line, not a new answer."""
        lowered = _normalize_text(text).lower()
        if not lowered:
            return False
        return any(marker in lowered for marker in (
            "не расслышал", "не расслышала", "не услышал", "не услышала",
            "плохо слышно", "не понял", "не поняла", "можете повторить",
            "можешь повторить", "повторите", "повтори", "повторить",
            "повторишь", "скажите еще раз", "скажите ещё раз", "можно еще раз", "можно ещё раз",
            "еще раз", "ещё раз", "что вы сказали",
        ))

    @staticmethod
    def _has_specific_objection(text: str) -> bool:
        """Detect a real question embedded after a repeat request."""
        lowered = _normalize_text(text).lower()
        return any(marker in lowered for marker in (
            "как вас зовут", "как тебя зовут", "ваше имя", "представьтесь",
            "как зовут", "ваше имя", "кто вы такая", "кто вы такой",
            "кем вы представлялись", "как вы представлялись", "как представились",
            "из какой компании", "из какой вы компании", "вы из какой компании",
            "какая компания", "на какую компанию",
            "откуда звоните", "откуда вы звоните", "откуда вы", "из какой организации",
            "откуда звонок", "с какой компании", "с какой организации", "что за компания", "кто вы",
            "какая должность", "на какую должность", "что за работа", "какая работа",
            "про работу", "о работе", "условия", "что за вакансия", "какая вакансия",
            "расскажите о вакансии", "ваканси", "сколько часов", "какой график",
            "график работы", "график", "время работы", "со скольки", "до скольки", "телеграм",
            "никнейм", "компан", "зарплат", "заработн", "сколько платят", "какая зарплата", "оклад", "доход", "зп",
            "гражданств", "компьютер", "ноутбук", "камера", "микрофон", "зум", "zoom",
            "онлайн-собеседован", "собеседован",
        ))

    @staticmethod
    def _repeat_reply_from_history(history: list[dict[str, str]] | None) -> str:
        """Repeat the original Jana line without nesting previous repeat prefixes."""
        for item in reversed(history or []):
            if not isinstance(item, dict) or not _is_assistant_history_role(item.get("role")):
                continue
            previous_line = _normalize_text(str(item.get("text", "")))
            while previous_line and re.match(
                r"^\s*(?:конечно[\s,]*)?повторю(?:\s*:\s*|[\s,]+)",
                previous_line,
                flags=re.IGNORECASE,
            ):
                previous_line = re.sub(
                    r"^\s*(?:конечно[\s,]*)?повторю(?:\s*:\s*|[\s,]+)",
                    "",
                    previous_line,
                    count=1,
                    flags=re.IGNORECASE,
                ).strip()
            if previous_line:
                # The caller asked for the line itself. A conversational prefix
                # is both redundant in audio and easy to loop back into STT.
                return previous_line
        return ""

    @staticmethod
    def _script_objection_reply(text: str) -> str | None:
        """Answer interruptions and clarification requests without losing the script stage."""
        lowered = _normalize_text(text).lower()
        if not lowered:
            return None
        asks_name = any(marker in lowered for marker in (
            "как вас зовут", "как тебя зовут", "ваше имя", "представьтесь", "кто вы",
            "как зовут", "кто вы такая", "кто вы такой",
            "кем вы представлялись", "как вы представлялись", "как представились",
            "как вас представляли",
        ))
        asks_company = any(marker in lowered for marker in (
            "из какой компании", "из какой вы компании", "вы из какой компании",
            "какая компания", "на какую компанию", "название компании",
            "кто звонит", "кто мне звонит", "откуда звоните", "откуда вы звоните",
            "откуда вы", "откуда звонок", "из какой организации", "с какой организации",
            "что за компания", "с какой компании",
        ))
        asks_position = any(marker in lowered for marker in (
            "какая должность", "на какую должность", "кем работать", "что за должность",
            "какая вакансия", "на какую вакансию",
        ))
        asks_office = any(marker in lowered for marker in (
            "где офис", "где находится офис", "адрес офиса", "где вы находитесь",
            "куда приезжать", "нужно приезжать в офис", "есть офис",
        ))
        asks_schedule = any(marker in lowered for marker in (
            "сколько часов", "сколько работать", "рабочий день", "во сколько",
            "со скольки", "с какого времени", "до скольки", "до какого времени",
            "какой график", "график работы", "частичн",
        )) or (
            any(marker in lowered for marker in ("вечер", "выходн"))
            and ("?" in text or "можно" in lowered or "разреш" in lowered)
        )
        asks_job = MangoCallService._is_job_question(lowered) or any(
            marker in lowered for marker in ("про работу", "о работе")
        )
        asks_telegram = any(marker in lowered for marker in ("телеграм", "телеграмм", "ник", "логин", "как найти", "не нашёл", "не нашел"))
        asks_handle_details = any(marker in lowered for marker in ("ник", "логин", "букв", "как пишется"))
        asks_letter_case = bool(re.search(r"\b(?:заглавн\w*|строчн\w*|больш\w*|маленьк\w*|регистр)\b", lowered))
        asks_letter_identity = bool(re.search(r"\b(?:латинск\w*|русск\w*|буква|буквы|эйч|икс|ар|эр)\b", lowered)) or bool(
            re.search(r"\b[xhr]\b", lowered)
        )
        asks_what_is_letter = asks_letter_identity and bool(
            re.search(r"\b(?:какая|какой|что|значит|обозначает|это)\b", lowered)
        )
        if asks_telegram and (asks_letter_case or asks_letter_identity):
            return (
                "Можно писать заглавными или строчными — регистр в телеграме не важен. "
                "В нике два икса, английская эйч и английская ар, затем цифра один. "
                "Икс — как крестик; эйч — не русская эн, а английская эйч; ар — английская ар, "
                "не русская эр."
            )
        if asks_telegram and (MangoCallService._is_repeat_request(lowered) or asks_handle_details):
            return (
                "Никнейм: два икса, английские буквы эйч и ар, затем цифра один. "
                "Икс — как крестик; эйч и ар — английские названия букв."
            )
        asks_letter_case_without_handle = asks_letter_case and any(
            marker in lowered for marker in ("ник", "логин", "букв", "телеграм", "телеграмм")
        )
        if asks_letter_case_without_handle:
            return "Можно писать заглавными или строчными — регистр букв в телеграме не важен."
        if asks_what_is_letter or (asks_letter_identity and any(marker in lowered for marker in ("какая буква", "что за буква", "латинск", "русск", "буква r", "буква h", "буква x", "букву r", "букву h", "букву x"))):
            return (
                "В нике два икса, английская эйч и английская ар. Икс — как крестик; "
                "эйч — не русская эн, ар — не русская эр."
            )
        asks_foreign = any(marker in lowered for marker in ("из-за границы", "за границей", "из другой страны", "иностран"))
        asks_salary = any(marker in lowered for marker in ("зарплат", "заработн", "оклад", "процент", "доход", "сколько плат", " зп", "зп "))
        asks_citizenship = any(marker in lowered for marker in ("гражданств", "гражданином", "паспорт"))
        asks_computer = any(marker in lowered for marker in ("компьютер", "ноутбук", "телефон")) and any(
            marker in lowered for marker in ("обязательно", "нужен", "можно с телефона")
        )
        asks_zoom = any(marker in lowered for marker in ("zoom", "зум", "камер", "микрофон"))

        # Answer every explicit subject present in a compound utterance. This
        # is intentionally grounded in the vacancy facts; the language model
        # classifies ambiguous wording but cannot drop a second direct question.
        answers: list[str] = []
        if asks_name:
            answers.append(MANGO_NAME_ANSWER)
        if asks_company:
            answers.append("Я звоню из рекрутинговой компании «Лекс-Торг». Запрос на вакансию поступил от компании «Баланс».")
        if asks_position:
            answers.append("Речь о должности персонального инвестиционного советника в компании «Баланс». Работа заключается в работе с клиентами.")
        if asks_office:
            answers.append("Работа полностью удалённая, посещать офис не нужно. Отдельный адрес офиса мне не сообщали.")
        if asks_job and not asks_position:
            answers.append(MANGO_JOB_OVERVIEW)
        if asks_schedule:
            answers.append("График пять на два, с десяти до двадцати по московскому времени. Предусмотрена полная занятость.")
        if asks_telegram:
            answers.append(MANGO_TELEGRAM)
        if asks_foreign:
            answers.append(MANGO_FOREIGN_ANSWER)
        if asks_salary:
            answers.append(MANGO_SALARY_ANSWER)
        if asks_citizenship and "обязательно" in lowered:
            answers.append(MANGO_CITIZENSHIP_ANSWER)
        if asks_computer:
            answers.append(MANGO_COMPUTER_ANSWER)
        if asks_zoom:
            answers.append(MANGO_ZOOM_CAMERA_ANSWER)
        if answers:
            return " ".join(dict.fromkeys(answers))
        if MangoCallService._is_repeat_request(lowered):
            if any(marker in lowered for marker in ("телеграм", "никнейм")):
                return MANGO_TELEGRAM
            if any(marker in lowered for marker in ("работ", "ваканс", "должност", "обязанност")):
                return MANGO_JOB_DESCRIPTION
            return MANGO_DEEP_ANSWER
        if MangoCallService._is_job_question(lowered):
            return None
        if any(marker in lowered for marker in ("из-за границы", "за границей", "из другой страны", "иностран")):
            return MANGO_FOREIGN_ANSWER
        if any(marker in lowered for marker in ("зарплат", "заработн", "оклад", "процент", "доход", "сколько плат", " зп", "зп ")):
            return MANGO_SALARY_ANSWER
        if any(marker in lowered for marker in ("гражданств", "гражданином", "паспорт")) and "обязательно" in lowered:
            return MANGO_CITIZENSHIP_ANSWER
        if any(marker in lowered for marker in ("компьютер", "ноутбук", "телефон")) and any(marker in lowered for marker in ("обязательно", "нужен", "можно с телефона")):
            return MANGO_COMPUTER_ANSWER
        if any(marker in lowered for marker in ("zoom", "зум", "камер", "микрофон")):
            return MANGO_ZOOM_CAMERA_ANSWER
        if "?" in text or any(marker in lowered for marker in ("почему", "как проходит", "какие документы", "подробн")):
            return MANGO_DEEP_ANSWER
        return None

    @staticmethod
    def _strip_audio_echo(text: str, last_assistant_text: str) -> str:
        """Remove a looped-back Jana line wherever it appears in the STT result."""
        tokenise = lambda value: re.findall(r"[а-яёa-z0-9]+", _normalize_text(value).lower())
        transcript_words = tokenise(text)
        assistant_words = tokenise(last_assistant_text)
        if not transcript_words or not assistant_words or len(assistant_words) < 5:
            return _normalize_text(text)
        # STT may return candidate speech plus the previous TTS line either at
        # the beginning or at the end. Remove the longest exact word sequence
        # of the assistant line, not only a prefix.
        best: tuple[int, int] | None = None
        max_match = min(len(assistant_words), 12)
        for length in range(max_match, 4, -1):
            for assistant_start in range(len(assistant_words) - length + 1):
                needle = assistant_words[assistant_start : assistant_start + length]
                for transcript_start in range(len(transcript_words) - length + 1):
                    if transcript_words[transcript_start : transcript_start + length] == needle:
                        best = (transcript_start, length)
                        break
                if best:
                    break
            if best:
                break
        if not best:
            return _normalize_text(text)
        transcript_start, length = best
        remaining = transcript_words[:transcript_start] + transcript_words[transcript_start + length :]
        return " ".join(remaining).strip()

    @staticmethod
    def _has_affirmative_marker(text: str) -> bool:
        lowered = re.sub(r"[^\wа-яё+ ]+", " ", _normalize_text(text).lower())
        return bool(re.search(
            r"(?:\bда\b|ага|угу|актуальн|интересн|подход|конечно|согласен|согласна|"
            r"рассматрива|готов|готова|давайте|почему бы и нет|можно)",
            lowered,
        ))

    @staticmethod
    def _is_audio_echo(text: str, last_assistant_text: str) -> bool:
        return not MangoCallService._strip_audio_echo(text, last_assistant_text)

    @staticmethod
    def _is_decline(text: str) -> bool:
        lowered = re.sub(r"[^\wа-яё+ ]+", " ", _normalize_text(text).lower())
        if not lowered or MangoCallService._is_job_question(lowered):
            return False
        if MangoCallService._is_open_question(text) and not re.search(
            r"не\s*(?:актуальн|интересн|подход)|не хочу|не буду|не рассматрива|не звоните|отказ",
            lowered,
        ):
            return False
        if any(marker in lowered for marker in (
            "не понял", "не поняла", "не расслышал", "не расслышала",
            "повторите", "повторить", "еще раз", "ещё раз",
        )):
            return False
        return bool(re.search(
            r"(?:\bнет\b|не актуальн|неактуальн|не интересн|неинтересн|не подход|"
            r"не хочу|не буду|не рассматрива|не звоните|отказ|уже наш|\bне\s+нужн\w*)",
            lowered,
        ))

    @staticmethod
    def _is_affirmative(text: str) -> bool:
        lowered = re.sub(r"[^\wа-яё+ ]+", " ", _normalize_text(text).lower())
        if not lowered or MangoCallService._is_decline(lowered) or MangoCallService._is_job_question(lowered):
            return False
        return bool(re.search(
            r"(?:\bда\b|ага|угу|актуальн|интересн|подход|конечно|согласен|согласна|"
            r"рассматрива|готов|готова|давайте|почему бы и нет|можно)",
            lowered,
        ))

    @staticmethod
    def _is_wrong_recipient(text: str) -> bool:
        lowered = re.sub(r"[^\wа-яё+ ]+", " ", _normalize_text(text).lower())
        return bool(re.search(
            r"(?:\bне я\b|\bне он\b|\bне она\b|\bне тот человек\b|\bне тот номер\b|"
            r"ошиблись(?: номером)?|не туда попали|не знаю такого человека|такого не знаю|"
            r"\bнет\b)",
            lowered,
        ))

    @staticmethod
    def _name_confirmed_by_text(text: str, name: str) -> bool:
        normalized_text = re.sub(r"[^\wа-яё]+", " ", _normalize_text(text).lower()).strip()
        normalized_name = re.sub(r"[^\wа-яё]+", " ", _normalize_text(name).lower()).strip()
        return bool(normalized_name and normalized_name in normalized_text)

    @staticmethod
    def _is_full_time_study(text: str) -> bool:
        lowered = _normalize_text(text).lower()
        if re.search(r"очно\s*[- ]\s*заоч|заочно\s*[- ]\s*очн", lowered):
            return False
        has_study = bool(re.search(r"\b(?:учусь|учёб\w*|учеб\w*|студент\w*)\b", lowered))
        has_full_time_marker = bool(re.search(
            r"\b(?:очн\w*|дневн\w*)\b",
            lowered,
        ))
        return has_study and has_full_time_marker

    @staticmethod
    def _is_open_question(text: str) -> bool:
        """Detect a non-script question before it can advance the state machine."""
        lowered = _normalize_text(text).lower()
        if not lowered:
            return False
        if "?" in text:
            return True
        if any(marker in lowered for marker in (
            "не понял", "не поняла", "не расслышал", "не расслышала",
            "повторите", "повторить", "еще раз", "ещё раз", "что вы сказали",
            "можете уточнить", "можете объяснить", "расскажите подробнее",
            "из какой компании", "какая компания", "на какую компанию",
            "откуда звоните", "откуда вы звоните", "откуда вы", "из какой организации",
            "что за компания", "с какой компании", "кто звонит", "кто вы",
            "на какую должность", "со скольки", "до скольки", "сколько часов",
            "как вас зовут", "как тебя зовут", "ваше имя", "представьтесь", "покажите вакансию",
        )):
            return True
        return bool(re.search(
            r"\b(?:а что|а как|а где|а когда|а почему|а можно|а сколько|"
            r"подскажите|уточните|объясните|расскажите|правильно ли я понял)\b",
            lowered,
        ))

    @staticmethod
    def _stage_reprompt(stage: str) -> str:
        return MANGO_STAGE_REPROMPTS.get(
            stage,
            "Давайте сначала закончим текущий вопрос.",
        )

    @staticmethod
    def _resume_stage_after_objection(stage: str, reply: str) -> str:
        """Answer an interruption, then return to the question already in progress."""
        cleaned = _normalize_text(reply).strip()
        if not cleaned or stage in {"finished", "conditions_followup"}:
            return cleaned
        prompt = MangoCallService._stage_reprompt(stage).strip()
        if not prompt:
            return cleaned
        reply_words = set(re.findall(r"[а-яёa-z0-9]+", cleaned.lower()))
        prompt_words = set(re.findall(r"[а-яёa-z0-9]+", prompt.lower()))
        # A fixed answer may already end with the same question. Do not make
        # the caller hear it twice when the candidate asked about that exact step.
        if len(prompt_words) >= 3 and len(prompt_words & reply_words) / len(prompt_words) >= 0.65:
            return cleaned
        return f"{cleaned} {prompt}"

    @staticmethod
    def _has_age_marker(text: str) -> bool:
        """Accept numeric and spoken Russian ages from STT."""
        lowered = re.sub(r"[^\wа-яё ]+", " ", _normalize_text(text).lower())
        numeric_age = bool(re.search(r"\b(?:1[6-9]|[2-9]\d)\s*(?:лет|года|год)?\b", lowered))
        spoken_age = bool(re.search(
            r"\b(?:шестнадцать|семнадцать|восемнадцать|девятнадцать|"
            r"двадцать|тридцать|сорок|пятьдесят|шестьдесят|семьдесят|"
            r"восемьдесят|девяносто)(?:\s+(?:один|два|три|четыре|пять|"
            r"шесть|семь|восемь|девять))?(?:\s+(?:лет|года|год))?\b",
            lowered,
        ))
        return numeric_age or spoken_age

    @staticmethod
    def _stage_answer_matches(stage: str, text: str) -> bool:
        """Prevent unrelated STT text from advancing the current conversation stage."""
        normalized = _normalize_text(text)
        lowered = re.sub(r"[^\wа-яё+ ]+", " ", normalized.lower())
        if not lowered:
            return False

        yes_no = bool(re.search(r"\b(?:да|нет|ага|угу|есть|нету|имею|имеется)\b", lowered))
        affirmative = bool(re.search(r"\b(?:да|ага|угу|конечно|согласен|согласна|подходит|подходят|устраивает|устраивают|готов|готова)\b", lowered))
        negative = bool(re.search(r"\b(?:нет|нету|не\s+имею|не\s+подходит|не\s+подходят|не\s+устраивает)\b", lowered))

        if stage == "relevance":
            return MangoCallService._is_affirmative(normalized) or MangoCallService._is_decline(normalized)
        if stage == "age_city":
            has_age = MangoCallService._has_age_marker(lowered) or bool(
                re.search(r"\b(?:мне|возраст)\b[^,.!?]{0,48}\b(?:лет|года|год)\b", lowered)
            )
            has_location = bool(re.search(
                r"\b(?:город|живу|проживаю|проживани|из\s+[а-яё-]+|нахожусь|"
                r"санкт\s*-?\s*петербург|москва)\b",
                lowered,
            ))
            return has_age and has_location
        if stage == "computer":
            has_device = bool(re.search(
                r"компьют|ноутбук|лэптоп|телефон|смартфон|планшет|айпад|ipad|пк",
                lowered,
            ))
            # The question already establishes the subject. A short "да",
            # "есть" or "компьютер" is a complete answer and must not trigger
            # a second reprompt.
            return has_device or yes_no or affirmative or negative
        if stage == "citizenship":
            return bool(re.search(r"граждан|росси|рф|паспорт", lowered)) or (yes_no and len(lowered.split()) <= 8)
        if stage == "employment":
            return bool(re.search(
                r"уч[её]б|учусь|университет|колледж|студент|работ|занят|трудоустро|служб|"
                r"не\s+работ|ничем\s+не\s+занят|свободен|свободна",
                lowered,
            )) or (negative and len(lowered.split()) <= 8)
        if stage == "study_format":
            return bool(re.search(r"очно|заочно|дистанцион|вечерн|смешан|онлайн", lowered))
        if stage == "study_schedule":
            return len(lowered.split()) >= 1
        if stage == "work_details":
            return bool(re.search(r"занят|полный|полную|частич|непол|отработ|увольн|работ", lowered))
        if stage in {"conditions", "conditions_before_details", "conditions_resume_age_city", "conditions_resume_computer"}:
            return MangoCallService._has_affirmative_marker(normalized) or negative or bool(
                re.search(r"услов|зарплат|график|работ", lowered)
            ) and (yes_no or "подход" in lowered or "устра" in lowered)
        if stage == "conditions_followup":
            return len(lowered.split()) >= 2
        if stage == "zoom":
            return affirmative or negative or bool(re.search(r"зум|собеседован|подключ|камера|микрофон", lowered))
        if stage == "telegram":
            return len(lowered.split()) >= 1
        return True

    @staticmethod
    def _candidate_answer_prefix(text: str) -> str:
        """Keep the candidate's answer when a follow-up question shares the utterance."""
        normalized = _normalize_text(text).strip()
        sentence = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)
        if len(sentence) > 1:
            return sentence[0].strip()
        question_start = re.search(
            r"\b(?:а\s+)?(?:из какой|из какой вы|из какой компании|откуда вы|откуда звон|"
            r"как вас зовут|кто вы|кто звонит|что за (?:работа|вакансия|компания)|"
            r"какая (?:работа|вакансия|компания)|какой график|сколько (?:часов|платят)|"
            r"когда (?:можно|ближайш)|во сколько|можно ли|подскажите|уточните)\b",
            normalized,
            flags=re.IGNORECASE,
        )
        if question_start and question_start.start() > 0:
            return normalized[:question_start.start()].strip(" ,;:-")
        return normalized

    @staticmethod
    def _deterministic_stage_answer(stage: str, text: str) -> str:
        """Normalize clear screening facts when Qwen is unavailable or uncertain."""
        answer = MangoCallService._candidate_answer_prefix(text)
        if stage == "age_city":
            return _extract_candidate_age_city(answer) or answer
        if stage == "computer":
            has_device = _computer_access_status(answer)
            if has_device is not None:
                return "есть" if has_device else "нет"
        if stage == "employment":
            lowered = answer.lower()
            mentions_study = bool(re.search(r"уч[её]б|учусь|университет|колледж|студент", lowered))
            mentions_work = bool(re.search(r"работ|занят|трудоустро|служб", lowered))
            facts = []
            if mentions_study:
                facts.append(f"учёба: {'есть' if MangoCallService._candidate_has_study(answer) else 'нет'}")
            if mentions_work:
                facts.append(f"работа: {'есть' if MangoCallService._candidate_has_work(answer) else 'нет'}")
            if facts:
                return "; ".join(facts)
        return answer

    @staticmethod
    def _requires_notice(text: str) -> bool:
        """Return true only when the candidate explicitly needs an exit notice."""
        lowered = re.sub(r"\s+", " ", _normalize_text(text).lower()).strip()
        if not re.search(r"отработ", lowered):
            return False
        if re.search(
            r"(?:не\s+(?:потребуется|нужна|нужно|будет)|нет\s+отработ|без\s+отработ|"
            r"отработ\w*\s+не\s+нуж|не\s+знаю|не\s+уверен)",
            lowered,
        ):
            return False
        return True

    @staticmethod
    def _candidate_has_study(text: str) -> bool:
        return _candidate_currently_studies(text)

    @staticmethod
    def _candidate_has_work(text: str) -> bool:
        lowered = _normalize_text(text).lower()
        if not re.search(r"работ|занят|трудоустро|служб", lowered):
            return False
        return not bool(re.search(
            r"(?:нет|нету|без)\s+(?:сейчас\s+)?(?:уч[её]б\w*\s+и\s+)?работ\w*|"
            r"\bне\s+(?:работаю|работает|работать|трудоустроен|трудоустроена)\b|"
            r"работ\w*[\s:,-]+(?:нет|не\s+имею|отсутств\w*)",
            lowered,
        ))

    @staticmethod
    def _study_schedule_conflict(text: str) -> bool:
        """Check explicit study overlap with the Moscow 10:00-20:00 work shift."""
        lowered = re.sub(r"\s+", " ", _normalize_text(text).lower()).strip()

        # STT can contain the tail of Jana's question together with the
        # candidate's answer.  For example: "... будут пересекаться с десяти
        # до двадцати? Нет, не будут".  The answer must win over the echoed
        # wording of the question; otherwise the time range below produces a
        # false rejection.
        explicit_clear = re.search(
            r"(?:не\s+(?:пересека|совпада|меша)|не\s+буд(?:у|ет|ут|ем|ете)\s+(?:пересек|совпад|меша)|"
            r"нет\b|неа\b|не\s+буд(?:ет|ут)\b|после\s+работ|до\s+десяти|"
            r"после\s+двадцати|вечер(?:ом)?\b|ноч(?:ью)?\b|выходн\w*|свободн\w*|"
            r"дистанцион\w*|онлайн\w*)",
            lowered,
        )
        if re.search(
            r"не\s+(?:пересека|совпада|меша)|"
            r"не\s+буд(?:у|ет|ут|ем|ете)\s+(?:пересек|совпад|меша)",
            lowered,
        ):
            return False
        explicit_conflict = re.search(
            r"(?:буд(?:ет|ут)\s+)?(?:пересека|совпада|меша)|"
            r"во\s+время\s+работы|в\s+рабочие\s+часы|дн(?:е|ё)м\b|дн(?:е|ё)вн\w*",
            lowered,
        )
        # When the loopback contains the question itself, a bare "нет" at
        # the end is still a complete answer to that question. Compare the
        # last clear/conflict marker so "нет, будет пересекаться" remains a
        # conflict while "будет пересекаться? нет" is accepted as clear.
        clear_positions = [
            match.start()
            for match in re.finditer(
                r"\b(?:нет|неа)\b|не\s+буд(?:ет|ут)\b|не\s+(?:пересека|совпада|меша)",
                lowered,
            )
        ]
        conflict_positions = [
            match.start()
            for match in re.finditer(
                r"(?:буд(?:ет|ут)\s+)?(?:пересека|совпада|меша)|"
                r"во\s+время\s+работы|в\s+рабочие\s+часы|дн(?:е|ё)м\b|дн(?:е|ё)вн\w*",
                lowered,
            )
        ]
        if clear_positions and (
            not conflict_positions or max(clear_positions) >= max(conflict_positions)
        ):
            return False
        if explicit_clear and not explicit_conflict:
            return False
        if explicit_conflict and not re.search(
            r"не\s+(?:пересека|совпада|меша)|не\s+буд(?:у|ет|ут|ем|ете)\s+(?:пересек|совпад|меша)",
            lowered,
        ):
            return True

        for start, end in re.findall(
            r"(?:с|от)\s*(\d{1,2}|[а-яё-]+)(?::\d{2})?\s*(?:до|по|-)\s*(\d{1,2}|[а-яё-]+)(?::\d{2})?",
            lowered,
        ):
            word_hours = {
                "восемь": 8, "восьми": 8, "девять": 9, "девяти": 9, "десять": 10, "десяти": 10,
                "одиннадцать": 11, "одиннадцати": 11,
                "двенадцать": 12, "двенадцати": 12, "тринадцать": 13, "тринадцати": 13,
                "четырнадцать": 14, "четырнадцати": 14, "пятнадцать": 15, "пятнадцати": 15,
                "шестнадцать": 16, "шестнадцати": 16, "семнадцать": 17, "семнадцати": 17,
                "восемнадцать": 18, "восемнадцати": 18, "девятнадцать": 19, "девятнадцати": 19,
                "двадцать": 20, "двадцати": 20, "двадцать-один": 21, "двадцати-одного": 21,
                "двадцать-два": 22, "двадцати-двух": 22, "двадцать-три": 23, "двадцати-трёх": 23,
            }
            start_hour = int(start) if start.isdigit() else word_hours.get(start)
            end_hour = int(end) if end.isdigit() else word_hours.get(end)
            if start_hour is not None and end_hour is not None and start_hour < 20 and end_hour > 10:
                return True
        return False

    @staticmethod
    def _study_schedule_is_clear(text: str) -> bool:
        """Require an explicit non-overlap statement before continuing."""
        lowered = re.sub(r"\s+", " ", _normalize_text(text).lower()).strip()
        if MangoCallService._study_schedule_conflict(lowered):
            return False
        return bool(re.search(
            r"не\s+(?:пересека|совпада|меша)|после\s+работ|до\s+десяти|после\s+двадцати|"
            r"нет\b|неа\b|не\s+буд(?:ет|ут)\b|вечер|ноч|утр|выходн|свободн|дистанцион|онлайн",
            lowered,
        )) or bool(re.search(
            r"(?:с|от)\s*(?:\d{1,2}|[а-яё-]+)(?::\d{2})?\s*(?:до|по|-)\s*"
            r"(?:\d{1,2}|[а-яё-]+)",
            lowered,
        ))

    @staticmethod
    def _study_schedule_answer_is_decisive(text: str) -> bool:
        """Tell an answer from a new question about the same schedule."""
        if MangoCallService._study_schedule_is_clear(text):
            return True
        lowered = re.sub(r"\s+", " ", _normalize_text(text).lower()).strip()
        if not MangoCallService._study_schedule_conflict(lowered):
            return False
        # A bare question such as "а пары будут пересекаться?" is not a
        # rejection. An explicit yes/statement or a question followed by an
        # answer is decisive.
        if "?" in text and not re.search(
            r"\b(?:да|ага|угу)\b",
            lowered,
        ):
            return False
        return True

    @staticmethod
    def _study_schedule_stage_reply(text: str, candidate: dict[str, Any]) -> tuple[str, str, bool]:
        """Resolve study overlap before any later vacancy stage can run."""
        candidate["study_schedule"] = text
        if MangoCallService._study_schedule_conflict(text):
            _add_candidate_review_flag(candidate, "учёба пересекается с графиком десять-двадцать по Москве")
            candidate["result"] = "declined_study_schedule"
            return MANGO_REJECT_STUDY, "finished", True
        if not MangoCallService._study_schedule_is_clear(text):
            _add_candidate_review_flag(candidate, "нужно точно уточнить часы учёбы")
            return MANGO_STUDY_SCHEDULE, "study_schedule", False
        if candidate.get("has_work"):
            return MANGO_WORK_DETAILS, "work_details", False
        if candidate.get("conditions_spoken"):
            return MANGO_ZOOM, "zoom", False
        candidate["conditions_spoken"] = True
        return MANGO_JOB_INTRO, "conditions", False

    @staticmethod
    def _schedule_offer_for_candidate(
        candidate: dict[str, Any],
        exclude: set[str] | None = None,
        day: date | None = None,
        after_start: str | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        boundary: datetime | None = None
        if after_start:
            try:
                boundary = datetime.fromisoformat(after_start).astimezone(calendar_service.tz)
            except (TypeError, ValueError):
                boundary = None
        selected_day = day or (boundary.date() if boundary else calendar_service.today())
        slots = calendar_service.available_slots(selected_day.isoformat(), limit=120, exclude=exclude)
        if boundary and selected_day == boundary.date():
            # "A little later" means the next free slot after the one just
            # offered, not a new search around the current clock time.
            filtered_slots: list[dict[str, Any]] = []
            for slot in slots:
                try:
                    slot_start = datetime.fromisoformat(str(slot["start"])).astimezone(calendar_service.tz)
                except (KeyError, TypeError, ValueError):
                    continue
                if slot_start > boundary:
                    filtered_slots.append(slot)
            slots = filtered_slots
        if not slots and selected_day == calendar_service.today():
            # Prefer today, but do not leave a qualified candidate without a
            # path forward when today's working slots are already occupied.
            selected_day = selected_day + timedelta(days=1)
            slots = calendar_service.available_slots(selected_day.isoformat(), limit=120, exclude=exclude)
        elif not slots and boundary and selected_day <= boundary.date():
            # If there is no later window today, continue with the first free
            # window on the following day.
            selected_day = boundary.date() + timedelta(days=1)
            slots = calendar_service.available_slots(selected_day.isoformat(), limit=120, exclude=exclude)
        preferred_minutes = MangoCallService._requested_time_minutes(str(candidate.get("schedule_request", "")))
        if preferred_minutes is not None and slots:
            slots.sort(key=lambda item: (
                abs(MangoCallService._slot_minutes(item["time"]) - preferred_minutes),
                MangoCallService._slot_minutes(item["time"]),
            ))
        # Start with one nearest window. If the candidate declines it or
        # names another hour, the next search is centered on that request.
        slots = slots[:1]
        if selected_day == calendar_service.today():
            prefix = "Сегодня"
        elif selected_day == calendar_service.today() + timedelta(days=1):
            prefix = "Завтра"
        else:
            prefix = calendar_service._date_words(selected_day)
        candidate["offered_slots"] = [slot["start"] for slot in slots]
        return calendar_service.offer_text(slots, prefix, requested_minutes=preferred_minutes), slots

    @staticmethod
    def _slot_minutes(value: str) -> int:
        try:
            hour, minute = (int(part) for part in str(value).split(":", 1))
            return hour * 60 + minute
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _requested_time_minutes(text: str) -> int | None:
        """Extract the candidate's latest stated time preference."""
        lowered = _normalize_text(text).lower()
        if not lowered:
            return None
        word_hours = {
            "час": 13, "часу": 13, "часа": 13, "часов": 13,
            "одному": 13, "одного": 13, "один": 13,
            "два": 14, "двум": 14, "двух": 14,
            "трём": 15, "трем": 15, "трёх": 15, "трех": 15, "три": 15,
            "четырём": 16, "четырем": 16, "четырёх": 16, "четырех": 16, "четыре": 16,
            "пяти": 17, "пять": 17, "пятью": 17,
            "шести": 18, "шесть": 18, "шестью": 18,
            "семи": 19, "семь": 19, "семью": 19,
            "восьми": 20, "восемь": 20, "восемью": 20,
            "десять": 10, "десяти": 10,
            "одиннадцать": 11, "одиннадцати": 11,
            "двенадцать": 12, "двенадцати": 12,
            "тринадцать": 13, "тринадцати": 13,
            "четырнадцать": 14, "четырнадцати": 14,
            "пятнадцать": 15, "пятнадцати": 15,
            "шестнадцать": 16, "шестнадцати": 16,
            "семнадцать": 17, "семнадцати": 17,
            "восемнадцать": 18, "восемнадцати": 18,
            "девятнадцать": 19, "девятнадцати": 19,
            "двадцать": 20, "двадцати": 20,
            "двадцать один": 21, "двадцать одного": 21,
            "двадцать два": 22, "двадцати двух": 22,
            "двадцать три": 23, "двадцати трёх": 23, "двадцати трех": 23,
        }
        time_prefix = r"(?:в\s+районе|ближе\s+к|около|примерно|после|к|в|на)"
        candidates: list[tuple[int, int]] = []
        explicit_morning = any(marker in lowered for marker in ("утр", "утра", "ноч", "ночи"))
        explicit_evening = any(marker in lowered for marker in ("днём", "днем", "дня", "вечер", "вечера"))

        for match in re.finditer(time_prefix + r"\s+(\d{1,2})(?:\s*:\s*(\d{2}))?", lowered):
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                continue
            if 0 < hour <= 11 and explicit_evening:
                hour += 12
            elif hour <= 7 and not explicit_morning:
                hour += 12
            candidates.append((match.start(), hour * 60 + minute))

        half_hours = {
            "второго": 14, "третьего": 15, "четвёртого": 16, "четвертого": 16,
            "пятого": 17, "шестого": 18, "седьмого": 19, "восьмого": 20,
        }
        for match in re.finditer(
            r"(?:к|в|на|около|примерно)\s+(?:половин\w*|пол)\s+([а-яё-]+)",
            lowered,
        ):
            next_hour = half_hours.get(match.group(1))
            if next_hour is not None:
                candidates.append((match.start(), next_hour * 60 - 30))

        word_pattern = re.compile(time_prefix + r"\s+([а-яё-]+(?:\s+[а-яё-]+)?)")
        for match in word_pattern.finditer(lowered):
            parts = match.group(1).replace("-", " ").split()
            if len(parts) > 1 and (
                parts[-1].startswith("час")
                or parts[-1] in {"утра", "утром", "вечера", "вечером", "дня", "днём", "днем"}
            ):
                parts.pop()
            word = " ".join(parts)
            if word not in word_hours and len(parts) > 1 and parts[0] in word_hours:
                # Do not absorb conversational continuations such as
                # "к трём можно?" into the time expression.
                word = parts[0]
            if word in word_hours:
                hour = word_hours[word]
                if explicit_morning and 13 <= hour <= 20:
                    hour -= 12
                elif explicit_evening and 0 < hour <= 11:
                    hour += 12
                candidates.append((match.start(), hour * 60))

        if candidates:
            # In corrections such as "не в пять, а можно к шести?", the last
            # mentioned time is the actual preference, not the rejected one.
            return max(candidates, key=lambda item: item[0])[1]
        if any(marker in lowered for marker in ("после обеда", "днём", "днем")):
            return 14 * 60
        if "утром" in lowered or "утра" in lowered:
            return 10 * 60
        if "вечером" in lowered or "вечера" in lowered:
            return 18 * 60
        return None

    @staticmethod
    def _contains_schedule_request(text: str) -> bool:
        """Detect a scheduling request before the dedicated schedule stage."""
        lowered = _normalize_text(text).lower()
        if MangoCallService._requested_time_minutes(text) is not None:
            return True
        return any(
            marker in lowered
            for marker in (
                "когда можно",
                "когда удобно",
                "когда ближайш",
                "когда свободн",
                "в какое время",
                "какое время",
                "на какое время",
                "на когда",
                "по времени",
                "записать на собеседование",
                "перейти к собеседованию",
                "перейти на собеседование",
            )
        )

    @staticmethod
    def _schedule_slot_from_text(text: str, offered: list[str]) -> str | None:
        lowered = _normalize_text(text).lower()
        requested_minutes = MangoCallService._requested_time_minutes(text)
        for start in offered:
            try:
                slot_start = datetime.fromisoformat(start).astimezone(calendar_service.tz)
                clock = slot_start.strftime("%H:%M")
            except ValueError:
                continue
            hour, minute = clock.split(":", 1)
            if (
                clock in lowered
                or f"{int(hour)} {minute}" in lowered
                or requested_minutes == int(hour) * 60 + int(minute)
            ):
                return start
            words = calendar_service._time_words(clock)
            if words and words in lowered:
                return start
        if (
            len(offered) == 1
            and MangoCallService._is_affirmative(text)
            and MangoCallService._requested_time_minutes(text) is None
            and not any(marker in lowered for marker in ("не смогу", "не могу", "неудобно", "не удобно"))
        ):
            return offered[0]
        if (
            len(offered) == 1
            and any(marker in lowered for marker in ("окей", "ок", "хорошо", "ладно", "подтверждаю", "записывайте", "запишите"))
            and not any(marker in lowered for marker in ("не смогу", "не могу", "неудобно", "не удобно"))
        ):
            return offered[0]
        if len(offered) > 1:
            # The TTS prompt names options as "первый", "второй" and
            # "третий". Resolve only an explicit option so a plain "да"
            # cannot silently reserve the first slot.
            option_patterns = (
                (0, r"\b(?:первый|первое|вариант\s+один|вариант\s+первый)\b"),
                (1, r"\b(?:второй|второе|вариант\s+два|вариант\s+второй)\b"),
                (2, r"\b(?:третий|третье|вариант\s+три|вариант\s+третий)\b"),
            )
            for index, pattern in option_patterns:
                if index < len(offered) and re.search(pattern, lowered):
                    return offered[index]
        return None

    @staticmethod
    def _schedule_time_question(text: str) -> bool:
        lowered = _normalize_text(text).lower()
        return any(marker in lowered for marker in (
            "ко скольки", "к скольки", "во сколько", "на какое время",
            "какое время", "на когда", "когда я записан", "когда я записана",
            "на какое число", "какого числа", "когда собеседование",
            "когда встреча", "в какое время", "напомните время",
            "напомни время", "на когда запись", "во сколько у меня",
            "когда я записан на", "когда я записана на",
            "когда созвон", "когда встречаемся", "когда назначено",
        ))

    @staticmethod
    def _schedule_availability_question(text: str) -> bool:
        lowered = _normalize_text(text).lower()
        return any(marker in lowered for marker in (
            "на какое время свободно", "какое время свободно", "какое время есть",
            "когда свободно", "когда есть свободн", "какие окна свободны",
            "какие есть окна", "какое ближайшее свободное", "когда ближайшее окно",
            "что свободно", "что есть свободно",
        ))

    @staticmethod
    def _schedule_change_request(text: str) -> bool:
        lowered = _normalize_text(text).lower()
        return any(marker in lowered for marker in (
            "перенести", "перенесём", "перенесем", "другое время",
            "на другое время", "изменить время", "поменять время",
            "поменять запись", "изменить запись", "перезаписаться",
            "переназначить", "не смогу в это время", "не получится в это время",
        ))

    @staticmethod
    def _schedule_cancel_request(text: str) -> bool:
        lowered = _normalize_text(text).lower()
        return any(marker in lowered for marker in (
            "отменить запись", "отмена записи", "не буду проходить",
            "не хочу проходить", "передумал", "передумала", "больше не актуально",
            "неактуально", "не хочу записываться", "не буду записываться",
            "не надо записывать", "не надо записываться", "отмените запись",
            "не хочу на собеседование", "не буду на собеседование", "не хочу идти",
        )) or bool(re.search(r"\bне\s+(?:хочу|буду)\b.{0,35}\b(?:запис\w*|собеседован\w*|участвовать|идти)\b", lowered))

    @staticmethod
    def _cancel_candidate_booking(candidate: dict[str, Any]) -> None:
        """Release the appointment that belongs to this active call."""
        event_id = _normalize_text(str(candidate.get("scheduled_event_id", "")))
        scheduled_at = _normalize_text(str(candidate.get("scheduled_at", "")))
        if not event_id and scheduled_at:
            try:
                scheduled_day = datetime.fromisoformat(scheduled_at).astimezone(calendar_service.tz).date()
                phone = re.sub(r"\D", "", str(candidate.get("number", "")))
                snapshot = calendar_service.snapshot(scheduled_day.isoformat())
                for item in snapshot.get("events", []):
                    item_phone = re.sub(r"\D", "", str(item.get("phone", "")))
                    if str(item.get("start", "")) == scheduled_at and (not phone or item_phone == phone):
                        event_id = str(item.get("id", ""))
                        break
            except (TypeError, ValueError):
                event_id = ""
        if event_id:
            calendar_service.delete(event_id)
        candidate.pop("scheduled_event_id", None)
        candidate.pop("scheduled_at", None)

    @staticmethod
    def _schedule_status_reply(text: str, candidate: dict[str, Any]) -> str | None:
        """Answer a time question without restarting or finishing the call."""
        if not MangoCallService._schedule_time_question(text):
            return None
        scheduled_at = _normalize_text(str(candidate.get("scheduled_at", "")))
        offered = [str(item) for item in candidate.get("offered_slots", []) if item]
        start_value = scheduled_at or (offered[0] if len(offered) == 1 else "")
        if not start_value:
            return None
        try:
            start = datetime.fromisoformat(start_value).astimezone(calendar_service.tz)
        except ValueError:
            return None
        time_words = calendar_service._time_words(start.strftime("%H:%M"))
        if scheduled_at:
            if start.date() == calendar_service.today():
                date_words = "сегодня"
            elif start.date() == calendar_service.today() + timedelta(days=1):
                date_words = "завтра"
            else:
                date_words = f"{calendar_service._date_words(start.date())}"
            return f"Вы записаны на онлайн-собеседование {date_words} на {time_words} по московскому времени."
        return f"Предложенное окно — {time_words} по московскому времени. Подтвердить запись?"

    @staticmethod
    def _schedule_stage_reply(text: str, candidate: dict[str, Any]) -> tuple[str, str, bool]:
        offered = [str(item) for item in candidate.get("offered_slots", []) if item]
        lowered = _normalize_text(text).lower()
        requested_minutes = MangoCallService._requested_time_minutes(text)
        selected = MangoCallService._schedule_slot_from_text(text, offered)
        availability_question = bool(re.search(
            r"(?:можно\s+(?:ли\s+)?(?:на|к|в)|есть\s+ли\s+(?:окно|время)|"
            r"свободно\s+ли|получится\s+(?:на|к|в))",
            lowered,
        )) or "?" in text
        explicit_booking = (MangoCallService._is_affirmative(text) and not availability_question) or any(
            marker in lowered
            for marker in ("записывайте", "запишите меня", "подтверждаю", "подтвердить запись", "мне подходит")
        )
        later_requested = any(
            marker in lowered
            for marker in ("чуть позже", "немного позже", "попозже", "можно позже", "через час", "через полчаса")
        )
        tomorrow_requested = any(marker in lowered for marker in ("завтра", "на следующий день", "на следующий"))
        if tomorrow_requested:
            candidate["schedule_day_preference"] = "tomorrow"
        elif "сегодня" in lowered:
            candidate["schedule_day_preference"] = "today"
        today_declined = any(marker in lowered for marker in ("сегодня не могу", "сегодня никак", "сегодня не получится", "сегодня не смогу"))
        if tomorrow_requested:
            if not candidate.get("schedule_today_prompted"):
                # Asking for tomorrow counts as the first refusal of a
                # same-day interview, but we still make one short attempt to
                # keep the meeting today.
                candidate["schedule_today_prompted"] = True
                candidate["schedule_today_refusal_count"] = max(
                    1, int(candidate.get("schedule_today_refusal_count", 0) or 0)
                )
                candidate["schedule_request"] = text
                return MANGO_SCHEDULE_TODAY_PERSUADE, "schedule", False
            # The candidate repeated that today is not suitable. Respect the
            # request and offer the nearest available slot tomorrow.
            candidate["schedule_request"] = text
            reply, _ = MangoCallService._schedule_offer_for_candidate(
                candidate,
                exclude=set(offered),
                day=calendar_service.today() + timedelta(days=1),
            )
            candidate["schedule_day_preference"] = "tomorrow"
            return reply, "schedule", False
        if today_declined:
            refusal_count = int(candidate.get("schedule_today_refusal_count", 0) or 0) + 1
            candidate["schedule_today_refusal_count"] = refusal_count
            candidate["schedule_request"] = text
            if refusal_count == 1:
                candidate["schedule_today_prompted"] = True
                return MANGO_SCHEDULE_TODAY_PERSUADE, "schedule", False
            # After the second clear refusal of today, stop persuading and
            # offer the nearest window on the next day.
            reply, _ = MangoCallService._schedule_offer_for_candidate(
                candidate,
                exclude=set(offered),
                day=calendar_service.today() + timedelta(days=1),
            )
            return reply, "schedule", False
        if later_requested and offered:
            candidate["schedule_request"] = text
            reply, _ = MangoCallService._schedule_offer_for_candidate(
                candidate,
                exclude=set(offered),
                after_start=offered[0],
            )
            return reply, "schedule", False
        if requested_minutes is not None and selected is None:
            candidate["schedule_request"] = text
            preferred_day = (
                calendar_service.today() + timedelta(days=1)
                if candidate.get("schedule_day_preference") == "tomorrow"
                else None
            )
            reply, _ = MangoCallService._schedule_offer_for_candidate(
                candidate,
                exclude=set(offered),
                day=preferred_day,
            )
            return reply, "schedule", False
        if selected and requested_minutes is not None and not explicit_booking:
            # A time phrased as a question or preference is not consent to
            # reserve it. First state/check the window and ask for confirmation.
            candidate["schedule_request"] = text
            return MangoCallService._schedule_status_reply("во сколько", candidate) or MANGO_SCHEDULE_REPROMPT, "schedule", False
        if any(marker in lowered for marker in ("другое время", "другой час", "не удобно", "неудобно", "не смогу", "не могу")):
            candidate["schedule_request"] = ""
            return MANGO_SCHEDULE_TIME_ASK, "schedule", False
        if selected:
            title = str(candidate.get("age_city") or "Кандидат")
            event = calendar_service.reserve(selected, title, str(candidate.get("number", "")))
            if event:
                candidate["scheduled_at"] = event["start"]
                candidate["scheduled_event_id"] = event["id"]
                candidate["result"] = "qualified"
                try:
                    event_start = datetime.fromisoformat(event["start"]).astimezone(calendar_service.tz)
                    booked_time = calendar_service._time_words(event_start.strftime("%H:%M"))
                    if event_start.date() == calendar_service.today():
                        booked_date = "сегодня"
                    elif event_start.date() == calendar_service.today() + timedelta(days=1):
                        booked_date = "завтра"
                    else:
                        booked_date = calendar_service._date_words(event_start.date())
                    confirmation = (
                        f"Отлично, записала вас на онлайн-собеседование {booked_date} на {booked_time} "
                        "по московскому времени."
                    )
                except (TypeError, ValueError):
                    confirmation = MANGO_SCHEDULE_CONFIRM
                return f"{confirmation} {MANGO_TELEGRAM}", "telegram", False
            # A different manual booking may have claimed the slot between
            # offering it and the candidate's confirmation.
            reply, _ = MangoCallService._schedule_offer_for_candidate(candidate, exclude=set(offered))
            return reply, "schedule", False
        if MangoCallService._is_open_question(text) or "когда" in lowered or "время" in lowered:
            reply, _ = MangoCallService._schedule_offer_for_candidate(candidate, exclude=set(offered))
            return reply, "schedule", False
        return MANGO_SCHEDULE_REPROMPT, "schedule", False

    @staticmethod
    def _next_unfinished_candidate_step(candidate: dict[str, Any]) -> tuple[str, str]:
        """Continue with the first unanswered screening field, never restart it."""
        if not _normalize_text(str(candidate.get("age_city", ""))):
            return MANGO_INTERESTED_WITH_AGE, "age_city"
        if not _normalize_text(str(candidate.get("computer", ""))):
            return MANGO_COMPUTER, "computer"
        if not _normalize_text(str(candidate.get("citizenship", ""))):
            return MANGO_CITIZENSHIP, "citizenship"
        employment = _normalize_text(str(candidate.get("employment", "")))
        if not employment:
            return MANGO_EMPLOYMENT, "employment"

        has_study = MangoCallService._candidate_has_study(employment)
        has_work = MangoCallService._candidate_has_work(employment)
        study_format = _normalize_text(str(candidate.get("study_format", "")))
        if has_study and not study_format:
            return MANGO_STUDY_FORMAT, "study_format"
        if has_study and not _normalize_text(str(candidate.get("study_schedule", ""))):
            return MANGO_STUDY_SCHEDULE, "study_schedule"
        if has_work and not _normalize_text(str(candidate.get("work_details", ""))):
            return MANGO_WORK_DETAILS, "work_details"
        return MANGO_ZOOM, "zoom"

    @staticmethod
    def _telegram_stage_reply(
        stage: str,
        text: str,
        candidate: dict[str, Any],
        llm_intent: dict[str, str] | None = None,
    ) -> tuple[str, str, bool]:
        """Keep the caller on the line through username lookup and message confirmation."""
        lowered = _normalize_text(text).lower()
        explicit_refusal = bool(re.search(
            r"(?:не\s+(?:хочу|буду|собираюсь)\s+(?:искать|пользоваться|переходить|писать)|"
            r"отказываюсь\s+(?:от\s+)?телеграм|не\s+хочу\s+продолжать|"
            r"не\s+буду\s+продолжать)",
            lowered,
        ))
        if explicit_refusal:
            candidate["result"] = "declined_telegram"
            return MANGO_GOODBYE, "finished", True

        repeat = MangoCallService._is_repeat_request(text) or any(marker in lowered for marker in (
            "по буквам", "медленнее", "как пишется", "какие буквы", "не нашёл", "не нашел",
            "не нашла", "не могу найти", "не получилось найти", "не вижу аккаунт",
        ))
        asks_for_handle = any(marker in lowered for marker in ("ник", "логин", "букв", "как пишется"))
        letter_question = any(marker in lowered for marker in (
            "заглавн", "строчн", "больш", "маленьк", "регистр", "латинск", "русск",
            "какая буква", "что за буква", "буква r", "буква h", "буква x",
            "букву r", "букву h", "букву x",
        )) or bool(re.search(r"\b[xhr]\b.*\b(?:какая|какой|что|значит|это)\b", lowered))
        if letter_question:
            answer = MangoCallService._script_objection_reply(text)
            if answer:
                return f"{answer} Удалось найти аккаунт?", "telegram_handle", False
        if MangoCallService._is_open_question(text) and not repeat and (not asks_for_handle or letter_question):
            objection = MangoCallService._script_objection_reply(text)
            if objection and objection not in {MANGO_GENERIC_CLARIFICATION, MANGO_DEEP_ANSWER} and not any(
                marker in lowered for marker in ("телеграм", "телеграмм")
            ):
                return MangoCallService._resume_stage_after_objection(stage, objection), stage, False

        model_reply = (llm_intent or {}).get("short_reply", "")
        model_intent = (llm_intent or {}).get("intent", "")
        if MangoCallService._is_open_question(text) and model_reply and model_intent in {
            "name_question", "company_question", "job_question", "schedule_question", "other_question",
        }:
            return f"{model_reply} {MangoCallService._stage_reprompt(stage)}", stage, False

        if stage == "telegram":
            if repeat or any(marker in lowered for marker in ("никнейм", "логин", "букв")):
                return MANGO_TELEGRAM_HANDLE, "telegram_handle", False
            if MangoCallService._is_affirmative(text) or any(
                marker in lowered for marker in ("сейчас найду", "найду", "могу найти")
            ):
                return MANGO_TELEGRAM_PERMISSION, "telegram_permission", False
            return "Хорошо, остаёмся на линии. Скажите, когда будете готовы найти аккаунт?", "telegram", False

        if stage == "telegram_permission":
            if MangoCallService._is_affirmative(text) or any(
                marker in lowered for marker in ("диктуйте", "говорите", "сейчас можно", "давайте")
            ):
                return MANGO_TELEGRAM_HANDLE, "telegram_handle", False
            return "Хорошо, подожду. Скажите, когда можно продиктовать никнейм?", "telegram_permission", False

        if stage == "telegram_handle":
            found = bool(re.search(r"\b(?:нашёл|нашел|нашла|нашли|нашёлся|нашлась)\b", lowered)) and not bool(
                re.search(r"\bне\s+(?:нашёл|нашел|нашла|нашли|нашёлся|нашлась)\b", lowered)
            )
            if found or MangoCallService._is_affirmative(text):
                return MANGO_TELEGRAM_SEND, "telegram_send", False
            # A plain "нет" means the account was not found yet. Repeat the
            # spelling slowly instead of interpreting it as a refusal to talk.
            if repeat or any(marker in lowered for marker in ("ник", "логин", "букв")):
                return MANGO_TELEGRAM_HANDLE, "telegram_handle", False
            objection = MangoCallService._script_objection_reply(text)
            if objection and not any(marker in lowered for marker in ("телеграм", "никнейм", "ник")):
                return MangoCallService._resume_stage_after_objection(stage, objection), stage, False
            return MANGO_TELEGRAM_HANDLE, "telegram_handle", False

        sent = bool(re.search(
            r"\b(?:отправил|отправила|отправлено|написал|написала|готово|получилось)\b",
            lowered,
        ))
        if sent or MangoCallService._is_affirmative(text):
            candidate["result"] = "qualified"
            return MANGO_FINAL, "finished", True
        return "Подождём, пока вы отправите сообщение. Напишите любое слово и скажите, когда будет готово.", "telegram_send", False

    @staticmethod
    def _script_candidate_reply(
        stage: str,
        transcript: str,
        candidate: dict[str, Any],
        dialogue_history: list[dict[str, str]] | None = None,
        llm_intent: dict[str, str] | None = None,
    ) -> tuple[str, str, bool]:
        """Return the next fixed line, stage, and whether Mango must hang up."""
        text = _normalize_text(transcript)
        intent = (llm_intent or {}).get("intent", "")
        if stage == "zoom" and (
            MangoCallService._is_decline(text)
            or re.search(r"\b(?:не\s+(?:надо|хочу|буду|смогу|готов)|отказываюсь)\b", text.lower())
        ):
            candidate["result"] = "declined_zoom"
            return MANGO_GOODBYE, "finished", True
        if stage == "name_confirm":
            if MangoCallService._is_wrong_recipient(text):
                candidate["name"] = ""
                candidate["result"] = "in_progress"
                return MANGO_ALTERNATE_CANDIDATE_ASK, "alternate_candidate_interest", False
            if (
                MangoCallService._is_affirmative(text)
                or MangoCallService._name_confirmed_by_text(text, str(candidate.get("name", "")))
                or re.search(r"\b(?:слушаю|это я|говорите)\b", text.lower())
            ):
                return MANGO_GREETING_AFTER_NAME, "relevance", False
            return f"Подскажите, пожалуйста, я дозвонилась до {candidate.get('name', 'вас')}?", "name_confirm", False
        if stage == "alternate_candidate_interest":
            if MangoCallService._is_decline(text):
                candidate["result"] = "declined_at_opening"
                return MANGO_GOODBYE, "finished", True
            if MangoCallService._is_affirmative(text):
                return MANGO_ALTERNATE_CANDIDATE_NAME, "alternate_candidate_name", False
            return MANGO_ALTERNATE_CANDIDATE_ASK, "alternate_candidate_interest", False
        if stage == "alternate_candidate_name":
            if MangoCallService._is_decline(text):
                candidate["result"] = "declined_at_opening"
                return MANGO_GOODBYE, "finished", True
            candidate["name"] = text
            return MANGO_GREETING_AFTER_NAME, "relevance", False
        if candidate.get("scheduled_at"):
            requested_minutes = MangoCallService._requested_time_minutes(text)
            try:
                booked_start = datetime.fromisoformat(
                    str(candidate.get("scheduled_at", ""))
                ).astimezone(calendar_service.tz)
                booked_minutes = booked_start.hour * 60 + booked_start.minute
            except (TypeError, ValueError):
                booked_minutes = None
            if MangoCallService._schedule_change_request(text) or (
                requested_minutes is not None and booked_minutes is not None
                and requested_minutes != booked_minutes
            ):
                MangoCallService._cancel_candidate_booking(candidate)
                candidate["result"] = "in_progress"
                candidate["schedule_request"] = text
                if requested_minutes is not None:
                    reply, _ = MangoCallService._schedule_offer_for_candidate(candidate)
                    return reply, "schedule", False
                return "Хорошо, давайте подберём другое время. На какое время вам будет удобно?", "schedule", False
            if MangoCallService._schedule_cancel_request(text):
                MangoCallService._cancel_candidate_booking(candidate)
                candidate["result"] = "declined_scheduled"
                return "Хорошо, отменяю вашу запись. Всего доброго.", "finished", True
        if MangoCallService._schedule_cancel_request(text):
            candidate["result"] = "declined_scheduling" if stage == "schedule" else "declined_by_candidate"
            if stage == "schedule":
                return "Хорошо, отменяю запись. Всего доброго.", "finished", True
            return "Хорошо, завершаю разговор. Всего доброго.", "finished", True
        schedule_status = MangoCallService._schedule_status_reply(text, candidate)
        if stage == "schedule" and MangoCallService._schedule_availability_question(text):
            # This asks for fresh availability, not confirmation of an earlier
            # preference. Clear that preference and read the calendar again.
            candidate["schedule_request"] = ""
            reply, _ = MangoCallService._schedule_offer_for_candidate(candidate)
            return reply, "schedule", False
        if schedule_status:
            return schedule_status, stage, False
        if MangoCallService._is_repeat_request(text) and not MangoCallService._has_specific_objection(text):
            repeated = MangoCallService._repeat_reply_from_history(dialogue_history)
            if repeated:
                return repeated, stage, False
        if stage == "schedule":
            if MangoCallService._schedule_cancel_request(text):
                candidate["result"] = "declined_scheduling"
                candidate["schedule_request"] = ""
                return "Хорошо, отменяю подбор времени. Всего доброго.", "finished", True
            has_day_change = any(marker in text.lower() for marker in ("завтра", "на следующий день", "на следующий", "сегодня не могу", "сегодня не получится", "сегодня не смогу", "сегодня никак"))
            if not has_day_change and any(marker in text.lower() for marker in ("неудобно", "не удобно", "не подойдёт", "не подойдет", "не подходит", "не смогу", "не могу", "нет, тоже")):
                request = str(candidate.get("schedule_request", ""))
                requested_minutes = MangoCallService._requested_time_minutes(text)
                previous_requested_minutes = MangoCallService._requested_time_minutes(request)
                tomorrow_preferred = (
                    candidate.get("schedule_day_preference") == "tomorrow"
                    and "сегодня" not in text.lower()
                )
                if tomorrow_preferred:
                    if requested_minutes is not None:
                        candidate["schedule_request"] = text
                    reply, _ = MangoCallService._schedule_offer_for_candidate(
                        candidate,
                        exclude=set(candidate.get("offered_slots", [])),
                        day=calendar_service.today() + timedelta(days=1),
                    )
                    return reply, "schedule", False
                if requested_minutes is not None:
                    candidate["schedule_request"] = text
                    offered = [str(item) for item in candidate.get("offered_slots", []) if item]
                    offered_minutes = (
                        MangoCallService._slot_minutes(offered[0].split("T", 1)[-1][:5])
                        if offered else None
                    )
                    if offered_minutes == requested_minutes and offered:
                        try:
                            boundary = datetime.fromisoformat(offered[0]).astimezone(calendar_service.tz)
                        except (TypeError, ValueError):
                            boundary = None
                        if boundary:
                            reply, _ = MangoCallService._schedule_offer_for_candidate(
                                candidate,
                                exclude=set(offered),
                                day=boundary.date(),
                                after_start=boundary.isoformat(timespec="minutes"),
                            )
                            return reply, "schedule", False
                    reply, _ = MangoCallService._schedule_offer_for_candidate(
                        candidate,
                        exclude=set(candidate.get("offered_slots", [])),
                    )
                    return reply, "schedule", False
                if previous_requested_minutes is not None:
                    today = calendar_service.today()
                    boundary = datetime.combine(
                        today,
                        datetime.min.time().replace(
                            hour=previous_requested_minutes // 60,
                            minute=previous_requested_minutes % 60,
                        ),
                        calendar_service.tz,
                    )
                    reply, _ = MangoCallService._schedule_offer_for_candidate(
                        candidate,
                        exclude=set(candidate.get("offered_slots", [])),
                        day=today,
                        after_start=boundary.isoformat(timespec="minutes"),
                    )
                    return reply, "schedule", False
                candidate["schedule_request"] = ""
                return MANGO_SCHEDULE_TIME_ASK, "schedule", False
            objection = MangoCallService._script_objection_reply(text)
            if objection and objection not in {MANGO_GENERIC_CLARIFICATION, MANGO_DEEP_ANSWER}:
                generated_answer = (llm_intent or {}).get("short_reply", "")
                if generated_answer and intent in {
                    "name_question", "company_question", "job_question", "schedule_question", "other_question",
                }:
                    objection = generated_answer
                requested_minutes = MangoCallService._requested_time_minutes(text)
                if requested_minutes is not None:
                    candidate["schedule_request"] = text
                    offer_reply, _ = MangoCallService._schedule_offer_for_candidate(
                        candidate,
                        exclude=set(candidate.get("offered_slots", [])),
                    )
                    return f"{objection} {offer_reply}".strip(), "schedule", False
                status = MangoCallService._schedule_status_reply("во сколько", candidate)
                return f"{objection} {status}".strip() if status else objection, "schedule", False
        if stage == "schedule" and MangoCallService._requested_time_minutes(text) is not None:
            # Preserve a newly stated time preference verbatim. LLM slot
            # normalization can turn "можно к шести?" into generic agreement
            # and accidentally book the previously offered time.
            return MangoCallService._schedule_stage_reply(text, candidate)
        if stage in {"telegram", "telegram_permission", "telegram_handle", "telegram_send"}:
            return MangoCallService._telegram_stage_reply(stage, text, candidate, llm_intent)
        # A candidate may accept the Zoom invitation and immediately ask for
        # a time in the same turn (for example: "да, свободно, когда можно").
        # Handle that deterministic transition before the advisory LLM intent;
        # a short model must not turn a scheduling request into a repeat reply.
        if stage == "zoom" and MangoCallService._is_affirmative(text):
            asks_tomorrow = any(
                marker in text.lower()
                for marker in ("завтра", "на следующий день", "на следующий")
            )
            if asks_tomorrow:
                candidate["schedule_request"] = text
                return MangoCallService._schedule_stage_reply(text, candidate)
            if (
                MangoCallService._contains_schedule_request(text)
                or not MangoCallService._is_open_question(text)
            ):
                candidate["schedule_request"] = text
                reply, _ = MangoCallService._schedule_offer_for_candidate(candidate)
                return reply, "schedule", False
        # A candidate can answer the active question and ask a second question
        # in the same breath. Apply the normalized answer first, then answer the
        # interruption and continue with the newly pending stage.
        answer_slot = (llm_intent or {}).get("answer_slot", "")
        normalized_answer = (llm_intent or {}).get("normalized_answer", "")
        if answer_slot == stage and normalized_answer:
            asks_job = MangoCallService._is_job_question(text)
            pre_details_stage = stage in {
                "relevance", "age_city", "computer", "citizenship", "employment",
                "study_format", "study_schedule", "work_details", "conditions_before_details",
                "conditions_resume_age_city", "conditions_resume_computer",
            }
            interruption_reply = MangoCallService._script_objection_reply(text)
            if asks_job and pre_details_stage:
                interruption_reply = MANGO_JOB_LATER
            elif MangoCallService._is_open_question(text) and interruption_reply is None:
                interruption_reply = MANGO_GENERIC_CLARIFICATION
            if interruption_reply in {MANGO_GENERIC_CLARIFICATION, MANGO_DEEP_ANSWER}:
                interruption_reply = (llm_intent or {}).get("short_reply", "") or interruption_reply
            if interruption_reply:
                transition_reply, next_stage, should_hangup = MangoCallService._script_candidate_reply(
                    stage,
                    normalized_answer,
                    candidate,
                    dialogue_history,
                    {},
                )
                if should_hangup:
                    return transition_reply, next_stage, True
                if next_stage != stage:
                    return f"{interruption_reply} {transition_reply}".strip(), next_stage, False
        if answer_slot == stage and normalized_answer:
            # Use the model's concise semantic extraction for field handling;
            # the raw utterance remains in call history and the saved turn log.
            text = normalized_answer
            lowered = _normalize_text(text).lower()
        elif (
            stage not in {"finished", "conditions_followup", "schedule"}
            and MangoCallService._stage_answer_matches(stage, text)
            and MangoCallService._is_open_question(text)
        ):
            # A question can be appended to a complete answer in the same
            # STT chunk. Preserve the fact and answer the interruption even
            # when the local model returns malformed JSON or is unavailable.
            answer_prefix = MangoCallService._candidate_answer_prefix(text)
            if answer_prefix and answer_prefix.lower() != text.lower():
                normalized = MangoCallService._deterministic_stage_answer(stage, answer_prefix)
                question_reply = MangoCallService._script_objection_reply(text)
                if (
                    not question_reply
                    and stage in {
                        "employment", "study_format", "study_schedule", "work_details",
                        "conditions_before_details", "conditions_resume_age_city",
                        "conditions_resume_computer",
                    }
                    and MangoCallService._is_job_question(text)
                ):
                    question_reply = MANGO_JOB_LATER
                if question_reply and normalized:
                    transition_reply, next_stage, should_hangup = MangoCallService._script_candidate_reply(
                        stage,
                        normalized,
                        candidate,
                        dialogue_history,
                        {},
                    )
                    if should_hangup:
                        return transition_reply, next_stage, True
                    if next_stage != stage:
                        return f"{question_reply} {transition_reply}".strip(), next_stage, False
                    return MangoCallService._resume_stage_after_objection(stage, question_reply), stage, False
        if stage in {
            "employment", "study_format", "study_schedule", "work_details",
            "conditions_before_details", "conditions_resume_age_city", "conditions_resume_computer",
        } and MangoCallService._is_job_question(text):
            # Vacancy details are deliberately deferred until the dedicated
            # conditions stage. Never let a question about the job advance the
            # current screening step or inject the full vacancy script early.
            return MangoCallService._resume_stage_after_objection(
                stage,
                MANGO_JOB_LATER,
            ), stage, False
        if intent == "repeat" and not MangoCallService._has_specific_objection(text):
            repeated = MangoCallService._repeat_reply_from_history(dialogue_history)
            if repeated:
                return repeated, stage, False
        if stage == "schedule":
            return MangoCallService._schedule_stage_reply(text, candidate)
        if stage == "conditions_followup":
            candidate["objection"] = text
            candidate["result"] = "declined_conditions"
            return MANGO_GOODBYE, "finished", True
        if stage == "zoom" and MangoCallService._is_decline(text):
            candidate["result"] = "declined_zoom"
            return MANGO_GOODBYE, "finished", True
        if MangoCallService._is_repeat_request(text) and not MangoCallService._has_specific_objection(text):
            # Repeating is a conversational repair, not an answer to the current
            # stage. Use the actual last Jana line so the LLM cannot invent a
            # different question or answer for a short clarification request.
            repeated = MangoCallService._repeat_reply_from_history(dialogue_history)
            if repeated:
                return repeated, stage, False
        # Resolve a clear answer to the study-overlap question before the
        # generic FAQ detector sees the echoed words "в какие часы" or
        # "пересекаться" and routes the turn back to an unrelated stage.
        if stage == "study_schedule" and MangoCallService._study_schedule_answer_is_decisive(text):
            return MangoCallService._study_schedule_stage_reply(text, candidate)
        # The local model is useful for ambiguous answers, but an explicit
        # factual question must win over a misclassified intent. Otherwise a
        # phrase such as "откуда вы звоните?" can be routed to the repeat or
        # current-stage branch and the candidate never gets the actual answer.
        grounded_objection = MangoCallService._script_objection_reply(text)
        model_question_reply = (llm_intent or {}).get("short_reply", "")
        is_targeted_clarification = MangoCallService._is_open_question(text) or (
            MangoCallService._is_repeat_request(text)
            and MangoCallService._has_specific_objection(text)
        )
        if (
            model_question_reply
            and intent in {"name_question", "company_question", "job_question", "schedule_question", "other_question"}
            and is_targeted_clarification
            and not MangoCallService._is_job_question(text)
        ):
            return (
                MangoCallService._resume_stage_after_objection(stage, model_question_reply),
                stage,
                False,
            )
        if grounded_objection and grounded_objection not in {
            MANGO_GENERIC_CLARIFICATION,
            MANGO_DEEP_ANSWER,
        } and not MangoCallService._is_job_question(text) and not (
            stage == "conditions"
            and MangoCallService._has_affirmative_marker(text)
            and not MangoCallService._is_open_question(text)
        ):
            return (
                MangoCallService._resume_stage_after_objection(stage, grounded_objection),
                stage,
                False,
            )
        # The LLM intent is advisory only. Short answers such as "да" or
        # "есть" are not objections, so never let a misclassified intent
        # replay Jana's name/company line or jump to another script section.
        if intent == "decline":
            if stage == "relevance":
                candidate["result"] = "declined_at_opening"
                return MANGO_GOODBYE, "finished", True
            if stage in {"conditions", "conditions_before_details", "conditions_resume_age_city", "conditions_resume_computer"}:
                return MANGO_NOT_SUITABLE, "conditions_followup", False
            if stage == "zoom":
                candidate["result"] = "declined_zoom"
                return MANGO_GOODBYE, "finished", True
        # An unexpected question must never be mistaken for an answer to the
        # current script step. Known objections are answered immediately;
        # unknown ones stay on the same stage until the candidate is heard.
        if not MangoCallService._is_decline(text):
            # Handle questions first, even when the same utterance also
            # contains a vacancy keyword. Otherwise "как вас зовут и покажите
            # вакансию" is misclassified as a stage transition.
            objection = MangoCallService._script_objection_reply(text)
            accepted_conditions = (
                stage == "conditions"
                and MangoCallService._has_affirmative_marker(text)
                and not MangoCallService._is_open_question(text)
            )
            if objection and not MangoCallService._is_job_question(text) and not accepted_conditions:
                return MangoCallService._resume_stage_after_objection(stage, objection), stage, False
            if not MangoCallService._is_job_question(text) and MangoCallService._is_open_question(text):
                return MANGO_GENERIC_CLARIFICATION, stage, False
        # STT can return a fragment of the previous TTS line or an answer to a
        # different question. Keep the state unchanged until the current field
        # is actually answered; this is especially important for the scripted
        # candidate questionnaire.
        if (
            stage not in {"finished", "conditions_followup"}
            and not MangoCallService._is_job_question(text)
            and not MangoCallService._stage_answer_matches(stage, text)
        ):
            return MangoCallService._stage_reprompt(stage), stage, False
        if stage == "relevance":
            if MangoCallService._is_decline(text):
                candidate["result"] = "declined_at_opening"
                return MANGO_GOODBYE, "finished", True
            if MangoCallService._is_job_question(text):
                return MANGO_JOB_LATER, "relevance", False
            if MangoCallService._is_affirmative(text):
                return MANGO_INTERESTED_WITH_AGE, "age_city", False
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("relevance", objection), "relevance", False
            return MANGO_RELEVANCE_REPROMPT, "relevance", False
        if stage == "age_city":
            if MangoCallService._is_job_question(text):
                return MANGO_JOB_LATER, "age_city", False
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("age_city", objection), "age_city", False
            candidate["age_city"] = _extract_candidate_age_city(text) or text
            return MANGO_COMPUTER, "computer", False
        if stage == "computer":
            if MangoCallService._is_job_question(text):
                return MANGO_JOB_LATER, "computer", False
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("computer", objection), "computer", False
            access = _computer_access_status(text)
            if access is None:
                return MANGO_COMPUTER, "computer", False
            candidate["computer"] = "есть" if access else "нет"
            if not access:
                _add_candidate_review_flag(candidate, "нет компьютера или ноутбука")
                candidate["result"] = "declined_no_device"
                return MANGO_REJECT_DEVICE, "finished", True
            return MANGO_CITIZENSHIP, "citizenship", False
        if stage == "citizenship":
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("citizenship", objection), "citizenship", False
            candidate["citizenship"] = text
            return MANGO_EMPLOYMENT, "employment", False
        if stage == "employment":
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("employment", objection), "employment", False
            candidate["employment"] = text
            lowered = text.lower()
            has_study = MangoCallService._candidate_has_study(text)
            has_work = MangoCallService._candidate_has_work(text)
            if has_study:
                if re.search(r"очно\s*[- ]\s*заоч|заочно\s*[- ]\s*очн", lowered):
                    candidate["study_format"] = "очно-заочно"
                    candidate["has_work"] = has_work
                    return MANGO_STUDY_SCHEDULE, "study_schedule", False
                if re.search(r"\bочн\w*|\bдневн\w*", lowered):
                    candidate["study_format"] = "очно"
                    candidate["has_work"] = has_work
                    return MANGO_STUDY_SCHEDULE, "study_schedule", False
                if re.search(r"заочно|дистанцион|вечерн", lowered):
                    candidate["study_format"] = text
                    candidate["has_work"] = has_work
                    return MANGO_STUDY_SCHEDULE, "study_schedule", False
                candidate["study_format"] = ""
                candidate["has_work"] = has_work
                return MANGO_STUDY_FORMAT, "study_format", False
            if has_work:
                return MANGO_WORK_DETAILS, "work_details", False
            if candidate.get("conditions_spoken"):
                return MANGO_ZOOM, "zoom", False
            candidate["conditions_spoken"] = True
            return MANGO_JOB_INTRO, "conditions", False
        if stage == "study_format":
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("study_format", objection), "study_format", False
            candidate["study_format"] = text
            lowered = text.lower()
            if re.search(r"очно\s*[- ]\s*заоч|заочно\s*[- ]\s*очн", lowered):
                candidate["study_format"] = "очно-заочно"
            elif re.search(r"\bочн\w*|\bдневн\w*", lowered):
                candidate["study_format"] = "очно"
            elif re.search(r"\bзаоч\w*|дистанцион|вечерн|онлайн", lowered):
                candidate["study_format"] = "заочно"
            # Every study format is checked before the vacancy conditions.
            # This keeps the overlap decision in its own stage and prevents
            # it from reappearing after the work schedule was read aloud.
            return MANGO_STUDY_SCHEDULE, "study_schedule", False
        if stage == "study_schedule":
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("study_schedule", objection), "study_schedule", False
            return MangoCallService._study_schedule_stage_reply(text, candidate)
        if stage == "work_details":
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("work_details", objection), "work_details", False
            candidate["work_details"] = text
            if MangoCallService._requires_notice(text):
                _add_candidate_review_flag(candidate, "требуется обязательная отработка")
                candidate["result"] = "declined_notice"
                return MANGO_REJECT_NOTICE, "finished", True
            if candidate.get("conditions_spoken"):
                return MANGO_ZOOM, "zoom", False
            candidate["conditions_spoken"] = True
            return MANGO_JOB_INTRO, "conditions", False
        if stage == "conditions_before_details":
            if MangoCallService._is_decline(text):
                return MANGO_NOT_SUITABLE, "conditions_followup", False
            if MangoCallService._is_job_question(text):
                return MANGO_JOB_LATER, "conditions_before_details", False
            wants_conditions = MangoCallService._has_affirmative_marker(text) or any(
                marker in text.lower()
                for marker in ("расскаж", "подроб", "услов", "график", "зарплат", "трудоустр")
            )
            objection = MangoCallService._script_objection_reply(text)
            if objection and not wants_conditions:
                return MangoCallService._resume_stage_after_objection("conditions_before_details", objection), "conditions_before_details", False
            candidate["conditions_spoken"] = True
            return MANGO_JOB_CONDITIONS, "conditions", False
        if stage == "conditions_resume_age_city":
            if MangoCallService._is_decline(text):
                return MANGO_NOT_SUITABLE, "conditions_followup", False
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("conditions_resume_age_city", objection), "conditions_resume_age_city", False
            reply, next_stage = MangoCallService._next_unfinished_candidate_step(candidate)
            return reply, next_stage, False
        if stage == "conditions_resume_computer":
            if MangoCallService._is_decline(text):
                return MANGO_NOT_SUITABLE, "conditions_followup", False
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("conditions_resume_computer", objection), "conditions_resume_computer", False
            if MangoCallService._has_affirmative_marker(text):
                return MANGO_COMPUTER, "computer", False
            return MANGO_COMPUTER, "computer", False
        if stage == "conditions":
            if MangoCallService._is_decline(text):
                return MANGO_NOT_SUITABLE, "conditions_followup", False
            if MangoCallService._is_job_question(text):
                if MangoCallService._has_affirmative_marker(text) and not MangoCallService._is_open_question(text):
                    reply, next_stage = MangoCallService._next_unfinished_candidate_step(candidate)
                    return reply, next_stage, False
                return MANGO_JOB_CONDITIONS, "conditions", False
            # An accepted offer must advance before the FAQ detector sees the
            # word "условия" as a new request to hear the vacancy again.
            if MangoCallService._has_affirmative_marker(text) and not MangoCallService._is_open_question(text):
                pending_reply, pending_stage = MangoCallService._next_unfinished_candidate_step(candidate)
                if pending_stage in {
                    "age_city", "computer", "citizenship", "employment",
                    "study_format", "study_schedule", "work_details",
                }:
                    return pending_reply, pending_stage, False
                reply, next_stage = MangoCallService._next_unfinished_candidate_step(candidate)
                return reply, next_stage, False
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("conditions", objection), "conditions", False
            # Never let a stale/partial state read the vacancy conditions
            # before the screening questionnaire is complete. This is also a
            # recovery path for calls resumed from an older saved record.
            pending_reply, pending_stage = MangoCallService._next_unfinished_candidate_step(candidate)
            if pending_stage in {
                "age_city", "computer", "citizenship", "employment",
                "study_format", "study_schedule", "work_details",
            }:
                return pending_reply, pending_stage, False
            # The candidate may accept the conditions and name a time in the
            # same sentence. Move directly to scheduling instead of asking
            # the Zoom question and making them repeat the request.
            if MangoCallService._contains_schedule_request(text):
                candidate["schedule_request"] = text
                reply, _ = MangoCallService._schedule_offer_for_candidate(candidate)
                return reply, "schedule", False
            # A loopback transcript can contain the previous job description
            # followed by the candidate's "да". The affirmative tail wins.
            if MangoCallService._has_affirmative_marker(text):
                reply, next_stage = MangoCallService._next_unfinished_candidate_step(candidate)
                return reply, next_stage, False
            return MANGO_JOB_CONDITIONS, "conditions", False
        if stage == "conditions_followup":
            candidate["objection"] = text
            candidate["result"] = "declined_conditions"
            return MANGO_GOODBYE, "finished", True
        if stage == "zoom":
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return MangoCallService._resume_stage_after_objection("zoom", objection), "zoom", False
            if MangoCallService._is_affirmative(text):
                reply, _ = MangoCallService._schedule_offer_for_candidate(candidate)
                return reply, "schedule", False
            if MangoCallService._is_decline(text):
                candidate["result"] = "declined_zoom"
                return MANGO_GOODBYE, "finished", True
            return MANGO_ZOOM, "zoom", False
        if stage == "telegram":
            objection = MangoCallService._script_objection_reply(text)
            if objection:
                return objection, "telegram", False
            if MangoCallService._is_decline(text):
                candidate["result"] = "declined_telegram"
                return MANGO_GOODBYE, "finished", True
            candidate["result"] = "qualified"
            return MANGO_FINAL, "finished", True
        return MANGO_RELEVANCE_REPROMPT, "relevance", False

    def _classify_candidate_intent(
        self,
        stage: str,
        transcript: str,
        dialogue_history: list[dict[str, str]],
        config: dict[str, Any],
    ) -> dict[str, str]:
        """Resolve non-standard answers and mixed answer/question turns with the selected LLM."""
        base_url = _normalize_text(str(config.get("llm_base_url", DEFAULT_LLM_BASE_URL))).rstrip("/")
        api_key = _normalize_text(str(config.get("llm_api_key", "")))
        model = _normalize_text(str(config.get("llm_model", DEFAULT_LLM_MODEL)))
        if not base_url or (base_url != LOCAL_LLM_BASE_URL and not api_key):
            return {}
        stage_answer_matches = self._stage_answer_matches(stage, transcript)
        is_compound = stage_answer_matches and (
            self._is_open_question(transcript)
            or self._has_specific_objection(transcript)
            or self._is_job_question(transcript)
        )
        # Every candidate turn goes through exactly the selected provider. The
        # deterministic script still overrides model output for clear answers.
        recent_history = self._compact_dialogue_history(dialogue_history)
        prompt = (
            f"[ТЕКУЩИЙ ЭТАП]: {stage}\n"
            f"[ТЕКУЩИЙ ВОПРОС]: {self._stage_reprompt(stage)}\n"
            f"[ПОСЛЕДНЯЯ РЕПЛИКА СОБЕСЕДНИКА]: {transcript}\n"
            "Разбери последнюю реплику относительно текущего вопроса и истории выше. Если кандидат "
            "ответил и задал встречный вопрос, одновременно сохрани ответ и подготовь короткий ответ. "
            "На уточнение конкретного факта (например, только средней зарплаты) отвечай только по нему, "
            "не перечитывай описание вакансии целиком. После ответа вернись к незавершённому этапу "
            "коротким вопросом. Не считай вопрос ответом и не теряй отрицания. Если человек задаёт "
            "вопрос, возражает, не хочет сообщать личные данные или отвечает нестандартно, обязательно "
            "заполни short_reply одной естественной фразой: ответь по существу, не дави и мягко вернись "
            "к текущему этапу. Пустым оставь short_reply только для простого ясного ответа на вопрос этапа."
        )
        try:
            response = llm_service.chat(
                base_url=base_url,
                api_key=api_key,
                model=model,
                user_text=prompt,
                system_prompt=MANGO_INTENT_SYSTEM_PROMPT,
                temperature=0.15,
                use_vpn=bool(config.get("use_vpn_llm", False)),
                thinking=False,
                history=recent_history,
                max_tokens=LOCAL_LLM_INTENT_MAX_TOKENS,
                request_timeout=8,
            )
        except Exception as exc:  # noqa: BLE001
            logging.info("Candidate intent classification unavailable; using deterministic fallback: %s", exc)
            return {}
        raw = _repair_mojibake(str(response.get("text", ""))).strip()
        raw = re.sub(r"```(?:json)?|```", "", raw, flags=re.IGNORECASE).strip()
        try:
            json_start = raw.index("{")
            parsed, _end = json.JSONDecoder().raw_decode(raw[json_start:])
        except (ValueError, json.JSONDecodeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        intent = _normalize_text(str(parsed.get("intent", ""))).lower()
        allowed = {
            "repeat", "name_question", "company_question", "job_question",
            "schedule_question", "other_question", "answer", "decline", "resistance", "unclear",
        }
        if intent not in allowed:
            return {}
        result = {"intent": intent, "classified": "1"}
        answer_slot = _normalize_text(str(parsed.get("answer_slot", ""))).lower()
        valid_slots = {
            "relevance", "age_city", "computer", "citizenship", "employment",
            "study_format", "study_schedule", "work_details", "conditions",
            "conditions_before_details", "conditions_resume_age_city",
            "conditions_resume_computer", "conditions_followup", "zoom", "telegram", "schedule",
        }
        normalized_answer = _normalize_text(str(parsed.get("normalized_answer", "")))
        if stage == "employment":
            lowered_transcript = _normalize_text(transcript).lower()
            mentions_study = bool(re.search(r"уч[её]б|учусь|университет|колледж|студент", lowered_transcript))
            mentions_work = bool(re.search(r"работ|занят|трудоустро|служб", lowered_transcript))
            employment_facts = []
            if mentions_study:
                employment_facts.append(
                    f"учёба: {'есть' if self._candidate_has_study(transcript) else 'нет'}"
                )
            if mentions_work:
                employment_facts.append(
                    f"работа: {'есть' if self._candidate_has_work(transcript) else 'нет'}"
                )
            if employment_facts:
                normalized_answer = "; ".join(employment_facts)
        if answer_slot in valid_slots and normalized_answer and len(normalized_answer) <= 180:
            result["answer_slot"] = answer_slot
            result["normalized_answer"] = normalized_answer
        short_reply = _normalize_text(str(parsed.get("short_reply", "")))
        short_reply = re.sub(r"<think>.*?</think>", "", short_reply, flags=re.IGNORECASE | re.DOTALL)
        short_reply = re.sub(r"^(?:ответ|реплика)\s*:\s*", "", short_reply, flags=re.IGNORECASE)
        short_reply = re.sub(r"\s+", " ", short_reply).strip(" \"'«»")
        if short_reply and short_reply.lower() in _normalize_text(transcript).lower():
            short_reply = ""
        if (
            short_reply
            and len(short_reply) <= 360
            and not short_reply.startswith("{")
            and not re.search(r"[{}<>]", short_reply)
        ):
            result["short_reply"] = short_reply
        if self._is_open_question(transcript) and intent in {"answer", "unclear"}:
            result["intent"] = "other_question"
        if self._is_open_question(transcript) and not result.get("short_reply"):
            result["short_reply"] = "Подробности могу рассказать на собеседовании."
        if stage_answer_matches and not is_compound:
            # The selected model observes every turn, but clear stage answers
            # keep deterministic, fact-checked routing.
            result = {
                "intent": "answer",
                "answer_slot": stage,
                "normalized_answer": self._deterministic_stage_answer(stage, transcript),
                "classified": "1",
            }
        return result

    @staticmethod
    def _dynamic_reply_needed(stage: str, transcript: str, fixed_reply: str) -> bool:
        """Use the LLM for off-script language at every stage, never for state decisions."""
        # A repeat request is handled from the verified dialogue history. Sending
        # it to a small model makes it answer the stage instead of repeating the
        # line the candidate actually asked to hear again.
        if MangoCallService._is_repeat_request(transcript):
            return False
        # Known FAQ answers are already grounded in the vacancy facts. Letting
        # the small local model rewrite them is what caused replies such as a
        # name question turning back into the relevance prompt.
        grounded_reply = MangoCallService._script_objection_reply(transcript)
        if (
            grounded_reply
            and grounded_reply not in {MANGO_GENERIC_CLARIFICATION, MANGO_DEEP_ANSWER}
        ) or MangoCallService._is_job_question(transcript):
            return False
        if fixed_reply in {MANGO_GENERIC_CLARIFICATION, MANGO_DEEP_ANSWER}:
            return True
        # Keep already-grounded replies and stage transitions deterministic.
        # Re-asking the model to rewrite every known answer added latency and
        # let the small local model replace correct replies with unrelated or
        # malformed text. Use it only where the scripted layer has no answer.
        if MangoCallService._is_open_question(transcript) or MangoCallService._is_job_question(transcript):
            return (
                fixed_reply in {MANGO_GENERIC_CLARIFICATION, MANGO_DEEP_ANSWER}
                and not MangoCallService._is_decline(transcript)
            )
        if stage == "relevance":
            return fixed_reply == MANGO_RELEVANCE_REPROMPT
        if stage == "conditions":
            return (
                fixed_reply == MANGO_JOB_DESCRIPTION
                and not MangoCallService._is_job_question(transcript)
                and not MangoCallService._is_affirmative(transcript)
                and not MangoCallService._is_decline(transcript)
            )
        if stage == "zoom":
            return fixed_reply == MANGO_ZOOM and not (
                MangoCallService._is_affirmative(transcript)
                or MangoCallService._is_decline(transcript)
                or MangoCallService._script_objection_reply(transcript)
            )
        return False

    @staticmethod
    def _compact_dialogue_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
        """Keep the opening and latest turns inside the local model context window."""
        cleaned = [
            {"role": str(item.get("role", "")), "text": _normalize_text(str(item.get("text", "")))}
            for item in history
            if isinstance(item, dict) and _normalize_text(str(item.get("text", "")))
        ]
        # Keep phone prompts compact so llama.cpp spends less time processing
        # old turns while retaining the opening and the latest context.
        max_chars = 6000
        total = sum(len(item["text"]) for item in cleaned)
        if total <= max_chars:
            return cleaned
        opening = cleaned[:1]
        tail: list[dict[str, str]] = []
        used = sum(len(item["text"]) for item in opening)
        for item in reversed(cleaned[1:]):
            if used + len(item["text"]) > max_chars:
                break
            tail.append(item)
            used += len(item["text"])
        return opening + list(reversed(tail))

    def _dynamic_candidate_reply(
        self,
        stage: str,
        transcript: str,
        fixed_reply: str,
        candidate: dict[str, Any],
        dialogue_history: list[dict[str, str]],
        config: dict[str, Any],
    ) -> str:
        """Ask the configured LLM for a natural off-script clarification.

        The returned text can change only the spoken wording. The deterministic
        state transition calculated by _script_candidate_reply remains in force.
        """
        if not self._dynamic_reply_needed(stage, transcript, fixed_reply):
            return ""
        base_url = _normalize_text(str(config.get("llm_base_url", DEFAULT_LLM_BASE_URL))).rstrip("/")
        api_key = _normalize_text(str(config.get("llm_api_key", "")))
        model = _normalize_text(str(config.get("llm_model", DEFAULT_LLM_MODEL)))
        if not base_url or (base_url != LOCAL_LLM_BASE_URL and not api_key):
            return ""

        compact_candidate = {
            key: value
            for key, value in candidate.items()
            if key in {
                "age_city", "computer", "citizenship", "employment",
                "study_format", "study_schedule", "work_details", "objection", "stage", "result",
                "review_flags",
            }
            and value
        }
        user_text = (
            f"[ТЕКУЩИЙ ЭТАП ИИ-АССИСТЕНТА]: {stage}.\n"
            f"[НЕЗАВЕРШЁННЫЙ ВОПРОС ИИ-АССИСТЕНТА]: {self._stage_reprompt(stage)}\n"
            f"[ПОСЛЕДНЯЯ РЕПЛИКА СОБЕСЕДНИКА]: {transcript}\n"
            f"[УЖЕ СОБРАННЫЕ ДАННЫЕ КАНДИДАТА]: {json.dumps(compact_candidate, ensure_ascii=False)}\n"
            f"[ФАКТИЧЕСКАЯ ЗАГОТОВКА ДЛЯ ОРИЕНТИРА]: {fixed_reply}\n"
            "Ответь только на [ПОСЛЕДНЮЮ РЕПЛИКУ СОБЕСЕДНИКА]. Не зачитывай вакансию целиком и "
            "не повторяй весь сценарий. Если это вопрос, дай краткий ответ по существу и "
            "одной фразой вернись к незавершённому вопросу текущего этапа. Если реплика не "
            "отвечает на этот вопрос, не переходи дальше и попроси ответить именно на него."
        )
        try:
            response = llm_service.chat(
                base_url=base_url,
                api_key=api_key,
                model=model,
                user_text=user_text,
                system_prompt=MANGO_DYNAMIC_SYSTEM_PROMPT,
                temperature=min(0.55, max(0.1, float(config.get("temperature", 0.4)))),
                use_vpn=bool(config.get("use_vpn_llm", False)),
                # Phone replies must be immediate; long reasoning is useful in
                # the general chat but makes a live call wait unnecessarily.
                thinking=False,
                history=self._compact_dialogue_history(dialogue_history),
                max_tokens=LOCAL_LLM_CALL_MAX_TOKENS,
                request_timeout=12,
            )
        except Exception as exc:  # noqa: BLE001
            logging.warning("Dynamic Mango reply failed; using fixed reply: %s", exc)
            return ""

        reply = _repair_mojibake(str(response.get("text", ""))).strip()
        reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.IGNORECASE | re.DOTALL).strip()
        reply = re.sub(r"```(?:text|русский)?|```", "", reply, flags=re.IGNORECASE).strip()
        reply = re.sub(r"\[(?:ЗАВЕРШИТЬ_ЗВОНОК|HANGUP|.*?)]", "", reply, flags=re.IGNORECASE).strip()
        reply = re.sub(r"\s+", " ", reply)
        if not reply or len(reply) > 600:
            return ""
        # Reject leaked JSON/markup and broken token fragments before they
        # reach TTS. The fixed, fact-checked reply remains the fallback.
        if re.search(r"[{}<>]", reply) or re.search(r"\w[,;:]\w", reply):
            return ""
        normalized_reply = re.sub(r"[^\wа-яё+ ]+", " ", reply.lower()).strip()
        normalized_transcript = re.sub(r"[^\wа-яё+ ]+", " ", transcript.lower()).strip()
        # Small local models occasionally return the candidate's question or a
        # JSON wrapper instead of an answer. Keep the grounded fixed fallback
        # in that case; echoing a question aloud makes the dialogue look broken.
        if normalized_reply == normalized_transcript or normalized_reply.startswith("response "):
            return ""
        if any(marker in normalized_reply for marker in (
            "текущего этапа", "незавершённого вопроса", "незавершенного вопроса",
            "последней реплике кандидата", "последнюю реплику кандидата",
            "вернись к", "системный промпт", "служебный маркер",
        )):
            return ""
        # A small model can answer from the candidate's point of view or leak an
        # English instruction into the spoken line. Never send those artifacts
        # to TTS; the grounded script reply is safer in that case.
        if re.search(
            r"(?:работа\s+для\s+меня|для\s+меня\s+актуальн|я\s+(?:согласен|согласна|рассматриваю|готов|готова)|"
            r"пожалуйста[,.]?\s*повтор(?:ите|ить)|\bplease\b)",
            normalized_reply,
            flags=re.IGNORECASE,
        ):
            return ""
        reply_tokens = set(normalized_reply.split())
        transcript_tokens = set(normalized_transcript.split())
        if len(reply_tokens) >= 4 and len(reply_tokens & transcript_tokens) >= max(4, int(len(reply_tokens) * 0.8)):
            return ""
        return reply

    @staticmethod
    def _conversation_input(history: list[dict[str, str]], transcript: str) -> str:
        context = "\n".join(
            f"{_llm_history_label(item.get('role'))}: {item['text']}"
            for item in history
            if item.get("text")
        )
        # Keep the complete in-memory call history, but stay inside the local
        # model context window when a very long call produces more text than it
        # can accept in one request.
        max_chars = 12000
        if len(context) > max_chars:
            context = "… начало разговора сокращено из-за лимита контекста …\n" + context[-max_chars:]
        if not context:
            return transcript
        return (
            "Полная история текущего звонка (это один разговор, не новый запрос):\n"
            f"{context}\n\n"
            "Новая реплика собеседника:\n"
            f"{transcript}\n\n"
            "Продолжи разговор строго со следующего шага сценария. Не повторяй уже сказанное."
        )

    @staticmethod
    def _autoanswer_match(transcript: str) -> str:
        normalized = re.sub(r"\s+", " ", _normalize_text(transcript).lower()).strip()
        if not normalized:
            return ""
        if "[beep]" in normalized or "[сигнал]" in normalized:
            return "сигнал автоответчика"
        unavailable = r"(?:недоступ\w*|вне\s+зон\w*|не\s+(?:находится\s+)?в\s+сет\w*|выключ\w*|отключ\w*|не\s+может\s+ответ\w*)"
        subject = r"(?:абонент\w*|номер\w*|телефон\w*)"
        if (
            re.search(rf"{subject}.{{0,80}}{unavailable}", normalized)
            or re.search(rf"{unavailable}.{{0,80}}{subject}", normalized)
        ):
            return "сетевое сообщение: абонент недоступен"
        for phrase in AUTOANSWER_PHRASES:
            if phrase in normalized:
                return phrase
        # Some modern voicemail assistants do not say the classic "leave a
        # message" phrase. They produce a long, generic monologue instead.
        # Require several independent markers so a normal "алло, слушаю" is
        # never mistaken for an answering machine.
        marker_hits = [marker for marker in AUTOANSWER_SOFT_MARKERS if marker in normalized]
        if len(marker_hits) >= 2 and len(normalized.split()) >= 8:
            return f"характерная речь автоответчика ({', '.join(marker_hits[:2])})"
        return ""

    @staticmethod
    def _is_greeting_only(transcript: str) -> bool:
        """Do not treat a simple human hello as an answer to the first stage."""
        words = re.findall(r"[а-яёa-z]+", _normalize_text(transcript).lower())
        if not words or len(words) > 10:
            return False
        greeting_words = {
            "алло", "здравствуйте", "здравствуй", "привет", "добрый", "день",
            "вечер", "утро", "слушаю", "да", "говорите", "угу", "ага",
        }
        return all(word in greeting_words for word in words)

    def _screen_remote_answer(self, config: dict[str, Any]) -> tuple[str, str, bool]:
        """Listen to the first remote phrase and detect explicit voicemail/IVR text."""
        screening_started = time.perf_counter()
        try:
            transcripts: list[str] = []
            for attempt in range(5):
                capture_started = time.perf_counter()
                sample = self.audio.capture_speech(
                    max_seconds=2.8,
                    requested=str(config.get("loopback_device", "")),
                    silence_seconds=0.55,
                    vad_threshold=0.74,
                    min_speech_seconds=0.22,
                    stop_event=self._stop,
                )
                logging.info(
                    "Remote-answer VAD window %d: %.2fs, speech=%s",
                    attempt + 1,
                    time.perf_counter() - capture_started,
                    bool(sample),
                )
                if not sample:
                    continue
                stt_started = time.perf_counter()
                transcript = self._transcribe_chunk(sample, config)
                logging.info("Remote-answer STT: %.2fs, text=%r", time.perf_counter() - stt_started, transcript[:160])
                if transcript:
                    transcripts.append(transcript)
                combined = _normalize_text(" ".join(transcripts))
                reason = self._autoanswer_match(combined)
                if reason:
                    logging.info("Remote answer classified as autoanswer in %.2fs: %s", time.perf_counter() - screening_started, reason)
                    return combined, reason, False
                # A single soft marker is enough to justify one short follow-up
                # capture; this catches assistants that pause between phrases.
                soft_hits = sum(marker in combined.lower() for marker in AUTOANSWER_SOFT_MARKERS)
                if soft_hits == 0:
                    break
            combined = _normalize_text(" ".join(transcripts))
            logging.info(
                "Remote-answer screening completed in %.2fs; speech transcript=%s",
                time.perf_counter() - screening_started,
                bool(combined),
            )
            return combined, self._autoanswer_match(combined), False
        except Exception as exc:  # noqa: BLE001
            # Screening is a guard, not a reason to lose a real call when the
            # selected STT provider is temporarily unavailable.
            logging.warning("Autoanswer screening unavailable; continuing call: %s", exc)
            return "", "", True

    def _run(self, number: str, config: dict[str, Any]) -> None:
        talker = None
        ringback_stop = Event()
        ringback_thread: Thread | None = None
        candidate = _new_candidate_record(number, str(config.get("candidate_name", "")))
        stage = "name_confirm" if candidate.get("name") else "relevance"
        output_device = str(config.get("output_device", ""))
        language = str(config.get("tts_language", DEFAULT_TTS_LANGUAGE))
        speaker = str(config.get("tts_speaker", ""))
        pace = float(config.get("pace", 1.0))
        greeting = _candidate_greeting(str(candidate.get("name", "")))
        greeting_audio: dict[str, bytes] = {}
        greeting_ready = Event()

        def prepare_greeting() -> None:
            try:
                greeting_audio["wav"] = silero_tts_service.synthesize_script(
                    greeting, language, pace, speaker=speaker,
                )
                greeting_audio["hearing_check_wav"] = silero_tts_service.synthesize_script(
                    MANGO_HEARING_CHECK_TEXT, language, pace, speaker=speaker,
                )
            except Exception:
                logging.exception("Could not prepare the opening greeting audio")
            finally:
                greeting_ready.set()

        Thread(target=prepare_greeting, name="mango-greeting-prepare", daemon=True).start()
        try:
            self._update(state="connecting", message="Открываю управление Mango Talker…")
            talker = self._get_talker()
            talker.open_keypad()
            self._update(state="dialing", message=f"Набираю номер {number}…")
            talker.dial_digits(number)
            talker.click_call()
            ringback_last_tone = [0.0]

            def note_ringback(detected_at: float) -> None:
                previous = ringback_last_tone[0]
                ringback_last_tone[0] = detected_at
                if detected_at - previous > 6.5:
                    self._update(state="dialing", message="Слышу гудки дозвона в Mango. Жду ответа…")

            ringback_thread = Thread(
                target=self.audio.monitor_ringback,
                args=(
                    str(config.get("loopback_device", "")),
                    ringback_stop,
                    note_ringback,
                ),
                name="mango-ringback-monitor",
                daemon=True,
            )
            ringback_thread.start()
            connection = talker.wait_for_connection(
                float(config.get("call_timeout", 60)),
                ringback_recent=lambda: time.monotonic() - ringback_last_tone[0] <= 6.5,
            )
            ringback_stop.set()
            ringback_thread.join(timeout=1.5)
            ringback_thread = None
            if connection != "connected":
                call_screen_text = talker.visible_text()
                candidate["result"] = "call_busy" if re.search(r"\bзанято\b", call_screen_text.lower()) else "call_no_answer"
                candidate["autoanswer_text"] = call_screen_text
                _refresh_candidate_report(candidate)
                self._update(
                    state="stopping",
                    transcript=call_screen_text,
                    candidate=dict(candidate),
                    message=(
                        "Линия занята. Завершаю вызов…"
                        if candidate["result"] == "call_busy"
                        else "Не дождался ответа в Mango. Завершаю вызов…"
                    ),
                )
                try:
                    talker.hang_up()
                except Exception as exc:  # noqa: BLE001
                    logging.info("Mango call already ended before cleanup: %s", exc)
                return
            self._connected = True
            self._update(connectedAt=time.time(), remoteAnswered=True, callElapsedSeconds=0.0)
            Thread(
                target=self._watch_remote_hangup,
                args=(talker,),
                name="mango-remote-hangup-watch",
                daemon=True,
            ).start()
            loopback_device = str(config.get("loopback_device", ""))
            logging.info(
                "Mango audio route: TTS output=%r, STT loopback=%r",
                output_device or "default",
                loopback_device or "default",
            )
            # Speak as soon as Mango confirms connection; voicemail/network
            # announcements are detected by the live transcript loop below.
            greeting_ready.wait(timeout=0.2)
            if not greeting_audio.get("wav"):
                greeting_ready.wait(timeout=30.0)
            greeting_wav = greeting_audio.get("wav")
            if not greeting_wav:
                raise RuntimeError("Не удалось подготовить аудио приветствия.")
            self._update(reply=greeting, state="speaking", message="Яна произносит приветствие…")
            self.audio.play_wav(greeting_wav, output_device)
            self._update(state="connected", message="Приветствие передано. Слушаю собеседника…")

            pending_chunk = b""
            pending_transcript = ""
            dialogue_history: list[dict[str, str]] = [
                {"role": "Яна", "text": greeting},
            ]
            max_utterance_seconds = max(5.0, min(float(config.get("listen_seconds", 60.0)), 60.0))
            last_response_at = time.monotonic()
            off_topic_turns = 0
            resistance_turns = 0
            hearing_check_sent = False
            while not self._stop.is_set():
                response_timeout = (
                    MANGO_HEARING_CHECK_TIMEOUT_SECONDS
                    if hearing_check_sent
                    else MANGO_NO_RESPONSE_TIMEOUT_SECONDS
                )
                if time.monotonic() - last_response_at >= response_timeout:
                    if not hearing_check_sent:
                        hearing_check_wav = greeting_audio.get("hearing_check_wav")
                        if not hearing_check_wav:
                            hearing_check_wav = silero_tts_service.synthesize_script(
                                MANGO_HEARING_CHECK_TEXT, language, pace, speaker=speaker,
                            )
                        self._update(
                            reply=MANGO_HEARING_CHECK_TEXT,
                            state="speaking",
                            message="Собеседник молчит. Один раз проверяю связь…",
                        )
                        self.audio.play_wav(hearing_check_wav, output_device)
                        dialogue_history.append({"role": "Яна", "text": MANGO_HEARING_CHECK_TEXT})
                        hearing_check_sent = True
                        last_response_at = time.monotonic()
                        continue
                    candidate["result"] = "no_response"
                    candidate["stage"] = stage
                    _refresh_candidate_report(candidate)
                    self._update(
                        state="stopping",
                        candidate=dict(candidate),
                        message="После проверки связи ответа нет. Завершаю звонок…",
                    )
                    self._local_hangup.set()
                    talker.hang_up()
                    self._connected = False
                    break
                if pending_transcript:
                    transcript = pending_transcript
                    pending_transcript = ""
                    chunk = b""
                elif pending_chunk:
                    chunk = pending_chunk
                    pending_chunk = b""
                    transcript = ""
                else:
                    self._update(state="connected", message="Слушаю собеседника до паузы…")
                    silence_abort = Event()
                    response_timeout = (
                        MANGO_HEARING_CHECK_TIMEOUT_SECONDS
                        if hearing_check_sent
                        else MANGO_NO_RESPONSE_TIMEOUT_SECONDS
                    )
                    silence_timer = Timer(response_timeout, silence_abort.set)
                    silence_timer.start()
                    try:
                        chunk = self.audio.capture_speech(
                            max_seconds=max_utterance_seconds,
                            requested=str(config.get("loopback_device", "")),
                            silence_seconds=MANGO_INTERRUPT_SILENCE_SECONDS,
                            stop_event=self._stop,
                            stop_before_speech_event=silence_abort,
                        )
                    finally:
                        silence_timer.cancel()
                    transcript = ""
                if not chunk and not transcript:
                    if self._stop.is_set():
                        break
                    continue
                if not transcript:
                    self._update(state="transcribing", message="Распознаю речь собеседника…")
                    stt_started = time.perf_counter()
                    transcript = self._transcribe_chunk(chunk, config)
                    logging.info("Candidate STT completed in %.2fs", time.perf_counter() - stt_started)
                if not transcript:
                    continue
                last_assistant_text = ""
                if dialogue_history and _is_assistant_history_role(dialogue_history[-1].get("role")):
                    last_assistant_text = dialogue_history[-1].get("text", "")
                cleaned_transcript = self._strip_audio_echo(transcript, last_assistant_text)
                if not cleaned_transcript:
                    logging.info("Ignoring loopback echo of Jana's last script line: %r", transcript[:160])
                    self._update(state="connected", message="Отфильтровал эхо своей реплики. Слушаю кандидата…")
                    continue
                if cleaned_transcript != _normalize_text(transcript):
                    logging.info("Removed Jana loopback prefix; candidate tail: %r", cleaned_transcript[:160])
                transcript = cleaned_transcript
                last_response_at = time.monotonic()
                hearing_check_sent = False
                automated_reason = self._autoanswer_match(transcript)
                if automated_reason:
                    is_network_notice = automated_reason.startswith("сетевое сообщение:")
                    candidate["result"] = "no_human_answer" if is_network_notice else "autoanswer_detected"
                    candidate["autoanswer_text"] = transcript
                    candidate["stage"] = stage
                    _refresh_candidate_report(candidate)
                    self._update(
                        state="stopping",
                        transcript=transcript,
                        candidate=dict(candidate),
                        message=f"Похоже на автоматическое сообщение ({automated_reason}). Завершаю звонок…",
                    )
                    self._local_hangup.set()
                    talker.hang_up()
                    self._connected = False
                    break
                _record_candidate_turn(candidate, stage, transcript)
                self._update(transcript=transcript, candidate=dict(candidate), script_stage=stage)
                self._update(state="thinking", message="Понимаю смысл реплики собеседника…")
                intent_started = time.perf_counter()
                llm_intent = self._classify_candidate_intent(
                    stage,
                    transcript,
                    dialogue_history,
                    config,
                )
                provider_label = (
                    "локальная Qwen3"
                    if _normalize_text(str(config.get("llm_base_url", DEFAULT_LLM_BASE_URL))).rstrip("/") == LOCAL_LLM_BASE_URL
                    else "выбранная OpenAI-compatible модель"
                )
                logging.info(
                    "%s intent analysis completed in %.2fs",
                    provider_label,
                    time.perf_counter() - intent_started,
                )
                stage_answer_matches = self._stage_answer_matches(stage, transcript)
                if (
                    llm_intent.get("intent") == "unclear"
                    and not stage_answer_matches
                    and not self._is_open_question(transcript)
                    and not self._is_decline(transcript)
                    and not llm_intent.get("short_reply")
                ):
                    off_topic_turns += 1
                else:
                    off_topic_turns = 0
                if off_topic_turns >= 2:
                    candidate["result"] = "autoanswer_detected"
                    candidate["autoanswer_text"] = transcript
                    candidate["stage"] = stage
                    _refresh_candidate_report(candidate)
                    self._update(
                        state="stopping",
                        candidate=dict(candidate),
                        message="Несколько реплик не относятся к вопросу и похожи на автоответчик. Завершаю звонок…",
                    )
                    self._local_hangup.set()
                    talker.hang_up()
                    self._connected = False
                    break
                reply, next_stage, should_hangup = self._script_candidate_reply(
                    stage,
                    transcript,
                    candidate,
                    dialogue_history,
                    llm_intent,
                )
                if llm_intent.get("intent") == "resistance":
                    resistance_turns += 1
                else:
                    resistance_turns = 0
                if resistance_turns >= 2:
                    candidate["result"] = "declined_by_candidate"
                    reply = MANGO_GOODBYE
                    next_stage = "finished"
                    should_hangup = True
                elif (
                    llm_intent.get("short_reply")
                    and not stage_answer_matches
                    and not self._is_decline(transcript)
                    and not self._script_objection_reply(transcript)
                ):
                    # Use the selected provider's contextual answer in the same
                    # turn as classification; avoid a second slow model call.
                    reply = llm_intent["short_reply"]
                dialogue_history.extend([
                    {"role": "Собеседник", "text": transcript},
                    {"role": "Яна", "text": reply},
                ])
                stage = next_stage
                candidate["stage"] = stage
                candidate["updatedAt"] = datetime.now().isoformat(timespec="seconds")
                _refresh_candidate_report(candidate)
                # Save every turn so a later TTS/RVC error cannot erase collected answers.
                if candidate.get("consent_to_continue"):
                    _save_candidate_record(dict(candidate))
                if candidate.get("scheduled_at"):
                    interview_reminder_service.schedule(candidate, config)
                self._update(
                    reply=reply,
                    candidate=dict(candidate),
                    script_stage=stage,
                    state="speaking",
                    message="Озвучиваю следующий шаг сценария…",
                )
                tts_started = time.perf_counter()
                wav_bytes = silero_tts_service.synthesize_script(reply, language, pace, speaker=speaker)
                logging.info("Silero TTS completed in %.2fs (stage=%s)", time.perf_counter() - tts_started, stage)
                # A final refusal/goodbye must never be cut by the VAD monitor.
                # Play the complete WAV first, then hang up so the last word is
                # delivered to Mango instead of being truncated mid-syllable.
                if should_hangup:
                    self.audio.play_wav(wav_bytes, output_device)
                    interrupted_chunk = b""
                    self._update(state="stopping", message="Прощание полностью передано. Завершаю звонок…")
                else:
                    # Finish each spoken line before reopening STT. Backchannels
                    # such as "ага" and non-lexical vocalizations must not cut
                    # TTS off halfway through a sentence.
                    self.audio.play_wav(wav_bytes, output_device)
                    interrupted_chunk = b""
                last_response_at = time.monotonic()
                hearing_check_sent = False
                if interrupted_chunk:
                    pending_chunk = interrupted_chunk
                    self._update(state="transcribing", message="Собеседник перебил ответ. Распознаю новую реплику…")
                else:
                    if not should_hangup:
                        self._update(state="connected", message="Ответ передан в Mango. Слушаю дальше…")
                if should_hangup:
                    time.sleep(0.15)
                    self._local_hangup.set()
                    talker.hang_up()
                    self._connected = False
                    break
        except Exception as exc:  # noqa: BLE001
            logging.exception("Mango call failed")
            self._update(state="error", message=str(exc))
        finally:
            ringback_stop.set()
            if ringback_thread is not None and ringback_thread.is_alive():
                ringback_thread.join(timeout=1.5)
            if self._peer_hangup.is_set():
                candidate["result"] = "remote_hangup"
                candidate["stage"] = stage
                _refresh_candidate_report(candidate)
                self._update(
                    state="stopping",
                    candidate=dict(candidate),
                    script_stage=stage,
                    message="Собеседник завершил звонок.",
                )
            if (
                talker is not None
                and self._connected
                and not self._peer_hangup.is_set()
                and not self._local_hangup.is_set()
            ):
                try:
                    talker.hang_up()
                except Exception as exc:  # noqa: BLE001
                    logging.warning("Mango final hang-up failed: %s", exc)
            self._connected = False
            if candidate.get("consent_to_continue") and talker is not None:
                self._send_scheduled_sms(talker, candidate)
            if candidate.get("scheduled_at"):
                interview_reminder_service.schedule(candidate, config)
            withdrawn_results = {
                "declined_scheduling", "declined_by_candidate", "declined_scheduled",
                "declined_at_opening", "declined_conditions", "declined_zoom",
                "declined_telegram", "wrong_recipient",
            }
            booked_with_consent = bool(
                candidate.get("consent_to_continue")
                and candidate.get("scheduled_at")
                and candidate.get("scheduled_event_id")
            )
            if candidate.get("result") in withdrawn_results and not booked_with_consent:
                _delete_candidate_record(str(candidate.get("call_id", "")))
            if booked_with_consent:
                candidate["stage"] = stage
                candidate["updatedAt"] = datetime.now().isoformat(timespec="seconds")
                _refresh_candidate_report(candidate)
                _save_candidate_record(candidate)
                self._update(candidate=dict(candidate), script_stage=stage)
                self._notify_telegram(config, candidate["report"])
            elif candidate.get("result") in _CANDIDATE_OUTCOMES:
                self._notify_telegram(config, _candidate_status_line(candidate))
            with self._lock:
                self._talker = talker if talker is not None else self._talker
            if talker is not None:
                try:
                    # Leave Mango visible and foregrounded after every exit
                    # path, including a remote hang-up and failed dialing.
                    talker.ensure_ready()
                except Exception as exc:  # noqa: BLE001
                    logging.warning("Could not restore Mango to foreground after call: %s", exc)
            if self.status()["state"] != "error":
                self._update(state="idle", message="Звонок завершён.")


class SileroTtsService:
    """In-process Silero TTS with warmed language models and cached prompt audio."""

    def __init__(self, voice_service: LocalVoiceService) -> None:
        self.voice_service = voice_service
        self._lock = RLock()
        self._activity_lock = RLock()
        self._activity = {
            "active": False,
            "phase": "idle",
            "progress": 0,
            "message": "Готово",
        }
        self._models: dict[str, Any] = {}
        self._model = None
        self._model_key = ""
        self._model_example = ""
        self._warmup_thread: Thread | None = None

    def _set_activity(self, phase: str, progress: int, message: str, active: bool = True) -> None:
        with self._activity_lock:
            self._activity = {
                "active": active,
                "phase": phase,
                "progress": max(0, min(int(progress), 100)),
                "message": message,
            }

    def activity(self) -> dict[str, Any]:
        with self._activity_lock:
            return dict(self._activity)

    @staticmethod
    def installed() -> bool:
        return torch is not None and hasattr(torch, "hub")

    def reset_model(self) -> None:
        with self._lock:
            self._models.clear()
            self._model = None
            self._model_key = ""
            self._model_example = ""
            gc.collect()
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
        self._set_activity("idle", 0, "Готово", active=False)
        self.start_warmup()

    def start_warmup(self) -> None:
        with self._lock:
            if self._warmup_thread and self._warmup_thread.is_alive():
                return
            self._warmup_thread = Thread(target=self._warmup, name="silero-warmup", daemon=True)
            self._warmup_thread.start()

    def _warmup(self) -> None:
        """Load both language models and render the short thinking prompt once."""
        for language in SILERO_TTS_LANGUAGES:
            try:
                with self._lock:
                    self._load_model(language)
                speaker = SILERO_TTS_SPEAKERS[language][0]
                self.prepared_thinking_audio(language, speaker, 1.0)
                logging.info("Silero %s model and thinking prompt are ready.", language)
            except Exception:  # noqa: BLE001
                logging.exception("Silero %s warmup failed", language)
        self._set_activity("idle", 0, "Готово", active=False)

    @staticmethod
    def _thinking_text(language: str) -> str:
        return "Сейчас, секундочку." if language == "ru" else "Just a second."

    @staticmethod
    def _thinking_cache_path(language: str, speaker: str, pace: float) -> Path:
        rvc_signature = "off"
        if "rvc_service" in globals():
            try:
                rvc = rvc_service.status()
                model_stamp = RVC_MODEL_PATH.stat().st_mtime_ns if RVC_MODEL_PATH.exists() else 0
                index_stamp = RVC_INDEX_PATH.stat().st_mtime_ns if RVC_INDEX_PATH.exists() else 0
                rvc_signature = f"{rvc.get('enabled', False)}:{model_stamp}:{index_stamp}"
            except OSError:
                pass
        signature = f"{language}|{speaker}|{float(pace):.3f}|{rvc_signature}"
        digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
        cache_dir = BASE_DIR / "tts_preload"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"thinking-{language}-{digest}.wav"

    def prepared_thinking_audio(self, language: str, speaker: str = "", pace: float = 1.0) -> bytes:
        """Return a persistent, already-rendered short prompt for LLM latency masking."""
        language = _normalize_text(language).lower() or DEFAULT_TTS_LANGUAGE
        if language not in SILERO_TTS_LANGUAGES:
            language = DEFAULT_TTS_LANGUAGE
        speaker = _normalize_text(speaker) or SILERO_TTS_SPEAKERS[language][0]
        cache_path = self._thinking_cache_path(language, speaker, pace)
        try:
            if cache_path.exists() and cache_path.stat().st_size > 44:
                return cache_path.read_bytes()
        except OSError:
            pass
        wav_bytes = self.synthesize(
            self._thinking_text(language),
            language,
            pace,
            speaker=speaker,
        )
        try:
            cache_path.write_bytes(wav_bytes)
        except OSError as exc:
            logging.warning("Could not persist thinking prompt: %s", exc)
        return wav_bytes

    def synthesize_script(self, text: str, language: str, pace: float, speaker: str = "") -> bytes:
        """Render a fixed call-script line once and reuse it across calls."""
        SCRIPT_AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        rvc_signature = "off"
        try:
            rvc_state = rvc_service.status()
            model_stamp = RVC_MODEL_PATH.stat().st_mtime_ns if RVC_MODEL_PATH.exists() else 0
            index_stamp = RVC_INDEX_PATH.stat().st_mtime_ns if RVC_INDEX_PATH.exists() else 0
            rvc_signature = f"{rvc_state.get('enabled', False)}:{model_stamp}:{index_stamp}"
        except (NameError, OSError):
            pass
        signature = json.dumps(
            # Bump the cache namespace whenever prosody handling changes so
            # old statement-like WAVs cannot survive a question-intonation fix.
            ["silero-prosody-v6", text, language, round(float(pace), 3), speaker, rvc_signature],
            ensure_ascii=False,
        ).encode("utf-8")
        cache_path = SCRIPT_AUDIO_CACHE_DIR / f"{hashlib.sha256(signature).hexdigest()}.wav"
        try:
            if cache_path.exists() and cache_path.stat().st_size > 44:
                return cache_path.read_bytes()
        except OSError:
            pass
        with self._lock:
            try:
                if cache_path.exists() and cache_path.stat().st_size > 44:
                    return cache_path.read_bytes()
            except OSError:
                pass
            wav_bytes = self.synthesize(text, language, pace, speaker=speaker)
            temporary = cache_path.with_suffix(".tmp")
            try:
                temporary.write_bytes(wav_bytes)
                temporary.replace(cache_path)
            except OSError:
                logging.warning("Could not persist script audio cache: %s", cache_path)
            return wav_bytes

    @staticmethod
    def quantization_info() -> dict[str, Any]:
        gpu = bool(torch is not None and torch.cuda.is_available())
        return {
            "backend": "silero-torchhub",
            "precision": "FP32 CUDA" if gpu else "FP32 CPU",
            "label": "Silero v5.5 · " + ("CUDA" if gpu else "CPU"),
            "models": {"silero-v5.5": {"label": "PyTorch / CUDA" if gpu else "PyTorch / CPU"}},
        }

    @staticmethod
    def speakers(language: str) -> list[str]:
        return list(SILERO_TTS_SPEAKERS.get(language, []))

    def _load_model(self, language: str):
        if torch is None:
            raise RuntimeError("PyTorch не установлен. Запусти setup_new_pc.cmd.")
        device = torch.device("cuda" if self.voice_service._device_mode == "gpu" else "cpu")
        key = f"{language}:{device.type}"
        if key in self._models:
            self._model = self._models[key]
            self._model_key = key
            return self._models[key]

        self._set_activity("loading", 15, "Загружаю Silero…")
        TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        torch.hub.set_dir(str(TTS_CACHE_DIR / "torch_hub"))
        model, example_text = torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language=language,
            speaker=SILERO_TTS_MODEL_IDS[language],
        )
        model.to(device)
        self._models[key] = model
        self._model = model
        self._model_key = key
        self._model_example = str(example_text or "")
        return self._model

    @staticmethod
    def _to_wav(audio, sample_rate: int, pace: float) -> bytes:
        import io
        import wave

        audio = audio.detach().float().flatten().cpu()
        if abs(pace - 1.0) > 0.001 and audio.numel() > 1:
            target_length = max(1, int(audio.numel() / pace))
            audio = torch.nn.functional.interpolate(
                audio.view(1, 1, -1), size=target_length, mode="linear", align_corners=False
            ).view(-1)
        pcm = (audio.clamp(-1, 1) * 32767).to(torch.int16).numpy().tobytes()
        output = io.BytesIO()
        with wave.open(output, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(sample_rate)
            writer.writeframes(pcm)
        return output.getvalue()

    @staticmethod
    def _join_wavs(wav_parts: list[bytes]) -> bytes:
        if not wav_parts:
            raise ValueError("Silero returned no audio.")
        if len(wav_parts) == 1:
            return wav_parts[0]
        with wave.open(io.BytesIO(wav_parts[0]), "rb") as first:
            params = first.getparams()
            frames = [first.readframes(first.getnframes())]
        for wav_bytes in wav_parts[1:]:
            with wave.open(io.BytesIO(wav_bytes), "rb") as part:
                if (
                    part.getnchannels() != params.nchannels
                    or part.getsampwidth() != params.sampwidth
                    or part.getframerate() != params.framerate
                ):
                    raise ValueError("Silero returned incompatible audio segments.")
                frames.append(part.readframes(part.getnframes()))
        output = io.BytesIO()
        with wave.open(output, "wb") as writer:
            writer.setnchannels(params.nchannels)
            writer.setsampwidth(params.sampwidth)
            writer.setframerate(params.framerate)
            writer.writeframes(b"".join(frames))
        return output.getvalue()

    def synthesize(
        self,
        text: str,
        language: str,
        pace: float,
        mode: str = "speaker",
        model_size: str = DEFAULT_SILERO_TTS_MODEL,
        speaker: str = "",
        instruct: str = "",
        temperature: float = 0.7,
        top_p: float = 0.8,
        top_k: int = 50,
        max_new_tokens: int = 384,
    ) -> bytes:
        del mode, model_size, instruct, temperature, top_p, top_k, max_new_tokens
        text = _prepare_silero_text(text)
        language = _normalize_text(language).lower() or DEFAULT_TTS_LANGUAGE
        if not text:
            raise HTTPException(status_code=400, detail="Text is required.")
        if len(text) > 12000:
            raise HTTPException(status_code=400, detail="Text is too long.")
        if not any(char.isalpha() for char in text):
            raise HTTPException(
                status_code=400,
                detail="Silero returned no audio: в тексте нет букв для озвучивания.",
            )
        if language not in SILERO_TTS_LANGUAGES:
            raise HTTPException(status_code=400, detail="Поддерживаются только русский и английский языки.")
        speaker = _normalize_text(speaker) or DEFAULT_SILERO_SPEAKER
        if speaker not in SILERO_TTS_SPEAKERS[language]:
            speaker = SILERO_TTS_SPEAKERS[language][0]
        pace = min(max(float(pace), 0.7), 1.4)
        self._set_activity("generating", 55, "Silero генерирует речь…")
        try:
            with self._lock:
                model = self._load_model(language)
                segments = _split_silero_text(text)
                wav_parts: list[bytes] = []
                total = max(1, len(segments))
                for index, segment in enumerate(segments, start=1):
                    if not any(char.isalpha() for char in segment):
                        logging.debug("Skipping punctuation-only Silero segment: %r", segment)
                        continue
                    self._set_activity(
                        "generating",
                        55 + int(index / total * 30),
                        f"Silero генерирует речь… фрагмент {index}/{total}",
                    )
                    segment_language = language
                    segment_speaker = speaker
                    model = self._load_model(segment_language)
                    try:
                        apply_kwargs = {
                            "text": _silero_question_focus(segment) if segment_language == "ru" else segment,
                            "speaker": segment_speaker,
                            "sample_rate": 48000,
                        }
                        # Some bundled Silero v5.5 packages do not expose the
                        # optional question-prosody argument. Keep the
                        # compatibility path so a model update cannot break
                        # all startup warmups with an unexpected keyword.
                        try:
                            audio = model.apply_tts(
                                **apply_kwargs,
                                type_str=_silero_type_for_segment(segment),
                                intensity=3,
                            )
                        except TypeError as type_error:
                            if "type_str" not in str(type_error):
                                raise
                            audio = model.apply_tts(**apply_kwargs)
                    except ValueError as primary_error:
                        # The v5.5 Russian package rejects a sentence that is
                        # entirely Latin (for example an English phrase, URL,
                        # or email). Retry that sentence with bundled English.
                        segment_language = _silero_fallback_language(segment, language)
                        if segment_language == language:
                            raise
                        segment_speaker = SILERO_TTS_SPEAKERS[segment_language][0]
                        logging.info(
                            "Retrying Silero segment with %s model after %s failed: %r",
                            segment_language,
                            type(primary_error).__name__,
                            segment[:160],
                        )
                        model = self._load_model(segment_language)
                        audio = model.apply_tts(
                            text=segment,
                            speaker=segment_speaker,
                            sample_rate=48000,
                        )
                    wav_parts.append(self._to_wav(audio, 48000, pace))
                self._set_activity("encoding", 92, "Сохраняю WAV…")
                if not wav_parts:
                    logging.warning("Silero produced no segments for text: %r", text[:240])
                wav_bytes = self._join_wavs(wav_parts)
                rvc_state = rvc_service.status()
                if rvc_state["enabled"] and rvc_state["ready"]:
                    self._set_activity("rvc", 96, "RVC меняет голос…")
                    wav_bytes = rvc_service.convert(wav_bytes)
                elif rvc_state["enabled"]:
                    logging.warning("RVC включён, но не готов (%s). Возвращаю исходный Silero WAV.", rvc_state["message"])
                return wav_bytes
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logging.exception("Silero synthesis failed")
            raise HTTPException(
                status_code=503,
                detail=f"Silero synthesis failed: {type(exc).__name__}: {exc!r}",
            ) from exc
        finally:
            self._set_activity("idle", 0, "Готово", active=False)

    def synthesize_batch(self, items: list[dict[str, Any]]) -> list[bytes]:
        if not items or len(items) > 8:
            raise HTTPException(status_code=400, detail="Batch must contain between 1 and 8 sentences.")
        outputs = []
        for item in items:
            outputs.append(
                self.synthesize(
                    str(item.get("text", "")),
                    str(item.get("language", DEFAULT_TTS_LANGUAGE)),
                    float(item.get("pace", 1.0)),
                    mode="speaker",
                    speaker=str(item.get("speaker", "")),
                )
            )
        return outputs


class LocalQwenService:
    """Manage the bundled Qwen3 GGUF through the local llama.cpp server."""

    def __init__(self, bundled_dir: Path) -> None:
        self.bundled_dir = bundled_dir
        self.model_path = bundled_dir / LOCAL_LLM_MODEL
        self.cuda_exe = bundled_dir / "cuda" / "llama-server.exe"
        self.cpu_exe = bundled_dir / "cpu" / "llama-server.exe"
        self.port = 0
        self._process: subprocess.Popen[Any] | None = None
        self._log_handle = None
        self._lock = RLock()
        self._start_lock = RLock()
        self._running_thinking = False
        self._warmup_thread: Thread | None = None

    def available(self) -> bool:
        return self.model_path.is_file() and self.cpu_exe.is_file()

    def _gpu_ready(self) -> bool:
        return bool(torch is not None and torch.cuda.is_available() and self.cuda_exe.is_file())

    def _endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def _healthy(self) -> bool:
        if self.port <= 0 or self._process is None or self._process.poll() is not None:
            return False
        try:
            response = requests.get(f"http://127.0.0.1:{self.port}/health", timeout=0.5)
            return response.ok
        except requests.RequestException:
            return False

    def _free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def start_warmup(self) -> None:
        """Load the bundled model after the UI opens so the first turn is not a cold start."""
        if not self.available():
            return
        with self._lock:
            if self._warmup_thread and self._warmup_thread.is_alive():
                return
            self._warmup_thread = Thread(
                target=self._warmup_after_startup,
                name="local-qwen-warmup",
                daemon=True,
            )
            self._warmup_thread.start()

    def _warmup_after_startup(self) -> None:
        time.sleep(max(0.0, float(os.getenv("VOICEBRIDGE_QWEN_WARMUP_DELAY", "8"))))
        try:
            self.ensure_running(thinking=False)
            logging.info("Bundled Qwen3 is loaded and ready before the first dialogue turn.")
        except Exception as exc:  # noqa: BLE001
            logging.warning("Qwen background warmup did not complete: %s", exc)

    def _stop_unlocked(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        if self._log_handle is not None:
            try:
                self._log_handle.close()
            except OSError:
                pass
            self._log_handle = None

    def ensure_running(self, thinking: bool = False) -> str:
        with self._start_lock:
            return self._ensure_running_serialized(thinking)

    def _ensure_running_serialized(self, thinking: bool = False) -> str:
        if not self.available():
            raise HTTPException(
                status_code=503,
                detail="Локальная Qwen3-1.7B не найдена в portable-сборке.",
            )
        with self._lock:
            if self._healthy() and self._running_thinking == bool(thinking):
                return self._endpoint()
            if self._healthy():
                logging.info("Restarting local Qwen3 to change thinking mode to %s.", thinking)
                self._stop_unlocked()
            elif self._process is not None and self._process.poll() is not None:
                self._process = None
            self.port = self._free_port()
            use_gpu = self._gpu_ready()
            executable = self.cuda_exe if use_gpu else self.cpu_exe
            log_path = BASE_DIR / "qwen3-llm.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            if self._log_handle is not None:
                try:
                    self._log_handle.close()
                except OSError:
                    pass
            self._log_handle = open(log_path, "a", encoding="utf-8")
            command = [
                str(executable),
                "--model", str(self.model_path),
                "--host", "127.0.0.1",
                "--port", str(self.port),
                "--ctx-size", "4096",
                "--n-predict", str(384 + LOCAL_LLM_REASONING_BUDGET if thinking else 384),
                "--reasoning", "on" if thinking else "off",
                "--reasoning-budget", str(LOCAL_LLM_REASONING_BUDGET if thinking else 0),
                "--temp", str(LOCAL_LLM_TEMPERATURE),
                "--top-p", "0.8",
                "--top-k", "20",
                "--no-ui",
                "--n-gpu-layers", "all" if use_gpu else "0",
                "--threads", str(_LLM_CPU_THREADS),
                "--threads-batch", str(_LLM_CPU_THREADS),
            ]
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._process = subprocess.Popen(
                command,
                cwd=str(executable.parent),
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            self._running_thinking = bool(thinking)
            logging.info(
                "Local Qwen3-1.7B started on %s (%s, thinking %s). Log: %s",
                self._endpoint(), "CUDA" if use_gpu else "CPU",
                "on" if thinking else "off", log_path,
            )

        deadline = time.monotonic() + 90.0
        while time.monotonic() < deadline:
            if self._healthy():
                return self._endpoint()
            if self._process is not None and self._process.poll() is not None:
                break
            time.sleep(0.25)
        raise HTTPException(
            status_code=503,
            detail=f"Локальная Qwen3-1.7B не запустилась. Подробности: {BASE_DIR / 'qwen3-llm.log'}",
        )

    def info(self) -> dict[str, Any]:
        running = self._healthy()
        return {
            "id": "local-qwen3-1.7b",
            "label": "Qwen3 1.7B · локально / llama.cpp",
            "model": LOCAL_LLM_MODEL,
            "bundled": self.available(),
            "running": running,
            "provider": "CUDA" if self._gpu_ready() else "CPU",
            "thinking": self._running_thinking if running else False,
            "thinkingBudget": LOCAL_LLM_REASONING_BUDGET,
            "context": 4096,
            "maxTokens": 384,
            "logPath": str(BASE_DIR / "qwen3-llm.log"),
        }

    def _messages(
        self,
        system_prompt: str,
        user_text: str,
        history: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        system = _normalize_text(system_prompt)
        if not system:
            system = "Отвечай по-русски, кратко и естественно. Не показывай рассуждения, отвечай сразу по делу."
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for item in history or []:
            text = _normalize_text(str(item.get("text", "")))
            if text:
                messages.append({
                    "role": "assistant" if _is_assistant_history_role(item.get("role")) else "user",
                    "content": f"{_llm_history_label(item.get('role'))}: {text}",
                })
        messages.append({"role": "user", "content": user_text})
        return messages

    def chat(
        self,
        user_text: str,
        system_prompt: str,
        temperature: float,
        thinking: bool = False,
        history: list[dict[str, str]] | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        base_url = self.ensure_running(thinking)
        payload = {
            "model": LOCAL_LLM_MODEL,
            "messages": self._messages(system_prompt, user_text, history),
            "temperature": max(0.0, min(float(temperature), 1.5)),
            "top_p": 0.8,
            "top_k": 20,
            "min_p": 0.0,
            "repeat_penalty": 1.08,
            "max_tokens": max_tokens or (384 + LOCAL_LLM_REASONING_BUDGET if thinking else 384),
        }
        if system_prompt == MANGO_INTENT_SYSTEM_PROMPT:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=300,
            )
        except requests.RequestException as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail="Локальная Qwen3 не отвечает.") from exc
        if not response.ok:
            raise HTTPException(status_code=503, detail=f"Локальная Qwen3 вернула HTTP {response.status_code}.")
        data = response.json()
        choices = data.get("choices") or []
        content = ""
        if choices:
            content = _repair_mojibake((choices[0].get("message") or {}).get("content") or "")
        return {"text": content, "raw": data}

    def open_stream(
        self,
        user_text: str,
        system_prompt: str,
        temperature: float,
        thinking: bool = False,
        history: list[dict[str, str]] | None = None,
    ) -> requests.Response:
        base_url = self.ensure_running(thinking)
        payload = {
            "model": LOCAL_LLM_MODEL,
            "messages": self._messages(system_prompt, user_text, history),
            "temperature": max(0.0, min(float(temperature), 1.5)),
            "top_p": 0.8,
            "top_k": 20,
            "min_p": 0.0,
            "repeat_penalty": 1.08,
            "max_tokens": 384 + LOCAL_LLM_REASONING_BUDGET if thinking else 384,
            "stream": True,
        }
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=(30, 300),
                stream=True,
            )
        except requests.RequestException as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail="Локальная Qwen3 не отвечает.") from exc
        if not response.ok:
            response.close()
            raise HTTPException(status_code=503, detail=f"Локальная Qwen3 вернула HTTP {response.status_code}.")
        return response

    def stop(self) -> None:
        with self._lock:
            self._stop_unlocked()


class OpenAICompatService:
    def chat(
        self,
        base_url: str,
        api_key: str,
        model: str,
        user_text: str,
        system_prompt: str = "",
        temperature: float = 0.4,
        use_vpn: bool = False,
        thinking: bool = False,
        history: list[dict[str, str]] | None = None,
        max_tokens: int | None = None,
        request_timeout: float = 300.0,
    ) -> dict[str, Any]:
        base_url = _normalize_text(base_url).rstrip("/")
        api_key = _normalize_text(api_key)
        model = _normalize_text(model)
        user_text = _normalize_text(user_text)
        system_prompt = _normalize_text(system_prompt)

        if base_url == LOCAL_LLM_BASE_URL:
            if not user_text:
                raise HTTPException(status_code=400, detail="Prompt text is required.")
            if system_prompt in {"", DEFAULT_SYSTEM_PROMPT}:
                system_prompt = MANGO_LOCAL_CALL_SYSTEM_PROMPT
            if _is_voice_history(history) and "[ИИ-АССИСТЕНТ]" not in system_prompt:
                system_prompt = f"{MANGO_ROLE_PROTOCOL}\n\n{system_prompt}"
            if not _is_voice_history(history):
                user_text = _local_qwen_turn_hint(history, user_text)
            return qwen_llm_service.chat(
                user_text,
                system_prompt,
                temperature,
                thinking,
                history,
                max_tokens=max_tokens,
            )

        if not base_url:
            raise HTTPException(status_code=400, detail="OpenAI-compatible base URL is required.")
        if not api_key:
            raise HTTPException(status_code=400, detail="OpenAI-compatible API key is required.")
        if not model:
            raise HTTPException(status_code=400, detail="OpenAI-compatible model is required.")
        if not user_text:
            raise HTTPException(status_code=400, detail="Prompt text is required.")
        if _is_voice_history(history) and "[ИИ-АССИСТЕНТ]" not in system_prompt:
            system_prompt = f"{MANGO_ROLE_PROTOCOL}\n\n{system_prompt}"

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for item in history or []:
            item_text = _normalize_text(str(item.get("text", "")))
            if item_text:
                messages.append({
                    "role": "assistant" if _is_assistant_history_role(item.get("role")) else "user",
                    "content": f"{_llm_history_label(item.get('role'))}: {item_text}",
                })
        messages.append({"role": "user", "content": user_text})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)

        try:
            proxy = vpn_proxy(use_vpn)
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=max(1.0, float(request_timeout)),
                **request_proxy_kwargs(proxy),
            )
        except requests.RequestException as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail="Failed to reach OpenAI-compatible API.") from exc

        response.encoding = "utf-8"
        if not response.ok:
            detail: Any
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            if response.status_code == 503:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "The selected LLM model is temporarily unavailable. "
                        "Choose another model or try again later."
                    ),
                )
            raise HTTPException(status_code=response.status_code, detail=detail)

        data = response.json()
        choices = data.get("choices") or []
        content = ""
        if choices:
            message = choices[0].get("message") or {}
            content = _repair_mojibake(message.get("content") or "")

        return {"text": content, "raw": data}

    def open_stream(
        self,
        base_url: str,
        api_key: str,
        model: str,
        user_text: str,
        system_prompt: str = "",
        temperature: float = 0.4,
        use_vpn: bool = False,
        thinking: bool = False,
        history: list[dict[str, str]] | None = None,
    ) -> requests.Response:
        base_url = _normalize_text(base_url).rstrip("/")
        api_key = _normalize_text(api_key)
        model = _normalize_text(model)
        user_text = _normalize_text(user_text)
        system_prompt = _normalize_text(system_prompt)

        if base_url == LOCAL_LLM_BASE_URL:
            if not user_text:
                raise HTTPException(status_code=400, detail="Prompt text is required.")
            if system_prompt in {"", DEFAULT_SYSTEM_PROMPT}:
                system_prompt = MANGO_LOCAL_CALL_SYSTEM_PROMPT
            if _is_voice_history(history) and "[ИИ-АССИСТЕНТ]" not in system_prompt:
                system_prompt = f"{MANGO_ROLE_PROTOCOL}\n\n{system_prompt}"
            if not _is_voice_history(history):
                user_text = _local_qwen_turn_hint(history, user_text)
            return qwen_llm_service.open_stream(user_text, system_prompt, temperature, thinking, history)

        if not base_url:
            raise HTTPException(status_code=400, detail="OpenAI-compatible base URL is required.")
        if not api_key:
            raise HTTPException(status_code=400, detail="OpenAI-compatible API key is required.")
        if not model:
            raise HTTPException(status_code=400, detail="OpenAI-compatible model is required.")
        if not user_text:
            raise HTTPException(status_code=400, detail="Prompt text is required.")
        if _is_voice_history(history) and "[ИИ-АССИСТЕНТ]" not in system_prompt:
            system_prompt = f"{MANGO_ROLE_PROTOCOL}\n\n{system_prompt}"

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for item in history or []:
            item_text = _normalize_text(str(item.get("text", "")))
            if item_text:
                messages.append({
                    "role": "assistant" if _is_assistant_history_role(item.get("role")) else "user",
                    "content": f"{_llm_history_label(item.get('role'))}: {item_text}",
                })
        messages.append({"role": "user", "content": user_text})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }

        try:
            proxy = vpn_proxy(use_vpn)
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=(30, 300),
                stream=True,
                **request_proxy_kwargs(proxy),
            )
        except requests.RequestException as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail="Failed to reach OpenAI-compatible API.") from exc

        response.encoding = "utf-8"
        if not response.ok:
            try:
                detail: Any = response.json()
            except ValueError:
                detail = response.text
            response.close()
            if response.status_code == 503:
                raise HTTPException(
                    status_code=503,
                    detail="The selected LLM model is temporarily unavailable. Choose another model or try again later.",
                )
            raise HTTPException(status_code=response.status_code, detail=detail)
        return response

    @staticmethod
    def iter_stream(response: requests.Response):
        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                if not choices:
                    continue
                choice = choices[0] or {}
                delta = choice.get("delta") or {}
                piece = delta.get("content") or choice.get("text") or ""
                piece = _repair_mojibake(piece)
                if isinstance(piece, str) and piece:
                    yield f"data: {json.dumps({'text': piece}, ensure_ascii=False)}\n\n"
        finally:
            response.close()
        yield "data: [DONE]\n\n"


class VisionInboxService:
    """Single persistent vision chat that turns image contacts into a call queue."""

    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file
        self._lock = RLock()

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return {
            "history": payload.get("history") if isinstance(payload.get("history"), list) else [],
            "queue": payload.get("queue") if isinstance(payload.get("queue"), list) else [],
        }

    def _save_unlocked(self, payload: dict[str, Any]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.state_file)

    def state(self) -> dict[str, Any]:
        with self._lock:
            return self._read_unlocked()

    @staticmethod
    def _phone(value: Any) -> str:
        raw = _normalize_text(str(value or ""))
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 5:
            return ""
        return ("+" if raw.startswith("+") else "") + digits

    @staticmethod
    def _response_text(data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", "")) for item in content if isinstance(item, dict)
            )
        return _repair_mojibake(str(content).strip())

    @classmethod
    def _parse_contacts(cls, text: str) -> list[dict[str, str]]:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
        parsed: Any = None
        try:
            parsed = json.loads(candidate)
        except ValueError:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(candidate[start : end + 1])
                except ValueError:
                    parsed = None
        if isinstance(parsed, dict):
            parsed = parsed.get("contacts") or parsed.get("people") or parsed.get("items") or []
        if not isinstance(parsed, list):
            parsed = []
        contacts: list[dict[str, str]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            number = cls._phone(item.get("number") or item.get("phone") or item.get("telephone"))
            if not number:
                continue
            name = _normalize_text(str(item.get("name") or item.get("full_name") or item.get("contact") or "Без имени"))
            contacts.append({"name": name[:180], "number": number})
        if contacts:
            return contacts

        # Vision providers sometimes ignore the JSON instruction and answer in prose.
        # Recover phone/name pairs from the line that contains each number so the
        # contact still reaches the call queue instead of disappearing silently.
        phone_pattern = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)")
        seen_numbers: set[str] = set()
        for line in text.splitlines():
            matches = list(phone_pattern.finditer(line))
            if not matches:
                continue
            for match in matches:
                number = cls._phone(match.group(0))
                if not number or number in seen_numbers:
                    continue
                before = line[: match.start()]
                before = re.sub(r"[*_`#•]+", " ", before)
                before = re.sub(r"^\s*[-–—:.)]+\s*", "", before)
                if ":" in before:
                    before = before.rsplit(":", 1)[-1]
                before = re.sub(
                    r"\b(?:имя|фио|контакт|человек|кандидат|номер|телефон|полный|указанн\w*|найден\w*|есть|только|один)\b",
                    " ",
                    before,
                    flags=re.IGNORECASE,
                )
                name = re.sub(r"\s+", " ", before).strip(" ,;:-–—")
                if not name:
                    name = "Без имени"
                seen_numbers.add(number)
                contacts.append({"name": name[:180], "number": number})
        return contacts

    def analyze(
        self,
        images: list[UploadFile],
        prompt: str,
        api_key: str,
        base_url: str,
        model: str,
        use_vpn: bool,
    ) -> dict[str, Any]:
        base_url = _normalize_text(base_url).rstrip("/")
        api_key = _normalize_text(api_key)
        model = _normalize_text(model)
        if not base_url or base_url == LOCAL_LLM_BASE_URL:
            raise HTTPException(status_code=400, detail="Для Vision укажи OpenAI-compatible URL с поддержкой изображений.")
        if not api_key:
            raise HTTPException(status_code=400, detail="Для Vision нужен API key.")
        if not model:
            raise HTTPException(status_code=400, detail="Для Vision укажи название модели.")
        if not images:
            raise HTTPException(status_code=400, detail="Вставь или добавь хотя бы одно изображение.")

        user_instruction = _normalize_text(prompt) or VISION_DEFAULT_PROMPT
        instruction = (
            f"{user_instruction}\n\n"
            "Сначала внимательно проверь каждый номер прямо на изображении. "
            "Никогда не угадывай, не дополняй и не придумывай цифры. "
            "Если номер не виден полностью или его нельзя уверенно прочитать, "
            "полностью пропусти этого человека. Не добавляй человека только по имени. "
            "Для каждого человека с полным номером верни только JSON без markdown, "
            'строго в формате {"contacts":[{"name":"Имя","number":"номер"}]}. '
            "Поле name должно содержать только ФИО, поле number — только полный номер телефона. "
            "number должен быть дословно переписан с изображения, включая все цифры. "
            "Не добавляй неполные номера, города или организации. Если подходящих людей нет, "
            'верни {"contacts":[]}. Никаких пояснений до или после JSON.'
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": instruction}]
        image_meta: list[dict[str, str]] = []
        for upload in images[:12]:
            raw = upload.file.read()
            if not raw:
                continue
            if len(raw) > 12 * 1024 * 1024:
                raise HTTPException(status_code=413, detail=f"Изображение {upload.filename or 'без имени'} больше 12 MB.")
            mime = (upload.content_type or "image/png").lower()
            if not mime.startswith("image/"):
                mime = "image/png"
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"}})
            image_meta.append({"name": upload.filename or "image", "mime": mime})
        if not image_meta:
            raise HTTPException(status_code=400, detail="Не удалось прочитать изображения.")

        system_instruction = (
            "Ты извлекаешь контакты только по тому, что реально видно на изображении. "
            "Запрещено придумывать, угадывать или восстанавливать отсутствующие цифры. "
            "Человек без полностью видимого номера не должен попасть в результат. "
            "Отвечай только валидным JSON без markdown и пояснений."
        )

        def request_vision(request_content: list[dict[str, Any]]) -> requests.Response:
            proxy = vpn_proxy(use_vpn)
            return requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": request_content},
                    ],
                    "temperature": 0,
                    "max_tokens": 512,
                },
                timeout=180,
                **request_proxy_kwargs(proxy),
            )

        successful_responses: list[str] = []
        try:
            response = request_vision(content)
            if response.ok:
                response.encoding = "utf-8"
                successful_responses.append(self._response_text(response.json()))
            elif response.status_code == 400 and len(content) > 2:
                # Some compatible providers accept one image per request only.
                # Retry each image separately, then merge the model responses.
                for image_item in content[1:]:
                    single_response = request_vision([content[0], image_item])
                    if single_response.ok:
                        single_response.encoding = "utf-8"
                        successful_responses.append(self._response_text(single_response.json()))
            if not successful_responses:
                response.encoding = "utf-8"
                if not response.ok:
                    try:
                        detail: Any = response.json()
                    except ValueError:
                        detail = response.text
                    raise HTTPException(status_code=response.status_code, detail=detail)
        except requests.RequestException as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail="Vision provider недоступен.") from exc

        assistant_text = "\n".join(text for text in successful_responses if text).strip()
        contacts = self._parse_contacts(assistant_text)
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            payload = self._read_unlocked()
            queued_numbers = {
                self._phone(item.get("number"))
                for item in payload["queue"]
                if self._phone(item.get("number"))
            }
            for contact in contacts:
                clean_number = self._phone(contact.get("number"))
                if not clean_number or clean_number in queued_numbers:
                    continue
                payload["queue"].append({
                    "id": uuid.uuid4().hex,
                    "name": contact.get("name") or "Без имени",
                    "number": clean_number,
                    "createdAt": now,
                    "status": "queued",
                })
                queued_numbers.add(clean_number)
            payload["history"].extend([
                {"id": uuid.uuid4().hex, "role": "user", "text": instruction, "images": image_meta, "createdAt": now},
                {
                    "id": uuid.uuid4().hex,
                    "role": "assistant",
                    "text": assistant_text or "Модель не вернула текст.",
                    "contacts": contacts,
                    "createdAt": now,
                },
            ])
            payload["history"] = payload["history"][-100:]
            self._save_unlocked(payload)
            return {"assistantText": assistant_text, "contacts": contacts, **payload}

    def add_contact(self, name: str, number: str) -> dict[str, Any]:
        clean_number = self._phone(number)
        clean_name = _normalize_text(name) or "Без имени"
        if not clean_number:
            raise HTTPException(status_code=400, detail="У контакта нет полного номера телефона.")
        with self._lock:
            payload = self._read_unlocked()
            existing = next(
                (item for item in payload["queue"] if self._phone(item.get("number")) == clean_number),
                None,
            )
            if existing:
                return {"added": False, "contact": existing, **payload}
            contact = {
                "id": uuid.uuid4().hex,
                "name": clean_name[:180],
                "number": clean_number,
                "createdAt": datetime.now().isoformat(timespec="seconds"),
                "status": "queued",
            }
            payload["queue"].append(contact)
            self._save_unlocked(payload)
            return {"added": True, "contact": contact, **payload}

    def delete(self, contact_id: str) -> dict[str, Any]:
        with self._lock:
            payload = self._read_unlocked()
            payload["queue"] = [item for item in payload["queue"] if str(item.get("id")) != contact_id]
            self._save_unlocked(payload)
            return payload

    def move_contact(self, contact_id: str, direction: str) -> dict[str, Any]:
        if direction not in {"up", "down"}:
            raise HTTPException(status_code=400, detail="Неизвестное направление перемещения.")
        with self._lock:
            payload = self._read_unlocked()
            index = next(
                (i for i, item in enumerate(payload["queue"]) if str(item.get("id")) == contact_id),
                None,
            )
            if index is None:
                raise HTTPException(status_code=404, detail="Контакт не найден в очереди.")
            target = index - 1 if direction == "up" else index + 1
            if 0 <= target < len(payload["queue"]):
                payload["queue"][index], payload["queue"][target] = (
                    payload["queue"][target], payload["queue"][index],
                )
                self._save_unlocked(payload)
            return payload

    def clear_queue(self) -> dict[str, Any]:
        with self._lock:
            payload = self._read_unlocked()
            payload["queue"] = []
            self._save_unlocked(payload)
            return payload

    def clear_history(self) -> dict[str, Any]:
        with self._lock:
            payload = self._read_unlocked()
            payload["history"] = []
            self._save_unlocked(payload)
            return payload


class InterviewCalendarService:
    """Persistent Moscow-time calendar with atomic slot reservation."""

    DEFAULT_SETTINGS = {
        "timezone": "Europe/Moscow",
        "work_start": "10:00",
        "work_end": "20:00",
        "slot_minutes": 20,
        "breaks": ["13:00-14:00"],
    }

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        if ZoneInfo is not None:
            try:
                self.tz = ZoneInfo("Europe/Moscow")
            except Exception:  # noqa: BLE001
                self.tz = timezone(timedelta(hours=3), "Europe/Moscow")
        else:
            self.tz = timezone(timedelta(hours=3), "Europe/Moscow")

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def today(self) -> date:
        return self.now().date()

    def _default_payload(self) -> dict[str, Any]:
        return {"settings": dict(self.DEFAULT_SETTINGS), "events": []}

    def _read_unlocked(self) -> dict[str, Any]:
        payload = self._default_payload()
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    settings = loaded.get("settings")
                    if isinstance(settings, dict):
                        payload["settings"].update(settings)
                    events = loaded.get("events")
                    if isinstance(events, list):
                        payload["events"] = [item for item in events if isinstance(item, dict)]
        except (OSError, ValueError):
            logging.warning("Interview calendar file is unreadable; using defaults.")
        return payload

    def _save_unlocked(self, payload: dict[str, Any]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def _parse_clock(value: str, fallback: str) -> datetime_time:
        try:
            parsed = datetime.strptime(str(value or fallback).strip(), "%H:%M").time()
            return parsed.replace(second=0, microsecond=0)
        except ValueError:
            return datetime.strptime(fallback, "%H:%M").time()

    @staticmethod
    def _parse_day(value: str | None, fallback: date) -> date:
        try:
            return date.fromisoformat(str(value or "").strip())
        except ValueError:
            return fallback

    def _settings_unlocked(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = dict(self.DEFAULT_SETTINGS)
        settings.update(payload.get("settings") or {})
        settings["work_start"] = self._parse_clock(settings.get("work_start"), "10:00").strftime("%H:%M")
        settings["work_end"] = self._parse_clock(settings.get("work_end"), "20:00").strftime("%H:%M")
        try:
            settings["slot_minutes"] = max(10, min(120, int(settings.get("slot_minutes", 20))))
        except (TypeError, ValueError):
            settings["slot_minutes"] = 30
        breaks = settings.get("breaks", [])
        if isinstance(breaks, str):
            breaks = [part.strip() for part in re.split(r"[,;]+", breaks) if part.strip()]
        if not isinstance(breaks, list):
            breaks = []
        normalized_breaks: list[str] = []
        for item in breaks:
            match = re.fullmatch(r"\s*(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s*", str(item))
            if not match:
                continue
            start = self._parse_clock(match.group(1), "13:00")
            end = self._parse_clock(match.group(2), "14:00")
            if start < end:
                normalized_breaks.append(f"{start:%H:%M}-{end:%H:%M}")
        settings["breaks"] = normalized_breaks
        return settings

    def _event_datetimes(self, event: dict[str, Any]) -> tuple[datetime, datetime] | None:
        try:
            start = datetime.fromisoformat(str(event.get("start", "")))
            end = datetime.fromisoformat(str(event.get("end", "")))
        except ValueError:
            return None
        if start.tzinfo is None:
            start = start.replace(tzinfo=self.tz)
        if end.tzinfo is None:
            end = end.replace(tzinfo=self.tz)
        return start.astimezone(self.tz), end.astimezone(self.tz)

    @staticmethod
    def _overlaps(start: datetime, end: datetime, other_start: datetime, other_end: datetime) -> bool:
        return start < other_end and end > other_start

    def _breaks_for_day(self, settings: dict[str, Any], day: date) -> list[tuple[datetime, datetime]]:
        result = []
        for item in settings.get("breaks", []):
            start_text, end_text = str(item).split("-", 1)
            start = datetime.combine(day, self._parse_clock(start_text, "13:00"), self.tz)
            end = datetime.combine(day, self._parse_clock(end_text, "14:00"), self.tz)
            if start < end:
                result.append((start, end))
        return result

    def _slots_unlocked(self, payload: dict[str, Any], day: date) -> list[dict[str, Any]]:
        settings = self._settings_unlocked(payload)
        start_clock = self._parse_clock(settings["work_start"], "10:00")
        end_clock = self._parse_clock(settings["work_end"], "20:00")
        step = timedelta(minutes=settings["slot_minutes"])
        start = datetime.combine(day, start_clock, self.tz)
        work_end = datetime.combine(day, end_clock, self.tz)
        now = self.now()
        events: list[tuple[dict[str, Any], datetime, datetime]] = []
        for event in payload.get("events", []):
            parsed = self._event_datetimes(event)
            if parsed:
                events.append((event, parsed[0], parsed[1]))
        breaks = self._breaks_for_day(settings, day)
        slots: list[dict[str, Any]] = []
        while start + step <= work_end:
            end = start + step
            event = next((item for item, item_start, item_end in events if self._overlaps(start, end, item_start, item_end)), None)
            on_break = any(self._overlaps(start, end, break_start, break_end) for break_start, break_end in breaks)
            status = "free"
            if on_break:
                status = "break"
            elif event is not None:
                status = "busy"
            elif start <= now:
                status = "past"
            slots.append({
                "start": start.isoformat(timespec="minutes"),
                "end": end.isoformat(timespec="minutes"),
                "time": start.strftime("%H:%M"),
                "status": status,
                "event": event,
            })
            start = end
        return slots

    def settings(self) -> dict[str, Any]:
        with self._lock:
            return self._settings_unlocked(self._read_unlocked())

    def snapshot(self, day_value: str | None = None) -> dict[str, Any]:
        with self._lock:
            payload = self._read_unlocked()
            settings = self._settings_unlocked(payload)
            day = self._parse_day(day_value, self.today())
            events = []
            for event in payload.get("events", []):
                item = dict(event)
                parsed = self._event_datetimes(item)
                if parsed:
                    item["start"] = parsed[0].isoformat(timespec="minutes")
                    item["end"] = parsed[1].isoformat(timespec="minutes")
                events.append(item)
            return {
                "timezone": "Europe/Moscow",
                "today": self.today().isoformat(),
                "selectedDate": day.isoformat(),
                "settings": settings,
                "slots": self._slots_unlocked(payload, day),
                "events": sorted(events, key=lambda item: str(item.get("start", ""))),
            }

    def update_settings(self, work_start: str, work_end: str, breaks: str, slot_minutes: int = 20) -> dict[str, Any]:
        with self._lock:
            payload = self._read_unlocked()
            settings = self._settings_unlocked(payload)
            start = self._parse_clock(work_start, settings["work_start"])
            end = self._parse_clock(work_end, settings["work_end"])
            if start >= end:
                raise ValueError("Начало рабочего дня должно быть раньше конца.")
            settings["work_start"] = start.strftime("%H:%M")
            settings["work_end"] = end.strftime("%H:%M")
            settings["breaks"] = breaks
            try:
                settings["slot_minutes"] = max(10, min(120, int(slot_minutes)))
            except (TypeError, ValueError):
                settings["slot_minutes"] = 20
            payload["settings"] = self._settings_unlocked({"settings": settings})
            self._save_unlocked(payload)
            return self.snapshot()

    def available_slots(self, day_value: str | None = None, limit: int = 1, exclude: set[str] | None = None) -> list[dict[str, Any]]:
        with self._lock:
            payload = self._read_unlocked()
            day = self._parse_day(day_value, self.today())
            excluded = exclude or set()
            return [
                slot for slot in self._slots_unlocked(payload, day)
                if slot["status"] == "free" and slot["start"] not in excluded
            ][:max(1, min(240, limit))]

    def reserve(self, start_value: str, title: str, phone: str, duration_minutes: int = 30) -> dict[str, Any] | None:
        with self._lock:
            payload = self._read_unlocked()
            try:
                start = datetime.fromisoformat(start_value)
            except ValueError:
                return None
            if start.tzinfo is None:
                start = start.replace(tzinfo=self.tz)
            start = start.astimezone(self.tz).replace(second=0, microsecond=0)
            end = start + timedelta(minutes=max(15, min(120, int(duration_minutes))))
            settings = self._settings_unlocked(payload)
            day_slots = self._slots_unlocked(payload, start.date())
            matching = next((slot for slot in day_slots if slot["start"] == start.isoformat(timespec="minutes")), None)
            if matching is None or matching["status"] != "free":
                return None
            event = {
                "id": uuid.uuid4().hex,
                "start": start.isoformat(timespec="minutes"),
                "end": end.isoformat(timespec="minutes"),
                "title": _normalize_text(title)[:180] or "Собеседование",
                "phone": re.sub(r"\D", "", _normalize_text(phone))[:30],
                "status": "scheduled",
                "createdAt": self.now().isoformat(timespec="seconds"),
                "timezone": settings["timezone"],
            }
            payload["events"].append(event)
            self._save_unlocked(payload)
            return event

    def delete(self, event_id: str) -> dict[str, Any]:
        with self._lock:
            payload = self._read_unlocked()
            payload["events"] = [item for item in payload.get("events", []) if str(item.get("id")) != event_id]
            self._save_unlocked(payload)
            return self.snapshot()

    @staticmethod
    def _time_words(value: str) -> str:
        hours = {
            0: "двенадцать", 1: "час", 2: "два", 3: "три", 4: "четыре", 5: "пять",
            6: "шесть", 7: "семь", 8: "восемь", 9: "девять", 10: "десять", 11: "одиннадцать",
            12: "двенадцать", 13: "тринадцать", 14: "четырнадцать", 15: "пятнадцать",
            16: "шестнадцать", 17: "семнадцать", 18: "восемнадцать", 19: "девятнадцать",
            20: "двадцать", 21: "двадцать один", 22: "двадцать два", 23: "двадцать три",
        }
        try:
            hour, minute = (int(part) for part in value.split(":", 1))
        except (TypeError, ValueError):
            return value
        if minute == 0:
            return f"{hours.get(hour, str(hour))} часов"
        if minute == 30:
            return f"{hours.get(hour, str(hour))} тридцать"
        minute_words = {
            10: "десять", 20: "двадцать", 30: "тридцать", 40: "сорок", 50: "пятьдесят",
        }
        if minute in minute_words:
            return f"{hours.get(hour, str(hour))} {minute_words[minute]}"
        return f"{hours.get(hour, str(hour))} часов {minute} минут"

    @staticmethod
    def _date_words(value: date) -> str:
        ordinals = {
            1: "первого", 2: "второго", 3: "третьего", 4: "четвёртого", 5: "пятого",
            6: "шестого", 7: "седьмого", 8: "восьмого", 9: "девятого", 10: "десятого",
            11: "одиннадцатого", 12: "двенадцатого", 13: "тринадцатого", 14: "четырнадцатого",
            15: "пятнадцатого", 16: "шестнадцатого", 17: "семнадцатого", 18: "восемнадцатого",
            19: "девятнадцатого", 20: "двадцатого", 21: "двадцать первого", 22: "двадцать второго",
            23: "двадцать третьего", 24: "двадцать четвёртого", 25: "двадцать пятого",
            26: "двадцать шестого", 27: "двадцать седьмого", 28: "двадцать восьмого",
            29: "двадцать девятого", 30: "тридцатого", 31: "тридцать первого",
        }
        months = (
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря",
        )
        return f"{ordinals.get(value.day, str(value.day))} {months[value.month - 1]}"

    def offer_text(
        self,
        slots: list[dict[str, Any]],
        prefix: str = "Сегодня",
        requested_minutes: int | None = None,
    ) -> str:
        if not slots:
            return MANGO_SCHEDULE_UNAVAILABLE
        if len(slots) == 1:
            slot = slots[0]
            time_words = self._time_words(slot["time"])
            slot_minutes = MangoCallService._slot_minutes(slot["time"])
            if requested_minutes is not None and slot_minutes != requested_minutes:
                return (
                    f"{prefix}, к сожалению, желаемое время занято. Ближайшее свободное окно — "
                    f"{time_words} по московскому времени. Записать вас на это время?"
                )
            return (
                f"{prefix} на {time_words} есть свободное окно. "
                f"Записать вас на собеседование на {time_words} по московскому времени?"
            )

        if requested_minutes is not None:
            intro = f"{prefix}, к сожалению, желаемое время занято."
        else:
            intro = f"{prefix} доступны ближайшие свободные варианты."
        labels = ("Первый вариант", "Второй вариант", "Третий вариант")
        options = "; ".join(
            f"{labels[index]} — {self._time_words(slot['time'])}"
            for index, slot in enumerate(slots)
        )
        return f"{intro} Могу предложить: {options}. Какой вариант вам подойдёт?"


class InterviewReminderService:
    """Send one Telegram reminder ten minutes before a still-booked interview."""

    def __init__(self, calendar: InterviewCalendarService) -> None:
        self.calendar = calendar
        self._lock = RLock()
        self._timers: dict[str, tuple[str, Timer]] = {}

    def schedule(self, candidate: dict[str, Any], config: dict[str, Any]) -> bool:
        event_id = _normalize_text(str(candidate.get("scheduled_event_id", "")))
        scheduled_at = _normalize_text(str(candidate.get("scheduled_at", "")))
        call_id = _normalize_text(str(candidate.get("call_id", "")))
        if not event_id or not scheduled_at or not call_id:
            return False
        if not _normalize_text(str(config.get("telegram_bot_token", ""))) or not _normalize_text(
            str(config.get("telegram_chat_ids", ""))
        ):
            return False
        try:
            start = datetime.fromisoformat(scheduled_at).astimezone(self.calendar.tz)
        except (TypeError, ValueError):
            logging.warning("Interview reminder skipped: invalid appointment time.")
            return False
        remaining = (start - self.calendar.now()).total_seconds()
        if remaining <= 0:
            return False
        delay = max(0.0, remaining - 10 * 60)
        with self._lock:
            existing = self._timers.get(call_id)
            if existing and existing[0] == event_id:
                return True
            if existing:
                existing[1].cancel()
            timer = Timer(
                delay,
                self._send_if_still_booked,
                args=(call_id, event_id, dict(candidate), dict(config)),
            )
            timer.daemon = True
            self._timers[call_id] = (event_id, timer)
            timer.start()
        logging.info("Telegram interview reminder scheduled for call %s in %.0f seconds.", call_id, delay)
        return True

    @staticmethod
    def _message(candidate: dict[str, Any], start: datetime, now: datetime) -> str:
        minutes = max(0, math.ceil((start - now).total_seconds() / 60))
        if minutes:
            timing = f"через {minutes} минут"
        else:
            timing = "скоро"
        name = _normalize_text(str(candidate.get("name", ""))) or "Имя не указано"
        phone = _normalize_text(str(candidate.get("number", "")))
        day = "сегодня" if start.date() == now.date() else InterviewCalendarService._date_words(start.date())
        clock = start.strftime("%H:%M")
        lines = [f"Напоминание: онлайн-собеседование в Zoom {timing}.", f"Кандидат: {name}"]
        if phone:
            lines.append(f"Телефон: {phone}")
        lines.append(f"Время: {day}, {clock} по Москве.")
        return "\n".join(lines)

    def _send_if_still_booked(
        self,
        call_id: str,
        event_id: str,
        candidate: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        with self._lock:
            current = self._timers.get(call_id)
            if not current or current[0] != event_id:
                return
            self._timers.pop(call_id, None)
        try:
            start = datetime.fromisoformat(str(candidate["scheduled_at"])).astimezone(self.calendar.tz)
            events = self.calendar.snapshot(start.date().isoformat()).get("events", [])
            if not any(
                str(event.get("id", "")) == event_id and event.get("status") == "scheduled"
                for event in events
            ):
                logging.info("Skipping reminder for cancelled or changed interview %s.", event_id)
                return
            message = self._message(candidate, start, self.calendar.now())
            if not MangoCallService._notify_telegram(config, message):
                logging.warning("Telegram interview reminder could not be delivered for event %s.", event_id)
        except Exception:  # noqa: BLE001
            logging.exception("Could not send Telegram interview reminder")


calendar_service = InterviewCalendarService(INTERVIEW_CALENDAR_FILE)
interview_reminder_service = InterviewReminderService(calendar_service)
tts_service = LocalVoiceService(VOICE_DIR)
gigaam_stt_service = GigaAmSttService(GIGAAM_CACHE_DIR, GIGAAM_BUNDLED_DIR)
silero_tts_service = SileroTtsService(tts_service)
rvc_service = RvcPostProcessor(RVC_DIR)
qwen_llm_service = LocalQwenService(QWEN_BUNDLED_DIR)
llm_service = OpenAICompatService()
audio_service = AudioRoutingService(AUDIO_ROUTING_FILE)
call_service = MangoCallService(audio_service)
vision_inbox_service = VisionInboxService(VISION_STATE_FILE)
if os.getenv("VOICEBRIDGE_DISABLE_STARTUP_WARMUPS") != "1":
    gigaam_stt_service.start_warmup()
    silero_tts_service.start_warmup()
    audio_service.start_vad_warmup()
    if DEFAULT_LLM_BASE_URL == LOCAL_LLM_BASE_URL:
        app.add_event_handler("startup", qwen_llm_service.start_warmup)
atexit.register(qwen_llm_service.stop)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(STATIC_DIR / "styles.css", media_type="text/css")


@app.get("/app.js")
def javascript() -> FileResponse:
    return FileResponse(STATIC_DIR / "app.js", media_type="application/javascript")


FULLCALENDAR_ASSETS = {
    "fullcalendar.bundle.js",
    "core.min.js",
    "daygrid.min.js",
    "timegrid.min.js",
    "interaction.min.js",
    "list.min.js",
    "locales-all.min.js",
}


@app.get("/vendor/fullcalendar.bundle.js")
def fullcalendar_bundle() -> FileResponse:
    return FileResponse(STATIC_DIR / "vendor" / "fullcalendar.bundle.js", media_type="application/javascript")


@app.get("/vendor/fullcalendar/{asset_name}")
def fullcalendar_asset(asset_name: str) -> FileResponse:
    if asset_name not in FULLCALENDAR_ASSETS:
        raise HTTPException(status_code=404, detail="FullCalendar asset not found.")
    asset_path = STATIC_DIR / "vendor" / asset_name
    if asset_name != "fullcalendar.bundle.js":
        asset_path = STATIC_DIR / "vendor" / "fullcalendar" / asset_name
    return FileResponse(asset_path, media_type="application/javascript")


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return {
        "defaultTtsLanguage": DEFAULT_TTS_LANGUAGE,
        "ttsLanguages": SILERO_TTS_LANGUAGES,
        "ttsLanguageNames": SILERO_TTS_LANGUAGE_NAMES,
        "ttsSpeakers": SILERO_TTS_SPEAKERS,
        "ttsSpeakerNames": SILERO_TTS_SPEAKER_NAMES,
        "ttsEngine": "Silero TTS v5.5",
        "defaultTtsModel": DEFAULT_SILERO_TTS_MODEL,
        "ttsModels": [{
            "id": DEFAULT_SILERO_TTS_MODEL,
            "label": "Silero v5.5 · PyTorch",
            "download": "русский v5.5 + английский v3",
            "supportsInstruct": False,
        }],
        "ttsDevice": tts_service.device_info(),
        "ttsQuantization": silero_tts_service.quantization_info(),
        "flashAttentionAvailable": False,
        "ttsInstalled": silero_tts_service.installed(),
        "rvc": rvc_service.status(),
        "audioRouting": audio_service.settings(),
        "audioDevices": audio_service.list_devices(),
        "call": call_service.status(),
        "defaultLanguage": DEFAULT_LANGUAGE,
        "defaultSttModel": DEFAULT_STT_MODEL,
        "sttModels": STT_MODELS,
        "sttModelNames": {
            "whisper-large-v3-turbo": "Groq Whisper large-v3 Turbo · API",
            "whisper-large-v3": "Groq Whisper large-v3 · API",
            LOCAL_STT_MODEL: "GigaAM v2 CTC · локально / ONNX",
        },
        "gigaamStt": gigaam_stt_service.info(),
        "groqConfigured": bool(os.getenv("GROQ_API_KEY")),
        "defaultLlmProvider": "local-qwen3-1.7b" if DEFAULT_LLM_BASE_URL == LOCAL_LLM_BASE_URL else "openai-compatible",
        "llmProviders": [
            {"id": "local-qwen3-1.7b", "label": "Qwen3 1.7B · локально / llama.cpp"},
            {"id": "openai-compatible", "label": "OpenAI-compatible API"},
        ],
        "localLlm": qwen_llm_service.info(),
        "defaultLlmBaseUrl": DEFAULT_LLM_BASE_URL,
        "defaultLlmModel": DEFAULT_LLM_MODEL,
        "defaultSystemPrompt": DEFAULT_SYSTEM_PROMPT,
        "savedAudio": active_audio_info(),
        "storage": {kind: storage_info(kind) for kind in STORAGE_DIRS},
        "vpn": vpn_service.status(),
        "calendar": calendar_service.snapshot(),
    }


@app.get("/api/system")
def get_system_status() -> dict[str, Any]:
    return system_status()


@app.get("/api/audio/devices")
def get_audio_devices() -> dict[str, Any]:
    return audio_service.list_devices()


@app.get("/api/audio/settings")
def get_audio_settings() -> dict[str, Any]:
    return audio_service.settings()


@app.post("/api/audio/settings")
def set_audio_settings(
    output_device: str = Form(""),
    loopback_device: str = Form(""),
) -> dict[str, Any]:
    return audio_service.set_settings(output_device, loopback_device)


@app.post("/api/audio/test")
def test_audio_route(output_device: str = Form("")) -> dict[str, Any]:
    try:
        audio_service.play_test_tone(output_device)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Audio route test failed")
        raise HTTPException(status_code=503, detail=f"Не удалось проиграть тестовый звук: {exc}") from exc
    return {"ok": True, "message": "Тестовый звук отправлен в выбранный TTS-выход."}


@app.get("/api/call/status")
def get_call_status() -> dict[str, Any]:
    return call_service.status()


@app.post("/api/telegram/test")
def test_telegram_notifications(
    bot_token: str = Form(""),
    chat_ids: str = Form(""),
) -> dict[str, Any]:
    token = _normalize_text(bot_token)
    try:
        ids = _telegram_chat_ids(chat_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    failures = _send_telegram_messages(token, ids, "Voice Bridge: тестовое уведомление подключено.")
    if failures:
        raise HTTPException(status_code=502, detail=failures[0])
    return {"ok": True, "recipients": len(ids)}


@app.get("/api/call/candidates")
def get_candidate_records() -> dict[str, Any]:
    try:
        if not CANDIDATE_RECORDS_FILE.exists():
            return {"items": []}
        payload = json.loads(CANDIDATE_RECORDS_FILE.read_text(encoding="utf-8"))
        return {"items": payload if isinstance(payload, list) else []}
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Не удалось прочитать записи кандидатов.") from exc


@app.get("/api/calendar")
def get_calendar(day: str = "") -> dict[str, Any]:
    return calendar_service.snapshot(day or None)


@app.post("/api/calendar/settings")
def save_calendar_settings(
    work_start: str = Form("10:00"),
    work_end: str = Form("20:00"),
    breaks: str = Form("13:00-14:00"),
    slot_minutes: int = Form(20),
) -> dict[str, Any]:
    try:
        return calendar_service.update_settings(work_start, work_end, breaks, slot_minutes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/calendar/events")
def create_calendar_event(
    day: str = Form(...),
    clock: str = Form(...),
    title: str = Form("Собеседование"),
    phone: str = Form(""),
    duration: int = Form(30),
) -> dict[str, Any]:
    selected_day = calendar_service._parse_day(day, calendar_service.today())
    start_clock = calendar_service._parse_clock(clock, "10:00")
    start = datetime.combine(selected_day, start_clock, calendar_service.tz)
    event = calendar_service.reserve(start.isoformat(timespec="minutes"), title, phone, duration)
    if event is None:
        raise HTTPException(status_code=409, detail="Этот слот уже занят, прошёл или попадает в перерыв.")
    return calendar_service.snapshot(selected_day.isoformat())


@app.post("/api/calendar/busy")
def mark_calendar_slot_busy(
    day: str = Form(...),
    clock: str = Form(...),
    duration: int = Form(20),
) -> dict[str, Any]:
    """Mark one calendar slot as manually occupied from the calendar UI."""
    selected_day = calendar_service._parse_day(day, calendar_service.today())
    start_clock = calendar_service._parse_clock(clock, "10:00")
    start = datetime.combine(selected_day, start_clock, calendar_service.tz)
    event = calendar_service.reserve(start.isoformat(timespec="minutes"), "Занято вручную", "", duration)
    if event is None:
        raise HTTPException(status_code=409, detail="Этот слот уже занят, прошёл или попадает в перерыв.")
    return calendar_service.snapshot(selected_day.isoformat())


@app.delete("/api/calendar/events/{event_id}")
def delete_calendar_event(event_id: str) -> dict[str, Any]:
    return calendar_service.delete(event_id)


@app.post("/api/dialog/turn")
def process_dialog_turn(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Run one test-dialog turn through the same script engine as Mango."""
    transcript = _normalize_text(str(payload.get("transcript", "")))
    if not transcript:
        raise HTTPException(status_code=400, detail="Реплика кандидата не может быть пустой.")
    raw_candidate = payload.get("candidate")
    candidate = dict(raw_candidate) if isinstance(raw_candidate, dict) else _new_candidate_record("")
    candidate.setdefault("turns", [])
    candidate.setdefault("result", "in_progress")
    stage = _normalize_text(str(payload.get("stage", "relevance"))) or "relevance"
    if stage == "consent":
        # Compatibility with an already-open browser tab using the old flow.
        stage = "relevance"
    candidate["consent_to_continue"] = True
    history = payload.get("history")
    dialogue_history = history if isinstance(history, list) else []
    dialogue_history = [
        {"role": str(item.get("role", "")), "text": str(item.get("text", ""))}
        for item in dialogue_history
        if isinstance(item, dict) and item.get("text")
    ]
    # The browser appends the current candidate turn before calling this
    # endpoint; it is also sent separately as `transcript`. Do not feed it to
    # the model twice, otherwise a short local model can mistake the duplicate
    # for an echo or a second answer.
    if dialogue_history and _normalize_text(dialogue_history[-1].get("text", "")) == transcript:
        dialogue_history.pop()
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    _record_candidate_turn(candidate, stage, transcript)
    llm_intent = call_service._classify_candidate_intent(
        stage,
        transcript,
        dialogue_history,
        config,
    )
    reply, next_stage, should_hangup = MangoCallService._script_candidate_reply(
        stage,
        transcript,
        candidate,
        dialogue_history,
        llm_intent,
    )
    if call_service._dynamic_reply_needed(stage, transcript, reply) and not llm_intent.get("short_reply"):
        dynamic_reply = call_service._dynamic_candidate_reply(
            stage,
            transcript,
            reply,
            candidate,
            dialogue_history,
            config,
        )
        if dynamic_reply:
            reply = dynamic_reply
    candidate["stage"] = next_stage
    candidate["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    _refresh_candidate_report(candidate)
    return {
        "reply": reply,
        "nextStage": next_stage,
        "ends": should_hangup,
        "candidate": candidate,
        "report": candidate.get("report", ""),
    }


@app.post("/api/dialog/report")
def send_dialog_test_report(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Send the final report from a user-started test dialogue to Telegram."""
    raw_candidate = payload.get("candidate")
    if not isinstance(raw_candidate, dict):
        raise HTTPException(status_code=400, detail="Нет данных тестового диалога для отчёта.")
    candidate = dict(raw_candidate)
    if not (
        candidate.get("consent_to_continue")
        and candidate.get("scheduled_at")
        and candidate.get("scheduled_event_id")
    ):
        raise HTTPException(
            status_code=409,
            detail="Отчёт отправляется только после согласия кандидата и подтверждённой записи на собеседование.",
        )
    turns = candidate.get("turns")
    if not isinstance(turns, list) or not turns:
        raise HTTPException(status_code=400, detail="В тестовом диалоге пока нет реплик кандидата.")
    report = _refresh_candidate_report(candidate)
    token = _normalize_text(str(payload.get("bot_token", "")))
    try:
        chat_ids = _telegram_chat_ids(str(payload.get("chat_ids", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    failures = _send_telegram_messages(token, chat_ids, report)
    if failures:
        raise HTTPException(status_code=502, detail=failures[0])
    return {"ok": True, "recipients": len(chat_ids), "report": report}


@app.post("/api/call/start")
def start_call(
    number: str = Form(...),
    candidate_name: str = Form(""),
    stt_api_key: str = Form(""),
    stt_model: str = Form(DEFAULT_STT_MODEL),
    stt_language: str = Form("auto"),
    llm_api_key: str = Form(""),
    llm_base_url: str = Form(DEFAULT_LLM_BASE_URL),
    llm_model: str = Form(DEFAULT_LLM_MODEL),
    system_prompt: str = Form(DEFAULT_SYSTEM_PROMPT),
    temperature: float = Form(0.4),
    tts_language: str = Form(DEFAULT_TTS_LANGUAGE),
    tts_speaker: str = Form(""),
    pace: float = Form(1.0),
    output_device: str = Form(""),
    loopback_device: str = Form(""),
    listen_seconds: float = Form(60.0),
    call_timeout: float = Form(60.0),
    use_vpn_stt: bool = Form(False),
    use_vpn_llm: bool = Form(False),
    thinking: bool = Form(False),
    telegram_bot_token: str = Form(""),
    telegram_chat_ids: str = Form(""),
) -> dict[str, Any]:
    return call_service.start(
        number=number,
        candidate_name=candidate_name,
        stt_api_key=stt_api_key,
        stt_model=stt_model,
        stt_language=stt_language,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        system_prompt=system_prompt,
        temperature=temperature,
        tts_language=tts_language,
        tts_speaker=tts_speaker,
        pace=pace,
        output_device=output_device,
        loopback_device=loopback_device,
        listen_seconds=listen_seconds,
        call_timeout=call_timeout,
        use_vpn_stt=use_vpn_stt,
        use_vpn_llm=use_vpn_llm,
        thinking=thinking,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_ids=telegram_chat_ids,
    )


@app.post("/api/call/stop")
def stop_call() -> dict[str, Any]:
    return call_service.stop()


@app.post("/api/call/sms")
def send_call_sms(
    number: str = Form(""),
    message: str = Form(""),
) -> dict[str, Any]:
    digits = re.sub(r"\D", "", _normalize_text(number))
    if len(digits) < 5:
        digits = str(call_service.status().get("number", ""))
    if len(digits) < 5:
        raise HTTPException(status_code=400, detail="Введи номер, для которого нужно отправить SMS.")
    return call_service.send_sms(digits, message)


@app.post("/api/voice")
def upload_voice(file: UploadFile = File(...)) -> dict[str, Any]:
    return tts_service.save_reference(file.filename or "", file.file.read())


@app.post("/api/voice/reference")
def upload_reference(file: UploadFile = File(...), reference_text: str = Form("")) -> dict[str, Any]:
    reference_text = _normalize_text(reference_text)
    if not reference_text:
        raise HTTPException(status_code=400, detail="Укажи точный текст референсной записи.")
    if len(reference_text) > 4000:
        raise HTTPException(status_code=400, detail="Reference transcript is too long.")
    saved = tts_service.save_reference(file.filename or "", file.file.read())
    tts_service.save_reference_text(reference_text)
    return {
        **saved,
        "referenceText": tts_service.reference_text(),
        "ready": True,
    }


@app.post("/api/voice/text")
def save_voice_text(reference_text: str = Form("")) -> dict[str, Any]:
    if len(reference_text) > 4000:
        raise HTTPException(status_code=400, detail="Reference transcript is too long.")
    tts_service.save_reference_text(reference_text)
    return {
        "referenceText": tts_service.reference_text(),
        "promptCached": tts_service.active_voice_path() is not None and bool(tts_service.reference_text()),
    }


@app.post("/api/voice/delete")
def delete_voice() -> dict[str, Any]:
    return tts_service.delete_reference()


@app.post("/api/tts/device")
def set_tts_device(device: str = Form(...)) -> dict[str, Any]:
    return tts_service.set_device(device)


@app.post("/api/rvc/settings")
def set_rvc_settings(
    enabled: bool = Form(False),
    command_template: str = Form(""),
) -> dict[str, Any]:
    return rvc_service.set_settings(enabled, command_template)


@app.post("/api/rvc/upload")
def upload_rvc(
    model: UploadFile = File(...),
    index: UploadFile | None = File(None),
) -> dict[str, Any]:
    index_filename = index.filename if index is not None else ""
    index_bytes = index.file.read() if index is not None else b""
    return rvc_service.save_files(
        model.filename or "",
        model.file.read(),
        index_filename or "",
        index_bytes,
    )


@app.post("/api/rvc/delete")
def delete_rvc() -> dict[str, Any]:
    return rvc_service.delete_files()


@app.post("/api/audio")
def upload_audio(file: UploadFile = File(...)) -> dict[str, Any]:
    return save_active_audio(file.filename or "", file.content_type or "", file.file.read())


@app.get("/api/audio")
def get_audio_info() -> dict[str, Any]:
    return active_audio_info()


@app.get("/api/audio/file")
def get_audio_file() -> FileResponse:
    path = active_audio_path()
    if path is None:
        raise HTTPException(status_code=404, detail="No saved input audio.")
    info = active_audio_info()
    return FileResponse(
        path,
        media_type=info.get("contentType") or "application/octet-stream",
        filename=info["name"],
    )


@app.post("/api/audio/delete")
def delete_audio() -> dict[str, Any]:
    return delete_active_audio()


@app.post("/api/storage/open")
def open_storage(kind: str = Form(...)) -> dict[str, Any]:
    if kind not in STORAGE_DIRS:
        raise HTTPException(status_code=400, detail="Unknown storage folder.")
    path = STORAGE_DIRS[kind]
    path.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == "nt":
            subprocess.Popen(
                ["explorer.exe", str(path)],
                creationflags=0x08000000,
            )
        elif os.name == "posix":
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not open folder: {exc}") from exc
    return storage_info(kind)


@app.post("/api/storage/clear")
def clear_storage(kind: str = Form(...)) -> dict[str, Any]:
    if kind not in {"voices", "audio", "outputs"}:
        raise HTTPException(status_code=400, detail="This folder cannot be cleared from the app.")
    if kind == "voices":
        tts_service.delete_reference()
    elif kind == "audio":
        delete_active_audio()
    else:
        clear_storage_files(OUTPUT_DIR)
    return storage_info(kind)


@app.get("/api/vpn/status")
def get_vpn_status() -> dict[str, Any]:
    return vpn_service.status()


@app.post("/api/vpn/download")
def download_vpn_client() -> dict[str, Any]:
    try:
        return vpn_service.download()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/vpn/start")
def start_vpn() -> dict[str, Any]:
    try:
        return vpn_service.start()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/vpn/stop")
def stop_vpn() -> dict[str, Any]:
    return vpn_service.stop()


@app.post("/api/transcribe")
def transcribe(
    file: UploadFile = File(...),
    api_key: str = Form(""),
    model: str = Form(DEFAULT_STT_MODEL),
    language: str = Form(DEFAULT_LANGUAGE),
    prompt: str = Form(""),
    use_vpn: bool = Form(False),
) -> dict[str, Any]:
    model = _normalize_text(model) or DEFAULT_STT_MODEL
    if model not in STT_MODELS:
        raise HTTPException(status_code=400, detail="Unsupported STT model.")

    if model == LOCAL_STT_MODEL:
        file.file.seek(0)
        audio_bytes = file.file.read()
        try:
            text, duration = gigaam_stt_service.transcribe(audio_bytes)
        except Exception as exc:  # noqa: BLE001
            logging.exception("GigaAM transcription failed")
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {
            "text": text,
            "language": "ru",
            "duration": duration,
            "model": model,
            "provider": "local-onnx",
            "words": [],
            "raw": {},
        }

    token = _normalize_text(api_key) or _normalize_text(os.getenv("GROQ_API_KEY", ""))
    if not token:
        raise HTTPException(status_code=400, detail="Groq API key is required.")

    language = _normalize_text(language)
    if language.lower() == "auto":
        language = ""

    data: list[tuple[str, str]] = [("model", model), ("response_format", "json")]
    if language:
        data.append(("language", language))
    if _normalize_text(prompt):
        data.append(("prompt", prompt.strip()))

    file.file.seek(0)
    files = {
        "file": (
            file.filename or "recording.webm",
            file.file,
            file.content_type or "application/octet-stream",
        )
    }

    try:
        proxy = vpn_proxy(use_vpn)
        response = requests.post(
            GROQ_STT_URL,
            headers={"Authorization": f"Bearer {token}"},
            data=data,
            files=files,
            timeout=300,
            **request_proxy_kwargs(proxy),
        )
    except requests.RequestException as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Failed to reach Groq STT.") from exc

    if not response.ok:
        detail: Any
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    payload = response.json()
    return {
        "text": payload.get("text", ""),
        "language": payload.get("language"),
        "duration": payload.get("duration"),
        "model": model,
        "words": payload.get("words", []),
        "raw": payload,
    }


@app.get("/api/vision/state")
def vision_state() -> dict[str, Any]:
    return vision_inbox_service.state()


@app.post("/api/vision/analyze")
def vision_analyze(
    images: list[UploadFile] = File(...),
    prompt: str = Form(""),
    api_key: str = Form(""),
    base_url: str = Form(""),
    model: str = Form(""),
    use_vpn_vision: bool = Form(False),
    use_vpn: bool = Form(False),
) -> dict[str, Any]:
    return vision_inbox_service.analyze(
        images,
        prompt,
        api_key,
        base_url,
        model,
        use_vpn_vision or use_vpn,
    )


@app.post("/api/vision/queue/add")
def vision_queue_add(
    name: str = Form(""),
    number: str = Form(...),
) -> dict[str, Any]:
    return vision_inbox_service.add_contact(name, number)


@app.post("/api/vision/queue/delete")
def vision_queue_delete(contact_id: str = Form(...)) -> dict[str, Any]:
    return vision_inbox_service.delete(contact_id)


@app.post("/api/vision/queue/move")
def vision_queue_move(
    contact_id: str = Form(...),
    direction: str = Form(...),
) -> dict[str, Any]:
    return vision_inbox_service.move_contact(contact_id, direction)


@app.post("/api/vision/queue/clear")
def vision_queue_clear() -> dict[str, Any]:
    return vision_inbox_service.clear_queue()


@app.post("/api/vision/history/clear")
def vision_history_clear() -> dict[str, Any]:
    return vision_inbox_service.clear_history()


@app.post("/api/chat")
def chat(
    text: str = Form(...),
    api_key: str = Form(""),
    base_url: str = Form(DEFAULT_LLM_BASE_URL),
    model: str = Form(DEFAULT_LLM_MODEL),
    system_prompt: str = Form(DEFAULT_SYSTEM_PROMPT),
    temperature: float = Form(0.4),
    use_vpn: bool = Form(False),
    thinking: bool = Form(False),
    history: str = Form(""),
) -> dict[str, Any]:
    return llm_service.chat(
        base_url,
        api_key,
        model,
        text,
        system_prompt,
        temperature,
        use_vpn,
        thinking,
        history=_parse_chat_history(history),
    )


@app.post("/api/chat/stream")
def chat_stream(
    text: str = Form(...),
    api_key: str = Form(""),
    base_url: str = Form(DEFAULT_LLM_BASE_URL),
    model: str = Form(DEFAULT_LLM_MODEL),
    system_prompt: str = Form(DEFAULT_SYSTEM_PROMPT),
    temperature: float = Form(0.4),
    use_vpn: bool = Form(False),
    thinking: bool = Form(False),
    history: str = Form(""),
) -> StreamingResponse:
    response = llm_service.open_stream(
        base_url,
        api_key,
        model,
        text,
        system_prompt,
        temperature,
        use_vpn,
        thinking,
        history=_parse_chat_history(history),
    )
    return StreamingResponse(
        llm_service.iter_stream(response),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/speak")
def speak(
    text: str = Form(...),
    tts_language: str = Form(DEFAULT_TTS_LANGUAGE),
    pace: float = Form(1.0),
    tts_mode: str = Form("speaker"),
    tts_model: str = Form(DEFAULT_SILERO_TTS_MODEL),
    tts_speaker: str = Form(""),
    tts_instruct: str = Form(""),
    tts_temperature: float = Form(0.7),
    tts_top_p: float = Form(0.8),
    tts_top_k: int = Form(50),
    tts_max_new_tokens: int = Form(384),
) -> Response:
    fixed_lines = {
        MANGO_GREETING, MANGO_GREETING_AFTER_NAME, MANGO_WRONG_RECIPIENT,
        MANGO_ALTERNATE_CANDIDATE_ASK, MANGO_ALTERNATE_CANDIDATE_NAME,
        MANGO_GOODBYE, MANGO_RELEVANCE_REPROMPT, MANGO_INTERESTED_OPENING,
        MANGO_AGE_CITY, MANGO_INTERESTED_WITH_AGE,
        MANGO_COMPUTER, MANGO_CITIZENSHIP, MANGO_EMPLOYMENT, MANGO_WORK_DETAILS, MANGO_JOB_DESCRIPTION,
        MANGO_JOB_OVERVIEW, MANGO_JOB_OVERVIEW_FOLLOWUP, MANGO_JOB_CONDITIONS,
        MANGO_JOB_INTRO, MANGO_NOT_SUITABLE, MANGO_FOREIGN_ANSWER, MANGO_SALARY_ANSWER,
        MANGO_CITIZENSHIP_ANSWER, MANGO_COMPUTER_ANSWER, MANGO_ZOOM_CAMERA_ANSWER,
        MANGO_DEEP_ANSWER, MANGO_ZOOM, MANGO_TELEGRAM, MANGO_FINAL,
    }
    if text.strip() in fixed_lines:
        wav_bytes = silero_tts_service.synthesize_script(text, tts_language, pace, speaker=tts_speaker)
    else:
        wav_bytes = silero_tts_service.synthesize(
            text,
            tts_language,
            pace,
            mode=tts_mode,
            model_size=tts_model,
            speaker=tts_speaker,
            instruct=tts_instruct,
            temperature=tts_temperature,
            top_p=tts_top_p,
            top_k=tts_top_k,
            max_new_tokens=tts_max_new_tokens,
        )
    saved = save_generated_audio(wav_bytes)
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "Content-Disposition": 'inline; filename="speech.wav"',
            "X-Saved-Audio": saved["name"],
        },
    )


@app.post("/api/speak/batch")
def speak_batch(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="Batch items are required.")
    wavs = silero_tts_service.synthesize_batch(items)
    encoded: list[dict[str, str]] = []
    for wav_bytes in wavs:
        saved = save_generated_audio(wav_bytes)
        encoded.append({
            "audio": base64.b64encode(wav_bytes).decode("ascii"),
            "name": saved["name"],
        })
    return {"items": encoded}


@app.post("/api/bridge")
def bridge(
    file: UploadFile = File(...),
    groq_api_key: str = Form(""),
    stt_model: str = Form(DEFAULT_STT_MODEL),
    language: str = Form(DEFAULT_LANGUAGE),
    prompt: str = Form(""),
    llm_api_key: str = Form(""),
    llm_base_url: str = Form(DEFAULT_LLM_BASE_URL),
    llm_model: str = Form(DEFAULT_LLM_MODEL),
    system_prompt: str = Form(DEFAULT_SYSTEM_PROMPT),
    temperature: float = Form(0.4),
    tts_language: str = Form(DEFAULT_TTS_LANGUAGE),
    pace: float = Form(1.0),
    tts_mode: str = Form("speaker"),
    tts_model: str = Form(DEFAULT_SILERO_TTS_MODEL),
    tts_speaker: str = Form(""),
    tts_instruct: str = Form(""),
    tts_temperature: float = Form(0.7),
    tts_top_p: float = Form(0.8),
    tts_top_k: int = Form(50),
    tts_max_new_tokens: int = Form(384),
    vpn_for_stt: bool = Form(False),
    vpn_for_llm: bool = Form(False),
) -> Response:
    transcript = transcribe(
        file=file,
        api_key=groq_api_key,
        model=stt_model,
        language=language,
        prompt=prompt,
        use_vpn=vpn_for_stt,
    )
    reply = chat(
        text=transcript["text"],
        api_key=llm_api_key,
        base_url=llm_base_url,
        model=llm_model,
        system_prompt=system_prompt,
        temperature=temperature,
        use_vpn=vpn_for_llm,
    )
    wav_bytes = silero_tts_service.synthesize(
        reply["text"],
        tts_language,
        pace,
        mode=tts_mode,
        model_size=tts_model,
        speaker=tts_speaker,
        instruct=tts_instruct,
        temperature=tts_temperature,
        top_p=tts_top_p,
        top_k=tts_top_k,
        max_new_tokens=tts_max_new_tokens,
    )
    saved = save_generated_audio(wav_bytes)
    headers = {
        "X-Transcript": transcript["text"],
        "X-Reply": reply["text"],
        "Content-Disposition": 'inline; filename="speech.wav"',
        "X-Saved-Audio": saved["name"],
    }
    return Response(content=wav_bytes, media_type="audio/wav", headers=headers)
