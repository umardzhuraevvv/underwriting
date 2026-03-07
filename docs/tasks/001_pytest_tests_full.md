# ТЗ: Покрытие тестами (pytest)

## Цель
Добавить pytest тесты для критической бизнес-логики: расчёты, авто-вердикт, аутентификация, пермишены.

## Стек тестов
- pytest + pytest-asyncio (если нужно)
- httpx (TestClient для FastAPI)
- SQLite in-memory для тестовой БД (не трогать прод PostgreSQL)
- НЕ мокать бизнес-логику — тестировать реальные функции

## Структура файлов

```
tests/
├── conftest.py          # Фикстуры: TestClient, тестовая БД, тестовый юзер, тестовые правила
├── test_calculations.py # Расчёты: аннуитет, DTI, ПВ, доход
├── test_verdict.py      # Авто-вердикт: DTI-решение, просрочки, рекомендованный ПВ
├── test_auth.py         # Аутентификация: JWT, логин, пермишены
├── test_api.py          # API эндпоинты: CRUD анкет, статусы
```

## conftest.py — Фикстуры

### Тестовая БД
```python
# Использовать SQLite in-memory
# engine = create_engine("sqlite:///:memory:")
# Переопределить get_db через app.dependency_overrides
# Создать все таблицы через Base.metadata.create_all
# Засеять: роли (Администратор, Инспектор), дефолтные UnderwritingRule, RiskRule
```

### Фикстуры
- `db_session` — сессия тестовой БД с rollback после каждого теста
- `client` — httpx.TestClient(app) с переопределённой БД
- `admin_token` — JWT токен для админа (все пермишены)
- `inspector_token` — JWT токен для инспектора (ограниченные пермишены)
- `sample_anketa_data` — dict с валидными данными для создания анкеты
- `default_rules` — dict с дефолтными правилами андеррайтинга

## test_calculations.py — Тесты расчётов

### calc_annuity(principal, annual_rate, months)
Функция в app/routers/anketa.py строка 325.
```
Формула: principal * (r * (1+r)^n) / ((1+r)^n - 1), где r = rate/100/12
```

Тесты:
1. `test_annuity_basic` — principal=1_000_000, rate=24, months=12 → проверить что ≈ 94_560 (±100)
2. `test_annuity_zero_rate` — rate=0 → return principal/months
3. `test_annuity_zero_principal` — principal=0 → return 0.0
4. `test_annuity_none_values` — любой аргумент None или 0 → return 0.0
5. `test_annuity_long_term` — months=60, rate=18 → проверить разумный результат
6. `test_annuity_high_rate` — rate=48 → проверить что результат > principal/months

### calc_total_monthly_income(anketa)
Функция в строке 335. Считает сумму всех доходов / на периоды.

Тесты:
1. `test_income_individual_salary_only` — salary=600_000, period=6 → 100_000/мес
2. `test_income_individual_all_sources` — salary + main_activity + additional + other → проверить сумму
3. `test_income_individual_no_data` — все None → 0.0
4. `test_income_legal_entity` — client_type="legal_entity", company_revenue + director_income → проверить
5. `test_income_partial_data` — только salary, остальное None → не падает, считает частично

### run_calculations(anketa)
Функция в строке 393. Запускает все расчёты на анкете.

Тесты:
1. `test_calculations_down_payment` — price=10_000_000, pv_percent=20 → amount=2_000_000, remaining=8_000_000
2. `test_calculations_monthly_payment` — проверить что monthly_payment = calc_annuity(remaining, rate, months)
3. `test_calculations_dti` — income=100_000, payment=30_000, obligations=10_000 → dti=40%
4. `test_calculations_dti_zero_income` — income=0 → dti=None (не деление на ноль)
5. `test_calculations_no_price` — price=None → down_payment_amount=None, remaining=None

### _worst_overdue_category(*categories)
Функция в строке 374.

Тесты:
1. `test_worst_overdue_single` — ("до 30 дней",) → "до 30 дней"
2. `test_worst_overdue_mixed` — ("до 30 дней", "61-90", "31-60") → "61-90"
3. `test_worst_overdue_all_none` — (None, None) → None
4. `test_worst_overdue_with_90plus` — ("31-60", "90+") → "90+"

## test_verdict.py — Тесты авто-вердикта

### calc_auto_verdict(anketa, rules)
Функция в строке 516. Главная функция — решение на основе DTI + просрочек.

Подготовка: создать мок-объект Anketa (можно SimpleNamespace) + dict rules с дефолтными значениями.

### DTI-тесты
1. `test_verdict_dti_approved` — dti=40 (≤50) → auto_decision="approved"
2. `test_verdict_dti_review` — dti=55 (>50, ≤60) → auto_decision="review"
3. `test_verdict_dti_rejected` — dti=65 (>60) → auto_decision="rejected"
4. `test_verdict_dti_none` — dti=None → reasons содержит "DTI не рассчитан"
5. `test_verdict_dti_edge_50` — dti=50.0 (ровно 50) → "approved" (≤50)
6. `test_verdict_dti_edge_60` — dti=60.0 (ровно 60) → "review" (≤60)

