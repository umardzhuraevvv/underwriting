# Fintech Drive — Underwriting System: Техническая документация

> Последнее обновление: 2 марта 2026

---

## 1. Обзор проекта

**Стек:** FastAPI + SQLAlchemy + PostgreSQL + Vanilla JS (SPA)
**Деплой:** Railway (автодеплой из `main` ветки GitHub)
**Язык кода:** Python 3.14, JavaScript ES6+
**Комментарии и UI:** русский язык

| Метрика | Кол-во |
|---------|--------|
| Python (backend) | ~4 000 строк |
| JavaScript (SPA) | ~4 700 строк |
| CSS | ~2 500 строк |
| Таблиц в БД | 10 |
| API эндпоинтов | 43 |
| Зависимостей (pip) | 14 |

---

## 2. Структура файлов

```
underwriting/
├── app/
│   ├── main.py                  # Точка входа FastAPI, маршруты, CORS
│   ├── auth.py                  # JWT (python-jose), bcrypt, get_current_user
│   ├── database.py              # SQLAlchemy модели (10 таблиц), миграции, init_db()
│   ├── credit_report_parser.py  # Парсер HTML InfoScore (UZ+RU, физик+юрик)
│   ├── email_service.py         # SMTP (Gmail)
│   ├── telegram_service.py      # Telegram Bot API (httpx)
│   ├── routers/
│   │   ├── auth.py              # POST /login, GET /me
│   │   ├── admin.py             # CRUD пользователей/ролей/правил, Excel-экспорт
│   │   └── anketa.py            # Основной роутер: CRUD анкет, расчёты, вердикт
│   └── static/
│       ├── css/style.css        # Все стили (light/dark тема, responsive, print)
│       ├── js/app.js            # SPA: навигация, формы, расчёты, рендеринг
│       └── pages/
│           ├── index.html       # Основной шаблон SPA
│           ├── login.html       # Страница логина
│           └── public-anketa.html  # Публичная ссылка на анкету
├── requirements.txt
├── Procfile                     # web: uvicorn app.main:app ...
├── railway.toml                 # healthcheck, restart policy
└── underwriting.db              # SQLite (локальная разработка)
```

---

## 3. Архитектура

```
┌─────────────────────────────────────────────────┐
│                  Клиент (SPA)                    │
│  index.html + app.js + style.css                │
│  Vanilla JS, без фреймворка                     │
│  Клиентская навигация: navigate(page, data)     │
└────────────────────┬────────────────────────────┘
                     │ fetch() + JWT Bearer
┌────────────────────▼────────────────────────────┐
│              FastAPI (app/main.py)               │
│  Роутеры: /api/auth, /api/anketas, /api/admin   │
│  Middleware: CORS, static files                  │
├─────────────────────────────────────────────────┤
│              Бизнес-логика                        │
│  anketa.py: расчёты, авто-вердикт, валидация     │
│  admin.py: RBAC, правила, Excel                  │
│  auth.py: JWT, хеширование, права                │
├─────────────────────────────────────────────────┤
│            SQLAlchemy ORM + PostgreSQL            │
│  database.py: 10 моделей, автомиграции           │
│  Локально: SQLite | Прод: PostgreSQL (Railway)   │
└─────────────────────────────────────────────────┘
```

### Почему Vanilla JS, а не React/Vue

Проект начинался как MVP. SPA реализован на чистом JS (~4700 строк) с клиентским роутингом. Вся логика в одном файле `app.js`. Для текущего объёма (13 страниц) это работает, но при дальнейшем росте рекомендуется миграция на React/Vue.

---

## 4. База данных — 10 таблиц

### Основные модели

