// The same UI runs in a browser during development and inside the Tauri shell.
// Tauri serves static files locally, so API requests must target the backend.
const isLocalBackendPage = ["127.0.0.1", "localhost"].includes(location.hostname);
const tauriInvoke = window.__TAURI__?.core?.invoke;
// In development the frontend and backend intentionally share the same
// localhost port. The Rust port command is only authoritative in the
// packaged Tauri window, where the frontend is served from tauri.localhost.
const backendBasePromise = tauriInvoke && !isLocalBackendPage
  ? tauriInvoke("backend_port").then((port) => `http://127.0.0.1:${port}`)
  : isLocalBackendPage
    ? Promise.resolve("")
    : Promise.resolve("http://127.0.0.1:8000");
const apiFetch = async (input, init) => {
  const apiBase = await backendBasePromise;
  const target = typeof input === "string" && input.startsWith("/") ? `${apiBase}${input}` : input;
  return window.fetch(target, init);
};

const els = {
  status: document.getElementById("status"),
  apiKey: document.getElementById("apiKey"),
  language: document.getElementById("language"),
  sttModel: document.getElementById("sttModel"),
  sttModelHelp: document.getElementById("sttModelHelp"),
  llmProvider: document.getElementById("llmProvider"),
  localLlmState: document.getElementById("localLlmState"),
  llmThinking: document.getElementById("llmThinking"),
  llmBaseUrl: document.getElementById("llmBaseUrl"),
  llmApiKey: document.getElementById("llmApiKey"),
  llmModel: document.getElementById("llmModel"),
  systemPrompt: document.getElementById("systemPrompt"),
  ttsModel: document.getElementById("ttsModel"),
  ttsModelHelp: document.getElementById("ttsModelHelp"),
  ttsLanguage: document.getElementById("ttsLanguage"),
  ttsSpeaker: document.getElementById("ttsSpeaker"),
  rvcEnabled: document.getElementById("rvcEnabled"),
  rvcModelFile: document.getElementById("rvcModelFile"),
  rvcIndexFile: document.getElementById("rvcIndexFile"),
  saveRvcBtn: document.getElementById("saveRvcBtn"),
  deleteRvcBtn: document.getElementById("deleteRvcBtn"),
  openRvcFolderBtn: document.getElementById("openRvcFolderBtn"),
  rvcState: document.getElementById("rvcState"),
  rvcCommandTemplate: document.getElementById("rvcCommandTemplate"),
  ttsTemperature: document.getElementById("ttsTemperature"),
  ttsTemperatureValue: document.getElementById("ttsTemperatureValue"),
  ttsTopK: document.getElementById("ttsTopK"),
  pace: document.getElementById("pace"),
  transcript: document.getElementById("transcript"),
  reply: document.getElementById("reply"),
  detectedLang: document.getElementById("detectedLang"),
  duration: document.getElementById("duration"),
  player: document.getElementById("player"),
  recordBtn: document.getElementById("recordBtn"),
  stopBtn: document.getElementById("stopBtn"),
  transcribeBtn: document.getElementById("transcribeBtn"),
  speakBtn: document.getElementById("speakBtn"),
  bridgeBtn: document.getElementById("bridgeBtn"),
  mangoCandidateName: document.getElementById("mangoCandidateName"),
  mangoNumber: document.getElementById("mangoNumber"),
  mangoListenSeconds: document.getElementById("mangoListenSeconds"),
  mangoStartBtn: document.getElementById("mangoStartBtn"),
  mangoStopBtn: document.getElementById("mangoStopBtn"),
  mangoSmsMessage: document.getElementById("mangoSmsMessage"),
  mangoSmsBtn: document.getElementById("mangoSmsBtn"),
  telegramBotToken: document.getElementById("telegramBotToken"),
  telegramChatIds: document.getElementById("telegramChatIds"),
  telegramTestBtn: document.getElementById("telegramTestBtn"),
  dialogTestName: document.getElementById("dialogTestName"),
  dialogTestInput: document.getElementById("dialogTestInput"),
  dialogTestBtn: document.getElementById("dialogTestBtn"),
  voiceDialogMaxSeconds: document.getElementById("voiceDialogMaxSeconds"),
  voiceDialogStartBtn: document.getElementById("voiceDialogStartBtn"),
  voiceDialogStopBtn: document.getElementById("voiceDialogStopBtn"),
  voiceDialogState: document.getElementById("voiceDialogState"),
  mangoCallState: document.getElementById("mangoCallState"),
  candidateStage: document.getElementById("candidateStage"),
  candidateName: document.getElementById("candidateName"),
  candidateAgeCity: document.getElementById("candidateAgeCity"),
  candidateComputer: document.getElementById("candidateComputer"),
  candidateCitizenship: document.getElementById("candidateCitizenship"),
  candidateEmployment: document.getElementById("candidateEmployment"),
  candidateStudyFormat: document.getElementById("candidateStudyFormat"),
  candidateWorkDetails: document.getElementById("candidateWorkDetails"),
  candidateObjection: document.getElementById("candidateObjection"),
  candidateReport: document.getElementById("candidateReport"),
  callIndicator: document.getElementById("callIndicator"),
  callTimer: document.getElementById("callTimer"),
  audioOutputDevice: document.getElementById("audioOutputDevice"),
  audioLoopbackDevice: document.getElementById("audioLoopbackDevice"),
  audioDeviceState: document.getElementById("audioDeviceState"),
  refreshAudioDevicesBtn: document.getElementById("refreshAudioDevicesBtn"),
  testAudioRouteBtn: document.getElementById("testAudioRouteBtn"),
  saveAudioSettingsBtn: document.getElementById("saveAudioSettingsBtn"),
  openAudioFolderBtn: document.getElementById("openAudioFolderBtn"),
  deleteAudioBtn: document.getElementById("deleteAudioBtn"),
  openOutputFolderBtn: document.getElementById("openOutputFolderBtn"),
  deleteOutputsBtn: document.getElementById("deleteOutputsBtn"),
  openModelFolderBtn: document.getElementById("openModelFolderBtn"),
  outputStorageState: document.getElementById("outputStorageState"),
  modelStorageState: document.getElementById("modelStorageState"),
  fileInput: document.getElementById("fileInput"),
  paceValue: document.getElementById("paceValue"),
  inputAudioState: document.getElementById("inputAudioState"),
  vpnEnabled: document.getElementById("vpnEnabled"),
  vpnForStt: document.getElementById("vpnForStt"),
  vpnForLlm: document.getElementById("vpnForLlm"),
  vpnState: document.getElementById("vpnState"),
  vpnIndicator: document.getElementById("vpnIndicator"),
  vpnStartBtn: document.getElementById("vpnStartBtn"),
  vpnStopBtn: document.getElementById("vpnStopBtn"),
  vpnDownloadBtn: document.getElementById("vpnDownloadBtn"),
  ttsDeviceLabel: document.getElementById("ttsDeviceLabel"),
  ttsDeviceSwitch: document.getElementById("ttsDeviceSwitch"),
  ttsDeviceHelp: document.getElementById("ttsDeviceHelp"),
  settingsDialog: document.getElementById("settingsDialog"),
  settingsBtn: document.getElementById("settingsBtn"),
  closeSettingsBtn: document.getElementById("closeSettingsBtn"),
  doneSettingsBtn: document.getElementById("doneSettingsBtn"),
  cpuMetricValue: document.getElementById("cpuMetricValue"),
  cpuMetricBar: document.getElementById("cpuMetricBar"),
  cpuMetricMeta: document.getElementById("cpuMetricMeta"),
  memoryMetricValue: document.getElementById("memoryMetricValue"),
  memoryMetricBar: document.getElementById("memoryMetricBar"),
  memoryMetricMeta: document.getElementById("memoryMetricMeta"),
  gpuMetricValue: document.getElementById("gpuMetricValue"),
  gpuMetricBar: document.getElementById("gpuMetricBar"),
  gpuMetricMeta: document.getElementById("gpuMetricMeta"),
  pipelineStage: document.getElementById("pipelineStage"),
  pipelineProgress: document.getElementById("pipelineProgress"),
  pipelineMessage: document.getElementById("pipelineMessage"),
  activityCard: document.querySelector(".activity-card"),
  visionBaseUrl: document.getElementById("visionBaseUrl"),
  visionApiKey: document.getElementById("visionApiKey"),
  visionModel: document.getElementById("visionModel"),
  visionChat: document.getElementById("visionChat"),
  visionDropzone: document.getElementById("visionDropzone"),
  visionFileInput: document.getElementById("visionFileInput"),
  visionPending: document.getElementById("visionPending"),
  visionPrompt: document.getElementById("visionPrompt"),
  visionUseVpn: document.getElementById("visionUseVpn"),
  visionAnalyzeBtn: document.getElementById("visionAnalyzeBtn"),
  visionClearHistoryBtn: document.getElementById("visionClearHistoryBtn"),
  visionQueue: document.getElementById("visionQueue"),
  visionClearQueueBtn: document.getElementById("visionClearQueueBtn"),
  calendarDate: document.getElementById("calendarDate"),
  calendarView: document.getElementById("calendarView"),
  calendarWorkStart: document.getElementById("calendarWorkStart"),
  calendarWorkEnd: document.getElementById("calendarWorkEnd"),
  calendarBreaks: document.getElementById("calendarBreaks"),
  calendarSlotMinutes: document.getElementById("calendarSlotMinutes"),
  calendarRefreshBtn: document.getElementById("calendarRefreshBtn"),
  calendarSaveSettingsBtn: document.getElementById("calendarSaveSettingsBtn"),
  calendarSlots: document.getElementById("calendarSlots"),
  calendarTitle: document.getElementById("calendarTitle"),
  calendarPhone: document.getElementById("calendarPhone"),
  calendarBookBtn: document.getElementById("calendarBookBtn"),
  calendarEvents: document.getElementById("calendarEvents"),
};

const state = {
  mediaRecorder: null,
  mediaStream: null,
  chunks: [],
  recordedFile: null,
  currentObjectUrl: null,
  savedAudio: null,
  storage: {},
  vpnStatus: null,
  ttsDevice: null,
  ttsQuantization: {},
  ttsSpeakers: {},
  ttsSpeakerNames: {},
  rvc: {},
  calendar: null,
  calendarInstance: null,
  calendarFallback: false,
  calendarFallbackView: "month",
  calendarRendering: false,
  calendarSelectedSlot: "",
  calendarBackendConnected: false,
  calendarRetryTimer: null,
  calendarRequest: false,
  audioDevices: null,
  callStatus: null,
  callTimer: null,
  callRequest: false,
  voiceDialogRunning: false,
  voiceDialogStream: null,
  voiceDialogRecorder: null,
  voiceDialogPlaybackCancel: null,
  voiceDialogGeneration: 0,
  voiceDialogTurns: 0,
  voiceDialogHistory: [],
  voiceDialogCandidate: {},
  voiceDialogReportSent: false,
  voiceDialogStage: "relevance",
  activeOperation: false,
  systemTimer: null,
  systemRequest: false,
  visionFiles: [],
  visionState: { history: [], queue: [] },
};
const VISION_PROMPT_VERSION = "2";
const DEFAULT_VISION_PROMPT = "Найди на изображении всех людей, у которых указан полный номер телефона. Для каждого человека определи только его ФИО и относящийся к нему номер. Не добавляй города, организации, должности и людей без полного номера.";
const CALL_SCRIPT_VERSION = "12";
const TEST_GREETING = "Добрый день! Я ассистент HR-менеджера Яны из компании «Лекс-Торг». Звоню по поводу вакансии. Подскажите, актуален ли вам сейчас поиск работы?";
const MANGO_GOODBYE = "Поняла, спасибо за ответ. Всего доброго.";
const MANGO_RELEVANCE_REPROMPT = "Подскажите, актуально?";
const MANGO_INTERESTED_OPENING = "Отлично! Позвольте уточнить несколько моментов.";
const MANGO_AGE_CITY = "Уточните ваш возраст и город проживания?";
const MANGO_INTERESTED_WITH_AGE = `${MANGO_INTERESTED_OPENING} ${MANGO_AGE_CITY}`;
const MANGO_COMPUTER = "У вас есть ноутбук или компьютер для удалённой работы?";
const MANGO_CITIZENSHIP = "Гражданство у вас Российской Федерации?";
const MANGO_EMPLOYMENT = "Есть ли у вас сейчас учёба или работа?";
const MANGO_JOB_DESCRIPTION = "Ещё раз напомню, звоню из компании «Лекс-Торг», мы рекрутинговая компания. К нам поступил запрос на должность: персональный инвестиционный советник из компании «Баланс». Эта должность подразумевает работу с клиентами. Трудоустройство по трудовому договору или договору гражданско-правового характера. Предусмотрена только полная занятость, работа полностью удалённая. График: пять на два, с десяти до двадцати по московскому времени. Средняя заработная плата от ста десяти тысяч рублей. Такие условия для себя рассматриваете?";
const MANGO_JOB_INTRO = `Тогда я коротко введу вас в курс дела. ${MANGO_JOB_DESCRIPTION}`;
const MANGO_NOT_SUITABLE = "Подскажите, что именно вам не подходит?";
const MANGO_FOREIGN_ANSWER = "Да, можно работать из-за границы.";
const MANGO_SALARY_ANSWER = "Заработная плата складывается из фиксированного оклада и неограниченного процента. В среднем в первый месяц около ста десяти тысяч рублей. Подробнее могу рассказать уже на собеседовании.";
const MANGO_CITIZENSHIP_ANSWER = "Нет, обязательно быть гражданином Российской Федерации не нужно.";
const MANGO_COMPUTER_ANSWER = "Да, обязательно работать с компьютера или ноутбука.";
const MANGO_ZOOM_CAMERA_ANSWER = "Да, нужны будут камера и микрофон. Можете не переживать, это всё конфиденциально и между нами.";
const MANGO_DEEP_ANSWER = "Подробные детали обсуждаются на собеседовании. Оно занимает около десяти минут, и на него можно зайти с компьютера или телефона.";
const MANGO_ZOOM = "Спасибо! Тогда я предлагаю перейти на следующий этап — онлайн-собеседование в зум. Само собеседование займёт всего десять-пятнадцать минут. Я расскажу об обязанностях и условиях. Сможете подключиться?";
const MANGO_TELEGRAM = "Сможете сейчас найти мой аккаунт в телеграме?";
const MANGO_TELEGRAM_PERMISSION = "Скажите, пожалуйста, когда можно продиктовать никнейм?";
const MANGO_TELEGRAM_HANDLE = "Никнейм по буквам. Первая буква — икс. Вторая буква — икс. Третья буква — эйч. Четвёртая буква — ар. Цифра — один. Удалось найти аккаунт?";
const MANGO_TELEGRAM_SEND = "Отлично. Отправьте мне любое сообщение в телеграме, чтобы я могла связаться с вами. Скажите, когда отправите.";
const MANGO_FINAL = "Спасибо за уделённое время, до скорой встречи!";

function isInitialDecline(text) {
  const normalized = String(text || "").toLowerCase().trim();
  if (!normalized || isJobQuestion(normalized)) return false;
  return /(?:^|[^\p{L}])нет(?:$|[^\p{L}])|не актуальн|неактуальн|не интересн|неинтересн|не подход|не хочу|не буду|отказ/u.test(normalized);
}

function testCandidateGreeting(name = "") {
  const cleanName = String(name || "").replace(/\s+/g, " ").trim();
  return cleanName
    ? `Добрый день! Это ${cleanName}?`
    : TEST_GREETING;
}

