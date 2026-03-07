#!/bin/bash
# ============================================
# Запуск Claude агента с контекстом проекта
# ============================================
# Использование:
#   ./scripts/run-agent.sh "Твоя задача здесь"
#   ./scripts/run-agent.sh docs/tasks/002_alembic.md
#
# Агент автоматически:
# 1. Читает CLAUDE.md (правила, архитектура, грабли)
# 2. Выполняет задачу из текста или из файла ТЗ
# 3. Создаёт ветку, коммитит, пушит
# ============================================

set -e

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверка аргументов
if [ -z "$1" ]; then
    echo -e "${YELLOW}Использование:${NC}"
    echo "  ./scripts/run-agent.sh \"Описание задачи\""
    echo "  ./scripts/run-agent.sh docs/tasks/002_alembic.md"
    exit 1
fi

# Перейти в корень проекта
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo -e "${BLUE}📁 Проект: ${PROJECT_ROOT}${NC}"

# Определить: это файл ТЗ или текстовая задача?
if [ -f "$1" ]; then
    TASK_FILE="$1"
    echo -e "${GREEN}📋 ТЗ из файла: ${TASK_FILE}${NC}"
    PROMPT="Прочитай файл ${TASK_FILE} и выполни все требования из него. Это твоё техническое задание. Обязательно прочитай CLAUDE.md для правил проекта."
else
    TASK_TEXT="$1"
    echo -e "${GREEN}📋 Задача: ${TASK_TEXT}${NC}"
    PROMPT="Прочитай CLAUDE.md — это правила проекта. Затем выполни задачу: ${TASK_TEXT}. После завершения: создай feature ветку, закоммить на русском, запушь."
fi

echo -e "${BLUE}🚀 Запускаю агента...${NC}"
echo ""

# Запуск с полными пермишенами
CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS=true claude -p "${PROMPT}"

echo ""
echo -e "${GREEN}✅ Агент завершил работу${NC}"
echo -e "${YELLOW}Проверь: git log --oneline -5 и git branch -a${NC}"
