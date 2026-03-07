# 001: Покрытие тестами (pytest)

- **Статус:** ✅ Выполнено
- **Дата:** 2026-03-07
- **Ветка:** feature/pytest-tests
- **Агент:** Claude (claude -p)

## Что сделано
- Создана папка `tests/` с 4 файлами тестов + conftest.py
- 62 теста, все зелёные
- Покрытие: расчёты (20), вердикт (18), auth (14), API (10)
- Тестовая БД: SQLite in-memory
- Добавлены зависимости: pytest>=8.0.0, python-dateutil>=2.9.0

## Файлы
- tests/conftest.py
- tests/test_calculations.py
- tests/test_verdict.py
- tests/test_auth.py
- tests/test_api.py
- requirements.txt (обновлён)

## Верификация
- Все расчёты проверены независимым Python-скриптом
- Аннуитет, DTI, ПВ, просрочки — всё совпадает с формулами
- Тесты не хардкодят значения, а считают динамически (правильный подход)

## Уроки
- `--dangerously-skip-permissions` не всегда работает для всех bash-команд
- Лучше использовать `CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS=true` как env variable
- Или настроить `.claude/settings.json` с разрешёнными командами