function isJobQuestion(text) {
  const normalized = String(text || "").toLowerCase();
  if (/что за работа|расскажите о работе|какая работа|что нужно делать|обязанност|ваканс/.test(normalized)) return true;
  return /(?:расскажите|уточните|какие|что за|подробнее).*услов/.test(normalized);
}

function isGreetingOnly(text) {
  const normalized = String(text || "").toLowerCase().trim();
  if (!normalized || /(?:^|[^\p{L}])(?:да|актуально|интересно|подходит|расскажите|какая работа|что за работа)(?:$|[^\p{L}])/u.test(normalized)) return false;
  return /^(?:привет|здравствуйте|добрый день|добрый вечер|алло)[\s,!.?\-]*$/.test(normalized);
}

function isInitialAffirmative(text) {
  const normalized = String(text || "").toLowerCase().trim();
  if (!normalized || isInitialDecline(normalized) || isGreetingOnly(normalized)) return false;
  if (isJobQuestion(normalized)) return false;
  return /(?:^|[^\p{L}])да(?:$|[^\p{L}])|ага|угу|актуальн|интересн|подход|конечно|согласен|согласна|рассматрива|готов|давайте/.test(normalized);
}

function hasAffirmativeMarker(text) {
  const normalized = String(text || "").toLowerCase().trim();
  return /(?:^|[^\p{L}])да(?:$|[^\p{L}])|ага|угу|актуальн|интересн|подход|конечно|согласен|согласна|рассматрива|готов|давайте|почему бы и нет|можно/u.test(normalized);
}

function scriptedObjection(text) {
  const normalized = String(text || "").toLowerCase();
  if (isJobQuestion(normalized)) return "";
  if (/телеграм|никнейм|ник|логин/.test(normalized) && /заглавн|строчн|больш|маленьк|регистр/.test(normalized)) {
    return "Можно писать заглавными или строчными — регистр в телеграме не важен. В нике два икса, английская эйч и английская ар, затем цифра один. Икс — как крестик; эйч — не русская эн, ар — не русская эр.";
  }
  if (/телеграм|никнейм|ник|логин/.test(normalized) && /букв|эйч|икс|ар|эр/.test(normalized)) {
    return "В нике два икса, английская эйч и английская ар, затем цифра один. Икс — как крестик; эйч — не русская эн, ар — не русская эр.";
  }
  if (/из-за границы|за границей|из другой страны|иностран/.test(normalized)) return MANGO_FOREIGN_ANSWER;
  if (/зарплат|заработн|оклад|процент|доход|сколько плат|\bзп\b/.test(normalized)) return MANGO_SALARY_ANSWER;
  if (/гражданств|гражданином|паспорт/.test(normalized) && /обязательно/.test(normalized)) return MANGO_CITIZENSHIP_ANSWER;
  if (/компьютер|ноутбук|телефон/.test(normalized) && /обязательно|нужен|можно с телефона/.test(normalized)) return MANGO_COMPUTER_ANSWER;
  if (/zoom|зум|камер|микрофон/.test(normalized)) return MANGO_ZOOM_CAMERA_ANSWER;
  if (/[?]/.test(text) || /почему|как проходит|какие документы|подробн/.test(normalized)) return MANGO_DEEP_ANSWER;
  return "";
}

function scriptedReply(stage, text) {
  const normalized = String(text || "").toLowerCase().trim();
  if (stage === "consent") stage = "relevance";
  if (stage === "relevance") {
    if (isInitialDecline(normalized)) return { reply: MANGO_GOODBYE, next: "finished", ends: true };
    if (isJobQuestion(normalized)) return { reply: MANGO_JOB_DESCRIPTION, next: "conditions_before_details", ends: false };
    if (isInitialAffirmative(normalized)) return { reply: MANGO_INTERESTED_WITH_AGE, next: "age_city", ends: false };
    const objection = scriptedObjection(normalized);
    if (objection) return { reply: objection, next: "relevance", ends: false };
    return { reply: MANGO_RELEVANCE_REPROMPT, next: "relevance", ends: false };
  }
  if (stage === "age_city") {
    if (isJobQuestion(normalized)) return { reply: MANGO_JOB_DESCRIPTION, next: "conditions_resume_age_city", ends: false };
    const objection = scriptedObjection(normalized);
    if (objection) return { reply: objection, next: "age_city", ends: false };
    return { reply: MANGO_COMPUTER, next: "computer", ends: false };
  }
  if (stage === "computer") {
    if (isJobQuestion(normalized)) return { reply: MANGO_JOB_DESCRIPTION, next: "conditions_resume_computer", ends: false };
    const objection = scriptedObjection(normalized);
    if (objection) return { reply: objection, next: "computer", ends: false };
    return { reply: MANGO_CITIZENSHIP, next: "citizenship", ends: false };
  }
  if (stage === "citizenship") {
    const objection = scriptedObjection(normalized);
    if (objection) return { reply: objection, next: "citizenship", ends: false };
    return { reply: MANGO_EMPLOYMENT, next: "employment", ends: false };
  }
  if (stage === "employment") {
    const objection = scriptedObjection(normalized);
    if (objection) return { reply: objection, next: "employment", ends: false };
    return { reply: MANGO_JOB_INTRO, next: "conditions", ends: false };
  }
  if (stage === "conditions_before_details") {
    if (isInitialDecline(normalized)) return { reply: MANGO_NOT_SUITABLE, next: "conditions_followup", ends: false };
    const objection = scriptedObjection(normalized);
    if (objection) return { reply: objection, next: "conditions_before_details", ends: false };
    return { reply: MANGO_INTERESTED_WITH_AGE, next: "age_city", ends: false };
  }
  if (stage === "conditions_resume_age_city") {
    if (isInitialDecline(normalized)) return { reply: MANGO_NOT_SUITABLE, next: "conditions_followup", ends: false };
    const objection = scriptedObjection(normalized);
    if (objection) return { reply: objection, next: "conditions_resume_age_city", ends: false };
    return { reply: MANGO_INTERESTED_WITH_AGE, next: "age_city", ends: false };
  }
  if (stage === "conditions_resume_computer") {
    if (isInitialDecline(normalized)) return { reply: MANGO_NOT_SUITABLE, next: "conditions_followup", ends: false };
    const objection = scriptedObjection(normalized);
    if (objection) return { reply: objection, next: "conditions_resume_computer", ends: false };
    return { reply: MANGO_COMPUTER, next: "computer", ends: false };
  }
  if (stage === "conditions") {
    if (isInitialDecline(normalized)) return { reply: MANGO_NOT_SUITABLE, next: "conditions_followup", ends: false };
    const objection = scriptedObjection(normalized);
    if (objection) return { reply: objection, next: "conditions", ends: false };
    if (hasAffirmativeMarker(normalized)) return { reply: MANGO_ZOOM, next: "zoom", ends: false };
    return { reply: MANGO_JOB_DESCRIPTION, next: "conditions", ends: false };
  }
  if (stage === "conditions_followup") return { reply: MANGO_GOODBYE, next: "finished", ends: true };
  if (stage === "zoom") {
    if (isInitialDecline(normalized)) return { reply: MANGO_GOODBYE, next: "finished", ends: true };
    const objection = scriptedObjection(normalized);
    if (objection) return { reply: objection, next: "zoom", ends: false };
    if (isInitialAffirmative(normalized)) return { reply: MANGO_TELEGRAM, next: "telegram", ends: false };
    return { reply: MANGO_ZOOM, next: "zoom", ends: false };
  }
  if (stage === "telegram") {
    if (isInitialAffirmative(normalized)) return { reply: MANGO_TELEGRAM_PERMISSION, next: "telegram_permission", ends: false };
    return { reply: "Хорошо, остаёмся на линии. Скажите, когда будете готовы найти аккаунт?", next: "telegram", ends: false };
  }
  if (stage === "telegram_permission") {
    if (isInitialAffirmative(normalized) || /диктуйте|говорите|сейчас можно|давайте/.test(normalized)) {
      return { reply: MANGO_TELEGRAM_HANDLE, next: "telegram_handle", ends: false };
    }
    return { reply: "Хорошо, подожду. Скажите, когда можно продиктовать никнейм?", next: "telegram_permission", ends: false };
  }
  if (stage === "telegram_handle") {
    if (/нашёл|нашел|нашла|нашли/.test(normalized) || isInitialAffirmative(normalized)) {
      return { reply: MANGO_TELEGRAM_SEND, next: "telegram_send", ends: false };
    }
    return { reply: MANGO_TELEGRAM_HANDLE, next: "telegram_handle", ends: false };
  }
  if (stage === "telegram_send") {
    if (/отправил|отправила|написал|написала|готово|получилось/.test(normalized) || isInitialAffirmative(normalized)) {
      return { reply: MANGO_FINAL, next: "finished", ends: true };
    }
    return { reply: "Подождём, пока вы отправите сообщение. Напишите любое слово и скажите, когда будет готово.", next: "telegram_send", ends: false };
  }
  return { reply: MANGO_RELEVANCE_REPROMPT, next: "relevance", ends: false };
}

const VOICE_DIALOG_CONTEXT =
  "Это голосовой тест рекрутингового звонка. Приложение уже представило Яну и спросило, актуальна ли вакансия. " +
  "Не повторяй приветствие. Обрабатывай только последнюю реплику кандидата и уважай отказ продолжать. " +
  "Сценарий фиксированный: после положительного ответа спроси по одному возраст и город, компьютер или ноутбук, гражданство, учёбу или работу. " +
  "Если спросил о вакансии, произнеси только заготовленные условия. Не повторяй историю, не придумывай факты и не выдавай весь сценарий сразу.";

function setStatus(message, kind = "idle") {
  els.status.textContent = message;
  els.status.dataset.kind = kind;
}

function saveVisionPrefs() {
  localStorage.setItem("voicebridge.visionBaseUrl", els.visionBaseUrl?.value || "");
  localStorage.setItem("voicebridge.visionApiKey", els.visionApiKey?.value || "");
  localStorage.setItem("voicebridge.visionModel", els.visionModel?.value || "");
  localStorage.setItem("voicebridge.visionPrompt", els.visionPrompt?.value || "");
  localStorage.setItem("voicebridge.visionUseVpn", els.visionUseVpn?.checked ? "1" : "0");
  localStorage.setItem("voicebridge.visionPromptVersion", VISION_PROMPT_VERSION);
}

