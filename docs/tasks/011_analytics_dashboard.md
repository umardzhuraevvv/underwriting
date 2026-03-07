# ТЗ 011: Аналитика — расширенный дашборд с графиками

## Статус: 📋 Запланировано

## Цель
Добавить графики и расширенную аналитику на дашборд. Руководство видит тренды визуально.

## Что сделать

### 1. Подключить Chart.js
В `app/static/pages/index.html` добавить CDN:
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
```

### 2. Расширить API аналитики
В `app/services/analytics_service.py` добавить функции:

#### a) Тренд анкет по месяцам (последние 12 месяцев)
```python
def get_monthly_trend(db: Session) -> list[dict]:
    # Возвращает: [{month: "2026-01", total: 45, approved: 30, rejected: 10, review: 5}, ...]
```

#### b) Распределение DTI
```python
def get_dti_distribution(db: Session) -> list[dict]:
    # Возвращает: [{range: "0-30%", count: 15}, {range: "30-50%", count: 25}, ...]
```

#### c) Топ инспекторов по количеству анкет
```python
def get_inspector_stats(db: Session) -> list[dict]:
    # Возвращает: [{name: "Иванов", total: 50, approved: 35, avg_dti: 42.5}, ...]
```

#### d) Средняя сумма лизинга по месяцам
```python
def get_avg_amount_trend(db: Session) -> list[dict]:
    # Возвращает: [{month: "2026-01", avg_amount: 150000}, ...]
```

### 3. Новые API эндпоинты
В `app/routers/anketa.py`:
- `GET /api/anketas/analytics/monthly-trend` → `get_monthly_trend()`
- `GET /api/anketas/analytics/dti-distribution` → `get_dti_distribution()`
- `GET /api/anketas/analytics/inspector-stats` → `get_inspector_stats()`
- `GET /api/anketas/analytics/amount-trend` → `get_avg_amount_trend()`

Все требуют пермишен `analytics_view`.

### 4. Фронтенд — графики в `app/static/js/app.js`
В секции дашборда добавить 4 canvas-элемента и рендерить графики:

#### a) Линейный график — тренд анкет по месяцам
- Ось X: месяцы
- Линии: approved (зелёный), rejected (красный), review (жёлтый)

#### b) Столбчатая диаграмма — распределение DTI
- Ось X: диапазоны (0-30%, 30-50%, 50-60%, 60%+)
- Столбцы: количество анкет

#### c) Горизонтальная диаграмма — топ инспекторов
- Ось Y: имена
- Столбцы: количество одобренных/отклонённых

#### d) Линейный график — средняя сумма лизинга
- Ось X: месяцы
- Линия: средняя сумма

### 5. Стили
В `app/static/css/style.css` добавить:
- `.analytics-charts` — grid на 2 колонки
- `.chart-card` — карточка с графиком (фон, тень, заголовок)
- Адаптив: на мобильных — 1 колонка

## Файлы
- `app/static/pages/index.html` — подключить Chart.js CDN
- `app/services/analytics_service.py` — новые функции
- `app/routers/anketa.py` — новые эндпоинты
- `app/static/js/app.js` — рендер графиков
- `app/static/css/style.css` — стили карточек

## Тесты
- Все существующие тесты зелёные
- Добавить 4 теста на новые эндпоинты аналитики (возвращают 200, формат правильный)

## Ветка
`feature/analytics-dashboard`

## Критерий готовности
- [ ] 4 графика отображаются на дашборде
- [ ] Графики используют реальные данные из API
- [ ] Адаптивная вёрстка (2 колонки → 1 на мобильном)
- [ ] Все тесты зелёные
- [ ] Dark mode поддерживается
