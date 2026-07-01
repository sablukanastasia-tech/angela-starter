"""ОПЦИОНАЛЬНЫЙ модуль: сбор идей в Notion.

Выключен по умолчанию. Включить: ENABLE_NOTION=true в .env (и на Railway).
Нужны переменные: NOTION_TOKEN, NOTION_IDEAS_DB_ID.

Что умеет:
  • save_idea   — Claude вызывает когда слышит «мысль», «идея», «хочу попробовать»
  • get_ideas   — возвращает необработанные идеи (для обзоров или по запросу)
"""

import logging

import httpx

from assistant.config import NOTION_IDEAS_DB_ID, NOTION_TOKEN

logger = logging.getLogger(__name__)

_BASE = "https://api.notion.com/v1"
_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

PROMPT_ADDON = """\
МОДУЛЬ ИДЕЙ включён.

если человек говорит «идея», «мысль», «хочу попробовать», «запомни», «есть идея» — \
сохрани через save_idea (без лишних вопросов), затем ОБЯЗАТЕЛЬНО спроси о состоянии:

«В каком состоянии записываешь?
1. Мечтаю
2. Планирую/сделаю
3. Возбуждение
4. Вдохновение
5. Тревога
6. Отчаяние
7. Безнадега
8. Хочу»

когда человек ответит (цифрой или словом) — вызови set_idea_state с page_id из \
предыдущего save_idea и соответствующим состоянием. коротко подтверди.

если просит показать идеи — вызови get_ideas и перечисли коротко.
"""

TOOLS = [
    {
        "name": "save_idea",
        "description": (
            "Сохранить идею в Notion. Вызывай когда человек говорит «идея», «мысль», "
            "'хочу попробовать', «запомни». Теги выбирай из: продукт, маркетинг, "
            "личное, работа, творчество — только если очевидно подходят."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "idea": {"type": "string", "description": "Текст идеи"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Теги из: продукт, маркетинг, личное, работа, творчество",
                },
                "notes": {"type": "string", "description": "Дополнительный контекст"},
            },
            "required": ["idea"],
        },
    },
    {
        "name": "set_idea_state",
        "description": (
            "Записать состояние к идее после того, как человек ответил на вопрос о состоянии. "
            "page_id берётся из ответа save_idea."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "ID страницы из save_idea"},
                "state": {
                    "type": "string",
                    "description": "Одно из: Мечтаю, Планирую/сделаю, Возбуждение, Вдохновение, Тревога, Отчаяние, Безнадега, Хочу",
                },
            },
            "required": ["page_id", "state"],
        },
    },
    {
        "name": "get_ideas",
        "description": (
            "Получить идеи из Notion. По умолчанию — только необработанные (статус «Новая»). "
            "Используй для обзоров или когда человек просит показать идеи."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Фильтр по статусу: '🆕 Новая', '🤔 Обдумать', '🚀 В работе'. "
                    "Если не указан — возвращает все необработанные (Новая + Обдумать).",
                },
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
]


def _save_idea(data: dict) -> dict:
    properties: dict = {
        "Идея": {"title": [{"text": {"content": data["idea"]}}]},
        "Статус": {"select": {"name": "🆕 Новая"}},
    }
    tags = data.get("tags") or []
    if tags:
        properties["Теги"] = {"multi_select": [{"name": t} for t in tags]}
    notes = data.get("notes", "").strip()
    if notes:
        properties["Заметки"] = {"rich_text": [{"text": {"content": notes}}]}

    resp = httpx.post(
        f"{_BASE}/pages",
        headers=_HEADERS,
        json={"parent": {"database_id": NOTION_IDEAS_DB_ID}, "properties": properties},
        timeout=15,
    )
    resp.raise_for_status()
    page_id = resp.json().get("id", "")
    return {"saved": True, "idea": data["idea"], "page_id": page_id}


def _get_ideas(data: dict) -> list[dict]:
    status = data.get("status")
    limit = min(data.get("limit", 10), 25)

    if status:
        filters = {"property": "Статус", "select": {"equals": status}}
    else:
        filters = {
            "or": [
                {"property": "Статус", "select": {"equals": "🆕 Новая"}},
                {"property": "Статус", "select": {"equals": "🤔 Обдумать"}},
                {"property": "Статус", "select": {"is_empty": True}},
            ]
        }

    resp = httpx.post(
        f"{_BASE}/databases/{NOTION_IDEAS_DB_ID}/query",
        headers=_HEADERS,
        json={
            "filter": filters,
            "sorts": [{"property": "Добавлено", "direction": "descending"}],
            "page_size": limit,
        },
        timeout=15,
    )
    resp.raise_for_status()

    ideas = []
    for page in resp.json().get("results", []):
        props = page.get("properties", {})
        title_parts = props.get("Идея", {}).get("title", [])
        text = "".join(t.get("plain_text", "") for t in title_parts)
        tags = [o["name"] for o in props.get("Теги", {}).get("multi_select", [])]
        status_val = (props.get("Статус", {}).get("select") or {}).get("name", "")
        added = props.get("Добавлено", {}).get("created_time", "")[:10]
        ideas.append({"idea": text, "status": status_val, "tags": tags, "added": added})

    return ideas


def _set_idea_state(data: dict) -> dict:
    page_id = data["page_id"]
    state = data["state"]
    resp = httpx.patch(
        f"{_BASE}/pages/{page_id}",
        headers=_HEADERS,
        json={"properties": {"Состояние": {"select": {"name": state}}}},
        timeout=15,
    )
    resp.raise_for_status()
    return {"updated": True, "state": state}


HANDLERS = {
    "save_idea": _save_idea,
    "set_idea_state": _set_idea_state,
    "get_ideas": _get_ideas,
}