function renderVisionPending() {
  if (!els.visionPending) return;
  els.visionPending.replaceChildren();
  for (const [index, file] of state.visionFiles.entries()) {
    const tile = document.createElement("figure");
    tile.className = "vision-pending-tile";
    const preview = document.createElement("img");
    preview.className = "vision-pending-preview";
    preview.alt = file.name || `image-${index + 1}`;
    if (!file.__visionPreviewUrl) file.__visionPreviewUrl = URL.createObjectURL(file);
    preview.src = file.__visionPreviewUrl;
    const caption = document.createElement("figcaption");
    caption.textContent = file.name || `image-${index + 1}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "vision-pending-remove";
    remove.textContent = "×";
    remove.title = "Удалить изображение";
    remove.setAttribute("aria-label", `Удалить ${file.name || "изображение"}`);
    remove.addEventListener("click", () => {
      if (file.__visionPreviewUrl) URL.revokeObjectURL(file.__visionPreviewUrl);
      state.visionFiles.splice(index, 1);
      renderVisionPending();
    });
    tile.append(preview, caption, remove);
    els.visionPending.appendChild(tile);
  }
}

function addVisionFiles(files) {
  const images = Array.from(files || []).filter((file) => file.type.startsWith("image/"));
  if (!images.length) return;
  const known = new Set(state.visionFiles.map((file) => `${file.name}:${file.size}`));
  state.visionFiles.push(...images.filter((file) => !known.has(`${file.name}:${file.size}`)).slice(0, 12 - state.visionFiles.length));
  renderVisionPending();
  setStatus(`${state.visionFiles.length} изображений готовы к анализу.`);
}

function renderVisionHistory() {
  if (!els.visionChat) return;
  els.visionChat.replaceChildren();
  const history = state.visionState?.history || [];
  if (!history.length) {
    const empty = document.createElement("div");
    empty.className = "vision-empty";
    empty.textContent = "Вставь сюда скриншот или фото с именами и номерами через Ctrl+V.";
    els.visionChat.appendChild(empty);
    return;
  }
  for (const message of history) {
    const card = document.createElement("article");
    card.className = "vision-message";
    card.dataset.role = message.role || "assistant";
    const head = document.createElement("div");
    head.className = "vision-message-head";
    head.textContent = message.role === "user" ? "Ты" : "Vision модель";
    if (Array.isArray(message.contacts) && message.contacts.length) head.textContent += ` · найдено ${message.contacts.length}`;
    const text = document.createElement("div");
    text.className = "vision-message-text";
    text.textContent = message.text || "";
    card.append(head, text);
    if (Array.isArray(message.images) && message.images.length) {
      const images = document.createElement("div");
      images.className = "vision-image-list";
      for (const image of message.images) {
        const chip = document.createElement("span");
        chip.className = "vision-image-chip";
        chip.textContent = image.name || "image";
        images.appendChild(chip);
      }
      card.appendChild(images);
    }
    if (message.role === "assistant" && Array.isArray(message.contacts) && message.contacts.length) {
      const foundContacts = document.createElement("div");
      foundContacts.className = "vision-found-contacts";
      for (const contact of message.contacts) {
        const row = document.createElement("div");
        row.className = "vision-found-contact";
        const label = document.createElement("span");
        label.textContent = `${contact.name || "Без имени"} · ${contact.number || ""}`;
        const queue = state.visionState?.queue || [];
        const queueIndex = queue.findIndex((item) => item.number === contact.number);
        const queued = document.createElement("span");
        queued.className = "vision-queue-position";
        queued.textContent = queueIndex >= 0 ? `Звонок №${queueIndex + 1}` : "Не в очереди";
        row.append(label, queued);
        foundContacts.appendChild(row);
      }
      card.appendChild(foundContacts);
    }
    els.visionChat.appendChild(card);
  }
  els.visionChat.scrollTop = els.visionChat.scrollHeight;
}

function renderVisionQueue() {
  if (!els.visionQueue) return;
  els.visionQueue.replaceChildren();
  const queue = state.visionState?.queue || [];
  if (!queue.length) {
    const empty = document.createElement("div");
    empty.className = "vision-empty";
    empty.textContent = "Очередь пока пуста.";
    els.visionQueue.appendChild(empty);
    return;
  }
  for (const [index, contact] of queue.entries()) {
    const card = document.createElement("article");
    card.className = "vision-contact";
    const info = document.createElement("div");
    info.className = "vision-contact-info";
    const name = document.createElement("strong");
    name.className = "vision-contact-name";
    name.textContent = contact.name || "Без имени";
    const number = document.createElement("span");
    number.className = "vision-contact-number";
    number.textContent = contact.number || "";
    info.append(name, number);
    const actions = document.createElement("div");
    actions.className = "vision-contact-actions";
    const position = document.createElement("span");
    position.className = "vision-queue-position";
    position.textContent = `№${index + 1}`;
    const moveUp = document.createElement("button");
    moveUp.type = "button";
    moveUp.textContent = "↑";
    moveUp.title = "Поставить раньше";
    moveUp.disabled = index === 0;
    moveUp.addEventListener("click", () => moveVisionContact(contact.id, "up"));
    const moveDown = document.createElement("button");
    moveDown.type = "button";
    moveDown.textContent = "↓";
    moveDown.title = "Поставить позже";
    moveDown.disabled = index === queue.length - 1;
    moveDown.addEventListener("click", () => moveVisionContact(contact.id, "down"));
    const call = document.createElement("button");
    call.type = "button";
    call.textContent = `Звонить №${index + 1}`;
    call.addEventListener("click", () => {
      if (els.mangoCandidateName) els.mangoCandidateName.value = contact.name || "";
      if (els.mangoNumber) els.mangoNumber.value = contact.number || "";
      startMangoCall().catch((error) => setStatus(error.message, "error"));
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.title = "Убрать из очереди";
    remove.addEventListener("click", () => removeVisionContact(contact.id));
    actions.append(position, moveUp, moveDown, call, remove);
    card.append(info, actions);
    els.visionQueue.appendChild(card);
  }
}

async function loadVisionState() {
  const res = await apiFetch("/api/vision/state", { cache: "no-store" });
  if (!res.ok) throw new Error("Vision queue unavailable.");
  state.visionState = await res.json();
  renderVisionHistory();
  renderVisionQueue();
}

async function analyzeVisionImages() {
  if (!state.visionFiles.length) throw new Error("Сначала вставь или добавь изображения.");
  saveVisionPrefs();
  const form = new FormData();
  for (const file of state.visionFiles) form.append("images", file, file.name || "image.png");
  form.append("prompt", els.visionPrompt.value.trim());
  form.append("api_key", els.visionApiKey.value.trim());
  form.append("base_url", els.visionBaseUrl.value.trim());
  form.append("model", els.visionModel.value.trim());
  form.append("use_vpn_vision", String(els.vpnEnabled.checked && els.visionUseVpn.checked));
  els.visionAnalyzeBtn.disabled = true;
  setStatus("Vision модель анализирует изображения…", "working");
  try {
    const res = await apiFetch("/api/vision/analyze", { method: "POST", body: form });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(payload.detail ? JSON.stringify(payload.detail) : "Vision analysis failed.");
    for (const file of state.visionFiles) {
      if (file.__visionPreviewUrl) URL.revokeObjectURL(file.__visionPreviewUrl);
    }
    state.visionFiles = [];
    renderVisionPending();
    state.visionState = payload;
    renderVisionHistory();
    renderVisionQueue();
    setStatus(`Готово. Найдено: ${(payload.contacts || []).length}; контакты автоматически добавлены в очередь.`);
  } finally {
    els.visionAnalyzeBtn.disabled = false;
  }
}

async function addVisionContact(contact, button = null) {
  const form = new FormData();
  form.append("name", contact.name || "Без имени");
  form.append("number", contact.number || "");
  if (button) button.disabled = true;
  try {
    const res = await apiFetch("/api/vision/queue/add", { method: "POST", body: form });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(payload.detail || "Не удалось добавить контакт в очередь.");
    state.visionState = payload;
    renderVisionHistory();
    renderVisionQueue();
    setStatus(payload.added ? `${contact.name || "Контакт"} добавлен в очередь.` : "Контакт уже есть в очереди.");
  } catch (error) {
    if (button) button.disabled = false;
    throw error;
  }
}

async function removeVisionContact(contactId) {
  const form = new FormData();
  form.append("contact_id", contactId);
  const res = await apiFetch("/api/vision/queue/delete", { method: "POST", body: form });
  if (!res.ok) throw new Error("Не удалось удалить контакт.");
  state.visionState = await res.json();
  renderVisionQueue();
}

async function moveVisionContact(contactId, direction) {
  const form = new FormData();
  form.append("contact_id", contactId);
  form.append("direction", direction);
  const res = await apiFetch("/api/vision/queue/move", { method: "POST", body: form });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось изменить порядок очереди.");
  state.visionState = payload;
  renderVisionQueue();
  renderVisionHistory();
}

async function clearVisionQueue() {
  const res = await apiFetch("/api/vision/queue/clear", { method: "POST" });
  if (!res.ok) throw new Error("Не удалось очистить очередь.");
  state.visionState = await res.json();
  renderVisionQueue();
}

async function clearVisionHistory() {
  const res = await apiFetch("/api/vision/history/clear", { method: "POST" });
  if (!res.ok) throw new Error("Не удалось очистить историю Vision.");
  state.visionState = await res.json();
  renderVisionHistory();
}

function formatBytes(bytes = 0) {
  if (!bytes) return "—";
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} GB`;
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

function renderSegments(element, percent, kind = "blue") {
  if (!element) return;
  element.dataset.kind = kind;
  element.innerHTML = "";
  const filled = Number.isFinite(percent) ? Math.round(Math.max(0, Math.min(100, percent)) / 100 * 12) : 0;
  for (let index = 0; index < 12; index += 1) {
    const segment = document.createElement("span");
    segment.classList.toggle("is-filled", index < filled);
    element.appendChild(segment);
  }
}

function renderPipelineActivity(activity) {
  if (!activity) return;
  const progress = Number(activity.progress) || 0;
  const active = Boolean(activity.active);
  const labels = {
    llm: "LLM",
    loading: "Silero загрузка",
    voice_prompt: "Silero загрузка голоса",
    generating: "Silero генерация",
    encoding: "Silero WAV",
    idle: "Готово",
  };
  els.pipelineStage.textContent = labels[activity.phase] || (active ? "TTS" : "Готово");
  els.pipelineProgress.style.width = `${progress}%`;
  els.pipelineMessage.textContent = activity.message || (active ? "Локальная модель работает…" : "Ожидаю запуск.");
  els.activityCard.dataset.phase = activity.phase || "idle";
  if (active && state.activeOperation && activity.message) {
    setStatus(activity.message, "working");
  }
}

function renderSystemStatus(system) {
  const cpu = system?.cpu || {};
  const memory = system?.memory || {};
  const gpu = system?.gpu || {};
  const cpuPercent = Number(cpu.percent);
  const memoryPercent = Number(memory.percent);
  const gpuPercent = Number(gpu.percent);
  els.cpuMetricValue.textContent = Number.isFinite(cpuPercent) ? `${Math.round(cpuPercent)}%` : "—";
  els.cpuMetricMeta.textContent = `${cpu.threads || "—"} потоков · общая загрузка`;
  renderSegments(els.cpuMetricBar, cpuPercent, "blue");
  els.memoryMetricValue.textContent = Number.isFinite(memoryPercent) ? `${Math.round(memoryPercent)}%` : "—";
  els.memoryMetricMeta.textContent = `${formatBytes(memory.used)} из ${formatBytes(memory.total)}`;
  renderSegments(els.memoryMetricBar, memoryPercent, "warm");
  if (gpu.available) {
    els.gpuMetricValue.textContent = Number.isFinite(gpuPercent) ? `${Math.round(gpuPercent)}%` : "ON";
    els.gpuMetricMeta.textContent = `${gpu.name || "NVIDIA"} · ${formatBytes(gpu.memoryUsed)} / ${formatBytes(gpu.memoryTotal)}`;
    renderSegments(els.gpuMetricBar, Number.isFinite(gpuPercent) ? gpuPercent : gpu.memoryPercent, "violet");
  } else {
    els.gpuMetricValue.textContent = "OFF";
    els.gpuMetricMeta.textContent = "NVIDIA/CUDA не обнаружена";
    renderSegments(els.gpuMetricBar, null, "off");
  }
  renderPipelineActivity(system?.tts);
}

async function syncSystemStatus() {
  if (state.systemRequest) return;
  state.systemRequest = true;
  try {
    const res = await apiFetch("/api/system", { cache: "no-store" });
    if (res.ok) renderSystemStatus(await res.json());
  } catch {
    // Monitoring is intentionally best-effort and must never interrupt audio.
  } finally {
    state.systemRequest = false;
  }
}

function startSystemMonitor() {
  syncSystemStatus();
  state.systemTimer = window.setInterval(syncSystemStatus, 800);
}

function ensureLlmThinkingControl() {
  if (els.llmThinking || !els.localLlmState) return;
  const row = document.createElement("div");
  row.className = "toggle-row compact-toggle";
  row.innerHTML = `<span><strong>Thinking / рассуждение</strong><small>Для чата с локальной Qwen. В живых звонках отключён ради скорости ответа.</small></span><input id="llmThinking" type="checkbox" />`;
  els.localLlmState.parentElement?.appendChild(row);
  els.llmThinking = row.querySelector("input");
  els.llmThinking.checked = localStorage.getItem("voicebridge.llmThinking") === "1";
  els.llmThinking.addEventListener("change", () => {
    applyLlmProvider();
    savePrefs();
  });
}

function placeVisionVpnControl() {
  const toggle = els.visionUseVpn?.closest("label");
  const llmRoute = els.vpnForLlm?.closest("label");
  if (!toggle || !llmRoute) return;
  const copy = toggle.querySelector("span");
  const title = copy?.querySelector("strong");
  const help = copy?.querySelector("small");
  if (title) title.textContent = "Vision через VPN";
  if (help) help.textContent = "Отдельный маршрут Vision API через включённый туннель.";
  llmRoute.after(toggle);
  const vpnSection = els.vpnEnabled?.closest(".settings-section");
  const description = vpnSection?.querySelector(".settings-section-title p");
  if (description) description.textContent = "Отдельный маршрут запросов STT, LLM и Vision через туннель.";
}

function applyLlmProvider() {
  const local = !els.llmProvider || els.llmProvider.value === "local-qwen3-1.7b";
  if (els.llmThinking) els.llmThinking.disabled = false;
  if (local) {
    els.llmBaseUrl.value = "local://qwen3-1.7b";
    els.llmApiKey.value = "";
    els.llmModel.value = "Qwen3-1.7B-Q4_K_M.gguf";
    els.llmBaseUrl.disabled = true;
    els.llmApiKey.disabled = true;
    els.llmModel.disabled = true;
    if (els.localLlmState) {
      const thinking = Boolean(els.llmThinking?.checked);
      els.localLlmState.textContent = thinking
        ? "Qwen3 встроена в portable-сборку. Thinking включён: ответы медленнее, но модель сначала рассуждает."
        : "Qwen3 встроена в portable-сборку. Thinking выключен, лимит ответа 384 токена.";
    }
  } else {
    els.llmBaseUrl.disabled = false;
    els.llmApiKey.disabled = false;
    els.llmModel.disabled = false;
    if (els.localLlmState) {
      els.localLlmState.textContent = "Внешняя OpenAI-compatible модель: укажи base URL, ключ и название модели.";
    }
  }
}

function savePrefs() {
  localStorage.setItem("voicebridge.apiKey", els.apiKey.value);
  localStorage.setItem("voicebridge.language", els.language.value);
  localStorage.setItem("voicebridge.sttModel", els.sttModel.value);
  localStorage.setItem("voicebridge.llmProvider", els.llmProvider?.value || "local-qwen3-1.7b");
  localStorage.setItem("voicebridge.llmThinking", els.llmThinking?.checked ? "1" : "0");
  localStorage.setItem("voicebridge.llmBaseUrl", els.llmBaseUrl.value);
  localStorage.setItem("voicebridge.llmApiKey", els.llmApiKey.value);
  localStorage.setItem("voicebridge.llmModel", els.llmModel.value);
  localStorage.setItem("voicebridge.systemPrompt", els.systemPrompt.value);
  localStorage.setItem("voicebridge.callScriptVersion", CALL_SCRIPT_VERSION);
  localStorage.setItem("voicebridge.ttsModel", els.ttsModel.value);
  localStorage.setItem("voicebridge.ttsLanguage", els.ttsLanguage.value);
  localStorage.setItem("voicebridge.ttsSpeaker", els.ttsSpeaker?.value || "");
  localStorage.setItem("voicebridge.ttsTemperature", els.ttsTemperature.value);
  localStorage.setItem("voicebridge.ttsTopK", els.ttsTopK.value);
  localStorage.setItem("voicebridge.pace", els.pace.value);
  localStorage.setItem("voicebridge.vpnEnabled", els.vpnEnabled.checked ? "1" : "0");
  localStorage.setItem("voicebridge.vpnForStt", els.vpnForStt.checked ? "1" : "0");
  localStorage.setItem("voicebridge.vpnForLlm", els.vpnForLlm.checked ? "1" : "0");
  localStorage.setItem("voicebridge.voiceDialogMaxSeconds", els.voiceDialogMaxSeconds?.value || "60");
  localStorage.setItem("voicebridge.telegramBotToken", els.telegramBotToken?.value || "");
  localStorage.setItem("voicebridge.telegramChatIds", els.telegramChatIds?.value || "");
}

function loadPrefs() {
  localStorage.removeItem("voicebridge.ttsEngine");
  els.apiKey.value = localStorage.getItem("voicebridge.apiKey") || "";
  if (els.telegramBotToken) els.telegramBotToken.value = localStorage.getItem("voicebridge.telegramBotToken") || "";
  if (els.telegramChatIds) els.telegramChatIds.value = localStorage.getItem("voicebridge.telegramChatIds") || "";
  els.language.value = localStorage.getItem("voicebridge.language") || "auto";
  els.sttModel.value = localStorage.getItem("voicebridge.sttModel") || "whisper-large-v3-turbo";
  if (els.llmProvider) {
    const savedProvider = localStorage.getItem("voicebridge.llmProvider");
    els.llmProvider.value = savedProvider === "local-qwen3-0.6b"
      ? "local-qwen3-1.7b"
      : (savedProvider || "local-qwen3-1.7b");
  }
  if (els.llmThinking) els.llmThinking.checked = localStorage.getItem("voicebridge.llmThinking") === "1";
  els.llmBaseUrl.value = localStorage.getItem("voicebridge.llmBaseUrl") || "";
  els.llmApiKey.value = localStorage.getItem("voicebridge.llmApiKey") || "";
  els.llmModel.value = localStorage.getItem("voicebridge.llmModel") || "";
  const savedCallScriptVersion = localStorage.getItem("voicebridge.callScriptVersion");
  if (savedCallScriptVersion !== CALL_SCRIPT_VERSION) {
    // Do not let an old, overly long prompt keep overriding the corrected one.
    els.systemPrompt.value = "";
    localStorage.removeItem("voicebridge.systemPrompt");
    localStorage.setItem("voicebridge.callScriptVersion", CALL_SCRIPT_VERSION);
  } else {
    els.systemPrompt.value = localStorage.getItem("voicebridge.systemPrompt") || "";
  }
  els.visionBaseUrl.value = localStorage.getItem("voicebridge.visionBaseUrl") || "https://api.openai.com/v1";
  els.visionApiKey.value = localStorage.getItem("voicebridge.visionApiKey") || "";
  els.visionModel.value = localStorage.getItem("voicebridge.visionModel") || "gpt-4o-mini";
  if (els.visionUseVpn) els.visionUseVpn.checked = localStorage.getItem("voicebridge.visionUseVpn") === "1";
  const savedVisionPromptVersion = localStorage.getItem("voicebridge.visionPromptVersion");
  if (savedVisionPromptVersion !== VISION_PROMPT_VERSION) {
    els.visionPrompt.value = DEFAULT_VISION_PROMPT;
    localStorage.setItem("voicebridge.visionPrompt", DEFAULT_VISION_PROMPT);
    localStorage.setItem("voicebridge.visionPromptVersion", VISION_PROMPT_VERSION);
  } else {
    els.visionPrompt.value = localStorage.getItem("voicebridge.visionPrompt") || DEFAULT_VISION_PROMPT;
  }
  applyLlmProvider();
  els.ttsModel.value = localStorage.getItem("voicebridge.ttsModel") || "silero-v5.5";
  els.ttsLanguage.value = localStorage.getItem("voicebridge.ttsLanguage") || "ru";
  if (els.ttsSpeaker) els.ttsSpeaker.value = localStorage.getItem("voicebridge.ttsSpeaker") || "xenia";
  els.ttsTemperature.value = localStorage.getItem("voicebridge.ttsTemperature") || "0.7";
  els.ttsTopK.value = localStorage.getItem("voicebridge.ttsTopK") || "5";
  els.pace.value = localStorage.getItem("voicebridge.pace") || "1";
  els.vpnEnabled.checked = localStorage.getItem("voicebridge.vpnEnabled") === "1";
  els.vpnForStt.checked = localStorage.getItem("voicebridge.vpnForStt") !== "0";
  els.vpnForLlm.checked = localStorage.getItem("voicebridge.vpnForLlm") !== "0";
  if (els.mangoNumber) els.mangoNumber.value = localStorage.getItem("voicebridge.mangoNumber") || "";
  if (els.mangoCandidateName) els.mangoCandidateName.value = localStorage.getItem("voicebridge.mangoCandidateName") || "";
  if (els.mangoListenSeconds) {
    const savedListenSeconds = localStorage.getItem("voicebridge.mangoListenSeconds");
    const savedVadVersion = localStorage.getItem("voicebridge.callVadVersion");
    // Migrate the old fixed 2.5s chunk setting to the new pause-based default once.
    if (!savedVadVersion && savedListenSeconds && Number(savedListenSeconds) <= 8) {
      els.mangoListenSeconds.value = "60";
      localStorage.setItem("voicebridge.mangoListenSeconds", "60");
    } else {
      const value = Number(savedListenSeconds || 60);
      els.mangoListenSeconds.value = String(Math.max(5, Math.min(60, value)));
    }
    localStorage.setItem("voicebridge.callVadVersion", "1");
  }
  if (els.voiceDialogMaxSeconds) els.voiceDialogMaxSeconds.value = localStorage.getItem("voicebridge.voiceDialogMaxSeconds") || "60";
  if (els.mangoSmsMessage) els.mangoSmsMessage.value = localStorage.getItem("voicebridge.mangoSmsMessage") || "";
  updatePaceLabel();
  updateGenerationLabels();
}

function updatePaceLabel() {
  els.paceValue.textContent = `${Number(els.pace.value).toFixed(2)}×`;
}

function updateGenerationLabels() {
  els.ttsTemperatureValue.textContent = Number(els.ttsTemperature.value).toFixed(2);
}

function updateTtsModelHelp(models = [], quantization = {}) {
  const selected = models.find((model) => model.id === els.ttsModel.value);
  if (!selected || !els.ttsModelHelp) return;
  const quantized = quantization.models?.[selected.id];
  const quantizationLabel = quantized ? ` · GPU: ${quantized.label}` : "";
  els.ttsModelHelp.textContent = `${selected.download || ""} · голос Silero загружается один раз в память.${quantizationLabel}`;
}

function revokePlayerUrl() {
  if (state.currentObjectUrl) {
    URL.revokeObjectURL(state.currentObjectUrl);
    state.currentObjectUrl = null;
  }
}

function fillTtsLanguages(languages = [], names = {}) {
  const current = els.ttsLanguage.value;
  els.ttsLanguage.innerHTML = "";

  for (const language of languages) {
    const option = document.createElement("option");
    option.value = language;
    option.textContent = names[language] || language;
    els.ttsLanguage.appendChild(option);
  }

  if (current && languages.includes(current)) els.ttsLanguage.value = current;
  else if (languages.includes("ru")) els.ttsLanguage.value = "ru";
  else if (languages.length > 0) els.ttsLanguage.value = languages[0];
}

function fillTtsSpeakers(speakers = {}, names = {}) {
  if (!els.ttsSpeaker) return;
  const language = els.ttsLanguage.value || "ru";
  const current = els.ttsSpeaker.value;
  els.ttsSpeaker.innerHTML = "";
  for (const speaker of speakers[language] || []) {
    const option = document.createElement("option");
    option.value = speaker;
    option.textContent = names[speaker] || speaker;
    els.ttsSpeaker.appendChild(option);
  }
  if (current && (speakers[language] || []).includes(current)) els.ttsSpeaker.value = current;
  else if ((speakers[language] || []).length) els.ttsSpeaker.value = speakers[language][0];
}

function renderRvc(rvc = {}) {
  state.rvc = rvc;
  if (!els.rvcEnabled) return;
  els.rvcEnabled.checked = Boolean(rvc.enabled);
  els.rvcCommandTemplate.value = rvc.commandTemplate || "";
  els.deleteRvcBtn.disabled = !rvc.modelName;
  if (rvc.enabled && rvc.degraded) {
    els.rvcState.textContent = rvc.message || "RVC CLI не найден. TTS работает без RVC.";
  } else if (rvc.enabled && !rvc.ready) {
    els.rvcState.textContent = rvc.message || "RVC ещё не готов.";
  } else if (rvc.enabled) {
    els.rvcState.textContent = `RVC включён: ${rvc.modelName}${rvc.indexName ? ` + ${rvc.indexName}` : ""}.`;
  } else if (rvc.modelName) {
    els.rvcState.textContent = `Модель сохранена: ${rvc.modelName}. RVC выключен.`;
  } else {
    els.rvcState.textContent = "RVC отключён.";
  }
}

function renderAudioDevices(payload = {}) {
  state.audioDevices = payload;
  const routing = payload.settings || {};
  const fill = (element, items, selected, fallbackLabel) => {
    if (!element) return;
    element.innerHTML = "";
    const fallback = document.createElement("option");
    fallback.value = "";
    fallback.textContent = fallbackLabel;
    element.appendChild(fallback);
    for (const item of items || []) {
      const option = document.createElement("option");
      option.value = item.id || item.name;
      const role = item.role === "tts-cable-input"
        ? " · TTS → Mango mic"
        : item.role === "stt-cable-loopback"
          ? " · STT вход кабеля"
          : "";
      const hostApi = item.hostApiName ? ` · ${item.hostApiName}` : "";
      option.textContent = `${item.name || item.id} · ${item.sampleRate || 48000} Hz${hostApi}${role}`;
      element.appendChild(option);
    }
    const selectedItem = (items || []).find((item) => String(item.id) === String(selected) || item.name === selected);
    element.value = selectedItem ? String(selectedItem.id) : "";
  };
  fill(els.audioOutputDevice, payload.outputs, routing.output_device, "Системное устройство по умолчанию");
  fill(els.audioLoopbackDevice, payload.loopbacks, routing.loopback_device, "Основной выход Windows");
  if (!els.audioDeviceState) return;
  if (!payload.available) {
    els.audioDeviceState.textContent = payload.error || "Аудиомодуль недоступен. Запусти setup_new_pc.cmd.";
  } else if ((payload.routeWarnings || []).length) {
    els.audioDeviceState.textContent = payload.routeWarnings.join(" ");
  } else if (payload.virtualCableDetected) {
    els.audioDeviceState.textContent = "Устройства найдены. Обнаружен виртуальный кабель.";
  } else {
    els.audioDeviceState.textContent = "Устройства найдены. Для маршрута в Mango установи VB-CABLE или выбери обычный выход.";
  }
}

function renderCallStatus(status = {}) {
  state.callStatus = status;
  const running = Boolean(status.running);
  // Mirror the live phone turn into the same large fields used by the test dialog.
  if (typeof status.transcript === "string" && els.transcript && els.transcript.value !== status.transcript) {
    els.transcript.value = status.transcript;
  }
  if (typeof status.reply === "string" && els.reply && els.reply.value !== status.reply) {
    els.reply.value = status.reply;
  }
  const stateLabels = {
    starting: "Подключение",
    connecting: "Mango подключается",
    dialing: "Набор номера",
    connected: "На линии",
    screening: "Проверка ответа",
    transcribing: "STT слушает",
    thinking: "LLM думает",
    speaking: "TTS говорит",
    stopping: "Завершение",
    error: "Ошибка",
    idle: "OFF",
  };
  if (els.callTimer) {
    const elapsed = Number(status.callElapsedSeconds || 0);
    const minutes = Math.floor(elapsed / 60).toString().padStart(2, "0");
    const seconds = Math.floor(elapsed % 60).toString().padStart(2, "0");
    els.callTimer.textContent = status.remoteAnswered
      ? `${minutes}:${seconds}`
      : running ? "Проверка" : "00:00";
    els.callTimer.dataset.kind = status.remoteAnswered ? "answered" : running ? "waiting" : "idle";
  }
  if (els.callIndicator) {
    els.callIndicator.textContent = stateLabels[status.state] || (running ? "ON" : "OFF");
    els.callIndicator.dataset.kind = status.state === "error" ? "error" : running ? "active" : "idle";
  }
  if (els.mangoCallState) {
    const details = [status.message || "Звонок не запущен."];
    if (running && !status.remoteAnswered) details.push("Жду ответа Mango.");
    else if (running && !status.humanSpeechDetected) details.push("Проверяю, что ответил человек.");
    else if (status.humanSpeechDetected) details.push("Собеседник ответил голосом.");
    if (status.transcript) details.push(`Собеседник: ${status.transcript}`);
    if (status.reply) details.push(`Ответ: ${status.reply}`);
    els.mangoCallState.textContent = details.join(" ");
  }
  renderCandidateData(status.candidate || {}, status.script_stage);
  if (els.mangoStartBtn) els.mangoStartBtn.disabled = running;
  if (els.mangoStopBtn) els.mangoStopBtn.disabled = !running;
  if (running && status.message) setStatus(status.message, "working");
  if (!running && status.state === "error") setStatus(status.message || "Звонок завершился ошибкой.", "error");
}

function renderCandidateData(candidate = {}, stage = "") {
  if (els.candidateStage) els.candidateStage.textContent = stage || candidate.stage || "Ожидание";
  if (els.candidateName) els.candidateName.textContent = candidate.name || "—";
  if (els.candidateAgeCity) els.candidateAgeCity.textContent = candidate.age_city || "—";
  if (els.candidateComputer) els.candidateComputer.textContent = candidate.computer || "—";
  if (els.candidateCitizenship) els.candidateCitizenship.textContent = candidate.citizenship || "—";
  if (els.candidateEmployment) els.candidateEmployment.textContent = candidate.employment || "—";
  if (els.candidateStudyFormat) els.candidateStudyFormat.textContent = candidate.study_format || "—";
  if (els.candidateWorkDetails) els.candidateWorkDetails.textContent = candidate.work_details || "—";
  if (els.candidateObjection) els.candidateObjection.textContent = candidate.objection || "—";
  if (els.candidateReport) els.candidateReport.textContent = candidate.report || "Пока нет ответов кандидата.";
}

function calendarDateKey(value) {
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value)) return value.slice(0, 10);
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (part) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

let calendarInitRetry = 0;
let calendarContextMenu = null;

const calendarMonthNames = [
  "январь", "февраль", "март", "апрель", "май", "июнь",
  "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
];
const calendarWeekdayNames = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"];

function makeCalendarButton(label, className, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function closeCalendarContextMenu() {
  calendarContextMenu?.remove();
  calendarContextMenu = null;
}

function showCalendarSlotMenu(event, slot) {
  event.preventDefault();
  event.stopPropagation();
  closeCalendarContextMenu();

  const menu = document.createElement("div");
  menu.className = "calendar-context-menu";
  menu.setAttribute("role", "menu");

  const heading = document.createElement("strong");
  heading.textContent = `${slot.time || slot.start.slice(11, 16)} · ${slot.status === "free" ? "Свободно" : slot.status === "break" ? "Перерыв" : slot.status === "past" ? "Прошло" : "Занято"}`;
  menu.appendChild(heading);

  const addAction = (label, handler) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", async () => {
      closeCalendarContextMenu();
      try {
        await handler();
      } catch (error) {
        setStatus(error.message, "error");
      }
    });
    menu.appendChild(button);
  };

  if (slot.status === "free") {
    addAction("Выбрать время", () => {
      state.calendarSelectedSlot = slot.start;
      renderCalendar(state.calendar);
      setStatus(`Выбрано время ${slot.time}. Заполни кандидата и нажми бронирование.`, "working");
    });
    addAction("Занято", () => markCalendarSlotBusy(slot.start));
  } else if (slot.event?.id) {
    addAction("Освободить", () => deleteCalendarEvent(slot.event.id));
  }
  addAction("Отмена", () => {});

  document.body.appendChild(menu);
  calendarContextMenu = menu;
  const margin = 8;
  const left = Math.min(event.clientX, window.innerWidth - menu.offsetWidth - margin);
  const top = Math.min(event.clientY, window.innerHeight - menu.offsetHeight - margin);
  menu.style.left = `${Math.max(margin, left)}px`;
  menu.style.top = `${Math.max(margin, top)}px`;
}

