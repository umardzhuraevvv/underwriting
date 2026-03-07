# ТЗ 010: API версионирование

## Статус: ✅ Выполнено

## Цель
Добавить версионирование API (`/api/v1/...`) чтобы в будущем можно было безболезненно менять API.

## Что сделать

### 1. Обновить префиксы роутеров

В `app/routers/anketa.py`:
```python
router = APIRouter(prefix="/api/v1/anketas", tags=["anketas"])
```

В `app/routers/auth.py`:
```python
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
```

В `app/routers/admin.py`:
```python
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
```

### 2. Добавить обратную совместимость
Чтобы старый фронтенд не сломался, добавить редиректы со старых URL.

В `app/main.py` добавить middleware или mount:
```python
# Обратная совместимость: /api/auth/* → /api/v1/auth/*
from fastapi.responses import RedirectResponse

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PATCH", "DELETE", "PUT"])
async def legacy_redirect(path: str, request: Request):
    new_url = str(request.url).replace("/api/", "/api/v1/", 1)
    return RedirectResponse(url=new_url, status_code=307)
```

### 3. Обновить фронтенд `app/static/js/app.js`
Заменить все `/api/` на `/api/v1/` в fetch-запросах.
Это можно сделать простой заменой строк.

### 4. Обновить `app/main.py`
- Health check оставить на `/api/health` (без версии — это инфраструктурный эндпоинт)
- Public-роутер: `/api/v1/public/...`

### 5. Обновить тесты
Заменить все URL в тестах: `/api/` → `/api/v1/`

## Файлы
- `app/routers/anketa.py` — обновить prefix
- `app/routers/auth.py` — обновить prefix
- `app/routers/admin.py` — обновить prefix
- `app/main.py` — legacy redirect
- `app/static/js/app.js` — обновить URL
- `tests/*.py` — обновить URL в тестах

## Ветка
`feature/api-versioning`

## ВАЖНО
- `/api/health` — БЕЗ версии (Railway healthcheck)
- Редирект со старых URL для обратной совместимости
- Все тесты обновить на новые URL

## Критерий готовности
- [x] Все API на `/api/v1/...`
- [x] Фронтенд обновлён
- [x] Тесты обновлены и зелёные
- [x] `/api/health` работает без версии
- [x] Старые URL `/api/*` редиректят на `/api/v1/*`
