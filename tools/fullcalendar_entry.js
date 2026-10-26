import { Calendar } from "@fullcalendar/core";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import listPlugin from "@fullcalendar/list";
import ruLocale from "@fullcalendar/core/locales/ru.js";

// Expose one stable browser global for both the Tauri WebView and dev browser.
window.FullCalendar = {
  Calendar,
  DayGrid: dayGridPlugin,
  TimeGrid: timeGridPlugin,
  Interaction: interactionPlugin,
  List: listPlugin,
  RuLocale: ruLocale,
};
