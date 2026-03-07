# 002: Настройка Alembic миграций

- **Статус:** 📋 Запланировано
- **Дата:** 2026-03-07
- **Ветка:** feature/alembic-migrations
- **Приоритет:** высокий

## Цель
Перейти с ручных try/except ALTER TABLE миграций на Alembic. Это позволит:
- Версионировать схему БД
- Безопасно добавлять/изменять/удалять колонки
- Откатывать миграции при проблемах
- Работать одинаково на SQLite (локал) и PostgreSQL (прод)

## Текущее состояние
Сейчас миграции в `app/database.py` функция `init_db()` (строка 306):
- 40+ колонок добавляются через `ALTER TABLE anketas ADD COLUMN ... ` в try/except
- 3 колонки добавляются в users через аналогичный try/except
- Очистка PINFL/паспортных данных через UPDATE
- Seed ролей, юзеров, правил

Проблемы текущего подхода:
- Нельзя переименовать колонку
- Нельзя изменить тип колонки
- Нельзя откатить изменение
- Нет истории миграций

## Требования к реализации

### 1. Установка Alembic
- Добавить `alembic>=1.13.0` в requirements.txt
- `pip install alembic`

### 2. Инициализация
```bash
alembic init alembic
```
Это создаст:
- `alembic/` — папка с миграциями
- `alembic.ini` — конфиг
- `alembic/env.py` — настройка окружения

### 3. Настройка alembic/env.py
```python
# Импортировать модели чтобы Alembic видел метадату
from app.database import Base, DATABASE_URL

# Установить URL из переменной окружения
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Указать target_metadata
target_metadata = Base.metadata
```

**ВАЖНО:** DATABASE_URL может быть SQLite или PostgreSQL — учитывать оба варианта.

### 4. Настройка alembic.ini
- `sqlalchemy.url` — оставить пустым (будет из env.py)
- Остальное — по умолчанию

### 5. Генерация начальной миграции
```bash
alembic revision --autogenerate -m "Initial: все существующие таблицы"
```
Это создаст миграцию которая описывает ВСЮ текущую схему БД (10 таблиц).

### 6. Пометить текущую БД как актуальную
```bash
alembic stamp head
```
Это скажет Alembic: "текущая БД уже соответствует последней миграции, не нужно ничего применять".

### 7. Очистка init_db()
Удалить из `init_db()`:
- ВСЕ блоки `ALTER TABLE anketas ADD COLUMN ...`
- ВСЕ блоки `ALTER TABLE users ADD COLUMN ...`
- НЕ УДАЛЯТЬ: seed ролей, юзеров, правил (оставить)
- НЕ УДАЛЯТЬ: очистку PINFL (оставить для безопасности, но пометить TODO для удаления после полной очистки)

Оставить `Base.metadata.create_all(bind=engine)` — это нужно для тестов (SQLite in-memory).

### 8. Обновить lifespan в main.py
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # seed данных
    yield
```
`init_db()` теперь только для seed, не для миграций.

### 9. Добавить скрипт миграции
Создать `scripts/migrate.sh`:
```bash
#!/bin/bash
# Запуск миграций Alembic
alembic upgrade head
```

### 10. Обновить railway.toml
```toml
[deploy]
startCommand = "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
```
Миграции будут запускаться автоматически при деплое ПЕРЕД стартом сервера.

## Файлы для создания/изменения
- `requirements.txt` — добавить alembic>=1.13.0
- `alembic.ini` — конфиг (создать)
- `alembic/env.py` — настройка (создать)
- `alembic/versions/xxx_initial.py` — начальная миграция (автогенерация)
- `app/database.py` — убрать ALTER TABLE блоки из init_db()
- `app/main.py` — без изменений (lifespan уже вызывает init_db)
- `railway.toml` — добавить alembic upgrade head перед uvicorn
- `scripts/migrate.sh` — скрипт для ручных миграций

## Что НЕ делать
- НЕ удалять seed данных из init_db() (роли, юзеры, правила)
- НЕ менять модели БД (только настроить Alembic)
- НЕ менять бизнес-логику
- НЕ ломать существующие тесты
- НЕ коммитить в main

## Тестирование
1. `python -m pytest tests/ -v` — все 62 теста должны быть зелёные
2. `alembic check` — проверить что миграции синхронизированы с моделями
3. `python -m py_compile app/database.py` — синтаксис

## Критерий готовности
- [ ] Alembic инициализирован, начальная миграция создана
- [ ] ALTER TABLE блоки удалены из init_db()
- [ ] Seed данных работает
- [ ] railway.toml обновлён
- [ ] Тесты зелёные (62/62)
- [ ] Коммит в feature/alembic-migrations
