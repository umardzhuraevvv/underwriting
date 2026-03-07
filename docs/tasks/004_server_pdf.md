# 004: Серверный PDF для анкет

- **Статус:** 📋 Запланировано
- **Дата:** 2026-03-07
- **Ветка:** feature/server-pdf
- **Приоритет:** средний

## Цель
Генерировать PDF анкеты на сервере. Сейчас PDF через window.print() — зависит от браузера. Серверный PDF позволит отправлять по email/Telegram и будет одинаковым везде.

## Требования

### 1. Установить WeasyPrint
- Добавить `weasyprint>=62.0` в requirements.txt
- WeasyPrint генерит PDF из HTML/CSS — подходит лучше всего т.к. у нас уже есть HTML-шаблон для печати

### 2. Создать сервис app/services/pdf_service.py
```python
def generate_anketa_pdf(anketa: Anketa, creator: User, concluder: User | None) -> bytes:
    """Генерирует PDF байты из анкеты."""
```

Логика:
1. Сформировать HTML из данных анкеты (шаблон как в buildPrintHtml() в app.js)
2. Добавить CSS для печати
3. Сконвертировать в PDF через WeasyPrint
4. Вернуть bytes

### 3. HTML-шаблон PDF
Создать `app/templates/anketa_pdf.html` — Jinja2-шаблон.

Блоки PDF (для физлица):
- Заголовок: "Анкета андеррайтинга №{id}" + дата
- Блок 1: Личные данные (ФИО, дата рождения, адрес, телефон)
- Блок 2: Условия сделки (авто, цена, ПВ, срок, ставка, ежемесячный платёж)
- Блок 3: Доходы (все источники, общий месячный доход)
- Блок 4: Кредитная история (обязательства, просрочки, DTI)
- Блок 5: Авто-вердикт (решение, причины, рекомендованный ПВ)
- Блок 6: Заключение (решение, комментарий, кто заключил, дата)
- Подвал: "Сформировано: дата, система Fintech Drive"

Для юрлица — аналогично но с блоками компании, директора, поручителя.

### 4. Добавить эндпоинт
В `app/routers/anketa.py`:
```python
@router.get("/{anketa_id}/pdf")
def download_anketa_pdf(anketa_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Скачать PDF анкеты."""
```

- Проверить доступ (creator или anketa_view_all)
- Вернуть `Response(content=pdf_bytes, media_type="application/pdf")`
- Заголовок: `Content-Disposition: attachment; filename="anketa_{id}.pdf"`

### 5. Добавить Jinja2
- Добавить `jinja2>=3.1.0` в requirements.txt

### 6. Тесты
Добавить `tests/test_pdf.py`:
- `test_pdf_endpoint_returns_pdf` — GET /api/anketas/{id}/pdf → 200, content-type = application/pdf
- `test_pdf_unauthorized` — без токена → 401
- `test_pdf_not_found` — несуществующий id → 404

## Файлы для создания/изменения
- `requirements.txt` — weasyprint>=62.0, jinja2>=3.1.0
- `app/services/__init__.py` — создать (пустой)
- `app/services/pdf_service.py` — создать
- `app/templates/anketa_pdf.html` — создать
- `app/routers/anketa.py` — добавить GET /{id}/pdf
- `tests/test_pdf.py` — создать

## Что НЕ делать
- НЕ менять существующие эндпоинты
- НЕ менять бизнес-логику расчётов
- НЕ удалять window.print() из фронтенда (оставить как fallback)
- НЕ ломать существующие 62 теста

## Критерий готовности
- [ ] WeasyPrint установлен
- [ ] PDF генерируется из анкеты
- [ ] Эндпоинт GET /{id}/pdf работает
- [ ] Шаблон покрывает физлицо и юрлицо
- [ ] Тесты зелёные
- [ ] Коммит в feature/server-pdf
