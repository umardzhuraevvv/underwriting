# Правила для агентов

> Этот файл — главная база знаний проекта. Каждый агент ОБЯЗАН прочитать его перед началом работы.
> Если в процессе работы обнаружен баг, особенность или важное решение — ДОПИСАТЬ сюда.

## Стек
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL (Railway)
- **Frontend:** Vanilla JavaScript SPA (app/static/js/app.js)
- **Python:** 3.11
- **БД прод:** PostgreSQL на Railway (DATABASE_URL)
- **БД локал:** SQLite (underwriting.db)
- **Деплой:** Railway (auto-deploy из main, `railway.toml`)

## Архитектура проекта

```
app/
├── main.py              # Точка входа FastAPI, lifespan, middleware, роутеры
├── auth.py              # JWT (HS256, 8ч), bcrypt, пермишены (9 штук)
├── database.py          # SQLAlchemy модели (10+ таблиц), init_db(), seed
├── schemas.py           # Pydantic-схемы запросов/ответов
├── limiter.py           # Rate limiting (slowapi)
├── logging_config.py    # Настройка логирования
├── credit_report_parser.py  # Парсер InfoScore HTML (UZ/RU)
├── email_service.py     # SMTP Gmail (отправка паролей)
├── telegram_service.py  # Telegram Bot API (уведомления)
├── routers/
│   ├── auth.py          # /api/v1/auth — логин, профиль
│   ├── anketa.py        # /api/v1/anketas — CRUD, вердикт, аналитика (~590 строк)
│   └── admin.py         # /api/v1/admin — юзеры, роли, правила (~500 строк)
├── services/
│   ├── calculation_service.py  # Аннуитет, DTI, авто-вердикт
│   ├── anketa_service.py       # CRUD хелперы, уведомления, дубликаты
│   ├── analytics_service.py    # Статистика, аналитика, графики
│   ├── pdf_service.py          # WeasyPrint генерация PDF
│   └── webhook_service.py      # HMAC вебхуки
├── static/
│   ├── js/app.js        # Главный SPA файл (~4870 строк)
│   ├── css/style.css    # Стили + dark mode (~2542 строк)
│   └── pages/           # HTML страницы (index, login, public-anketa)
alembic/                 # Миграции БД (Alembic)
tests/
├── conftest.py          # Фикстуры: SQLite in-memory, TestClient
├── test_calculations.py # Тесты расчётов
├── test_verdict.py      # Тесты авто-вердикта
├── test_auth.py         # Тесты аутентификации
├── test_api.py          # Тесты API эндпоинтов
└── ...                  # + тесты rate-limiting, webhooks, PDF, logging, versioning
```

## Ключевые модели БД
- **Anketa** — 90+ полей, два типа клиентов (individual/legal_entity), soft delete
- **User** — email-auth, bcrypt, role_id → Role
- **Role** — 9 гранулярных пермишенов (anketa_create, anketa_edit, anketa_view_all, anketa_conclude, anketa_delete, user_manage, analytics_view, export_excel, rules_manage)
- **UnderwritingRule** — 17+ настраиваемых бизнес-правил (DTI пороги, просрочки, ПВ)
- **RiskRule** — категории риска (E, E1-E4, F, F1-F4) с min_pv
- **AnketaHistory** — аудит всех изменений полей
- **EditRequest** — запросы на редактирование заключённых анкет
- **Notification** — in-app + Telegram уведомления

## Бизнес-логика расчётов

### Аннуитет
```
monthly = principal × [r × (1+r)^n] / [(1+r)^n - 1]
где r = annual_rate / 100 / 12, n = lease_term_months
```

### DTI (Debt-to-Income)
```
DTI = (monthly_payment + monthly_obligations_payment) / total_monthly_income × 100
```

### Авто-вердикт
1. DTI ≤ 50% → approved, ≤ 60% → review, > 60% → rejected
2. Просрочки по матрице: до 30 дней / 31-60 / 61-90 / 90+ с порогами давности
3. Финальное решение = worst(DTI, overdue)
4. Рекомендуемый ПВ = min_pv + pv_additions

## Git-воркфлоу

### Ветки
- **main** — продакшен. Автодеплой на Railway. НИКОГДА не коммитить напрямую.
- **dev** — ветка разработки. Все фичи мержатся сюда первыми.
- **feature/xxx** — ветки задач, создаются ОТ `dev`.