document.addEventListener("click", (event) => {
  if (!event.target.closest(".calendar-context-menu")) closeCalendarContextMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeCalendarContextMenu();
});

function renderCalendarFallback(payload = {}) {
  if (!els.calendarView) return;
  state.calendarFallback = true;
  els.calendarView.replaceChildren();

  const selectedKey = payload.selectedDate || calendarDateKey(new Date());
  const selectedDate = new Date(`${selectedKey}T12:00:00`);
  const selectedMonth = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1, 12);
  const shell = document.createElement("div");
  shell.className = "calendar-fallback";

  const toolbar = document.createElement("div");
  toolbar.className = "calendar-fallback-toolbar";
  if (state.calendarFallbackView === "day") {
    toolbar.appendChild(makeCalendarButton("Месяц", "calendar-fallback-back", () => {
      state.calendarFallbackView = "month";
      renderCalendar(state.calendar);
    }));
  } else {
    toolbar.appendChild(document.createElement("span"));
  }
  const title = document.createElement("strong");
  title.textContent = state.calendarFallbackView === "day"
    ? selectedDate.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })
    : `${calendarMonthNames[selectedMonth.getMonth()]} ${selectedMonth.getFullYear()}`;
  toolbar.appendChild(title);
  const navigation = document.createElement("div");
  navigation.className = "calendar-fallback-navigation";
  navigation.appendChild(makeCalendarButton("‹", "calendar-fallback-nav", () => {
    const target = new Date(selectedMonth);
    target.setMonth(target.getMonth() - 1);
    state.calendarFallbackView = "month";
    fetchCalendar(calendarDateKey(target)).catch((error) => setStatus(error.message, "error"));
  }));
  navigation.appendChild(makeCalendarButton("›", "calendar-fallback-nav", () => {
    const target = new Date(selectedMonth);
    target.setMonth(target.getMonth() + 1);
    state.calendarFallbackView = "month";
    fetchCalendar(calendarDateKey(target)).catch((error) => setStatus(error.message, "error"));
  }));
  toolbar.appendChild(navigation);
  shell.appendChild(toolbar);

  if (state.calendarFallbackView === "day") {
    const day = document.createElement("div");
    day.className = "calendar-fallback-day";
    const help = document.createElement("p");
    help.className = "field-help";
    help.textContent = "Свободные окна отмечены синим. Нажми на время, чтобы выбрать его.";
    day.appendChild(help);
    const slots = document.createElement("div");
    slots.className = "calendar-fallback-slots";
    for (const slot of Array.isArray(payload.slots) ? payload.slots : []) {
      const isFree = slot.status === "free";
      const slotButton = document.createElement(isFree ? "button" : "div");
      if (isFree) slotButton.type = "button";
      slotButton.className = `calendar-fallback-slot calendar-fallback-slot-${slot.status || "busy"}${state.calendarSelectedSlot === slot.start ? " is-selected" : ""}`;
      slotButton.textContent = `${slot.time || ""} · ${isFree ? "Свободно" : slot.status === "break" ? "Перерыв" : "Занято"}`;
      if (isFree) {
        slotButton.addEventListener("click", () => {
          state.calendarSelectedSlot = slot.start;
          renderCalendar(state.calendar);
          setStatus(`Выбрано время ${slot.time}. Заполни кандидата и нажми бронирование.`, "working");
        });
      }
      slotButton.addEventListener("contextmenu", (event) => showCalendarSlotMenu(event, slot));
      slots.appendChild(slotButton);
    }
    if (!slots.children.length) {
      const empty = document.createElement("span");
      empty.className = "field-help";
      empty.textContent = "Для этой даты нет доступных окон.";
      slots.appendChild(empty);
    }
    day.appendChild(slots);
    shell.appendChild(day);
  } else {
    const weekdays = document.createElement("div");
    weekdays.className = "calendar-fallback-weekdays";
    calendarWeekdayNames.forEach((name) => {
      const cell = document.createElement("span");
      cell.textContent = name;
      weekdays.appendChild(cell);
    });
    shell.appendChild(weekdays);

    const grid = document.createElement("div");
    grid.className = "calendar-fallback-grid";
    const firstDay = new Date(selectedMonth);
    const mondayOffset = (firstDay.getDay() + 6) % 7;
    firstDay.setDate(firstDay.getDate() - mondayOffset);
    const todayKey = calendarDateKey(new Date());
    for (let index = 0; index < 42; index += 1) {
      const day = new Date(firstDay);
      day.setDate(firstDay.getDate() + index);
      const key = calendarDateKey(day);
      const cell = makeCalendarButton(String(day.getDate()), "calendar-fallback-day-cell", () => {
        state.calendarFallbackView = "day";
        fetchCalendar(key).catch((error) => setStatus(error.message, "error"));
      });
      if (day.getMonth() !== selectedMonth.getMonth()) cell.classList.add("is-muted");
      if (key === todayKey) cell.classList.add("is-today");
      if (key === selectedKey) cell.classList.add("is-selected");
      grid.appendChild(cell);
    }
    shell.appendChild(grid);
  }
  els.calendarView.appendChild(shell);
}

