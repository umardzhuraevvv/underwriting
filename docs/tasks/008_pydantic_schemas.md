# ТЗ 008: Pydantic-схемы для всех API эндпоинтов

## Статус: 📋 Запланировано

## Цель
Добавить Pydantic response/request модели для всех API эндпоинтов. Это даст:
- Валидацию входных данных (некорректные поля → понятная ошибка 422)
- Типизированные ответы (автодокументация Swagger)
- Контракт API для фронтенда и интеграций

## Что сделать

### 1. Расширить `app/schemas.py`
В файле уже есть базовые coerce-типы. Добавить:

#### Request-модели:
- `LoginRequest(email: str, password: str)`
- `AnketaCreateRequest(client_type: str, ...)`  — все поля формы анкеты
- `AnketaSaveRequest` — обновление полей анкеты
- `ConcludeRequest(final_pv: float, conclusion_text: str | None)`
- `EditRequestCreate(reason: str)`
- `WebhookConfigCreate(url: str, events: list[str], secret: str | None)`
- `WebhookConfigUpdate(url: str | None, events: list[str] | None, ...)`

#### Response-модели:
- `AnketaListItem(id, client_type, client_name, status, created_at, ...)`
- `AnketaDetail` — полная анкета (все поля)
- `VerdictResponse(decision: str, reasons: list[str], recommended_pv: float)`
- `StatsResponse(total, approved, rejected, review, ...)`
- `UserResponse(id, email, full_name, role, permissions)`
- `NotificationResponse(id, type, title, message, read, created_at)`
- `HealthResponse(status: str)`

### 2. Обновить эндпоинты в роутерах
Для каждого эндпоинта добавить `response_model`:
```python
@router.get("", response_model=list[AnketaListItem])
def list_anketas(...):
```

Для POST/PATCH добавить типизированный body:
```python
@router.post("", response_model=AnketaDetail)
def create_anketa(data: AnketaCreateRequest, ...):
```

### 3. Файлы для изменения
- `app/schemas.py` — добавить модели
- `app/routers/anketa.py` — добавить response_model и request body
- `app/routers/auth.py` — LoginRequest, UserResponse
- `app/routers/admin.py` — WebhookConfig модели, UserManage модели

### 4. НЕ ЛОМАТЬ существующий API
- response_model — только добавить, не менять формат ответов
- Если текущий ответ не соответствует модели — подогнать модель под ответ, НЕ наоборот
- Все поля Optional где нужно, чтобы не сломать существующие данные

## Тесты
- Все существующие тесты должны пройти
- Добавить 5+ тестов на валидацию:
  - Невалидный email при логине → 422
  - Пустой client_type при создании анкеты → 422
  - Невалидный URL вебхука → 422

## Ветка
`feature/pydantic-schemas`

## Критерий готовности
- [ ] Swagger UI (`/docs`) показывает типизированные запросы/ответы
- [ ] Все существующие тесты зелёные
- [ ] Невалидные данные возвращают 422 с описанием ошибки