### Тесты просрочек (физлицо)
7. `test_verdict_overdue_30_days` — cat="до 30 дней" → "approved"
8. `test_verdict_overdue_31_60_recent` — cat="31-60", last_overdue=2 мес назад (<6) → "rejected"
9. `test_verdict_overdue_31_60_medium` — cat="31-60", last_overdue=8 мес назад (6-12) → "review", pv_add=5
10. `test_verdict_overdue_31_60_old` — cat="31-60", last_overdue=15 мес назад (>12) → "approved", pv_add=5
11. `test_verdict_overdue_61_90_recent` — cat="61-90", ≤12 мес → "rejected"
12. `test_verdict_overdue_61_90_old` — cat="61-90", >12 мес → "review"
13. `test_verdict_overdue_90plus_recent` — cat="90+", ≤24 мес → "rejected"
14. `test_verdict_overdue_90plus_old` — cat="90+", >24 мес → "review"

### Комбинированные тесты
15. `test_verdict_worst_decision` — dti="approved" + overdue="review" → final="review"
16. `test_verdict_recommended_pv` — pv_add=5, min_pv=5, current_pv=8 → recommended=10, reasons содержит "ниже рекомендуемого"
17. `test_verdict_pv_sufficient` — current_pv=25, recommended=10 → нет предупреждения о ПВ

### Тесты юрлицо
18. `test_verdict_legal_entity_worst_of_three` — company="до 30 дней", director="61-90", guarantor="31-60" → берёт worst от всех трёх

## test_auth.py — Тесты аутентификации

### JWT
1. `test_create_token` — создать токен, декодировать, проверить sub и exp
2. `test_token_expired` — создать токен с exp в прошлом → 401
3. `test_invalid_token` — рандомная строка → 401

### Логин API
4. `test_login_success` — POST /api/auth/login → 200 + token
5. `test_login_wrong_password` — POST /api/auth/login → 401
6. `test_login_nonexistent_user` — POST /api/auth/login → 401
7. `test_login_inactive_user` — is_active=False → 401

### Пермишены
8. `test_superadmin_all_permissions` — is_superadmin=True → все 9 пермишенов True
9. `test_inspector_limited_permissions` — роль Инспектор → anketa_create=True, user_manage=False
10. `test_require_permission_denied` — инспектор → GET /api/admin/users → 403
11. `test_require_permission_allowed` — админ → GET /api/admin/users → 200

### Пароли
12. `test_hash_and_verify_password` — hash_password("test123") → verify_password("test123", hash) == True
13. `test_verify_wrong_password` — verify_password("wrong", hash) == False
14. `test_generate_password_strength` — generate_password() содержит upper + lower + digit + special

## test_api.py — Тесты API эндпоинтов

### CRUD
1. `test_create_anketa` — POST /api/anketas → 200, проверить id и status="draft"
2. `test_get_anketa` — GET /api/anketas/{id} → 200, данные совпадают
3. `test_list_anketas` — GET /api/anketas → 200, список содержит созданную
4. `test_update_anketa` — PATCH /api/anketas/{id} → 200, поля обновлены
5. `test_delete_anketa` — DELETE /api/anketas/{id} → 200, soft delete (deleted_at not None)

### Бизнес-флоу
6. `test_save_anketa` — POST /api/anketas/{id}/save → status="saved", расчёты запущены
7. `test_conclude_anketa` — POST /api/anketas/{id}/conclude → decision записан, concluded_by заполнен
8. `test_conclude_without_permission` — инспектор без anketa_conclude → 403

### Публичный доступ
9. `test_public_anketa` — GET /api/public/anketa/{share_token} → 200 (без авторизации)
10. `test_public_anketa_invalid_token` — рандомный токен → 404

## Требования к реализации

1. Добавить `pytest` и `httpx` в requirements.txt
2. Все тесты должны проходить: `pytest tests/ -v`
3. Каждый тест изолирован (rollback после каждого)
4. Тестовая БД — SQLite in-memory, НЕ трогать прод
5. Засеять дефолтные правила (UnderwritingRule) в conftest — скопировать из database.py seed_default_rules()
6. Все assert-сообщения на русском
7. Покрытие: минимум 40 тестов
8. После написания: запустить pytest -v, убедиться что всё зелёное
9. git checkout -b feature/pytest-tests
10. Коммит на русском: "Добавить pytest тесты для расчётов, вердикта, auth и API"
11. git push origin feature/pytest-tests

## Что НЕ делать
- НЕ менять существующий код (только добавлять tests/)
- НЕ менять структуру БД
- НЕ коммитить в main
- НЕ использовать моки для бизнес-логики (тестировать реальные функции)
