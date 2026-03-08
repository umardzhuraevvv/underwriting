# Воркфлоу: как работать с агентами

> Скинь этот файл в новый чат Cowork, чтобы восстановить контекст.

## Проект
- **Fintech Drive — Андеррайтинг** (FastAPI + PostgreSQL + Vanilla JS SPA)
- **Прод:** https://underwriting.up.railway.app
- **Репо:** ~/underwriting
- **Главная база знаний:** `CLAUDE.md` в корне репо (агенты читают автоматически)

## Процедура работы

### 1. Формулируем задачу (в Cowork)
Я (советчик) помогаю сформулировать ТЗ, создаю файл в `docs/tasks/`.

### 2. Подготовка (ты в терминале)
```bash
cd ~/underwriting && git checkout dev && git pull origin dev
```

### 3. Запуск агента (ты в терминале)
```bash
CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS=true claude -p "Прочитай CLAUDE.md. Задача: <описание>. Создай ветку feature/<название> от dev, сделай работу, запусти тесты, замержь в dev и запуш." --allowedTools Edit,Write,Bash
```

Для параллельных задач — открой несколько вкладок терминала и запусти в каждой.

### 4. Проверка на dev (ты в терминале)
```bash
cd ~/underwriting && git checkout dev && git pull origin dev
source venv/bin/activate && uvicorn app.main:app --port 8001 --reload
```
Открой localhost:8001, проверь что всё работает. Ctrl+C чтобы остановить.

### 5. Деплой в прод (ты в терминале)
Когда всё проверено:
```bash
git checkout main && git merge dev --no-edit && git push origin main
```
Railway задеплоит автоматически.

## Ключевые правила
- **Агенты работают ТОЛЬКО через dev**, никогда не пушат в main
- **CLAUDE.md** — единственный источник правды для агентов
- **Тесты обязательны** — агент должен запустить `pytest tests/ -v`
- **Все URL в app.js** должны быть `/api/v1/...`
- **Healthcheck:** `/api/health` (без /v1/)

## Если что-то сломалось
- Логи на Railway: вкладка Deploy Logs
- Проверить healthcheck: `curl https://underwriting.up.railway.app/api/health`
- Откатить прод: `git checkout main && git revert HEAD && git push origin main`

## Выполненные задачи (ТЗ)
Все ТЗ в `docs/tasks/` (001-011). Текущий статус смотри в файлах.