| Таблица | Назначение | Ключевые поля |
|---------|-----------|---------------|
| **users** | Пользователи системы | email, password_hash, role_id, is_superadmin, is_active |
| **roles** | Роли с правами (RBAC) | name, 9 полей прав (anketa_create, user_manage и т.д.) |
| **anketas** | Заявки на лизинг | 90+ полей: личные данные, сделка, доходы, КИ, вердикт |
| **anketa_history** | История изменений | anketa_id, field_name, old_value, new_value, changed_by |
| **edit_requests** | Запросы на редактирование | anketa_id, reason, status (pending/approved/rejected) |
| **notifications** | Уведомления | user_id, type, title, message, is_read |
| **anketa_view_log** | Журнал просмотров | anketa_id, user_id, viewed_at |
| **underwriting_rules** | Правила андеррайтинга | category, rule_key, value (DTI лимиты, пороги) |
| **risk_rules** | Риск-категории | category (E, F1...), min_pv (мин. ПВ%) |
| **system_settings** | Системные настройки | key/value (telegram_token и т.д.) |

### Миграции

Файл `database.py`, функция `init_db()`:
- `Base.metadata.create_all()` — создаёт новые таблицы
- `ALTER TABLE ... ADD COLUMN` — добавляет новые колонки (список `new_columns`)
- Автоматически выполняется при запуске приложения
- Безопасно: `try/except` на каждую колонку (если уже существует — пропускается)

**Нет Alembic** — миграции вручную через `init_db()`. При интеграции Kafka или других сервисов рекомендуется перейти на Alembic.

---

## 5. API — полный список эндпоинтов

### Авторизация (`/api/auth`)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/login` | Логин по email/password, возвращает JWT |
| GET | `/me` | Текущий пользователь + права |

JWT: `python-jose`, HS256, срок жизни 8 часов.
Пароли: `bcrypt` через `passlib`.

### Анкеты (`/api/anketas`)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/` | Создать анкету |
| GET | `/` | Список анкет (фильтр, пагинация) |
| GET | `/{id}` | Детали анкеты |
| PATCH | `/{id}` | Обновить поля |
| DELETE | `/{id}` | Мягкое удаление |
| POST | `/{id}/save` | Сохранить (статус: saved) |
| POST | `/{id}/conclude` | Вынести решение (approved/review/rejected) |
| GET | `/{id}/history` | История изменений |
| GET | `/{id}/view-log` | Журнал просмотров |
| POST | `/{id}/edit-request` | Запрос на редактирование |
| GET | `/edit-requests` | Список запросов |
| GET | `/check-duplicate` | Проверка дубликатов (телефон, ИНН) |
| GET | `/verdict-rules` | Правила для авто-вердикта |
| GET | `/risk-rules` | Риск-категории |
| GET | `/stats` | Статистика (по статусам) |
| GET | `/analytics` | Аналитика |
| GET | `/employee-stats/data` | Статистика по сотрудникам |
| GET | `/notifications/list` | Уведомления |
| GET | `/notifications/unread-count` | Непрочитанные |
| PATCH | `/notifications/{id}/read` | Пометить прочитанным |
| POST | `/notifications/read-all` | Прочитать все |

### Администрирование (`/api/admin`)

| Метод | Путь | Описание |
|-------|------|----------|
| GET/POST | `/roles` | CRUD ролей |
| PATCH/DELETE | `/roles/{id}` | Обновить/удалить роль |
| GET/POST | `/users` | CRUD пользователей |
| PATCH | `/users/{id}` | Обновить пользователя |
| POST | `/users/{id}/reset-password` | Сброс пароля |
| DELETE | `/users/{id}` | Удалить |
| GET | `/rules` | Правила андеррайтинга |
| PATCH | `/rules/{id}` | Изменить правило |
| GET/POST | `/risk-rules` | Риск-категории |
| PATCH/DELETE | `/risk-rules/{id}` | Изменить/удалить |
| PATCH | `/edit-requests/{id}` | Рассмотреть запрос |
| GET | `/edit-requests/count` | Счётчик ожидающих |
| GET | `/export-excel` | Выгрузка в XLSX |

### Публичный (`/api/public`)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/anketa/{token}` | Анкета по публичной ссылке (без авторизации) |

---

## 6. Бизнес-логика

### Авто-расчёты (клиент + сервер)

Расчёты дублируются на фронте (мгновенный отклик) и на бэкенде (при сохранении):