### Правила для агентов (ОБЯЗАТЕЛЬНО)
1. **Перед началом работы** — убедиться что находишься на `dev`:
   ```bash
   git checkout dev && git pull origin dev
   ```
2. **Создать ветку от dev**:
   ```bash
   git checkout -b feature/название-задачи dev
   ```
3. **Работать в своей ветке**, коммитить туда.
4. **После завершения** — замержить в `dev`:
   ```bash
   git checkout dev && git merge feature/название-задачи --no-edit && git push origin dev
   ```
5. **НИКОГДА не мержить в main** — это делает только тимлид вручную после проверки на dev.
6. **НИКОГДА не пушить в main** напрямую.

### Формат веток
- `feature/что-делаем` (kebab-case)
- Примеры: `feature/rate-limiting`, `feature/pdf-export`, `feature/fix-404`

### Деплой в прод (только вручную)
Когда всё проверено на dev:
```bash
git checkout main && git merge dev --no-edit && git push origin main
```
Railway автоматически задеплоит из main.

## Структура кода (куда что писать)
- Эндпоинты: `app/routers/`
- Модели БД: `app/database.py`
- Бизнес-логика: `app/services/` (calculation, anketa, analytics, pdf, webhook)
- Тесты: `tests/`
- ТЗ и документация: `docs/tasks/`

## Тесты
- Фреймворк: pytest
- Запуск: `source venv/bin/activate && python -m pytest tests/ -v`
- Тестовая БД: SQLite in-memory (НИКОГДА не трогать прод)
- **Каждая новая фича = тесты** (обязательно)
- Не мокать бизнес-логику — тестировать реальные функции

## Перед каждым коммитом
1. Проверить синтаксис: `python -m py_compile файл.py`
2. Проверить что импорты не сломаны
3. Запустить тесты: `python -m pytest tests/ -v`
4. Написать понятный commit message на русском

## Известные нюансы и грабли

### Миграции БД
- Alembic настроен, но НЕ используется в startCommand (зависал на Railway)
- Новые миграции: `alembic revision --autogenerate -m "описание"`
- Миграции также дублируются через try/except ALTER TABLE в `database.py init_db()`
- При добавлении новой колонки в Anketa — добавить ALTER TABLE в init_db()
- PostgreSQL и SQLite имеют разный синтаксис ALTER — учитывать оба

### Безопасность
- PINFL и паспортные данные удалены из UI и очищаются при init_db()
- SECRET_KEY по умолчанию захардкожен — в проде берётся из env
- JWT токен живёт 8 часов

### Frontend
- `app.js` — монолит на 4720 строк, будь осторожен с изменениями
- SPA без History API — навигация через toggle `.active` классов на div
- Все расчёты дублируются на клиенте (`runClientCalc()`) и сервере (`run_calculations()`)
- При изменении логики расчётов — менять в ОБОИХ местах

### Особенности кода
- `calc_annuity(principal, rate, months)` возвращает 0.0 при rate=0 (потому что `not 0` = True)
- `_worst_overdue_category()` принимает *args, не список
- Для юрлиц вердикт проверяет 3 субъекта: компания, директор, поручитель
- Soft delete: `deleted_at` + `deleted_by` + `deletion_reason`

### Деплой
- Railway автодеплой из main: push → build (nixpacks) → deploy
- Конфиг: `railway.toml` (nixpacks builder) + `nixpacks.toml` (apt-зависимости для WeasyPrint)
- Health check: `/api/health` (без версии, НЕ /api/v1/)
- Рестарт при падении (max 3 retries)
- **startCommand** обёрнут в `sh -c` для раскрытия `$PORT`
- Alembic НЕ запускается в startCommand — миграции через init_db()

### API версионирование
- Все роуты: `/api/v1/...` (anketas, auth, admin, public)
- Healthcheck: `/api/health` (без версии)
- При добавлении нового эндпоинта — обязательно использовать `/api/v1/` префикс
- При добавлении fetch() в app.js — обязательно `/api/v1/...`

## История задач
Все ТЗ хранятся в `docs/tasks/` с нумерацией:
- `001_название.md` — описание задачи
- Статус фиксируется в файле: ✅ выполнено / 🔄 в работе / 📋 запланировано

## Changelog
Все значимые изменения фиксируются в `CHANGELOG.md` в корне проекта.
