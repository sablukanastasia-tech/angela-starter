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
МОДУЛЬ ИДЕЙ включён. если человек говорит «идея», «мысль», «хочу попробовать», \
«запомни», «есть идея» — сохрани через save_idea, не переспрашивай лишнего. \
ВСЕГДА после вызова save_idea напиши текстовый ответ — хотя бы «записала». \
если просит показать идеи — вызови get_ideas и перечисли их коротко.
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
    return {"saved": True, "idea": data["idea"]}


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


HANDLERS = {
    "save_idea": _save_idea,
    "get_ideas": _get_ideas,
}