function ensureCalendar() {
  if (!els.calendarView) return;
  // Keep the original lightweight month/day calendar. FullCalendar was only
  // an experiment and changed the layout the user already had configured.
  if (state.calendarInstance) {
    state.calendarInstance.destroy?.();
    state.calendarInstance = null;
  }
  state.calendarFallback = true;
}

function renderCalendar(payload = {}) {
  state.calendar = payload;
  if (els.calendarDate && payload.selectedDate) els.calendarDate.value = payload.selectedDate;
  const settings = payload.settings || {};
  if (els.calendarWorkStart && settings.work_start) els.calendarWorkStart.value = settings.work_start;
  if (els.calendarWorkEnd && settings.work_end) els.calendarWorkEnd.value = settings.work_end;
  if (els.calendarBreaks && Array.isArray(settings.breaks)) els.calendarBreaks.value = settings.breaks.join(", ");
  if (els.calendarSlotMinutes && settings.slot_minutes) els.calendarSlotMinutes.value = String(settings.slot_minutes);

  ensureCalendar();
  if (state.calendarFallback) {
    renderCalendarFallback(payload);
    return;
  }
  if (state.calendarInstance) {
    const startClock = settings.work_start || "10:00";
    const endClock = settings.work_end || "20:00";
    state.calendarRendering = true;
    const slotMinutes = Math.max(10, Number(settings.slot_minutes || 20));
    state.calendarInstance.setOption("slotDuration", `00:${String(slotMinutes).padStart(2, "0")}:00`);
    state.calendarInstance.setOption("slotMinTime", `${startClock}:00`);
    state.calendarInstance.setOption("slotMaxTime", `${endClock}:00`);
    state.calendarInstance.gotoDate(payload.selectedDate || calendarDateKey(new Date()));
    state.calendarInstance.removeAllEvents();
    const events = [];
    for (const event of Array.isArray(payload.events) ? payload.events : []) {
      events.push({
        id: `scheduled-${event.id}`,
        title: event.title || "Собеседование",
        start: event.start,
        end: event.end,
        classNames: ["calendar-scheduled-event"],
        extendedProps: { kind: "scheduled", phone: event.phone || "", eventId: event.id },
      });
    }
    for (const slot of Array.isArray(payload.slots) ? payload.slots : []) {
      if (slot.status === "free") {
        events.push({
          id: `free-${slot.start}`,
          title: state.calendarSelectedSlot === slot.start ? "Выбрано" : "Свободно",
          start: slot.start,
          end: slot.end,
          classNames: ["calendar-free-slot", state.calendarSelectedSlot === slot.start ? "is-selected" : ""].filter(Boolean),
          extendedProps: { kind: "free", slot },
        });
      } else if (slot.status === "break") {
        events.push({
          id: `break-${slot.start}`,
          title: "Перерыв",
          start: slot.start,
          end: slot.end,
          display: "background",
          classNames: ["calendar-break-slot"],
        });
      } else if (slot.status === "past") {
        events.push({
          id: `past-${slot.start}`,
          title: "Прошло",
          start: slot.start,
          end: slot.end,
          display: "background",
          classNames: ["calendar-past-slot"],
        });
      }
    }
    state.calendarInstance.addEventSource(events);
    state.calendarRendering = false;
  }

  if (els.calendarEvents) {
    els.calendarEvents.replaceChildren();
    const events = Array.isArray(payload.events) ? payload.events : [];
    if (!events.length) {
      const empty = document.createElement("span");
      empty.className = "field-help";
      empty.textContent = "Запланированных встреч пока нет.";
      els.calendarEvents.appendChild(empty);
    }
    for (const event of events) {
      const row = document.createElement("div");
      row.className = "calendar-event";
      const details = document.createElement("div");
      details.className = "calendar-event-details";
      const title = document.createElement("strong");
      title.textContent = event.title || "Собеседование";
      const meta = document.createElement("small");
      meta.textContent = `${String(event.start || "").replace("T", " ").slice(0, 16)} · ${event.phone || "без номера"}`;
      details.append(title, meta);
      const remove = document.createElement("button");
      remove.className = "text-button";
      remove.type = "button";
      remove.textContent = "Удалить";
      remove.addEventListener("click", () => deleteCalendarEvent(event.id).catch((error) => setStatus(error.message, "error")));
      row.append(details, remove);
      els.calendarEvents.appendChild(row);
    }
  }
}

function scheduleCalendarReconnect() {
  if (state.calendarRetryTimer) return;
  state.calendarRetryTimer = window.setTimeout(async () => {
    state.calendarRetryTimer = null;
    try {
      await fetchCalendar();
    } catch {
      scheduleCalendarReconnect();
    }
  }, 1500);
}

async function fetchCalendar(dayOverride = "") {
  const day = dayOverride || els.calendarDate?.value || "";
  if (state.calendarRequest) return state.calendar;
  state.calendarRequest = true;
  const query = day ? `?day=${encodeURIComponent(day)}` : "";
  try {
    const res = await apiFetch(`/api/calendar${query}`, { cache: "no-store" });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(payload.detail || "Не удалось загрузить календарь.");
    const wasConnected = state.calendarBackendConnected;
    state.calendarBackendConnected = true;
    if (state.calendarRetryTimer) {
      window.clearTimeout(state.calendarRetryTimer);
      state.calendarRetryTimer = null;
    }
    renderCalendar(payload);
    if (!wasConnected || /Календарь показан без backend|Backend не подключён|Failed to fetch/i.test(els.status?.textContent || "")) {
      setStatus("Backend подключён. Календарь обновлён.");
    }
    return payload;
  } catch (error) {
    state.calendarBackendConnected = false;
    scheduleCalendarReconnect();
    throw error;
  } finally {
    state.calendarRequest = false;
  }
}

async function initializeCalendar() {
  let lastError;
  for (let attempt = 0; attempt < 12; attempt += 1) {
    try {
      await fetchCalendar();
      return;
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => window.setTimeout(resolve, 250));
    }
  }
  const today = calendarDateKey(new Date());
  state.calendarFallbackView = "month";
  state.calendar = {
    selectedDate: today,
    settings: { work_start: "10:00", work_end: "20:00", slot_minutes: 20, breaks: [] },
    slots: [],
    events: [],
  };
  renderCalendarFallback(state.calendar);
  setStatus(`Календарь временно без backend. Повторяю подключение автоматически. ${lastError?.message || ""}`, "error");
  scheduleCalendarReconnect();
}

