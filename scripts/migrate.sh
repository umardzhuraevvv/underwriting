#!/bin/bash
# Запуск миграций Alembic
set -e
cd "$(dirname "$0")/.."
source venv/bin/activate 2>/dev/null || true
alembic upgrade head
echo "Миграции применены успешно"
