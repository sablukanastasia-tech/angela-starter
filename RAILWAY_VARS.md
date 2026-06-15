# Переменные Railway — эталонный список (для сервиса `angela-starter`)

Шпаргалка: какие переменные должны стоять на Railway, чтобы Мозгоправ работал
полностью (чекины, напоминания, недельный обзор, голосовые).

## Как пользоваться

1. Railway → сервис `angela-starter` → вкладка **Variables**
2. Кнопка ⋮ → **Raw Editor**
3. Должны присутствовать ВСЕ 16 строк ниже. Если чего-то нет — добавь.
4. Сохрани → дождись зелёного деплоя → при необходимости **Deployments → ⋮ → Redeploy**.
5. Проверь: текст боту + голосовое.

> ⚠️ Не добавляй переменные из панели **«Suggested Variables»** — они тянут дефолты
> из `.env.example` (всё `false`, `Europe/Kyiv`, `8`) и перетирают нужные значения.

## Секреты (значения НЕ здесь — бери из локального `.env` или своих записей)

| Переменная | Что это |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен бота от @BotFather |
| `TELEGRAM_CHAT_ID` | твой chat_id (бот отвечает только тебе) |
| `ANTHROPIC_API_KEY` | ключ Claude (мозг бота) |
| `SUPABASE_URL` | адрес базы Supabase |
| `SUPABASE_KEY` | service_role ключ Supabase (секретный!) |
| `OPENAI_API_KEY` | ключ OpenAI для голосовых (Whisper) |

## Несекретные значения (можно ставить прямо так)

```
TIMEZONE=Europe/Vienna
MORNING_HOUR=9
MORNING_MINUTE=15
EVENING_HOUR=21
EVENING_MINUTE=30
ENABLE_REMINDERS=true
ENABLE_WEEKLY_REVIEW=true
WEEKLY_REVIEW_DOW=mon
WEEKLY_REVIEW_HOUR=9
WEEKLY_REVIEW_MINUTE=15
```

## Итог: расписание и функции при этих переменных

- 🌅 утренний чекин — будни 9:15 (Вена)
- 🌙 вечерний чекин — будни 21:30
- 📅 недельный обзор — понедельник 9:15
- ⏰ напоминания — включены
- 🎤 голосовые — включены (нужен OPENAI_API_KEY)

## Если что-то «слетело»

- Бот молчит и на текст → деплой упал, смотри Deployments / логи.
- Голос: «голосовые пока не подключены» → нет `OPENAI_API_KEY` при старте → добавь + Redeploy.
- Голос: «не получилось разобрать» → ключ есть, но битый → перезапиши `OPENAI_API_KEY`.
- Напоминания/обзор не идут → проверь `ENABLE_REMINDERS` / `ENABLE_WEEKLY_REVIEW` = `true`.

Полные значения секретов лежат в локальном `.env` (он в `.gitignore`).
