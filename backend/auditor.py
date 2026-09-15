import os
import re
import json
import time
import logging
from typing import Dict, List, Optional

import requests

from economics import MANDATORY_BY_PROCESS, FULLY_LOADED_MULT

logger = logging.getLogger(__name__)

YC_FOLDER_ID = os.getenv("YC_FOLDER_ID", "")
YC_API_KEY = os.getenv("YC_API_KEY", "")
YAGPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Поля, по которым AI уточняет после закрытия обязательных
HV_ORDER = ["fte_cost_rub", "staff_headcount", "avg_distance_m",
            "aisle_width_m", "shifts_count"]

_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_BASE = 1.5

# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """Ты — AI-аудитор платформы «РобоМера», инженер-консультант по роботизации.
Тип объекта уже выбран: retail=склад торговли, airport=аэропорт, clinic=медучреждение, other=произвольный.

ОБЯЗАТЕЛЬНЫЕ ПОЛЯ (без них нельзя считать ТЭО):
1. process_type — transport (транспортировка), palletizing (паллетизация), cleaning (уборка), delivery (доставка).
2. cargo_type — для transport: pallets (паллеты), boxes (коробки), carts (тележки). 
   Для palletizing: cases. Для delivery: deliveries. Для cleaning: не важно.
3. Объём:
   - transport / palletizing / delivery: pallets_per_day (объём в сутки)
   - cleaning: area_m2 (площадь уборки) + cleaning_frequency_per_day

ВАЖНО: ПОЛЕЗНЫЕ ПОЛЯ (спрашивай максимум 2 после обязательных, если не сказал сам):
- payload_kg — МАКСИМАЛЬНЫЙ вес единицы груза. КРИТИЧНО для выбора робота. 
  Паллеты обычно 300–1200 кг, коробки 5–50 кг, доставки 5–15 кг.
  Если пользователь не знает точно — спроси диапазон или хотя бы «до сколько кг».
- units_per_trip — сколько единиц груза робот везёт за рейс. Спрашивай ТОЛЬКО для transport + boxes.
  Например: «Сколько коробок робот должен везти за один рейс?»
- avg_distance_m — среднее плечо транспортировки (м)
- area_m2 — площадь объекта (м²)
- aisle_width_m — минимальная ширина проходов (м)
- staff_headcount — сколько человек выполняет процесс сейчас
- fte_cost_rub — зарплата в месяц. Формула: сумма × 12 × 1.55 (взносы + overhead)
- shifts_count (1-4) и shift_hours (6/8/10/12), смены × часы ≤ 24; «круглосуточно» → 3×8; «сутки через двое» → 2×12
- boxes_per_pallet — только для palletizing (коробов на паллете)
- cleaning_frequency_per_day — только для cleaning
- operating_days — рабочих дней в году
- discount_rate — ставка дисконтирования
- horizon_years — горизонт 5–10 лет
- released_headcount — сколько человек из штата заменить роботами (0 = никого не увольняем)
- min_pult_fte_per_shift — минимум людей на пульте на смену

ЛОГИКА ВЕСА И ВЫБОРА РОБОТА:
- Если пользователь не указал payload_kg — задай уточняющий вопрос.
- Если вес > 250 кг, лёгкие AMR не подойдут. Если вес > 1350 кг — только AGV паллетные.
- Для коробок > 21 кг паллетайзер не подойдёт.

ФОРМАТ ОТВЕТА — ТОЛЬКО JSON:
{"reply": "твой ответ на русском", "extracted": {...}, "ready": bool}

