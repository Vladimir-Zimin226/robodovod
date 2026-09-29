"""Structured object requirements and evidence-backed catalog facts for C05."""
from decimal import Decimal, InvalidOperation
from calculation.constraints import CandidateConstraintFacts, ObjectConstraintContext
from catalog_selection import SAFE_FACT_STATUSES, numeric_fact

UNITS = {'max_lift_height_m': 'm', 'temperature_min_c': 'C', 'temperature_max_c': 'C',
         'noise_dba': 'dBA', 'floor_flatness_tolerance_mm_2m': 'mm/2m',
         'max_slope_percent': '%', 'charging_power_kw': 'kW', 'availability': '1'}


def validate_object_context(raw: dict, process) -> dict:
    context = ObjectConstraintContext.model_validate(raw)
    if context.object_kind != process.object_kind:
        raise ValueError('object constraints must belong to this object')
    for field in context.model_fields_set - {'object_kind', 'requirement_sources'}:
        value = getattr(context, field)
        if value is None or value is False or value == []:
            continue
        if field == 'time_scope' and value == 'ANY':
            continue
        source = context.requirement_sources.get(field)
        if source is None or not source.user_confirmed:
            raise ValueError(f'confirm object requirement: {field}')
    mass = process.item_mass
    if mass is not None and mass.status == 'KNOWN' and context.max_payload_kg is None:
        raise ValueError('confirm required trip payload from item mass and batch')
    if mass is not None and mass.status == 'KNOWN' and context.max_payload_kg is not None:
        batch = process.explicit_batch
        units = Decimal(batch.normalized_value) if batch is not None and batch.status == 'KNOWN' else Decimal(1)
        if Decimal(context.max_payload_kg) < Decimal(mass.normalized_value) * units:
            raise ValueError('confirmed trip load is less than item mass times batch')
    return context.model_dump(mode='json')


def catalog_constraint_facts(position, fallback: CandidateConstraintFacts) -> CandidateConstraintFacts:
    """Only matching safe facts; duplicate/conflicting values never become a passport."""
    values = fallback.model_dump(mode='json', exclude_none=True)
    evidence = values['evidence']
    # A calculation profile or industry tag proves a formula's scope, not a
    # passport for the requested warehouse, airport or hospital environment.
    values.pop('supported_object_kinds', None)
    evidence.pop('supported_object_kinds', None)
    facts = position.model.facts
    raw = {'facts': [{'code': fact.code, 'value': fact.value, 'unit': fact.canonical_unit,
                     'status': fact.resolution_status, 'evidence_id': fact.evidence_id} for fact in facts]}
    for field, alias in [('payload_kg', 'payload'), ('min_aisle_width_m', 'min_aisle_width')]:
        value, ref = numeric_fact(raw, alias)
        values.pop(field, None); evidence.pop(field, None)
        if value is not None:
            values[field] = format(value, 'f')
            evidence[field] = {'evidence_status': 'MATCHING_SAFE', 'source_ref': ref}
    for field in set(CandidateConstraintFacts.model_fields) - {'model_id', 'position_id', 'evidence', 'payload_kg', 'min_aisle_width_m'}:
        eligible = [fact for fact in facts if fact.code == field and fact.value is not None
                    and fact.evidence_id and fact.resolution_status in SAFE_FACT_STATUSES]
        if not eligible:
            continue
        first = eligible[0]
        if any(fact.value != first.value or fact.canonical_unit != first.canonical_unit for fact in eligible):
            values.pop(field, None); evidence.pop(field, None)
            continue
        if field in UNITS:
            if first.canonical_unit != UNITS[field]:
                continue
            try:
                amount = Decimal(str(first.value))
                if not amount.is_finite():
                    continue
                value = format(amount, 'f')
            except (InvalidOperation, ValueError):
                continue
        else:
            value = first.value
            if field.endswith(('supported', 'available', 'permission', 'surface')) and not isinstance(value, bool):
                continue
        try:
            CandidateConstraintFacts.model_validate({**values, field: value})
        except ValueError:
            continue
        values[field] = value
        evidence[field] = {'evidence_status': 'MATCHING_SAFE', 'source_ref': first.evidence_id}
    return CandidateConstraintFacts.model_validate(values)
