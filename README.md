# AngelA Starter 🌿

Your personal AI assistant in **Telegram** — checks in with you every morning
and evening, remembers your conversations, and grows with you one skill at a time.
Built on Claude. Fork it, make it yours.

> **Russian-first:** the bot speaks Russian out of the box, lessons are in Russian
> (`docs/`). The personality lives in one file — easy to translate to any language.

---

## What works out of the box

- **🌅 Morning** — writes to you first: asks for your focus and top-3 priorities
- **🌙 Evening** — what did you get done? main win of the day?
- **💬 Chat** — talk any time; it remembers recent context
- Saves your reflections so you can look back

No email, no calendar, no clutter — until *you* add it.

## Add more, one lesson at a time

| Lesson | What you unlock |
|--------|----------------|
| `docs/03-add-cycle.md` | 🌙 Cycle tracking & energy by phase |
| `docs/04-add-gmail.md` | 📧 Read your important email |
| `docs/05-add-calendar.md` | 📅 Google Calendar — see events, create meetings |
| `docs/06-add-reminders.md` | ⏰ Reminders + Sunday weekly review |
| `docs/07-build-your-own-tool.md` | 🛠 Build your own tool from scratch |

---

## Two ways to start

### 🚀 One-click deploy (fastest)

Click the button, fill in your API keys in Railway's form, hit Deploy.
The bot starts itself and messages you in Telegram.

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template)

> You'll need: [Telegram bot token](docs/01-setup.md#шаг-1-создай-telegram-бота-5-мин) ·
> [Anthropic API key](docs/01-setup.md#шаг-3-получи-ключ-claude-5-мин) ·
> [Supabase URL + key](docs/01-setup.md#шаг-4-создай-базу-данных-supabase-10-мин)
> — each takes 5-10 min to get. See [`docs/01-setup.md`](docs/01-setup.md) for step-by-step.

### 🤖 Guided setup with Claude Code (interactive)

Clone or fork this repo, open in [Claude Code](https://claude.ai/code),
type **"начнём"**. Claude reads `CLAUDE.md` and walks you through everything —
asks your name, schedule, preferred tone, and edits the files itself.

```bash
git clone https://github.com/YOUR_USERNAME/angela-starter
cd angela-starter
claude   # opens Claude Code
# then type: начнём
```

---

## What you'll need

| Service | Cost | What for |
|---------|------|----------|
| Telegram | free | the bot lives here |
| [Anthropic API](https://console.anthropic.com) | ~$5 to start | the brain (Claude) |
| [Supabase](https://supabase.com) | free tier | memory & reflections |
| [Railway](https://railway.app) | ~$5/mo | runs the bot 24/7 |

---

## Structure

```
assistant/
  prompts.py   ← the ONLY file to customize (name, tone, check-in text)
  config.py    reads env variables
  agent.py     Claude brain — tool-use loop with caching & retries
  bot.py       Telegram handlers
  scheduler.py morning / evening / weekly check-ins
  db.py        Supabase — memory, reflections
  tools/       capabilities: core always on, the rest optional by flag
docs/          step-by-step lessons (Russian)
CLAUDE.md      interactive onboarding guide for Claude Code
schema.sql     run once in Supabase to create tables
.env.example   all settings with explanations
```

## License

MIT © 2026 Kate Andreeva — use it, fork it, build your own assistant on top.
