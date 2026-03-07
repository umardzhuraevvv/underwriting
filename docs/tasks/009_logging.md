# ТЗ 009: Структурированное логирование

## Статус: ✅ Выполнено

## Цель
Добавить нормальное логирование вместо `print()`. В Railway логах будет видно: кто, когда, что делал, сколько времени заняло.

## Что сделать

### 1. Создать `app/logging_config.py`
Использовать стандартный `logging` модуль Python (НЕ structlog — чтобы не добавлять зависимости).

```python
import logging
import sys

def setup_logging():
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger
```

### 2. Добавить middleware для логирования запросов
В `app/main.py` добавить middleware:
- Логировать: метод, URL, статус-код, время выполнения (мс)
- Логировать: user_id из JWT (если авторизован)
- НЕ логировать: пароли, токены, тело запроса

Формат: `[2026-03-07 17:30:00] INFO app: POST /api/auth/login → 200 (45ms) user=admin@company.com`

### 3. Добавить логи в ключевые бизнес-операции
В `app/services/anketa_service.py`:
- `logger.info(f"Анкета #{id} создана пользователем {user.email}")`
- `logger.info(f"Анкета #{id} заключена: {decision}")`
- `logger.warning(f"Анкета #{id} удалена пользователем {user.email}")`

В `app/services/calculation_service.py`:
- `logger.info(f"Авто-вердикт для анкеты #{id}: {decision}, DTI={dti:.1f}%")`

В `app/routers/auth.py`:
- `logger.info(f"Успешный вход: {email}")`
- `logger.warning(f"Неудачная попытка входа: {email}")`

В `app/services/webhook_service.py`:
- `logger.info(f"Webhook отправлен: {url} → {status_code}")`
- `logger.error(f"Webhook ошибка: {url} → {error}")`

### 4. Вызвать setup_logging() в lifespan
В `app/main.py` в функции `lifespan()` вызвать `setup_logging()` перед `init_db()`.

### 5. Убрать все `print()`
Заменить все существующие `print()` на `logger.info/error/warning`.

## Файлы
- `app/logging_config.py` — новый
- `app/main.py` — middleware + setup
- `app/routers/auth.py` — логи входа
- `app/services/anketa_service.py` — логи операций с анкетами
- `app/services/calculation_service.py` — логи вердикта
- `app/services/webhook_service.py` — логи вебхуков

## Тесты
- Все существующие тесты должны пройти
- Логирование не влияет на поведение — тесты не меняются

## Ветка
`feature/logging`

## Критерий готовности
- [ ] Все `print()` заменены на `logger`
- [ ] Middleware логирует каждый HTTP-запрос
- [ ] Ключевые операции (создание, заключение, удаление анкет) логируются
- [ ] Все тесты зелёные