```
ПВ сумма = Стоимость × ПВ% / 100
Остаток = Стоимость − ПВ сумма
Ежемесячный платёж = аннуитет(Остаток, Ставка, Срок)
Общий месячный доход = сумма всех доходов / период
DTI = (Платёж + Обязательства) / Доход × 100
```

### Авто-вердикт

Конфигурируемые правила (`underwriting_rules`):

| Правило | Описание |
|---------|----------|
| `max_dti_approve` | DTI ≤ X% → одобрение (по умолч. 50%) |
| `max_dti_review` | DTI ≤ X% → на рассмотрение (60%) |
| `max_dti_reject` | DTI > X% → отказ |
| `overdue_*` | Пороги по категориям просрочки |
| `min_pv_*` | Минимальный ПВ% для авто-одобрения |

Вердикт: `approved` / `review` / `rejected` + список причин + рекомендуемый ПВ%.

### Риск-грейды

Таблица `risk_rules`: категории (A, B, C, D, E, E1-E4, F, F1-F4) с минимальным ПВ%. Если фактический ПВ < минимального → предупреждение.

### Дупликат-проверка

Поиск совпадений при вводе по:
- Номеру телефона (нормализация: только цифры, последние 9)
- ИНН компании (точное совпадение)

---

## 7. Фронтенд (SPA)

### Навигация

```javascript
function navigate(page, data) { ... }
// page: 'dashboard', 'ankety', 'new-anketa', 'view-anketa', 'users', 'rules', ...
```

Все страницы — div-ы внутри `index.html`, переключаются классом `.active`.
URL не меняется (hash-роутинга нет). History API не используется.

### Форма анкеты — 4 вкладки

**Физическое лицо:**
1. Личные данные (ФИО, дата рождения, адрес, телефон)
2. Условия сделки (авто, стоимость, ПВ%, срок, ставка)
3. Доходы (зарплата, основная деятельность, доп. доход)
4. Кредитная история (обязательства, просрочки, DTI, риск-грейд)

**Юридическое лицо:**
1. Компания (название, ИНН, ОКЭД, директор, контакты)
2. Условия сделки
3. Доходы (выручка компании + доход директора)
4. КИ (компания + директор + DTI + риск-грейд)
5. Поручитель

### Ключевые функции JS

| Функция | Строка | Что делает |
|---------|--------|-----------|
| `navigate()` | ~406 | Роутинг SPA |
| `loadAnketas()` | ~1019 | Загрузка списка анкет |
| `fillAnketaForm()` | ~1152 | Заполнение формы данными |
| `collectAnketaData()` | ~1303 | Сбор данных из формы |
| `runClientCalc()` | ~2021 | Авторасчёты (ПВ, платёж, DTI) |
| `renderAnketaView()` | ~1773 | Рендер просмотра анкеты |
| `renderFormSidebar()` | ~2825 | Превью метрик в сайдбаре |
| `calcClientAutoVerdict()` | ~2893 | Авто-вердикт на клиенте |
| `buildPrintHtml()` | ~4270 | Генерация HTML для печати |

---

## 8. Развёртывание

### Production (Railway)

```toml
# railway.toml
[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
healthcheckPath = "/api/health"
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

**Переменные окружения:**
- `DATABASE_URL` — PostgreSQL URL (Railway предоставляет)
- `SECRET_KEY` — ключ для JWT
- `SMTP_*` — настройки email (опционально)
- `PINFL_SALT` — соль для хеширования (устаревшее)

### Локальная разработка

```bash
cd ~/underwriting
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

БД: SQLite (`underwriting.db`). Автоматически создаётся при первом запуске.

---

## 9. Что реализовано (по стадиям)

### Стадия 1 — Авторизация и админка ✅
- JWT-авторизация, логин/логаут
- RBAC: роли с 9 правами (создание, просмотр, редактирование, удаление анкет и т.д.)
- Суперадмин с полным доступом
- CRUD пользователей с генерацией паролей
- Управление ролями