async function saveCalendarSettings() {
  const body = new FormData();
  body.append("work_start", els.calendarWorkStart?.value || "10:00");
  body.append("work_end", els.calendarWorkEnd?.value || "20:00");
  body.append("breaks", els.calendarBreaks?.value || "");
  body.append("slot_minutes", els.calendarSlotMinutes?.value || "20");
  const res = await apiFetch("/api/calendar/settings", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось сохранить график.");
  state.calendarSelectedSlot = "";
  renderCalendar(payload);
  setStatus("График и перерывы сохранены.");
}

async function bookCalendarSlot() {
  if (!state.calendarSelectedSlot) throw new Error("Сначала выбери свободный слот в календаре.");
  const title = els.calendarTitle?.value.trim() || "Кандидат";
  const phone = els.calendarPhone?.value.trim() || els.mangoNumber?.value.trim() || "";
  const start = state.calendarSelectedSlot;
  const body = new FormData();
  body.append("day", start.slice(0, 10));
  body.append("clock", start.slice(11, 16));
  body.append("title", title);
  body.append("phone", phone);
  body.append("duration", String(state.calendar?.settings?.slot_minutes || 20));
  const res = await apiFetch("/api/calendar/events", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось занять слот.");
  state.calendarSelectedSlot = "";
  renderCalendar(payload);
  setStatus("Собеседование добавлено в календарь.");
}

async function markCalendarSlotBusy(start) {
  const slot = (state.calendar?.slots || []).find((item) => item.start === start);
  if (!slot || slot.status !== "free") throw new Error("Это время уже недоступно.");
  const time = slot.time || start.slice(11, 16);
  if (!window.confirm(`Отметить ${time} как занятое время?`)) return;
  const body = new FormData();
  body.append("day", start.slice(0, 10));
  body.append("clock", time);
  body.append("duration", String(state.calendar?.settings?.slot_minutes || 20));
  const res = await apiFetch("/api/calendar/busy", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось отметить время занятым.");
  state.calendarSelectedSlot = "";
  renderCalendar(payload);
  setStatus(`Время ${time} отмечено как занятое.`);
}

async function deleteCalendarEvent(eventId) {
  const res = await apiFetch(`/api/calendar/events/${encodeURIComponent(eventId)}`, { method: "DELETE" });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось удалить встречу.");
  renderCalendar(payload);
  setStatus("Встреча удалена из календаря.");
}

async function fetchAudioDevices() {
  const res = await apiFetch("/api/audio/devices", { cache: "no-store" });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось получить аудиоустройства.");
  renderAudioDevices(payload);
}

async function saveAudioSettings() {
  const body = new FormData();
  body.append("output_device", els.audioOutputDevice?.value || "");
  body.append("loopback_device", els.audioLoopbackDevice?.value || "");
  const res = await apiFetch("/api/audio/settings", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось сохранить аудиомаршрут.");
  setStatus("Аудиомаршрут сохранён.");
  await fetchAudioDevices();
}

async function testAudioRoute() {
  const body = new FormData();
  body.append("output_device", els.audioOutputDevice?.value || "");
  const res = await apiFetch("/api/audio/test", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось проверить аудиоканал.");
  setStatus("Тестовый звук отправлен в выбранный TTS-выход.", "working");
}

async function fetchCallStatus() {
  if (state.callRequest) return;
  state.callRequest = true;
  try {
    const res = await apiFetch("/api/call/status", { cache: "no-store" });
    if (res.ok) renderCallStatus(await res.json());
  } finally {
    state.callRequest = false;
  }
}

function startCallMonitor() {
  fetchCallStatus();
  if (state.callTimer) window.clearInterval(state.callTimer);
  state.callTimer = window.setInterval(fetchCallStatus, 700);
}

async function startMangoCall() {
  const number = els.mangoNumber?.value.trim() || "";
  const candidateName = els.mangoCandidateName?.value.trim() || "";
  if (number.replace(/\D/g, "").length < 5) throw new Error("Введи номер минимум из 5 цифр.");
  const body = new FormData();
  body.append("number", number);
  body.append("candidate_name", candidateName);
  body.append("stt_api_key", els.apiKey.value.trim());
  body.append("stt_model", els.sttModel.value);
  body.append("stt_language", els.language.value);
  body.append("llm_api_key", els.llmApiKey.value.trim());
  body.append("llm_base_url", els.llmBaseUrl.value.trim());
  body.append("llm_model", els.llmModel.value.trim());
  body.append("system_prompt", els.systemPrompt.value);
  body.append("temperature", "0.7");
  body.append("thinking", String(Boolean(els.llmThinking?.checked)));
  body.append("tts_language", els.ttsLanguage.value);
  body.append("tts_speaker", els.ttsSpeaker?.value || "");
  body.append("pace", els.pace.value);
  body.append("output_device", els.audioOutputDevice?.value || "");
  body.append("loopback_device", els.audioLoopbackDevice?.value || "");
  body.append("listen_seconds", els.mangoListenSeconds?.value || "60");
  body.append("use_vpn_stt", String(els.vpnEnabled.checked && els.vpnForStt.checked));
  body.append("use_vpn_llm", String(els.vpnEnabled.checked && els.vpnForLlm.checked));
  body.append("telegram_bot_token", els.telegramBotToken?.value.trim() || "");
  body.append("telegram_chat_ids", els.telegramChatIds?.value.trim() || "");
  const res = await apiFetch("/api/call/start", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось запустить звонок.");
  localStorage.setItem("voicebridge.mangoNumber", number);
  localStorage.setItem("voicebridge.mangoCandidateName", candidateName);
  localStorage.setItem("voicebridge.mangoListenSeconds", els.mangoListenSeconds?.value || "60");
  renderCallStatus(payload);
  setStatus("Звонок запускается…", "working");
  startCallMonitor();
}

async function stopMangoCall() {
  const res = await apiFetch("/api/call/stop", { method: "POST" });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось завершить звонок.");
  renderCallStatus(payload);
  setStatus("Завершаю звонок…", "working");
}

async function sendMangoSms() {
  const message = els.mangoSmsMessage?.value.trim() || "";
  if (!message) throw new Error("Введи текст SMS.");
  const body = new FormData();
  body.append("number", els.mangoNumber?.value.trim() || "");
  body.append("message", message);
  const res = await apiFetch("/api/call/sms", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось отправить SMS.");
  localStorage.setItem("voicebridge.mangoSmsMessage", message);
  renderCallStatus(payload);
  setStatus("SMS отправлено через Mango.");
}

async function testTelegram() {
  const body = new FormData();
  body.append("bot_token", els.telegramBotToken?.value.trim() || "");
  body.append("chat_ids", els.telegramChatIds?.value.trim() || "");
  const res = await apiFetch("/api/telegram/test", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось отправить тестовое уведомление.");
  savePrefs();
  setStatus("Тестовое сообщение отправлено в Telegram.");
}

async function sendVoiceDialogReport() {
  if (state.voiceDialogReportSent) return;
  const candidate = state.voiceDialogCandidate || {};
  if (!Array.isArray(candidate.turns) || candidate.turns.length === 0) return;
  const body = {
    candidate,
    bot_token: els.telegramBotToken?.value.trim() || "",
    chat_ids: els.telegramChatIds?.value.trim() || "",
  };
  const res = await apiFetch("/api/dialog/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось отправить отчёт тестового диалога в Telegram.");
  state.voiceDialogReportSent = true;
  savePrefs();
  setStatus("Краткий отчёт тестового диалога отправлен в Telegram.");
}

async function runDialogTest() {
  const input = els.dialogTestInput?.value.trim() || "";
  const candidateName = els.dialogTestName?.value.trim() || "";
  const greeting = testCandidateGreeting(candidateName);
  // An empty text field means the user wants the hands-free test. This keeps
  // the main test button useful without forcing them to type a fake reply.
  if (!input) {
    await startVoiceDialog();
    return;
  }
  state.activeOperation = true;
  state.voiceDialogReportSent = false;
  state.voiceDialogHistory = [{ role: "Яна", text: greeting }];
  state.voiceDialogStage = candidateName ? "name_confirm" : "relevance";
  state.voiceDialogCandidate = { name: candidateName };
  renderCandidateData({}, state.voiceDialogStage);
  els.transcript.value = input;
  renderPipelineActivity({ active: true, phase: "generating", progress: 18, message: "Яна начинает тестовый диалог…" });
  setStatus("Яна произносит приветствие…", "working");
  try {
    await synthesizeAndPlay(greeting, true);
    state.voiceDialogHistory.push({ role: "Собеседник", text: input });
    renderPipelineActivity({ active: true, phase: "generating", progress: 38, message: "Сценарий выбирает следующий шаг…" });
    setStatus("Выбираю следующий шаг сценария…", "working");
    const processed = await processVoiceDialogTurn(input);
    const spokenReply = processed.reply;
    if (!spokenReply) return;
    state.voiceDialogHistory.push({ role: "Яна", text: spokenReply });
    const endsCall = processed.ends;
    els.reply.value = spokenReply || reply;
    renderPipelineActivity({ active: true, phase: "generating", progress: 58, message: "TTS озвучивает тестовый ответ…" });
    setStatus("TTS озвучивает тестовый ответ…", "working");
    if (spokenReply) await synthesizeAndPlay(spokenReply, true);
    setStatus(endsCall ? "Тестовый сценарий завершён: Яна завершает разговор." : "Тестовый ответ готов.");
  } finally {
    state.activeOperation = false;
    try {
      await sendVoiceDialogReport();
    } catch (error) {
      setStatus(`Отчёт тестового диалога не отправлен: ${error.message}`, "error");
    }
    state.voiceDialogHistory = [];
  }
}

function formatVoiceDialogHistory() {
  const items = state.voiceDialogHistory || [];
  const lines = items.map((item) => `${item.role}: ${item.text}`).join("\n");
  const maxChars = 12000;
  const trimmed = lines.length > maxChars
    ? `… начало разговора сокращено из-за лимита контекста …\n${lines.slice(-maxChars)}`
    : lines;
  return `Полная история текущего голосового диалога:\n${trimmed}`;
}

function setVoiceDialogState(message, kind = "idle") {
  if (els.voiceDialogState) els.voiceDialogState.textContent = message;
  if (kind === "working") setStatus(message, "working");
}

function recordVoiceDialogTurn(stream, maxDurationMs, silenceMs = 800) {
  return new Promise((resolve, reject) => {
    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";
    const recorder = new MediaRecorder(stream, { mimeType });
    const chunks = [];
    let maxTimer = null;
    let sampleTimer = null;
    let context = null;
    let analyser = null;
    let source = null;
    let settled = false;
    let heardSpeech = false;
    let lastSpeechAt = 0;
    const samples = new Float32Array(1024);
    const startedAt = performance.now();

    const cleanupAudioMonitor = () => {
      if (maxTimer) window.clearTimeout(maxTimer);
      if (sampleTimer) window.clearTimeout(sampleTimer);
      try { source?.disconnect(); } catch (_) { /* best effort */ }
      if (context) context.close().catch(() => {});
    };
    const finish = (error = null) => {
      if (settled) return;
      settled = true;
      cleanupAudioMonitor();
      state.voiceDialogRecorder = null;
      if (error) reject(error);
      else resolve(new Blob(chunks, { type: mimeType }));
    };
    state.voiceDialogRecorder = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onerror = () => {
      finish(new Error("Не удалось записать микрофон."));
    };
    recorder.onstop = () => {
      finish();
    };
    recorder.start();
    maxTimer = window.setTimeout(() => {
      if (recorder.state !== "inactive") recorder.stop();
    }, maxDurationMs);

    try {
      context = new (window.AudioContext || window.webkitAudioContext)();
      analyser = context.createAnalyser();
      analyser.fftSize = 2048;
      source = context.createMediaStreamSource(stream);
      source.connect(analyser);
    } catch (_) {
      // Recording still works without VAD; the maximum duration remains active.
      return;
    }

    const sample = () => {
      if (settled || recorder.state === "inactive") return;
      analyser.getFloatTimeDomainData(samples);
      let energy = 0;
      for (const value of samples) energy += value * value;
      const rms = Math.sqrt(energy / samples.length);
      const now = performance.now();
      if (rms > 0.025) {
        heardSpeech = true;
        lastSpeechAt = now;
      }
      if (heardSpeech && now - lastSpeechAt >= silenceMs && now - startedAt > 900) {
        recorder.stop();
        return;
      }
      sampleTimer = window.setTimeout(sample, 50);
    };
    sample();
  });
}

async function transcribeVoiceDialogChunk(blob) {
  const file = await prepareSttFile(blob, "voice-dialog.wav");
  const res = await apiFetch("/api/transcribe", { method: "POST", body: getCommonForm(file) });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail ? JSON.stringify(payload.detail) : "Voice STT failed.");
  els.transcript.value = payload.text || "";
  els.detectedLang.textContent = payload.language || "—";
  els.duration.textContent = typeof payload.duration === "number" ? `${payload.duration.toFixed(2)} s` : "—";
  return payload.text || "";
}

async function processVoiceDialogTurn(transcript) {
  const config = {
    llm_base_url: els.llmBaseUrl?.value.trim() || "",
    llm_api_key: els.llmApiKey?.value.trim() || "",
    llm_model: els.llmModel?.value.trim() || "",
    temperature: 0.4,
    use_vpn_llm: Boolean(els.vpnEnabled?.checked && els.vpnForLlm?.checked),
    thinking: Boolean(els.llmThinking?.checked),
  };
  const res = await apiFetch("/api/dialog/turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      stage: state.voiceDialogStage,
      transcript,
      candidate: state.voiceDialogCandidate,
      history: state.voiceDialogHistory,
      config,
    }),
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "Не удалось обработать реплику диалога.");
  state.voiceDialogStage = payload.nextStage || state.voiceDialogStage;
  state.voiceDialogCandidate = payload.candidate || state.voiceDialogCandidate;
  renderCandidateData(state.voiceDialogCandidate, state.voiceDialogStage);
  return {
    reply: String(payload.reply || "").trim(),
    ends: Boolean(payload.ends),
  };
}

async function prepareSttFile(fileOrBlob, filename = "recording.wav") {
  const source = fileOrBlob instanceof Blob ? fileOrBlob : new Blob([fileOrBlob]);
  const type = (source.type || "").toLowerCase();
  if (type.includes("wav") || type.includes("wave")) {
    return source instanceof File ? source : new File([source], filename, { type: "audio/wav" });
  }

  // MediaRecorder produces WebM/Opus in Chromium. GigaAM accepts PCM WAV,
  // so decode it in the browser without requiring ffmpeg or SoX on Windows.
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    return source instanceof File ? source : new File([source], filename, { type: source.type });
  }
  const context = new AudioContextClass();
  try {
    const decoded = await context.decodeAudioData(await source.arrayBuffer());
    const channels = decoded.numberOfChannels;
    const sourceLength = decoded.length;
    const targetRate = 16000;
    const targetLength = Math.max(1, Math.round(sourceLength * targetRate / decoded.sampleRate));
    const mono = new Float32Array(targetLength);
    for (let index = 0; index < targetLength; index += 1) {
      const position = index * decoded.sampleRate / targetRate;
      const left = Math.floor(position);
      const right = Math.min(left + 1, sourceLength - 1);
      const fraction = position - left;
      let sample = 0;
      for (let channel = 0; channel < channels; channel += 1) {
        const data = decoded.getChannelData(channel);
        sample += data[left] * (1 - fraction) + data[right] * fraction;
      }
      mono[index] = Math.max(-1, Math.min(1, sample / Math.max(1, channels)));
    }
    return new File([encodePcm16Wav(mono, targetRate)], filename, { type: "audio/wav" });
  } finally {
    await context.close().catch(() => {});
  }
}

function encodePcm16Wav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeText = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index));
  };
  writeText(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let index = 0; index < samples.length; index += 1) {
    const value = samples[index] < 0 ? samples[index] * 32768 : samples[index] * 32767;
    view.setInt16(44 + index * 2, Math.round(value), true);
  }
  return buffer;
}

async function startVoiceDialog() {
  if (state.voiceDialogRunning) return;
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  state.voiceDialogStream = stream;
  state.voiceDialogRunning = true;
  state.voiceDialogGeneration += 1;
  state.voiceDialogTurns = 0;
  state.voiceDialogReportSent = false;
  const candidateName = els.dialogTestName?.value.trim() || "";
  const greeting = testCandidateGreeting(candidateName);
  state.voiceDialogStage = candidateName ? "name_confirm" : "relevance";
  state.voiceDialogCandidate = { name: candidateName };
  state.voiceDialogHistory = [{ role: "Яна", text: greeting }];
  renderCandidateData({}, state.voiceDialogStage);
  const generation = state.voiceDialogGeneration;
  state.activeOperation = true;
  els.voiceDialogStartBtn.disabled = true;
  els.voiceDialogStopBtn.disabled = false;
  setVoiceDialogState("Яна произносит приветствие…", "working");
  try {
    // The opening is a fixed TTS line. It is played once and is never sent
    // back to the LLM as a user or assistant message.
    await synthesizeAndPlay(greeting, true);
    if (!state.voiceDialogRunning || generation !== state.voiceDialogGeneration) return;
    setVoiceDialogState("Приветствие прозвучало. Слушаю ответ…", "working");
    while (state.voiceDialogRunning && generation === state.voiceDialogGeneration) {
      const seconds = Math.max(5, Math.min(60, Number(els.voiceDialogMaxSeconds?.value || 60)));
      savePrefs();
      setVoiceDialogState("Слушаю реплику… говори свободно, остановлюсь после паузы.", "working");
      const blob = await recordVoiceDialogTurn(stream, seconds * 1000);
      if (!state.voiceDialogRunning || generation !== state.voiceDialogGeneration) break;
      setVoiceDialogState("Распознаю твою реплику…", "working");
      const transcript = await transcribeVoiceDialogChunk(blob);
      if (!transcript.trim()) {
        setVoiceDialogState("Ничего не расслышал. Слушаю дальше…", "working");
        continue;
      }
      state.voiceDialogHistory.push({ role: "Собеседник", text: transcript });
      state.voiceDialogTurns += 1;
      const processed = await processVoiceDialogTurn(transcript);
      if (!state.voiceDialogRunning || generation !== state.voiceDialogGeneration) break;
      const endsCall = processed.ends;
      const spokenReply = processed.reply;
      els.reply.value = spokenReply;
    state.voiceDialogHistory.push({ role: "Яна", text: spokenReply });
      setVoiceDialogState("TTS отвечает…", "working");
      if (!spokenReply) break;
      await synthesizeAndPlay(spokenReply, true);
      if (endsCall) {
        state.voiceDialogRunning = false;
        break;
      }
      setVoiceDialogState(
        "Слушаю следующую реплику…",
        "working",
      );
    }
  } finally {
    state.activeOperation = false;
    try {
      await sendVoiceDialogReport();
    } catch (error) {
      setStatus(`Отчёт тестового диалога не отправлен: ${error.message}`, "error");
    }
    if (state.voiceDialogStream === stream) {
      stream.getTracks().forEach((track) => track.stop());
      state.voiceDialogStream = null;
    }
    state.voiceDialogRecorder = null;
    state.voiceDialogHistory = [];
    state.voiceDialogStage = "relevance";
    els.voiceDialogStartBtn.disabled = false;
    els.voiceDialogStopBtn.disabled = true;
    if (state.voiceDialogRunning) state.voiceDialogRunning = false;
    setVoiceDialogState("Голосовой диалог остановлен.");
  }
}

function stopVoiceDialog() {
  state.voiceDialogRunning = false;
  state.voiceDialogGeneration += 1;
  if (state.voiceDialogRecorder && state.voiceDialogRecorder.state !== "inactive") {
    state.voiceDialogRecorder.stop();
  }
  if (state.voiceDialogStream) {
    state.voiceDialogStream.getTracks().forEach((track) => track.stop());
    state.voiceDialogStream = null;
  }
  state.voiceDialogPlaybackCancel?.();
  els.player.pause();
  setVoiceDialogState("Останавливаю голосовой диалог…");
}

async function fetchConfigOnce() {
  const res = await apiFetch("/api/config");
  if (!res.ok) throw new Error(`Backend config request failed (${res.status}).`);

  const cfg = await res.json();
  if (els.llmProvider && !localStorage.getItem("voicebridge.llmProvider") && cfg.defaultLlmProvider) {
    els.llmProvider.value = cfg.defaultLlmProvider;
  }
  applyLlmProvider();
  if (els.localLlmState && cfg.localLlm) {
    const runtime = cfg.localLlm.running ? `запущена на ${cfg.localLlm.provider}` : "готова к запуску без скачивания";
    const thinking = Boolean(els.llmThinking?.checked);
    els.localLlmState.textContent = `${cfg.localLlm.label || "Qwen3 1.7B"}: ${runtime}. Thinking ${thinking ? "включён" : "выключен"}.`;
  }
  if (els.sttModelHelp && cfg.gigaamStt) {
    const provider = String(cfg.gigaamStt.provider || "CPUExecutionProvider")
      .replace("ExecutionProvider", "")
      .toUpperCase();
    const available = Array.isArray(cfg.gigaamStt.availableProviders)
      ? cfg.gigaamStt.availableProviders.join(", ")
      : "CPUExecutionProvider";
    els.sttModelHelp.textContent = provider === "CUDA"
      ? "GigaAM работает локально на русском через NVIDIA CUDA. Провайдер готов."
      : `GigaAM работает локально на русском через CPU. Доступные ONNX-провайдеры: ${available}.`;
  }
  if (cfg.ttsDevice) state.ttsDevice = cfg.ttsDevice;
  state.ttsQuantization = cfg.ttsQuantization || {};
  state.ttsSpeakers = cfg.ttsSpeakers || {};
  state.ttsSpeakerNames = cfg.ttsSpeakerNames || {};
  renderRvc(cfg.rvc || {});
  renderAudioDevices(cfg.audioDevices || { settings: cfg.audioRouting || {} });
  renderCallStatus(cfg.call || {});

  try {

  if (Array.isArray(cfg.sttModels) && cfg.sttModels.length > 0) {
    const existing = new Set(Array.from(els.sttModel.options).map((option) => option.value));
    for (const model of cfg.sttModels) {
      if (!existing.has(model)) {
        const option = document.createElement("option");
        option.value = model;
        option.textContent = cfg.sttModelNames?.[model] || model;
        els.sttModel.appendChild(option);
      }
    }
  }

  fillTtsLanguages(cfg.ttsLanguages || [], cfg.ttsLanguageNames || {});
  fillTtsSpeakers(cfg.ttsSpeakers || {}, cfg.ttsSpeakerNames || {});
  if (Array.isArray(cfg.ttsModels) && cfg.ttsModels.length > 0) {
    const savedModel = els.ttsModel.value;
    els.ttsModel.innerHTML = "";
    for (const model of cfg.ttsModels) {
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = `${model.label}${model.download ? ` · ${model.download}` : ""}`;
      els.ttsModel.appendChild(option);
    }
    const preferred = savedModel || cfg.defaultTtsModel;
    els.ttsModel.value = cfg.ttsModels.some((model) => model.id === preferred)
      ? preferred
      : cfg.defaultTtsModel;
    updateTtsModelHelp(cfg.ttsModels, cfg.ttsQuantization || {});
  }
  if (!els.ttsLanguage.value && cfg.defaultTtsLanguage) els.ttsLanguage.value = cfg.defaultTtsLanguage;
  fillTtsSpeakers(cfg.ttsSpeakers || {}, cfg.ttsSpeakerNames || {});
  if (!els.ttsModel.value && cfg.defaultTtsModel) els.ttsModel.value = cfg.defaultTtsModel;
  if (!els.sttModel.value && cfg.defaultSttModel) {
    els.sttModel.value = cfg.defaultSttModel;
  }
  if (!els.llmBaseUrl.value && cfg.defaultLlmBaseUrl) {
    els.llmBaseUrl.value = cfg.defaultLlmBaseUrl;
  }
  if (!els.llmModel.value && cfg.defaultLlmModel) {
    els.llmModel.value = cfg.defaultLlmModel;
  }
  if (cfg.defaultSystemPrompt && localStorage.getItem("voicebridge.callScriptVersion") !== CALL_SCRIPT_VERSION) {
    els.systemPrompt.value = cfg.defaultSystemPrompt;
    localStorage.setItem("voicebridge.systemPrompt", cfg.defaultSystemPrompt);
    localStorage.setItem("voicebridge.callScriptVersion", CALL_SCRIPT_VERSION);
  } else if (!els.systemPrompt.value && cfg.defaultSystemPrompt) {
    els.systemPrompt.value = cfg.defaultSystemPrompt;
  }
  state.savedAudio = cfg.savedAudio || null;
  state.storage = cfg.storage || {};
  renderSavedAudio();
  renderStorage();
  if (cfg.vpn) renderVpn(cfg.vpn);
  if (cfg.ttsDevice) renderTtsDevice(cfg.ttsDevice);
    if (!els.apiKey.value && cfg.groqConfigured) setStatus("Groq key detected in environment.");
  } catch (error) {
    console.error("Config rendering failed:", error);
  }
}

