"""Exact decimal helpers shared by capacity formula implementations."""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, localcontext


def decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def canonical(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("capacity values must be finite")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def ceil_exact(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def floor_exact(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def operating_hours(shifts: Decimal, hours_per_shift: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        result = shifts * hours_per_shift
    if shifts <= 0 or hours_per_shift <= 0 or result > 24:
        raise ValueError("H = shifts × hours must be in (0, 24] without clamp")
    return result


def cycle_time(
    one_way_distance_m: Decimal,
    operating_speed_m_s: Decimal,
    exchange_seconds: Decimal,
) -> Decimal:
    if one_way_distance_m < 0 or operating_speed_m_s <= 0 or exchange_seconds < 0:
        raise ValueError("distance/exchange must be non-negative and speed positive")
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        return Decimal(2) * one_way_distance_m / operating_speed_m_s + exchange_seconds


def resolve_batch(
    *,
    box_mode: bool,
    payload_kg: Decimal,
    item_mass_kg: Decimal | None,
    explicit_limit: Decimal | None,
    passport_limit: Decimal | None = None,
    geometry_limit: Decimal | None = None,
) -> tuple[Decimal, int | None]:
    limits: list[Decimal] = []
    mass_limit: int | None = None
    if box_mode:
        if item_mass_kg is None or item_mass_kg <= 0:
            raise ValueError("box batch requires positive item mass")
        mass_limit = floor_exact(payload_kg / item_mass_kg)
        if mass_limit < 1:
            raise ValueError("payload is below one item mass")
        if explicit_limit is not None and explicit_limit > mass_limit:
            raise ValueError("explicit batch exceeds payload-derived mass limit")
        limits.append(Decimal(mass_limit))
    for value in (explicit_limit, passport_limit, geometry_limit):
        if value is not None:
            if value <= 0 or value != value.to_integral_value():
                raise ValueError("batch limits must be positive integers")
            limits.append(value)
    return (min(limits) if limits else Decimal(1)), mass_limit


def nominal_capacity(
    seconds_per_hour: Decimal, cycle_seconds: Decimal, units_per_trip: Decimal
) -> tuple[Decimal, Decimal]:
    if seconds_per_hour <= 0 or cycle_seconds <= 0 or units_per_trip <= 0:
        raise ValueError("nominal capacity inputs must be positive")
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        trips_per_hour = seconds_per_hour / cycle_seconds
        return trips_per_hour, trips_per_hour * units_per_trip


def size_fleet(
    *, demand_per_day: Decimal, operating_hours_per_day: Decimal,
    intraday_peak: Decimal, reserve_share: Decimal,
    nominal_units_per_hour: Decimal, availability: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal, int]:
    if demand_per_day <= 0 or operating_hours_per_day <= 0 or nominal_units_per_hour <= 0:
        raise ValueError("active demand, hours, and nominal capacity must be positive")
    if not Decimal(0) < availability <= Decimal(1) or intraday_peak < 0 or reserve_share < 0:
        raise ValueError("peak/reserve/availability outside formula domain")
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        average = demand_per_day / operating_hours_per_day
        peak_factor = intraday_peak * (Decimal(1) + reserve_share)
        required = average * peak_factor
        effective = nominal_units_per_hour * availability
        recommended = ceil_exact(required / effective)
        return average, peak_factor, required, effective, recommended


def actual_fleet_capacity(
    *, selected: int, nominal_per_robot: Decimal,
    effective_per_robot: Decimal, required: Decimal,
) -> tuple[Decimal, Decimal, Decimal | None, Decimal | None, bool]:
    if selected < 0 or required <= 0:
        raise ValueError("selected fleet must be non-negative and demand positive")
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        nominal = Decimal(selected) * nominal_per_robot
        effective = Decimal(selected) * effective_per_robot
        if selected == 0:
            return nominal, effective, Decimal(0), None, True
        raw_load = required / effective
        return nominal, effective, min(effective / required, Decimal(1)), raw_load, raw_load > 1


def cleaning_capacity(
    *,
    area_m2: Decimal,
    frequency_per_day: Decimal,
    rate_m2_hour: Decimal,
    operating_hours_per_day: Decimal,
    availability: Decimal,
) -> tuple[Decimal, Decimal, Decimal, int]:
    """F05 daily required, nominal/effective capacity, and exact fleet ceil."""
    if area_m2 <= 0 or frequency_per_day <= 0:
        raise ValueError("cleaning area and frequency must be positive")
    if rate_m2_hour <= 0 or operating_hours_per_day <= 0:
        raise ValueError("cleaning rate and operating hours must be positive")
    if not Decimal(0) < availability <= Decimal(1):
        raise ValueError("availability must be in (0, 1]")
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        required = area_m2 * frequency_per_day
        nominal = rate_m2_hour * operating_hours_per_day
        effective = nominal * availability
        return required, nominal, effective, ceil_exact(required / effective)
