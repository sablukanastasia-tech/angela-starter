"""ОПЦИОНАЛЬНЫЙ модуль: Google Calendar (события на сегодня/ближайшие + создание).

Выключен по умолчанию. Включить: ENABLE_GCAL=true в .env + ключи Google.
Сначала пройди общий шаг авторизации Google. Подробно — docs/05-add-calendar.md
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from assistant.config import TIMEZONE
from assistant.google_auth import get_access_token

logger = logging.getLogger(__name__)
API = "https://www.googleapis.com/calendar/v3"

PROMPT_ADDON = """\
МОДУЛЬ КАЛЕНДАРЯ включён. ПРАВИЛО: любой вопрос про расписание, встречи, события, \
«что у меня», «что на сегодня/завтра/на неделе» — СНАЧАЛА вызови инструмент, потом отвечай. \
Никогда не отвечай про календарь без вызова инструмента.
— утренний чекин: вызови gcal_today, покажи встречи на сегодня (время + название).
— «сегодня» / «что у меня» → gcal_today.
— «завтра» / «ближайшие дни» / «на неделе» → gcal_upcoming с hours=48 (или больше).
— «поставь встречу / добавь в календарь / создай» → gcal_create_event (время в ISO).
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
            resp = httpx.get(f"{API}/calendars/{cal_id}/events", headers={
                "Authorization": f"Bearer {token}",
            }, params={
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
            }, timeout=15)
            resp.raise_for_status()
            items = resp.json().get("items", [])
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


HANDLERS = {
    "gcal_today": _gcal_today,
    "gcal_upcoming": _gcal_upcoming,
    "gcal_create_event": _gcal_create_event,
}
