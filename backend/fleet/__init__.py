"""
Парк роботов РобоМера.

Каждая категория — отдельный JSON-файл. Loader:
  - читает все *.json в папке
  - валидирует через Pydantic-модель Robot
  - падает с понятной ошибкой, если что-то не так
  - экспортирует ROBOTS, ROBOT_BY_ID, BY_CATEGORY
"""
import json
import pathlib
from typing import Dict, List

from pydantic import ValidationError

from models import Robot

FLEET_DIR = pathlib.Path(__file__).parent

# Порядок категорий для UI/отчётов
CATEGORY_ORDER: List[str] = [
    "internal_mobile",
    "service_delivery",
    "cleaning_robot",
    "fixed_cell",
    "aerial",
]

CATEGORY_LABELS: Dict[str, str] = {
    "internal_mobile":  "Мобильные транспортные роботы",
    "service_delivery": "Роботы доставки",
    "cleaning_robot":   "Уборочные роботы",
    "fixed_cell":       "Стационарные ячейки паллетизации",
    "aerial":           "Летательные системы",
}


def _load_one(path: pathlib.Path) -> List[Robot]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path.name}: ожидался JSON-массив роботов")
    robots: List[Robot] = []
    for item in raw:
        try:
            robots.append(Robot(**item))
        except ValidationError as e:
            raise ValueError(
                f"{path.name}: робот {item.get('id', '?')} не прошёл валидацию:\n{e}"
            ) from e
    return robots


def load_fleet() -> List[Robot]:
    files = sorted(FLEET_DIR.glob("*.json"))
    if not files:
        raise RuntimeError(f"В {FLEET_DIR} нет ни одного *.json")

    robots: List[Robot] = []
    seen_ids: set[str] = set()
    for f in files:
        batch = _load_one(f)
        for r in batch:
            if r.id in seen_ids:
                raise ValueError(f"Дублирующийся id робота: {r.id} (файл {f.name})")
            if r.category not in CATEGORY_LABELS:
                raise ValueError(
                    f"{r.id}: неизвестная категория '{r.category}'. "
                    f"Допустимые: {list(CATEGORY_LABELS)}"
                )
            seen_ids.add(r.id)
        robots += batch
    return robots


# ═══════ Экспорт (загружается один раз при импорте) ═══════
ROBOTS: List[Robot] = load_fleet()
ROBOT_BY_ID: Dict[str, Robot] = {r.id: r for r in ROBOTS}

BY_CATEGORY: Dict[str, List[Robot]] = {c: [] for c in CATEGORY_ORDER}
for _r in ROBOTS:
    BY_CATEGORY[_r.category].append(_r)


def as_dicts() -> List[dict]:
    """Сериализованный вид для отдачи в API."""
    return [r.model_dump() for r in ROBOTS]


def by_category_dicts() -> Dict[str, dict]:
    return {
        cat: {
            "label": CATEGORY_LABELS[cat],
            "robots": [r.model_dump() for r in BY_CATEGORY[cat]],
        }
        for cat in CATEGORY_ORDER
    }