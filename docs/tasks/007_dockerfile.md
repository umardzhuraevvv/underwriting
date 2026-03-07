# ТЗ 007: Dockerfile для Railway

## Статус: ✅ Выполнено

## Цель
Заменить nixpacks на свой Dockerfile. Полный контроль над сборкой, никаких сюрпризов.

## Что сделать

### 1. Создать `Dockerfile` в корне проекта
```dockerfile
FROM python:3.11-slim

# Системные зависимости для WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libglib2.0-0 \
    libharfbuzz0b \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование проекта
COPY . .

# Порт
EXPOSE 8000

# Запуск
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

### 2. Создать `.dockerignore`
```
.git
.github
__pycache__
*.pyc
.pytest_cache
venv
.env
*.db
.claude
docs/
tests/
scripts/
*.md
```

### 3. Обновить `railway.toml`
```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
healthcheckPath = "/api/health"
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```
Убрать startCommand — он теперь в CMD Dockerfile.

### 4. Удалить `nixpacks.toml`
Больше не нужен.

## Файлы
- `Dockerfile` — новый
- `.dockerignore` — новый
- `railway.toml` — обновить
- `nixpacks.toml` — удалить

## Тесты
- Тесты не затрагиваются (инфраструктурная задача)
- Проверить: `python -c "from app.main import app"` — работает

## Ветка
`feature/dockerfile`

## Критерий готовности
- [ ] Dockerfile создан
- [ ] .dockerignore создан
- [ ] railway.toml обновлён на builder = "dockerfile"
- [ ] nixpacks.toml удалён
- [ ] Закоммичено и запушено
