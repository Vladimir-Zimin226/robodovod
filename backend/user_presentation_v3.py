"""Display overlay; historical report/presentation implementations stay intact."""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from presentation import field as historical_field
from calculation.readable_report import _number

GLOSSARY = json.loads((Path(__file__).resolve().parents[1] / 'contracts/user-presentation-v3.json').read_text(encoding='utf-8'))


def field(key):
    item = GLOSSARY['fields'].get(key)
    return (item['label'], item['action']) if item else historical_field(key)


def source_label(source, rationale=None):
    text = str(source or '')
    if str(rationale or '').startswith('Авторское') or re.search('автор|типов|test|fixture|demo', text, re.I):
        return 'Авторское допущение'
    return {'USER': 'Условия пользователя', 'ORGANIZER': 'Материалы организаторов',
            'FILE': 'Введено из файла', 'ASSUMPTION': 'Допущение'}.get(text, 'Источник сохранён в техническом архиве' if text else 'Источник не указан')


def humanize(value):
    text = str(value)
    for code, label in GLOSSARY['statuses'].items():
        text = re.sub(rf'\b{re.escape(code)}\b', label, text)
    text = re.sub(r'\b[CFRK]\d{2}\b', 'раздел расчёта', text)
    text = re.sub(r'\b[0-9a-f]{8}-[0-9a-f-]{27,}\b|sha256:[0-9a-f]{64}', 'подробности в техническом архиве', text, flags=re.I)
    text = re.sub(r'(?:backend/test_|registry[./]|conversion[./])\S*', 'источник в техническом архиве', text)
    return re.sub(r'\b[A-Z][A-Z_]{2,}\b', 'условие требует уточнения', text)


def input_value(key, value):
    if value is None:
        return 'Не указано'
    if isinstance(value, bool):
        return 'Да' if value else 'Нет'
    try:
        numeric = Decimal(str(value))
        if not numeric.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        return humanize(value)
    if key in {'discount_rate', 'fraction', 'work_share.fraction'}:
        return _number(numeric * 100) + ' %'
    if key == 'start_seconds_from_midnight':
        seconds = int(numeric)
        return f'{seconds // 3600:02d}:{seconds % 3600 // 60:02d}'
    unit = GLOSSARY['fields'].get(key, {}).get('unit')
    if key.endswith('_gross') or unit == 'RUB':
        return _number(numeric, money=True) + ' ₽'
    if 'percent' in key:
        return _number(numeric) + ' %'
    suffix = {'horizon_years': 'лет', 'warranty_years': 'лет', 'raas_contract_months': 'мес.',
              'control_headcount': 'чел.', 'technician_headcount': 'чел.', 'average_power_w': 'Вт',
              'manual_units_per_shift': 'ед./чел./смену'}.get(key, GLOSSARY.get('units', {}).get(unit, unit or ''))
    return _number(numeric) + (' ' + suffix if suffix else '')
