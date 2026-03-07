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
├── main.py              # Точка входа FastAPI, lifespan, подключение роутеров
├── auth.py              # JWT (HS256, 8ч), bcrypt, пермишены (9 штук)
├── database.py          # SQLAlchemy модели (10 таблиц), init_db(), seed
├── credit_report_parser.py  # Парсер InfoScore HTML (UZ/RU)
├── email_service.py     # SMTP Gmail (отправка паролей)
├── telegram_service.py  # Telegram Bot API (уведомления)
├── routers/
│   ├── auth.py          # POST /login, GET /me
│   ├── anketa.py        # CRUD анкет, расчёты, вердикт, аналитика (~1860 строк)
│   └── admin.py         # Управление юзерами, ролями, правилами (~500 строк)
├── static/
│   ├── js/app.js        # Главный SPA файл (~4720 строк)
│   ├── css/style.css    # Стили + dark mode (~2542 строк)
│   └── pages/           # HTML страницы (index, login, public-anketa)
tests/
├── conftest.py          # Фикстуры: SQLite in-memory, TestClient, юзеры, правила
├── test_calculations.py # Тесты расчётов (20 тестов)
├── test_verdict.py      # Тесты авто-вердикта (18 тестов)
├── test_auth.py         # Тесты аутентификации (14 тестов)
└── test_api.py          # Тесты API эндпоинтов (10 тестов)
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

## Ветки
- **НИКОГДА** не коммитить напрямую в main
- Каждая задача = новая ветка `feature/название`
- После завершения создать PR в dev
- Формат веток: `feature/что-делаем` (kebab-case)

## Структура кода (куда что писать)
- Эндпоинты: `app/routers/`
- Модели БД: `app/database.py`
- Бизнес-логика: `app/routers/anketa.py` (TODO: вынести в `app/services/`)
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
- Alembic НЕ настроен (пока). Миграции через try/except ALTER TABLE в `database.py init_db()`
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
- Railway автодеплой из main: push → build → deploy
- Health check: `/api/health`
- Рестарт при падении (max 3 retries)

## История задач
Все ТЗ хранятся в `docs/tasks/` с нумерацией:
- `001_название.md` — описание задачи
- Статус фиксируется в файле: ✅ выполнено / 🔄 в работе / 📋 запланировано

## Changelog
Все значимые изменения фиксируются в `CHANGELOG.md` в корне проекта.
