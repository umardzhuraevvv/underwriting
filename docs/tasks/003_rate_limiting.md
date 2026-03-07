# 003: Rate Limiting на login

- **Статус:** 📋 Запланировано
- **Дата:** 2026-03-07
- **Ветка:** feature/rate-limiting
- **Приоритет:** высокий

## Цель
Защитить `/api/auth/login` от брутфорса. Ограничить количество попыток входа.

## Требования

### 1. Установить slowapi
- Добавить `slowapi>=0.1.9` в requirements.txt
- slowapi — обёртка над limits, работает с FastAPI из коробки

### 2. Настроить лимитер в app/main.py
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### 3. Добавить лимит на login
В `app/routers/auth.py`:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

@router.post("/login")
@limiter.limit("5/minute")  # 5 попыток в минуту с одного IP
def login(request: Request, ...):
```

**Лимиты:**
- `/api/auth/login` — 5 запросов в минуту
- Все остальные эндпоинты — без лимита (пока)

### 4. Ответ при превышении лимита
HTTP 429 Too Many Requests с JSON:
```json
{
  "detail": "Слишком много попыток входа. Попробуйте через минуту."
}

### 5. Тесты
Добавить в `tests/test_auth.py`:
- `test_rate_limit_login` — отправить 6 запросов подряд, 6-й должен вернуть 429

## Файлы для изменения
- `requirements.txt` — добавить slowapi>=0.1.9
- `app/main.py` — инициализация limiter
- `app/routers/auth.py` — декоратор @limiter.limit на login
- `tests/test_auth.py` — тест rate limit

## Что НЕ делать
- НЕ менять бизнес-логику
- НЕ ставить лимиты на другие эндпоинты (только login)
- НЕ ломать существующие 62 теста
- НЕ коммитить в main

## Критерий готовности
- [ ] slowapi установлен
- [ ] login ограничен 5/мин
- [ ] 429 ответ с русским сообщением
- [ ] Тест на rate limit
- [ ] Все тесты зелёные
- [ ] Коммит в feature/rate-limiting