async function fetchConfig() {
  let lastError;
  for (let attempt = 0; attempt < 12; attempt += 1) {
    try {
      return await fetchConfigOnce();
    } catch (error) {
      lastError = error;
      if (state.ttsDevice || attempt === 11) break;
      await new Promise((resolve) => window.setTimeout(resolve, 250));
    }
  }
  throw lastError || new Error("Backend config request failed.");
}

function renderTtsDevice(device) {
  state.ttsDevice = device;
  const isGpu = device.selected === "gpu";
  const threadInfo = device.torchThreads ? ` CPU-потоки: ${device.torchThreads}.` : "";
  els.ttsDeviceLabel.textContent = isGpu ? "GPU / CUDA" : "CPU";
  els.ttsDeviceSwitch.classList.toggle("is-gpu", isGpu);
  els.ttsDeviceSwitch.setAttribute("aria-checked", String(isGpu));
  els.ttsDeviceSwitch.disabled = !device.gpuAvailable && !isGpu;
  if (isGpu) {
    els.ttsDeviceHelp.textContent = device.mixedPrecision
      ? "GPU / CUDA активен. Silero использует PyTorch CUDA."
      : "GPU / CUDA доступен, но Silero запущен в CPU-режиме.";
  } else if (device.gpuAvailable) {
    els.ttsDeviceHelp.textContent = `CPU активен.${threadInfo} Silero работает через PyTorch.`;
  } else {
    els.ttsDeviceHelp.textContent = `CPU активен.${threadInfo} ${device.gpuMessage || "CUDA не обнаружена: проверьте NVIDIA и драйвер."}`;
  }
}

async function toggleTtsDevice() {
  if (!state.ttsDevice) {
    setStatus("Получаю состояние GPU...", "working");
    try {
      await fetchConfig();
    } catch (error) {
      setStatus(`Backend не отвечает: ${error.message}`, "error");
      return;
    }
  }
  const nextDevice = state.ttsDevice?.selected === "gpu" ? "cpu" : "gpu";
  if (nextDevice === "gpu" && !state.ttsDevice?.gpuAvailable) {
    setStatus(state.ttsDevice?.gpuMessage || "GPU недоступен: проверьте совместимость видеокарты, драйвера и CUDA.");
    return;
  }
  els.ttsDeviceSwitch.disabled = true;
  setStatus(`Переключение локальной модели на ${nextDevice.toUpperCase()}...`);
  const body = new FormData();
  body.append("device", nextDevice);
  const res = await apiFetch("/api/tts/device", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    els.ttsDeviceSwitch.disabled = false;
    throw new Error(payload.detail ? JSON.stringify(payload.detail) : "Device switch failed.");
  }
  renderTtsDevice(payload);
  setStatus(`Локальная модель переключена на ${payload.label}.`);
}

function renderSavedAudio() {
  if (!state.savedAudio?.active) {
    els.inputAudioState.textContent = "Нет сохранённого входного аудио.";
    els.deleteAudioBtn.disabled = true;
    return;
  }
  const size = Math.max(state.savedAudio.size / 1024, 1).toFixed(0);
  els.inputAudioState.textContent = `Сохранено на диске: ${state.savedAudio.name} · ${size} KB`;
  els.deleteAudioBtn.disabled = false;
}