Правила:
- Не пиши ничего кроме JSON.
- В extracted включай только те поля, которые пользователь явно указал или ты уверенно извлёк.
- НЕ включай payload_kg, если пользователь не назвал вес — лучше уточни.
- Если все обязательные поля есть и готов к расчёту — верни ready=true и попрощайся.
- Пиши дружелюбно, коротко, на русском."""

MOCK_QUESTIONS = {
    "pallets_per_day": "Каков объём в сутки (паллет / коробок / доставок / тележко-рейсов)?",
    "area_m2": "Какова площадь уборки (м²)?",
    "fte_cost_rub": "Какова зарплата сотрудника в месяц?",
    "staff_headcount": "Сколько человек выполняет этот процесс сейчас?",
    "avg_distance_m": "Какое среднее плечо транспортировки (м)?",
    "aisle_width_m": "Какая минимальная ширина проходов (м)?",
    "shifts_count": "Сколько смен в сутки?",
    "cleaning_frequency_per_day": "Сколько раз в день выполняется уборка?",
    "boxes_per_pallet": "Сколько коробов укладывается на одну паллету?",
    "released_headcount": "Сколько человек из текущего штата планируете заменить роботами?",
    "payload_kg": "Какой максимальный вес единицы груза (кг)?",
    "units_per_trip": "Сколько коробок робот должен везти за один рейс?",
}


# ═══════════════════════════════════════════════════════════════
# Основная функция интервью
# ═══════════════════════════════════════════════════════════════
def conduct_interview(message: str, history: list, collected: dict,
                      meta: Optional[dict] = None) -> dict:
    """
    Возвращает {"reply", "collected", "ready", "missing", "meta"}.
    Служебные флаги (hv_asked) хранятся в meta, не в collected.
    """
    meta = dict(meta or {})
    extracted, reply = {}, ""

    if YC_FOLDER_ID and YC_API_KEY:
        try:
            raw = _call_yagpt_with_retry(history, message)
            data = _parse_llm_json(raw)
            if data:
                reply = data.get("reply", "") or ""
                extracted = {
                    k: v for k, v in (data.get("extracted") or {}).items()
                    if v is not None and not k.startswith("_")
                }
        except Exception:
            logger.exception("YandexGPT call failed; falling back to regex extractor")

    if not extracted:
        extracted = _fallback_extract(message)

    for k, v in extracted.items():
        if v is not None:
            collected[k] = v

    # Приводим график к допустимому
    sc, sh = collected.get("shifts_count"), collected.get("shift_hours")
    if sc and sh and sc * sh > 24:
        collected["shift_hours"] = 24 // sc
        reply += f" График скорректирован: {sc} смены × {24 // sc} ч (максимум 24 ч/сутки)."

    proc = collected.get("process_type", "transport")
    mandatory = [k for k in MANDATORY_BY_PROCESS.get(proc, ["pallets_per_day"])
                 if collected.get(k) is None]

    # Для cleaning обязательно нужна cleaning_frequency_per_day
    if proc == "cleaning" and collected.get("cleaning_frequency_per_day") is None:
        if "cleaning_frequency_per_day" not in mandatory:
            mandatory.append("cleaning_frequency_per_day")

    if not reply:
        if extracted:
            reply = "Зафиксировал: " + ", ".join(f"{k}={v}" for k, v in extracted.items()) + "."
        else:
            reply = "Принято."

    if not mandatory:
        if not meta.get("hv_asked"):
            missing_hv = [k for k in HV_ORDER if collected.get(k) is None]
            if missing_hv:
                meta["hv_asked"] = True
                qs = " ".join(MOCK_QUESTIONS.get(k, f"Уточните {k}") for k in missing_hv[:2])
                reply += f" Для точности уточните: {qs}"
                return {"reply": reply, "collected": collected,
                        "ready": False, "missing": missing_hv, "meta": meta}
        reply += " Данных достаточно — передаю в расчётный движок."
    else:
        q = MOCK_QUESTIONS.get(mandatory[0], f"Уточните {mandatory[0]}")
        reply += f" Уточните: {q}"

    return {"reply": reply, "collected": collected,
            "ready": not mandatory, "missing": mandatory, "meta": meta}


# ═══════════════════════════════════════════════════════════════
# YandexGPT
# ═══════════════════════════════════════════════════════════════
def _call_yagpt(history, message):
    messages = [{"role": "system", "text": SYSTEM_PROMPT}]
    for h in history[-6:]:
        messages.append({"role": h.get("role", "user"), "text": h.get("content", "")})
    messages.append({"role": "user", "text": message})
    body = {
        "modelUri": f"gpt://{YC_FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {"temperature": 0.2, "maxTokens": 500},
        "messages": messages,
    }
    r = requests.post(YAGPT_URL,
                      headers={"Authorization": f"Api-Key {YC_API_KEY}"},
                      json=body, timeout=15)
    r.raise_for_status()
    return r.json()["result"]["alternatives"][0]["message"]["text"]


def _call_yagpt_with_retry(history, message):
    last_exc: Optional[BaseException] = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return _call_yagpt(history, message)
        except requests.Timeout as e:
            last_exc = e
        except requests.ConnectionError as e:
            last_exc = e
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status and 400 <= status < 500 and status != 429:
                raise
            last_exc = e
        if attempt < _RETRY_ATTEMPTS - 1:
            time.sleep(_RETRY_BACKOFF_BASE ** attempt)
    if last_exc:
        raise last_exc
    raise RuntimeError("YandexGPT call failed with unknown error")


def _parse_llm_json(raw):
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


# ═══════════════════════════════════════════════════════════════
# Числовые утилиты
# ═══════════════════════════════════════════════════════════════
def _num(s: str) -> float:
    """Терпимый к '12 000', '12,5', '80,000', '1.234.567' парсер."""
    s = re.sub(r"[\s\u00A0]", "", s)
    # 1,234,567 — тысячный разделитель
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", s):
        return float(s.replace(",", ""))
    # 1.234.567 — европейский тысячный разделитель (несколько точек)
    if s.count(".") >= 2 and re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        return float(s.replace(".", ""))
    # 12,5 — десятичная запятая
    if "," in s:
        return float(s.replace(",", "."))
    return float(s)


_NUM_RE = r"(\d{1,3}(?:[\s\u00A0]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"


def _parse_money(t: str) -> Optional[float]:
    """Извлекает зарплату. Возвращает годовую стоимость FTE с overhead."""
    m = re.search(r"(?:зарплат\w*|зп\b|оклад\w*)\D{0,40}"
                  + _NUM_RE + r"\s*(млн|тыс\w*|к|k)?", t)
    if not m:
        m = re.search(_NUM_RE + r"\s*(млн|тыс\w*)\s*(?:руб|₽)", t)
    if not m:
        return None
    try:
        val = _num(m.group(1))
    except ValueError:
        return None

    unit = (m.group(2) or "").lower()
    if unit.startswith("млн"):
        val *= 1_000_000
    elif unit.startswith("тыс") or unit in ("к", "k"):
        val *= 1_000

    if val < 1000:
        return None
    # Эвристика: < 500k — почти наверняка за месяц.
    # Используем FULLY_LOADED_MULT = 1.55, синхронизировано с economics._fte_cost.
    if val < 500_000:
        val = val * 12 * FULLY_LOADED_MULT
    return round(val, -3)


# ═══════════════════════════════════════════════════════════════
# Fallback-экстрактор
# ═══════════════════════════════════════════════════════════════
def _fallback_extract(text: str) -> dict:
    t = " " + text.lower() + " "
    out: dict = {}

    # ─── Площадь ───
    m = re.search(r"(\d[\d\s\u00A0]*\d|\d)\s*(?:кв\.?\s*м|м2|м²|квадрат)", t)
    if m:
        try:
            out["area_m2"] = _num(m.group(1))
        except ValueError:
            pass

    # ─── Смены (1-4) ───
    m = re.search(r"(?<!\d)([1-4])(?!\d)\s*смен", t)
    if m:
        out["shifts_count"] = int(m.group(1))

    # ─── Объём в сутки: паллет / коробок / доставок / тележек ───
    m = re.search(
        r"(\d{2,6})\s*(?:паллет|паллето|коробк|груз|перемещен|отправлен|"
        r"доставок|тележко|рейсов|единиц|шт)",
        t,
    )
    if m:
        out["pallets_per_day"] = int(m.group(1))

    # ─── Плечо / дистанция ───
    m = re.search(r"(?:плеч\w*|дистанц\w*|расстоян\w*)\D{0,15}(\d{2,4})", t)
    if m:
        out["avg_distance_m"] = float(m.group(1))

    # ─── Проход ───
    m = re.search(r"проход\w*\D{0,20}(\d(?:[.,]\d+)?)", t)
    if m:
        try:
            out["aisle_width_m"] = _num(m.group(1))
        except ValueError:
            pass

    # ─── Максимальный вес груза ───
    # 1) «весом до 500 кг», «максимальный вес 700 кг», «груз 300 кг»
    m = re.search(
        r"(?:вес\w*|груз\w*|коробк\w*|паллет\w*)\D{0,20}(\d{1,4})\s*кг", t
    )
    if m:
        out["payload_kg"] = float(m.group(1))
    else:
        # 2) просто «500 кг» без ключевого слова
        m = re.search(r"(?<!\d)(\d{1,4})\s*кг", t)
        if m:
            v = float(m.group(1))
            if 1 <= v <= 5000:
                out["payload_kg"] = v

    # ─── boxes_per_pallet ───
    v = None
    m = re.search(r"(?<!\d)(\d{1,3})\s*короб\w*\s*(?:на|в)\s*паллет", t)
    if m:
        v = int(m.group(1))
    else:
        m = re.search(r"паллет\w*\D{0,25}?(\d{1,3})\s*короб", t)
        if m:
            v = int(m.group(1))
    if v is not None and 1 <= v <= 200:
        out["boxes_per_pallet"] = v

    # ─── Зарплата ───
    money = _parse_money(t)
    if money:
        out["fte_cost_rub"] = money

    # ─── Штат ───
    m = re.search(
        r"(\d{1,3})\s*(?:человек|сотрудник\w*|оператор\w*|"
        r"комплектовщик\w*|курьер\w*|уборщик\w*|санитар\w*)",
        t,
    )
    if m:
        out["staff_headcount"] = int(m.group(1))

    # ─── Частота уборки ───
    m = re.search(r"(?<!\d)([1-4])(?!\d)\s*раз[а]?\s*в\s*день", t)
    if m:
        out["cleaning_frequency_per_day"] = int(m.group(1))

    # ─── Сколько заменить ───
    # «заменим 8», «сократим 5», «высвободим 6», «вместо 5 операторов»
    m = re.search(
        r"(?:замен\w*|сократ\w*|высвобод\w*|вместо)\D{0,15}(\d{1,3})\s*"
        r"(?:чел|сотрудник|оператор|грузчик|комплектовщик|уборщик)?",
        t,
    )
    if m:
        v = int(m.group(1))
        if 0 <= v <= 500:
            out["released_headcount"] = v
    elif re.search(
        r"никого не (увол|сократ|замен)|не планируем сокращ|"
        r"без сокращен|не увольняем",
        t,
    ):
        out["released_headcount"] = 0

    # ─── Горизонт ───
    m = re.search(r"(?:горизонт\w*|на)\s*(\d{1,2})\s*(?:лет|год)", t)
    if m:
        v = int(m.group(1))
        if 5 <= v <= 10:
            out["horizon_years"] = v

    # ─── Ставка дисконтирования ───
    m = re.search(r"(?:ставк\w*|дисконт\w*)\D{0,15}(\d{1,2})\s*%", t)
    if m:
        v = int(m.group(1))
        if 4 <= v <= 40:
            out["discount_rate"] = v / 100

    # ─── Рабочих дней ───
    m = re.search(r"(\d{3})\s*(?:рабочих\s*дн|дней\s*в\s*год)", t)
    if m:
        v = int(m.group(1))
        if 1 <= v <= 365:
            out["operating_days"] = v

    # ─── units_per_trip ───
    # «по 10 коробок за рейс», «10 шт за раз», «везёт 8 коробок»
    m = re.search(
        r"(?:по\s*)?(\d{1,2})\s*(?:короб\w*|шт|единиц)\s*"
        r"(?:за|на)?\s*(?:рейс|раз|поездку)",
        t,
    )
    if m:
        v = int(m.group(1))
        if 1 <= v <= 50:
            out["units_per_trip"] = v

    # ─── Процесс ───
    if re.search(r"уборк|моют|полы|дезинф", t):
        out["process_type"] = "cleaning"
    elif re.search(r"достав|курьер|пациент|образц|бель|пищ", t) and not re.search(
        r"коробк|паллет", t
    ):
        out["process_type"] = "delivery"
    elif re.search(r"паллетиз|укладыва\w+ на паллет|паллетиру", t):
        out["process_type"] = "palletizing"

    # ─── Cargo type ───
    if re.search(r"багаж|тележк|тягач", t):
        out["cargo_type"] = "carts"
    elif re.search(r"коробк|штучн", t) and "cargo_type" not in out:
        out["cargo_type"] = "boxes"
    elif re.search(r"паллет", t) and "cargo_type" not in out:
        out["cargo_type"] = "pallets"
    elif re.search(r"доставк|курьер", t) and "cargo_type" not in out:
        out["cargo_type"] = "deliveries"

    # ─── Object type ───
    if re.search(r"аэропорт|терминал", t):
        out["object_type"] = "airport"
    elif re.search(r"клиник|больниц|медиц|госпит", t):
        out["object_type"] = "clinic"

    # ─── Длительность смены ───
    if re.search(r"12[- ]?час|двенадцатичас|сутки через", t):
        out["shift_hours"] = 12
    elif re.search(r"10[- ]?час", t):
        out["shift_hours"] = 10
    elif re.search(r"6[- ]?час", t):
        out["shift_hours"] = 6

    # ─── Особые графики ───
    if re.search(r"круглосуточ|непрерывн", t):
        out["shifts_count"] = 3
        out["shift_hours"] = 8

    return out