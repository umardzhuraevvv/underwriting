# ТЗ 006: Разделение anketa.py — вынос бизнес-логики в services/

## Статус: 📋 Запланировано

## Цель
Разбить монолитный `app/routers/anketa.py` (1894 строки) на модули:
- **Роутер** — только HTTP-обработка (принять запрос → вызвать сервис → вернуть ответ)
- **Сервисы** — вся бизнес-логика

## Что выносить и куда

### 1. `app/services/calculation_service.py` (расчёты)
Вынести из `anketa.py`:
- `calc_annuity(principal, annual_rate, months)` — строка 327
- `calc_total_monthly_income(anketa)` — строка 337
- `calc_overdue_check(category)` — строка 361
- `_worst_overdue_category(*categories)` — строка 376
- `run_calculations(anketa)` — строка 395
- `load_rules(db)` — строка 438
- `_months_since(d)` — строка 452
- `_worst_decision(a, b)` — строка 460
- `_calc_overdue_decision_for_category(...)` — строка 470
- `calc_auto_verdict(anketa, rules)` — строка 518

### 2. `app/services/anketa_service.py` (CRUD + бизнес-операции)
Вынести из `anketa.py`:
- `anketa_to_detail(a, db)` — строка 636 (сериализация анкеты в dict)
- `record_history(db, anketa_id, user_id, ...)` — строка 776
- `create_notification(db, user_id, ...)` — строка 789
- `_normalize_phone(raw)` — строка 793
- `find_duplicates(db, anketa)` — строка 798
- `check_anketa_access(anketa, user, db)` — строка 835

### 3. `app/services/analytics_service.py` (аналитика)
Вынести из `anketa.py`:
- Логику из `get_analytics()` — строка 1124 (110 строк SQL-аггрегаций)
- Логику из `get_stats()` — строка 970 (55 строк)
- Логику из `get_employee_stats()` — строка 1793 (90 строк)

### 4. `app/routers/anketa.py` — остаётся (~400-500 строк)
Только HTTP-эндпоинты:
- Принимают request/params
- Вызывают сервисы
- Возвращают response

### 5. Вспомогательные типы — вынести в `app/schemas.py`
- `_coerce_float`, `_coerce_int`, `_coerce_str` — строки 20-46
- `CoerceFloat`, `CoerceInt`, `CoerceStr` — типы
- Все Pydantic-модели (`AnketaCreate`, `AnketaSave` и т.д. если есть inline)

## Правила рефакторинга

### ОБЯЗАТЕЛЬНО:
1. **НЕ менять API-контракт** — все эндпоинты, URL, параметры, ответы остаются идентичными
2. **НЕ менять бизнес-логику** — только перемещение кода, без изменения поведения
3. **Импорты** — в `anketa.py` заменить на `from app.services.calculation_service import calc_annuity, ...`
4. **Тесты должны пройти** — все 82 существующих теста должны остаться зелёными
5. **Без циклических импортов** — сервисы импортируют из `app.database`, роутеры из сервисов

### Порядок работы:
1. Прочитать CLAUDE.md
2. Создать ветку `feature/split-services`
3. Создать файлы сервисов и перенести функции
4. Обновить импорты в `anketa.py`
5. Обновить импорты в тестах (если тесты импортируют напрямую)
6. Запустить `python -m pytest tests/ -v` — все 82 теста зелёные
7. Закоммитить и запушить

## Структура после рефакторинга
```
app/
├── services/
│   ├── __init__.py
│   ├── calculation_service.py   # ~200 строк — расчёты, вердикт
│   ├── anketa_service.py        # ~250 строк — CRUD хелперы
│   ├── analytics_service.py     # ~250 строк — аналитика, статистика
│   ├── pdf_service.py           # уже есть
│   └── webhook_service.py       # уже есть
├── schemas.py                   # ~50 строк — типы, Pydantic
├── routers/
│   ├── anketa.py                # ~500 строк — только эндпоинты
│   ├── admin.py
│   └── auth.py
```

## Критерий готовности
- [ ] `anketa.py` уменьшился до ≤600 строк
- [ ] Все 82 теста зелёные
- [ ] Нет циклических импортов
- [ ] `python -c "from app.main import app"` работает без ошибок
- [ ] Каждый сервис-файл отвечает за одну область
