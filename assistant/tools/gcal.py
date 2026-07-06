"""ОПЦИОНАЛЬНЫЙ модуль: Google Calendar (события на сегодня/ближайшие + создание).

Выключен по умолчанию. Включить: ENABLE_GCAL=true в .env + ключи Google.
Сначала пройди общий шаг авторизации Google. Подробно — docs/05-add-calendar.md
"""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from assistant.config import TIMEZONE
from assistant.google_auth import get_access_token

logger = logging.getLogger(__name__)
API = "https://www.googleapis.com/calendar/v3"
TASKS_API = "https://tasks.googleapis.com/tasks/v1"

PROMPT_ADDON = """\
МОДУЛЬ КАЛЕНДАРЯ включён. ПРАВИЛО: любой вопрос про расписание, встречи, события, задачи, \
«что у меня», «что на сегодня/завтра/на неделе» — СНАЧАЛА вызови инструмент, потом отвечай. \
Никогда не отвечай про календарь или задачи без вызова инструмента.
— утренний чекин: вызови gcal_today и gtasks_upcoming, покажи встречи и задачи (✓) на сегодня.
— «сегодня» / «что у меня» → gcal_today + gtasks_upcoming.
— «завтра» / «ближайшие дни» / «на неделе» → gcal_upcoming с hours=48 (или больше).
— «поставь встречу / добавь в календарь / создай» → gcal_create_event (время в ISO).
— «задачи» / «дела» / «что с галочкой» → gtasks_upcoming.
— «добавь задачу / запиши дело / надо не забыть сделать X» → gtasks_create (только дата, без времени).
"""

TOOLS = [
    {
        "name": "gcal_today",
        "description": "События календаря на сегодня (время + название).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gcal_upcoming",
        "description": "Ближайшие события (по умолчанию на 24 часа вперёд).",
        "input_schema": {
            "type": "object",
            "properties": {"hours": {"type": "integer", "default": 24}},
        },
    },
    {
        "name": "gcal_create_event",
        "description": "Создать событие. Время в ISO: 2026-01-31T09:00:00. attendees — email-ы участников.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_time": {"type": "string", "description": "ISO начало"},
                "end_time": {"type": "string", "description": "ISO конец"},
                "description": {"type": "string"},
                "location": {"type": "string", "description": "Место или ссылка (напр. на Zoom)"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "start_time", "end_time"],
        },
    },
    {
        "name": "gtasks_upcoming",
        "description": (
            "Задачи (с галочкой ✓) из Google Tasks — невыполненные. "
            "У задачи есть только ДАТА (due_date, YYYY-MM-DD), без времени — "
            "не придумывай час, говори про день ('на сегодня', 'просрочена вчера')."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gtasks_create",
        "description": (
            "Создать задачу (с галочкой ✓) в Google Tasks. "
            "У задачи только ДАТА (YYYY-MM-DD), время указать нельзя — "
            "если человек называет время, предложи событие календаря (gcal_create_event)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Название задачи"},
                "due_date": {"type": "string", "description": "Срок YYYY-MM-DD (можно без срока)"},
                "notes": {"type": "string", "description": "Заметка к задаче"},
            },
            "required": ["title"],
        },
    },
]


def _list_calendar_ids(token: str) -> list[str]:
    """Вернуть ID всех календарей, подключённых к аккаунту."""
    try:
        resp = httpx.get(f"{API}/users/me/calendarList", headers={
            "Authorization": f"Bearer {token}",
        }, timeout=15)
        resp.raise_for_status()
        ids = [c["id"] for c in resp.json().get("items", [])]
        logger.info("gcal календари: %s", ids)
        return ids or ["primary"]
    except Exception:
        logger.exception("не смог получить список календарей, использую primary")
        return ["primary"]


def _events_between(start: datetime, end: datetime) -> list[dict] | dict:
    token = get_access_token()
    if not token:
        return {"error": "Google не авторизован — открой /google/auth у бота"}
    try:
        time_min = start.isoformat()
        time_max = end.isoformat()
        logger.info("gcal запрос: %s → %s", time_min, time_max)
        cal_ids = _list_calendar_ids(token)
        all_items: list[dict] = []
        for cal_id in cal_ids:
            try:
                resp = httpx.get(f"{API}/calendars/{quote(cal_id, safe='')}/events", headers={
                    "Authorization": f"Bearer {token}",
                }, params={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "singleEvents": "true",
                    "orderBy": "startTime",
                }, timeout=15)
                resp.raise_for_status()
                items = resp.json().get("items", [])
            except Exception:
                logger.exception("gcal: пропускаю календарь %s (ошибка запроса)", cal_id)
                continue
            logger.info("  [%s] вернул %d событий", cal_id, len(items))
            for e in items:
                logger.info("    событие: %s | %s", e.get("summary"), e.get("start"))
            all_items.extend(items)
        all_items.sort(key=lambda e: (
            e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", "")
        ))
        return [{
            "title": e.get("summary", "(без названия)"),
            "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date", ""),
            "location": e.get("location", ""),
        } for e in all_items]
    except Exception as exc:
        logger.exception("ошибка Calendar")
        return {"error": str(exc)}


