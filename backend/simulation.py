import math
import random
from typing import List

from models import SimulationData, SimulationUnit, UserInput

# ═══════ Геометрия по типу объекта ═══════
ASPECT_BY_OBJECT = {
    "retail":  0.60,   # типовой склад торговли
    "airport": 0.35,   # длинные узкие терминалы
    "clinic":  0.75,   # ближе к квадрату
    "other":   0.60,
}

MAIN_AISLE_FRACTION = 0.06
DOCK_X_FRACTION = 0.03
DOCK_MARGIN_FRACTION = 0.05
MIN_DOCK_GAP_M = 0.5

# Число коридоров в зависимости от площади
CORRIDORS_BY_AREA = [
    (2_000,       2),
    (10_000,      3),
    (40_000,      4),
    (float("inf"), 5),
]

PATTERNS = ("single", "double", "zigzag", "sweep")


def _corridor_count(area_m2: float) -> int:
    for threshold, count in CORRIDORS_BY_AREA:
        if area_m2 < threshold:
            return count
    return 5


def _route_length(route: List[List[float]]) -> float:
    return sum(
        math.hypot(x2 - x1, y2 - y1)
        for (x1, y1), (x2, y2) in zip(route, route[1:])
    )


def _build_route(rng: random.Random, dock: List[float], main_y: float,
                 corridors: List[float], h: float, pattern: str) -> List[List[float]]:
    """Собирает замкнутый маршрут одного робота по выбранному шаблону."""
    dx = dock[0]
    n = len(corridors)

    if pattern == "single":
        c = rng.choice(corridors)
        y = round(rng.uniform(0.25, 0.85) * h, 1)
        return [dock, [dx, main_y], [c, main_y], [c, y], [c, main_y],
                [dx, main_y], dock]

    if pattern == "double":
        if n >= 2:
            i1, i2 = rng.sample(range(n), 2)
        else:
            i1 = i2 = 0
        c1, c2 = corridors[i1], corridors[i2]
        y1 = round(rng.uniform(0.25, 0.85) * h, 1)
        y2 = round(rng.uniform(0.25, 0.85) * h, 1)
        return [dock, [dx, main_y],
                [c1, main_y], [c1, y1], [c1, main_y],
                [c2, main_y], [c2, y2], [c2, main_y],
                [dx, main_y], dock]

    if pattern == "zigzag":
        if n >= 2:
            i1, i2 = rng.sample(range(n), 2)
        else:
            i1 = i2 = 0
        c1, c2 = corridors[i1], corridors[i2]
        y1 = round(rng.uniform(0.25, 0.45) * h, 1)
        y2 = round(rng.uniform(0.55, 0.85) * h, 1)
        return [dock, [dx, main_y],
                [c1, main_y], [c1, y1],
                [c2, y1], [c2, y2],
                [c1, y2], [c1, main_y],
                [dx, main_y], dock]

    # pattern == "sweep": широкий проход от первого коридора к последнему
    c1, c2 = corridors[0], corridors[-1]
    y = round(rng.uniform(0.35, 0.80) * h, 1)
    return [dock, [dx, main_y],
            [c1, main_y], [c1, y], [c2, y], [c2, main_y],
            [dx, main_y], dock]


def generate_simulation(inp: UserInput, robot: dict, qty: int,
                        seed: int = 42) -> SimulationData:
    if not inp.area_m2:
        raise ValueError("area_m2 is required for simulation")

    rng = random.Random(seed)
    area = float(inp.area_m2)

    aspect = ASPECT_BY_OBJECT.get(inp.object_type, 0.6)
    w = round(math.sqrt(area * aspect), 1)
    h = round(w / aspect, 1)

    n_corr = _corridor_count(area)
    # Равномерное распределение коридоров по ширине
    corridors = [round(w * (i + 1) / (n_corr + 1), 1) for i in range(n_corr)]

    main_y = round(h * MAIN_AISLE_FRACTION, 1)
    dock_x = round(w * DOCK_X_FRACTION, 1)

    # Границы для доков с отступами
    dock_min_y = round(main_y + h * DOCK_MARGIN_FRACTION, 1)
    dock_max_y = round(h - h * DOCK_MARGIN_FRACTION, 1)
    if dock_max_y <= dock_min_y + MIN_DOCK_GAP_M:
        dock_max_y = dock_min_y + MIN_DOCK_GAP_M

    # Пул шаблонов: перемешиваем и циклически назначаем
    pattern_pool = list(PATTERNS)
    rng.shuffle(pattern_pool)

    units: List[SimulationUnit] = []
    speed = float(robot["specs"]["max_speed_m_s"]) or 1.0

    for i in range(qty):
        # Позиция дока: равномерно вдоль левой стены
        if qty == 1:
            dock_y = (dock_min_y + dock_max_y) / 2
        else:
            dock_y = dock_min_y + (dock_max_y - dock_min_y) * i / (qty - 1)
        dock = [dock_x, round(dock_y, 1)]

        pattern = pattern_pool[i % len(pattern_pool)]
        route = _build_route(rng, dock, main_y, corridors, h, pattern)

        length_m = _route_length(route)
        cycle_s = length_m / speed if speed > 0 else 0.0
        # Фаза: размазываем старты, чтобы не было пробок на главном проходе
        phase_s = (cycle_s / qty) * i if qty > 1 else 0.0

        units.append(SimulationUnit(
            id=i,
            speed=speed,
            route=route,
            pattern=pattern,
            route_length_m=round(length_m, 1),
            cycle_time_s=round(cycle_s, 1),
            phase_offset_s=round(phase_s, 1),
        ))

    return SimulationData(
        width_m=w,
        height_m=h,
        robots_count=qty,
        corridors_x=corridors,
        main_aisle_y=main_y,
        units=units,
        docks=[u.route[0] for u in units],
        aspect=aspect,
    )