function formatStorageSize(bytes = 0) {
  if (bytes < 1024 * 1024) return `${Math.max(bytes / 1024, 1).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function renderStorage() {
  const outputs = state.storage.outputs || {};
  const modelCache = state.storage.model_cache || {};
  els.outputStorageState.textContent = `${outputs.fileCount || 0} файлов · ${formatStorageSize(outputs.size || 0)}`;
  els.modelStorageState.textContent = `${formatStorageSize(modelCache.size || 0)} · повторная загрузка не нужна`;
  els.deleteOutputsBtn.disabled = !(outputs.fileCount > 0);
}

async function storageAction(path, kind, message) {
  const body = new FormData();
  body.append("kind", kind);
  setStatus(message);
  const res = await apiFetch(path, { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail ? JSON.stringify(payload.detail) : "Storage action failed.");
  if (path.endsWith("/clear")) {
    state.storage[kind] = payload;
    if (kind === "audio") {
      state.savedAudio = { active: false };
      renderSavedAudio();
    }
    renderStorage();
  }
  setStatus(path.endsWith("/open") ? "Папка открыта." : "Файлы удалены.");
}

function renderVpn(status) {
  state.vpnStatus = status;
  const running = Boolean(status?.running);
  const available = Boolean(status?.available);
  els.vpnIndicator.textContent = running ? "ON" : available ? "READY" : "OFF";
  els.vpnIndicator.dataset.kind = running ? "active" : available ? "ready" : "idle";
  els.vpnState.textContent = running
    ? `Туннель активен · SOCKS5 localhost:${status.port}`
    : available
      ? "Клиент установлен, туннель остановлен."
      : "Клиент не установлен. Нажмите «Скачать клиент».";
  els.vpnStartBtn.disabled = running;
  els.vpnStopBtn.disabled = !running;
}

async function syncVpnStatus() {
  const res = await apiFetch("/api/vpn/status");
  if (!res.ok) throw new Error("VPN status unavailable.");
  const status = await res.json();
  renderVpn(status);
  if (els.vpnEnabled.checked && status.available && !status.running) {
    vpnAction("/api/vpn/start", "Starting saved VPN tunnel...").catch((error) => setStatus(error.message));
  }
}

async function vpnAction(path, message, successMessage = "") {
  setStatus(message);
  const res = await apiFetch(path, { method: "POST" });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail ? JSON.stringify(payload.detail) : "VPN action failed.");
  renderVpn(payload);
  setStatus(successMessage || (payload.running ? "VPN tunnel is active." : "VPN tunnel stopped."));
}

async function persistInputAudio(file) {
  const body = new FormData();
  body.append("file", file, file.name || "recording.webm");
  const res = await apiFetch("/api/audio", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail ? JSON.stringify(payload.detail) : "Audio save failed.");
  state.savedAudio = payload;
  renderSavedAudio();
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";
    const recorder = new MediaRecorder(stream, { mimeType });

    state.mediaStream = stream;
    state.mediaRecorder = recorder;
    state.chunks = [];
    state.recordedFile = null;

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) state.chunks.push(event.data);
    };

    recorder.onstop = () => {
      const blob = new Blob(state.chunks, { type: mimeType });
      state.recordedFile = new File([blob], "recording.webm", { type: blob.type });
      state.chunks = [];
      persistInputAudio(state.recordedFile).catch((error) => setStatus(error.message));
      setStatus(`Recorded ${Math.max(blob.size / 1024, 1).toFixed(0)} KB`);
    };

    recorder.start();
    els.recordBtn.disabled = true;
    els.stopBtn.disabled = false;
    setStatus("Recording...");
  } catch (error) {
    setStatus(error.message || "Could not start recording.");
  }
}

function stopRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
    state.mediaRecorder.stop();
  }
  if (state.mediaStream) {
    state.mediaStream.getTracks().forEach((track) => track.stop());
    state.mediaStream = null;
  }
  els.recordBtn.disabled = false;
  els.stopBtn.disabled = true;
}

async function getInputFile() {
  const localFile = state.recordedFile || els.fileInput.files?.[0] || null;
  if (localFile) return localFile;
  if (!state.savedAudio?.active) return null;

  const res = await apiFetch("/api/audio/file");
  if (!res.ok) return null;
  const blob = await res.blob();
  return new File([blob], state.savedAudio.name || "saved-audio.webm", {
    type: state.savedAudio.contentType || blob.type || "audio/webm",
  });
}

function getCommonForm(file) {
  const form = new FormData();
  form.append("file", file, file.name || "recording.webm");
  form.append("api_key", els.apiKey.value.trim());
  form.append("model", els.sttModel.value);
  form.append("language", els.language.value);
  form.append("prompt", "");
  form.append("use_vpn", String(els.vpnEnabled.checked && els.vpnForStt.checked));
  return form;
}

async function transcribeCurrent() {
  const sourceFile = await getInputFile();
  if (!sourceFile) {
    setStatus("Record audio or pick a file first.");
    return "";
  }
  const file = await prepareSttFile(sourceFile, "recording.wav");

  setStatus("Transcribing...");
  const res = await apiFetch("/api/transcribe", {
    method: "POST",
    body: getCommonForm(file),
  });
  const payload = await res.json();
  if (!res.ok) throw new Error(payload.detail ? JSON.stringify(payload.detail) : "Transcription failed.");

  els.transcript.value = payload.text || "";
  els.detectedLang.textContent = payload.language || "—";
  els.duration.textContent = typeof payload.duration === "number" ? `${payload.duration.toFixed(2)} s` : "—";
  setStatus("Transcription complete.");
  return payload.text || "";
}

async function askCurrent(contextPrefix = "", includeCurrent = true) {
  const text = els.transcript.value.trim();
  if (!text) {
    setStatus("No transcript yet.");
    return "";
  }

  if (!els.llmBaseUrl.value.trim()) {
    setStatus("Set OpenAI-compatible base URL first.");
    return "";
  }

  setStatus("Asking model...");
  const form = new FormData();
  form.append("text", contextPrefix && includeCurrent ? `${contextPrefix}\n\nРеплика для обработки: ${text}` : (contextPrefix || text));
  form.append("api_key", els.llmApiKey.value.trim());
  form.append("base_url", els.llmBaseUrl.value.trim());
  form.append("model", els.llmModel.value.trim());
  form.append("system_prompt", els.systemPrompt.value);
  form.append("temperature", "0.7");
  form.append("thinking", String(Boolean(els.llmThinking?.checked)));
  form.append("use_vpn", String(els.vpnEnabled.checked && els.vpnForLlm.checked));
  if (!includeCurrent && state.voiceDialogHistory?.length) {
    form.append("history", JSON.stringify(state.voiceDialogHistory));
  }

  const res = await apiFetch("/api/chat", { method: "POST", body: form });
  const payload = await res.json();
  if (!res.ok) throw new Error(payload.detail ? JSON.stringify(payload.detail) : "Chat failed.");

  els.reply.value = payload.text || "";
  setStatus("Model reply ready.");
  return payload.text || "";
}

function waitForBargeIn(stream, signal) {
  return new Promise((resolve) => {
    let context = null;
    let analyser = null;
    let source = null;
    let timer = null;
    let settled = false;
    let streak = 0;
    const samples = new Float32Array(1024);
    const startedAt = performance.now();

    const finish = (interrupted) => {
      if (settled) return;
      settled = true;
      if (timer) window.clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
      try { source?.disconnect(); } catch (_) { /* best effort */ }
      if (context) context.close().catch(() => {});
      resolve(interrupted);
    };
    const abort = () => finish(false);
    signal?.addEventListener("abort", abort, { once: true });

    try {
      context = new (window.AudioContext || window.webkitAudioContext)();
      analyser = context.createAnalyser();
      analyser.fftSize = 2048;
      source = context.createMediaStreamSource(stream);
      source.connect(analyser);
    } catch (_) {
      finish(false);
      return;
    }

    const sample = () => {
      if (settled) return;
      analyser.getFloatTimeDomainData(samples);
      let energy = 0;
      for (const value of samples) energy += value * value;
      const rms = Math.sqrt(energy / samples.length);
      const warmup = performance.now() - startedAt < 350;
      streak = !warmup && rms > 0.045 ? streak + 1 : 0;
      if (streak >= 3) {
        finish(true);
        return;
      }
      timer = window.setTimeout(sample, 50);
    };
    sample();
  });
}

async function synthesizeAndPlay(text, waitForEnd = false, interruptStream = null) {
  const blob = await synthesizeAudio(text);
  return playAudioBlob(blob, waitForEnd, interruptStream);
}

async function playAudioBlob(blob, waitForEnd = false, interruptStream = null) {
  revokePlayerUrl();
  state.currentObjectUrl = URL.createObjectURL(blob);
  els.player.src = state.currentObjectUrl;
  els.player.hidden = false;
  if (!waitForEnd) {
    await els.player.play().catch(() => {});
    return;
  }

  return new Promise((resolve) => {
    let finished = false;
    const abortController = interruptStream ? new AbortController() : null;
    const bargeIn = interruptStream ? waitForBargeIn(interruptStream, abortController.signal) : null;
    const finish = () => {
      if (finished) return;
      finished = true;
      abortController?.abort();
      if (state.voiceDialogPlaybackCancel === cancel) state.voiceDialogPlaybackCancel = null;
      els.player.onended = null;
      els.player.onerror = null;
      resolve(false);
    };
    const cancel = () => {
      if (finished) return;
      els.player.pause();
      finish();
    };
    if (interruptStream) state.voiceDialogPlaybackCancel = cancel;
    els.player.onended = finish;
    els.player.onerror = finish;
    bargeIn?.then((interrupted) => {
      if (!interrupted || finished) return;
      els.player.pause();
      finished = true;
      abortController.abort();
      if (state.voiceDialogPlaybackCancel === cancel) state.voiceDialogPlaybackCancel = null;
      els.player.onended = null;
      els.player.onerror = null;
      resolve(true);
    });
    els.player.play().catch(finish);
  });
}

async function speakCurrent(textOverride = "") {
  const sourceText = textOverride || els.reply.value.trim() || els.transcript.value.trim();
  if (!sourceText) {
    setStatus("No text to speak.");
    return;
  }

  state.activeOperation = true;
  renderPipelineActivity({ active: true, phase: "loading", progress: 5, message: "Silero загружается…" });
  setStatus("Silero загружается…", "working");
  try {
    await synthesizeAndPlay(sourceText);
    setStatus("Озвучка готова.");
  } finally {
    state.activeOperation = false;
  }
}

function synthesizeAudio(text) {
  const form = new FormData();
  form.append("text", text);
  form.append("tts_language", els.ttsLanguage.value);
  form.append("tts_speaker", els.ttsSpeaker?.value || "");
  form.append("pace", els.pace.value);
  form.append("tts_temperature", els.ttsTemperature.value);
  form.append("tts_top_k", els.ttsTopK.value);
  return apiFetch("/api/speak", { method: "POST", body: form }).then(async (res) => {
    if (!res.ok) {
      const payload = await res.json().catch(() => ({}));
      throw new Error(payload.detail ? JSON.stringify(payload.detail) : "TTS failed.");
    }
    return res.blob();
  });
}

async function streamAskAndSpeak() {
  const text = els.transcript.value.trim();
  if (!text) {
    setStatus("No transcript yet.");
    return;
  }
  if (!els.llmBaseUrl.value.trim()) {
    setStatus("Set OpenAI-compatible base URL first.");
    return;
  }

  state.activeOperation = true;
  els.reply.value = "";
  renderPipelineActivity({ active: true, phase: "llm", progress: 18, message: "LLM думает…" });
  setStatus("LLM думает…", "working");
  const form = new FormData();
  form.append("text", text);
  form.append("api_key", els.llmApiKey.value.trim());
  form.append("base_url", els.llmBaseUrl.value.trim());
  form.append("model", els.llmModel.value.trim());
  form.append("system_prompt", els.systemPrompt.value);
  form.append("temperature", "0.7");
  form.append("thinking", String(Boolean(els.llmThinking?.checked)));
  form.append("use_vpn", String(els.vpnEnabled.checked && els.vpnForLlm.checked));

  const res = await apiFetch("/api/chat/stream", { method: "POST", body: form });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail ? JSON.stringify(payload.detail) : "Streaming chat failed.");
  }
  if (!res.body) throw new Error("Streaming response is unavailable in this browser.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let eventBuffer = "";
  let completeReply = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      eventBuffer += decoder.decode(value, { stream: true });
      const events = eventBuffer.split("\n\n");
      eventBuffer = events.pop() || "";
      for (const event of events) {
        const line = event.split("\n").find((item) => item.startsWith("data:"));
        if (!line) continue;
        const payload = line.slice(5).trim();
        if (payload === "[DONE]") continue;
        const chunk = JSON.parse(payload).text || "";
        if (!chunk) continue;
        renderPipelineActivity({ active: true, phase: "llm", progress: 42, message: "LLM отвечает…" });
        els.reply.value += chunk;
        completeReply += chunk;
      }
    }
    eventBuffer += decoder.decode();
    const finalEvents = eventBuffer.split("\n\n");
    for (const event of finalEvents) {
      const line = event.split("\n").find((item) => item.startsWith("data:"));
      if (!line || line.slice(5).trim() === "[DONE]") continue;
      const chunk = JSON.parse(line.slice(5).trim()).text || "";
      els.reply.value += chunk;
      completeReply += chunk;
    }
  } finally {
    reader.releaseLock();
  }

  const textToSpeak = completeReply.trim() || els.reply.value.trim();
  if (!textToSpeak) throw new Error("LLM вернула пустой ответ.");
  renderPipelineActivity({ active: true, phase: "generating", progress: 52, message: "LLM готов. Silero озвучивает весь ответ…" });
  setStatus("LLM готов. Silero озвучивает весь ответ…", "working");
  await synthesizeAndPlay(textToSpeak, true);
  state.activeOperation = false;
  setStatus("Цельная озвучка ответа завершена.");
}

async function transcribeAskAndSpeak() {
  await transcribeCurrent();
  await streamAskAndSpeak();
}

async function saveRvcSettings() {
  const body = new FormData();
  body.append("enabled", String(Boolean(els.rvcEnabled.checked)));
  body.append("command_template", els.rvcCommandTemplate.value.trim());
  const res = await apiFetch("/api/rvc/settings", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail ? JSON.stringify(payload.detail) : "RVC settings failed.");
  renderRvc(payload);
  setStatus(payload.enabled ? "RVC включён." : "RVC выключен.");
}

async function uploadRvcFiles() {
  const model = els.rvcModelFile.files?.[0];
  const index = els.rvcIndexFile.files?.[0];
  if (!model) {
    await saveRvcSettings();
    return;
  }
  const body = new FormData();
  body.append("model", model, model.name);
  if (index) body.append("index", index, index.name);
  const res = await apiFetch("/api/rvc/upload", { method: "POST", body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail ? JSON.stringify(payload.detail) : "RVC upload failed.");
  renderRvc(payload);
  els.rvcModelFile.value = "";
  els.rvcIndexFile.value = "";
  setStatus("RVC-модель сохранена.");
}

async function deleteRvcFiles() {
  const res = await apiFetch("/api/rvc/delete", { method: "POST" });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail ? JSON.stringify(payload.detail) : "RVC delete failed.");
  renderRvc(payload);
  setStatus("RVC-модель удалена.");
}

els.recordBtn.addEventListener("click", startRecording);
els.stopBtn.addEventListener("click", stopRecording);
els.transcribeBtn.addEventListener("click", () => transcribeCurrent().catch((err) => setStatus(err.message)));
els.speakBtn.addEventListener("click", () => speakCurrent().catch((err) => setStatus(err.message)));
els.bridgeBtn.addEventListener("click", () => {
  state.activeOperation = true;
  transcribeAskAndSpeak()
    .catch((err) => setStatus(err.message, "error"))
    .finally(() => { state.activeOperation = false; });
});
if (els.mangoStartBtn) els.mangoStartBtn.addEventListener("click", () => startMangoCall().catch((error) => setStatus(error.message, "error")));
if (els.mangoStopBtn) els.mangoStopBtn.addEventListener("click", () => stopMangoCall().catch((error) => setStatus(error.message, "error")));
if (els.mangoSmsBtn) els.mangoSmsBtn.addEventListener("click", () => sendMangoSms().catch((error) => setStatus(error.message, "error")));
if (els.telegramTestBtn) els.telegramTestBtn.addEventListener("click", () => testTelegram().catch((error) => setStatus(error.message, "error")));
if (els.dialogTestBtn) els.dialogTestBtn.addEventListener("click", () => runDialogTest().catch((error) => setStatus(error.message, "error")));
if (els.calendarDate) els.calendarDate.addEventListener("change", () => fetchCalendar().catch((error) => setStatus(error.message, "error")));
if (els.calendarRefreshBtn) els.calendarRefreshBtn.addEventListener("click", () => fetchCalendar().then(() => setStatus("Календарь обновлён.")).catch((error) => setStatus(error.message, "error")));
if (els.calendarSaveSettingsBtn) els.calendarSaveSettingsBtn.addEventListener("click", () => saveCalendarSettings().catch((error) => setStatus(error.message, "error")));
if (els.calendarBookBtn) els.calendarBookBtn.addEventListener("click", () => bookCalendarSlot().catch((error) => setStatus(error.message, "error")));
if (els.voiceDialogStartBtn) els.voiceDialogStartBtn.addEventListener("click", () => startVoiceDialog().catch((error) => { stopVoiceDialog(); setStatus(error.message, "error"); }));
if (els.voiceDialogStopBtn) els.voiceDialogStopBtn.addEventListener("click", stopVoiceDialog);
els.openAudioFolderBtn.addEventListener("click", () => storageAction("/api/storage/open", "audio", "Открываю папку входных файлов...").catch((err) => setStatus(err.message)));
els.deleteAudioBtn.addEventListener("click", () => storageAction("/api/storage/clear", "audio", "Удаляю входной файл...").catch((err) => setStatus(err.message)));
els.openOutputFolderBtn.addEventListener("click", () => storageAction("/api/storage/open", "outputs", "Открываю папку готовых WAV...").catch((err) => setStatus(err.message)));
els.deleteOutputsBtn.addEventListener("click", () => storageAction("/api/storage/clear", "outputs", "Очищаю готовые WAV...").catch((err) => setStatus(err.message)));
els.openModelFolderBtn.addEventListener("click", () => storageAction("/api/storage/open", "model_cache", "Открываю кэш модели...").catch((err) => setStatus(err.message)));
els.fileInput.addEventListener("change", () => {
  state.recordedFile = null;
  const file = els.fileInput.files?.[0];
  if (!file) return;
  persistInputAudio(file)
    .then(() => setStatus("Аудиофайл сохранён на диске проекта."))
    .catch((error) => setStatus(error.message));
});

els.pace.addEventListener("input", updatePaceLabel);
els.ttsTemperature.addEventListener("input", updateGenerationLabels);
els.vpnEnabled.addEventListener("change", () => {
  savePrefs();
  const action = els.vpnEnabled.checked ? "/api/vpn/start" : "/api/vpn/stop";
  vpnAction(action, els.vpnEnabled.checked ? "Starting VPN tunnel..." : "Stopping VPN tunnel...")
    .catch((error) => setStatus(error.message));
});
els.vpnForStt.addEventListener("change", savePrefs);
els.vpnForLlm.addEventListener("change", savePrefs);
els.vpnStartBtn.addEventListener("click", () => vpnAction("/api/vpn/start", "Starting VPN tunnel...").catch((error) => setStatus(error.message)));
els.vpnStopBtn.addEventListener("click", () => vpnAction("/api/vpn/stop", "Stopping VPN tunnel...").catch((error) => setStatus(error.message)));
els.vpnDownloadBtn.addEventListener("click", () => vpnAction("/api/vpn/download", "Downloading VPN client...", "VPN client downloaded.").catch((error) => setStatus(error.message)));
els.ttsDeviceSwitch.addEventListener("click", () => toggleTtsDevice().catch((error) => setStatus(error.message)));
els.ttsLanguage.addEventListener("change", () => {
  fillTtsSpeakers(state.ttsSpeakers || {}, state.ttsSpeakerNames || {});
  savePrefs();
});
if (els.ttsSpeaker) els.ttsSpeaker.addEventListener("change", savePrefs);
if (els.saveRvcBtn) els.saveRvcBtn.addEventListener("click", () => uploadRvcFiles().catch((error) => setStatus(error.message, "error")));
if (els.deleteRvcBtn) els.deleteRvcBtn.addEventListener("click", () => deleteRvcFiles().catch((error) => setStatus(error.message, "error")));
if (els.openRvcFolderBtn) els.openRvcFolderBtn.addEventListener("click", () => storageAction("/api/storage/open", "rvc", "Открываю папку RVC...").catch((error) => setStatus(error.message, "error")));
if (els.rvcEnabled) els.rvcEnabled.addEventListener("change", () => saveRvcSettings().catch((error) => setStatus(error.message, "error")));
if (els.rvcCommandTemplate) els.rvcCommandTemplate.addEventListener("change", () => saveRvcSettings().catch((error) => setStatus(error.message, "error")));
if (els.refreshAudioDevicesBtn) els.refreshAudioDevicesBtn.addEventListener("click", () => fetchAudioDevices().then(() => setStatus("Список аудиоустройств обновлён.")).catch((error) => setStatus(error.message, "error")));
if (els.testAudioRouteBtn) els.testAudioRouteBtn.addEventListener("click", () => testAudioRoute().catch((error) => setStatus(error.message, "error")));
if (els.saveAudioSettingsBtn) els.saveAudioSettingsBtn.addEventListener("click", () => saveAudioSettings().catch((error) => setStatus(error.message, "error")));
if (els.llmProvider) els.llmProvider.addEventListener("change", () => {
  applyLlmProvider();
  savePrefs();
});

if (els.visionBaseUrl) [els.visionBaseUrl, els.visionApiKey, els.visionModel, els.visionPrompt, els.visionUseVpn].forEach((element) => {
  element.addEventListener("input", saveVisionPrefs);
});
if (els.visionFileInput) els.visionFileInput.addEventListener("change", (event) => {
  addVisionFiles(event.target.files);
  event.target.value = "";
});
if (els.visionDropzone) {
  els.visionDropzone.addEventListener("click", () => els.visionFileInput?.click());
  els.visionDropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    els.visionDropzone.dataset.dragging = "true";
  });
  els.visionDropzone.addEventListener("dragleave", () => { delete els.visionDropzone.dataset.dragging; });
  els.visionDropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    delete els.visionDropzone.dataset.dragging;
    addVisionFiles(event.dataTransfer.files);
  });
}
document.addEventListener("paste", (event) => {
  const images = Array.from(event.clipboardData?.items || [])
    .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
    .map((item) => item.getAsFile())
    .filter(Boolean);
  if (images.length) {
    event.preventDefault();
    addVisionFiles(images);
  }
});
if (els.visionAnalyzeBtn) els.visionAnalyzeBtn.addEventListener("click", () => analyzeVisionImages().catch((error) => setStatus(error.message, "error")));
if (els.visionClearQueueBtn) els.visionClearQueueBtn.addEventListener("click", () => clearVisionQueue().catch((error) => setStatus(error.message, "error")));
if (els.visionClearHistoryBtn) els.visionClearHistoryBtn.addEventListener("click", () => clearVisionHistory().catch((error) => setStatus(error.message, "error")));

startSystemMonitor();
els.ttsModel.addEventListener("change", () => {
  updateTtsModelHelp(Array.from(els.ttsModel.options).map((option) => ({
    id: option.value,
    supportsInstruct: option.value === "1.7b",
    download: option.textContent.split(" · ").slice(-1)[0],
  })), state.ttsQuantization);
  savePrefs();
});
[
  "input",
  "change",
].forEach((eventName) => {
  els.apiKey.addEventListener(eventName, savePrefs);
  els.language.addEventListener(eventName, savePrefs);
  els.sttModel.addEventListener(eventName, savePrefs);
  if (els.llmProvider) els.llmProvider.addEventListener(eventName, savePrefs);
  els.llmBaseUrl.addEventListener(eventName, savePrefs);
  els.llmApiKey.addEventListener(eventName, savePrefs);
  els.llmModel.addEventListener(eventName, savePrefs);
  els.systemPrompt.addEventListener(eventName, savePrefs);
  els.telegramBotToken?.addEventListener(eventName, savePrefs);
  els.telegramChatIds?.addEventListener(eventName, savePrefs);
  els.ttsModel.addEventListener(eventName, savePrefs);
  els.ttsLanguage.addEventListener(eventName, savePrefs);
  els.ttsTemperature.addEventListener(eventName, savePrefs);
  els.ttsTopK.addEventListener(eventName, savePrefs);
  els.pace.addEventListener(eventName, savePrefs);
});

ensureLlmThinkingControl();
placeVisionVpnControl();
loadPrefs();
loadVisionState().catch((error) => setStatus(`Vision не подключён: ${error.message}`, "error"));
fetchConfig()
  .then(() => {
    if (!state.calendarBackendConnected && !state.calendarRetryTimer) setStatus("Готово.");
  })
  .catch((error) => setStatus(`Backend не подключён: ${error.message}`, "error"));
initializeCalendar();
syncVpnStatus().catch(() => {});

function openSettings() {
  if (typeof els.settingsDialog.showModal === "function") {
    els.settingsDialog.showModal();
  } else {
    els.settingsDialog.setAttribute("open", "");
  }
}

function closeSettings() {
  if (typeof els.settingsDialog.close === "function") els.settingsDialog.close();
  else els.settingsDialog.removeAttribute("open");
}

els.settingsBtn.addEventListener("click", openSettings);
els.closeSettingsBtn.addEventListener("click", closeSettings);
els.doneSettingsBtn.addEventListener("click", closeSettings);
els.settingsDialog.addEventListener("click", (event) => {
  if (event.target === els.settingsDialog) closeSettings();
});