### Стадия 2 — Анкеты и андеррайтинг ✅
- Форма анкеты: 4 вкладки, 90+ полей, 2 типа клиентов
- Авторасчёты: ПВ, платёж, DTI (клиент + сервер)
- Авто-вердикт: 15+ конфигурируемых правил
- Риск-грейды с минимальным ПВ%
- Мягкое удаление анкет
- История изменений (каждое поле)
- Журнал просмотров
- Запросы на редактирование (approve/reject workflow)
- Уведомления (in-app + Telegram)
- Публичная ссылка на анкету
- Excel-экспорт (физики + юрики на разных листах)
- Проверка дубликатов (телефон, ИНН)
- Дашборд со статистикой
- Аналитика по сотрудникам
- Печать анкеты (PDF через window.print)
- Калькулятор лизинга

### Стадия 2а — Визуальный редизайн ✅
- Новая цветовая схема
- Тёмная тема
- Мобильная адаптация (нижняя навигация)
- Print-стили

### Стадия 3 — Не начата
- Расширенная система прав
- Интеграция с внешними системами (Kafka и т.д.)

---

## 10. Рекомендации для разработчиков

### Код

- **Язык комментариев**: смешанный (RU + EN). Модели и переменные — английские. UI-строки и комментарии — русские. При доработке рекомендуется придерживаться единого стиля.
- **Один файл JS**: `app.js` — 4700 строк. При интеграции Kafka/микросервисов рекомендуется разбить на модули (можно через ES modules или сборщик).
- **Миграции**: нет Alembic. Используется ручной `ALTER TABLE` в `init_db()`. Для production-ready системы рекомендуется Alembic.
- **Тесты**: нет unit/integration тестов. Рекомендуется добавить pytest для критических путей (расчёты, вердикт, авторизация).

### Интеграция Kafka

Текущая архитектура — монолит. Для интеграции с Kafka:

1. **Producer** (отправка событий): добавить в `anketa.py` после `db.commit()`:
   ```python
   # После создания/обновления/заключения анкеты
   kafka_producer.send('anketa-events', {
       'event': 'anketa_concluded',
       'anketa_id': anketa.id,
       'decision': anketa.decision,
       'timestamp': datetime.utcnow().isoformat()
   })
   ```

2. **Consumer** (приём событий): отдельный процесс или background task:
   ```python
   # Новый файл: app/kafka_consumer.py
   from aiokafka import AIOKafkaConsumer
   ```

3. **Зависимости**: добавить `aiokafka` или `confluent-kafka` в `requirements.txt`.

4. **API контракты**: все эндпоинты возвращают JSON. Схемы определены через Pydantic (см. классы в `anketa.py`). OpenAPI-документация автоматически доступна на `/docs`.

### Масштабирование

- **Сессии**: stateless (JWT) — можно горизонтально масштабировать.
- **БД**: PostgreSQL — стандартно, никаких SQLite-специфичных конструкций.
- **Статика**: `app/static/` обслуживается FastAPI напрямую. Для CDN — вынести в отдельный бакет.

---

## 11. Зависимости (requirements.txt)

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0.35
psycopg2-binary>=2.9.9
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
bcrypt>=4.0.0
python-multipart>=0.0.12
aiofiles>=24.1.0
pydantic[email]>=2.9.0
openpyxl>=3.1.0
cryptography>=42.0.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
```

Все зависимости — стабильные, широко используемые библиотеки. Никаких экзотических пакетов.

---

## 12. Быстрый старт для нового разработчика

```bash
# 1. Клонировать
git clone https://github.com/umardzhuraevvv/underwriting.git
cd underwriting

# 2. Виртуальное окружение
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Запустить
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# 4. Открыть
# http://localhost:8001
# Логин: admin@fintechdrive.uz / Forever0109!

# 5. API документация
# http://localhost:8001/docs (Swagger UI)
# http://localhost:8001/redoc (ReDoc)
```

---

*Документ подготовлен для передачи команде разработчиков. Вопросы по архитектуре и коду — через GitHub Issues.*
