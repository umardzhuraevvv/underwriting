# 005: Webhook-уведомления при смене статуса

- **Статус:** 📋 Запланировано
- **Дата:** 2026-03-07
- **Ветка:** feature/webhooks
- **Приоритет:** средний

## Цель
При смене статуса анкеты (approved, rejected, review) — отправлять HTTP POST на настроенный URL партнёра. Это позволит интегрироваться с внешними системами.

## Требования

### 1. Модель БД: WebhookConfig
Добавить в `app/database.py`:
```python
class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)        # "Партнёр X"
    url = Column(String(500), nullable=False)          # https://partner.com/webhook
    secret = Column(String(200))                        # HMAC secret для подписи
    events = Column(String(500), default="all")        # "all" или "approved,rejected"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
```

### 2. Создать Alembic миграцию
```bash
alembic revision --autogenerate -m "Add webhook_configs table"
```

### 3. Сервис app/services/webhook_service.py
```python
import httpx
import hashlib
import hmac
import json

async def send_webhook(config: WebhookConfig, event: str, payload: dict):
    """Отправить webhook. Не блокирует основной запрос."""

def notify_webhooks(db: Session, event: str, anketa: Anketa):
    """Найти все активные webhook-конфиги для события и отправить."""
```

Payload:
```json
{
    "event": "anketa.approved",
    "anketa_id": 123,
    "client_name": "Иванов Иван",
    "client_type": "individual",
    "decision": "approved",
    "dti": 45.5,
    "purchase_price": 10000000,
    "down_payment_percent": 20,
    "timestamp": "2026-03-07T15:30:00Z"
}
```

Подпись (если secret задан):
- Заголовок `X-Webhook-Signature: sha256=...`
- HMAC-SHA256 от body с secret

### 4. Интеграция в conclude
В `app/routers/anketa.py` эндпоинт `POST /{id}/conclude`:
- После сохранения решения — вызвать `notify_webhooks(db, f"anketa.{decision}", anketa)`
- Отправка асинхронная (через background task), не блокирует ответ

### 5. API для управления webhooks
В `app/routers/admin.py`:
```
GET    /api/admin/webhooks        — список всех webhook-конфигов
POST   /api/admin/webhooks        — создать новый
PATCH  /api/admin/webhooks/{id}   — обновить (url, events, is_active)
DELETE /api/admin/webhooks/{id}   — удалить
POST   /api/admin/webhooks/{id}/test — отправить тестовый webhook
```
Все требуют пермишен `rules_manage`.

### 6. Тесты
Создать `tests/test_webhooks.py`:
- `test_create_webhook` — POST создаёт конфиг
- `test_list_webhooks` — GET возвращает список
- `test_webhook_signature` — проверить HMAC подпись
- `test_webhook_on_conclude` — при conclude отправляется webhook (мокнуть httpx)

## Файлы для создания/изменения
- `app/database.py` — добавить модель WebhookConfig
- `alembic/versions/xxx_add_webhooks.py` — миграция (автогенерация)
- `app/services/webhook_service.py` — создать
- `app/routers/admin.py` — добавить CRUD эндпоинты для webhooks
- `app/routers/anketa.py` — вызвать notify_webhooks в conclude
- `tests/test_webhooks.py` — создать
- `requirements.txt` — httpx уже есть, ничего добавлять не нужно

## Что НЕ делать
- НЕ менять логику conclude (только добавить вызов webhook после)
- НЕ делать синхронную отправку (использовать BackgroundTasks)
- НЕ ломать существующие тесты

## Критерий готовности
- [ ] Модель WebhookConfig создана
- [ ] Alembic миграция сгенерирована
- [ ] Webhook отправляется при conclude
- [ ] HMAC подпись работает
- [ ] CRUD API для управления webhooks
- [ ] Тесты зелёные
- [ ] Коммит в feature/webhooks