def _gcal_today(data: dict):
    now = datetime.now(TIMEZONE)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return _events_between(start, start + timedelta(days=1))


def _gcal_upcoming(data: dict):
    now = datetime.now(TIMEZONE)
    return _events_between(now, now + timedelta(hours=data.get("hours", 24)))


def _gcal_create_event(data: dict) -> dict:
    token = get_access_token()
    if not token:
        return {"error": "Google не авторизован — открой /google/auth у бота"}
    body = {
        "summary": data["title"],
        "start": {"dateTime": data["start_time"], "timeZone": str(TIMEZONE)},
        "end": {"dateTime": data["end_time"], "timeZone": str(TIMEZONE)},
    }
    if data.get("description"):
        body["description"] = data["description"]
    if data.get("location"):
        body["location"] = data["location"]
    if data.get("attendees"):
        body["attendees"] = [{"email": e} for e in data["attendees"]]
    try:
        resp = httpx.post(f"{API}/calendars/primary/events", headers={
            "Authorization": f"Bearer {token}",
        }, params={"sendUpdates": "all"}, json=body, timeout=15)
        resp.raise_for_status()
        e = resp.json()
        return {"created": True, "title": e.get("summary", ""), "link": e.get("htmlLink", "")}
    except Exception as exc:
        logger.exception("ошибка создания события")
        return {"error": str(exc)}


def _list_tasklist_ids(token: str) -> list[str]:
    """Вернуть ID всех списков задач на аккаунте."""
    try:
        resp = httpx.get(f"{TASKS_API}/users/@me/lists", headers={
            "Authorization": f"Bearer {token}",
        }, timeout=15)
        resp.raise_for_status()
        ids = [t["id"] for t in resp.json().get("items", [])]
        return ids or ["@default"]
    except Exception:
        logger.exception("не смог получить списки задач, использую @default")
        return ["@default"]


def _gtasks_upcoming(data: dict):
    token = get_access_token()
    if not token:
        return {"error": "Google не авторизован — открой /google/auth у бота"}
    try:
        all_items: list[dict] = []
        for list_id in _list_tasklist_ids(token):
            try:
                resp = httpx.get(f"{TASKS_API}/lists/{quote(list_id, safe='')}/tasks", headers={
                    "Authorization": f"Bearer {token}",
                }, params={
                    "showCompleted": "false",
                    "showHidden": "false",
                }, timeout=15)
                resp.raise_for_status()
                all_items.extend(resp.json().get("items", []))
            except Exception:
                logger.exception("gtasks: пропускаю список %s (ошибка запроса)", list_id)
                continue
        all_items.sort(key=lambda t: t.get("due", "9999"))
        for t in all_items:
            logger.info("    задача: %s | сырой due: %s", t.get("title"), t.get("due"))
        # У задач Google Tasks есть только ДАТА (время всегда 00:00 UTC — фикция).
        # Отдаём боту только дату (YYYY-MM-DD), без выдуманного часа и без съезда суток.
        return [{
            "title": t.get("title", "(без названия)"),
            "due_date": (t.get("due") or "")[:10],
            "notes": t.get("notes", ""),
        } for t in all_items]
    except Exception as exc:
        logger.exception("ошибка Tasks")
        return {"error": str(exc)}


def _gtasks_create(data: dict) -> dict:
    token = get_access_token()
    if not token:
        return {"error": "Google не авторизован — открой /google/auth у бота"}
    body: dict = {"title": data["title"]}
    if data.get("notes"):
        body["notes"] = data["notes"]
    if data.get("due_date"):
        # API принимает due только как RFC3339-момент; время игнорируется,
        # значима лишь дата — поэтому полночь UTC.
        body["due"] = f"{data['due_date']}T00:00:00.000Z"
    try:
        resp = httpx.post(f"{TASKS_API}/lists/@default/tasks", headers={
            "Authorization": f"Bearer {token}",
        }, json=body, timeout=15)
        resp.raise_for_status()
        t = resp.json()
        return {
            "created": True,
            "title": t.get("title", ""),
            "due_date": (t.get("due") or "")[:10],
        }
    except Exception as exc:
        logger.exception("ошибка создания задачи")
        return {"error": str(exc)}


HANDLERS = {
    "gcal_today": _gcal_today,
    "gcal_upcoming": _gcal_upcoming,
    "gcal_create_event": _gcal_create_event,
    "gtasks_upcoming": _gtasks_upcoming,
    "gtasks_create": _gtasks_create,
}
