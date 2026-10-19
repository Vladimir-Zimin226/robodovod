"""Owner-bound saved warehouse picking calculations and immutable exports."""

from __future__ import annotations

import csv
import io
import json
import uuid
from decimal import Decimal, InvalidOperation
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import AuthContext, require_auth_context, require_csrf
from calculation.picking_project import PickingProjectInputV1, calculate_picking_project
from calculation.readable_report import _pdf
from database import database_session
from persistence_api import _audit, _canonical_sha256, _owned_project
from persistence_models import PickingProjectRun


class PickingSaveRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input: PickingProjectInputV1
    parent_run_id: uuid.UUID | None = None


router = APIRouter(prefix='/api')


def _owned_run(db: Session, project_id: uuid.UUID, run_id: uuid.UUID) -> PickingProjectRun:
    run = db.scalar(select(PickingProjectRun).where(PickingProjectRun.id == run_id,
                                                   PickingProjectRun.project_id == project_id))
    if run is None:
        raise HTTPException(status_code=404, detail='picking run not found')
    if (_canonical_sha256(run.input_snapshot) != run.input_sha256
            or _canonical_sha256(run.result_snapshot) != run.result_sha256):
        raise HTTPException(status_code=409, detail='picking run integrity check failed')
    return run


def _run_dict(run: PickingProjectRun) -> dict:
    return {'id': str(run.id), 'project_id': str(run.project_id),
            'parent_run_id': None if run.parent_run_id is None else str(run.parent_run_id),
            'status': run.status, 'created_at': run.created_at.isoformat(),
            'input_snapshot': run.input_snapshot, 'result_snapshot': run.result_snapshot,
            'checksums': {'input': run.input_sha256, 'result': run.result_sha256}}


def _csv_value(value: object) -> str:
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    rendered = str(value)
    if rendered.lstrip().startswith(('=', '+', '-', '@')):
        try:
            Decimal(rendered)
        except InvalidOperation:
            return "'" + rendered
    return rendered


def _report_lines(run: PickingProjectRun) -> list[tuple[str, str]]:
    input_ = run.input_snapshot
    result = run.result_snapshot
    capacity = result['capacity']
    lines = [('РОБОДОВОД', 'brand'), ('Комплектация склада', 'title'),
             ('Сохранённая сценарная оценка; не является допуском к закупке', 'subtitle'),
             (f"Run: {run.id}", 'cover'),
             (f"Статус: {result['status']}; процесс: {result['process_id']}; единица: {result['unit']}", 'cover'),
             ('', 'page'),
             ('Входы и парк', 'section'),
             (f"Спрос: {input_['demand_per_day']} {result['unit']} в сутки; основание: {input_['unit_basis']}", 'body'),
             (f"Объём, график, доступность и доля: {input_['operation_source']}; {input_['operation_basis']}", 'body'),
             (f"Выработка решения: {input_.get('robot_units_per_hour') or 'не указана'} {result['unit']}/ч; источник: {input_.get('robot_rate_source') or 'не указан'}", 'body'),
             (f"Парк: {capacity['selected_fleet'] if capacity['selected_fleet'] is not None else 'не рассчитан'}; рекомендуемый: {capacity['recommended_fleet'] if capacity['recommended_fleet'] is not None else 'не рассчитан'}", 'metric'),
             ('Труд по ролям', 'section')]
    for role in result['labour']['roles']:
        lines.append((f"{role['role_code']}: штат {role['headcount']}, высвобождение {role['released_people'] if role['released_people'] is not None else 'не рассчитано'}, осталось {role['remaining_people'] if role['remaining_people'] is not None else 'не рассчитано'}; {role['source']}", 'body'))
    lines.append(('Денежный результат', 'section'))
    for name, finance in result['financial'].items():
        npv = f"{finance['npv_rub']} ₽" if finance.get('npv_rub') is not None else 'не рассчитан'
        tco = f"{finance['tco_rub']} ₽" if finance.get('tco_rub') is not None else 'не рассчитан'
        roi = f"{finance['roi_pct']} %" if finance.get('roi_pct') is not None else 'не определён'
        lines.append((f"{name}: NPV {npv}; TCO {tco}; ROI {roi}", 'body'))
    lines.extend([('Границы', 'section'), *[(item, 'note') for item in result['limitations']]])
    if result['missing']:
        lines.append(('Недостающие входы: ' + ', '.join(result['missing']), 'note'))
    return lines


@router.post('/v2/projects/{project_id}/picking-runs/preview')
def preview(project_id: uuid.UUID, payload: PickingProjectInputV1,
            context: AuthContext = Depends(require_csrf),
            db: Session = Depends(database_session)):
    _owned_project(db, project_id, context.user.id)
    return calculate_picking_project(payload)


@router.post('/v2/projects/{project_id}/picking-runs', status_code=status.HTTP_201_CREATED)
def save(project_id: uuid.UUID, payload: PickingSaveRequest,
         context: AuthContext = Depends(require_csrf),
         db: Session = Depends(database_session)):
    _owned_project(db, project_id, context.user.id)
    if payload.parent_run_id is not None:
        _owned_run(db, project_id, payload.parent_run_id)
    input_snapshot = payload.input.model_dump(mode='json')
    result_snapshot = calculate_picking_project(payload.input)
    run = PickingProjectRun(id=uuid.uuid4(), project_id=project_id,
                            parent_run_id=payload.parent_run_id,
                            status=result_snapshot['status'], input_snapshot=input_snapshot,
                            input_sha256=_canonical_sha256(input_snapshot),
                            result_snapshot=result_snapshot,
                            result_sha256=_canonical_sha256(result_snapshot))
    db.add(run)
    _audit(db, 'PICKING_PROJECT_RUN_SAVED', actor_id=context.user.id,
           project_id=project_id,
           aggregate={'run_id': str(run.id), 'status': run.status,
                      'process_id': input_snapshot['process_id'], 'reason_code': 'CALCULATED'})
    db.commit()
    return _run_dict(run)


@router.get('/v2/projects/{project_id}/picking-runs')
def list_runs(project_id: uuid.UUID, process_id: str | None = None,
              context: AuthContext = Depends(require_auth_context),
              db: Session = Depends(database_session)):
    _owned_project(db, project_id, context.user.id)
    query = select(PickingProjectRun).where(PickingProjectRun.project_id == project_id)
    if process_id is not None:
        query = query.where(PickingProjectRun.input_snapshot['process_id'].astext == process_id)
    runs = db.scalars(query.order_by(PickingProjectRun.created_at.desc(), PickingProjectRun.id.desc()).limit(50)).all()
    return {'items': [{'id': str(run.id), 'status': run.status,
                       'created_at': run.created_at.isoformat(),
                       'parent_run_id': None if run.parent_run_id is None else str(run.parent_run_id)}
                      for run in runs]}


@router.get('/v2/projects/{project_id}/picking-runs/{run_id}')
def get_run(project_id: uuid.UUID, run_id: uuid.UUID,
            context: AuthContext = Depends(require_auth_context),
            db: Session = Depends(database_session)):
    _owned_project(db, project_id, context.user.id)
    return _run_dict(_owned_run(db, project_id, run_id))


@router.post('/v2/projects/{project_id}/picking-runs/{run_id}/replay')
def replay(project_id: uuid.UUID, run_id: uuid.UUID,
           context: AuthContext = Depends(require_csrf),
           db: Session = Depends(database_session)):
    _owned_project(db, project_id, context.user.id)
    run = _owned_run(db, project_id, run_id)
    calculated = calculate_picking_project(run.input_snapshot)
    matches = _canonical_sha256(calculated) == run.result_sha256
    if not matches:
        raise HTTPException(status_code=409, detail='picking run replay mismatch')
    return {'matches': True, 'result_sha256': run.result_sha256,
            'engine_version': calculated['engine_version']}


@router.get('/v2/projects/{project_id}/picking-runs/{run_id}/report.pdf')
def pdf(project_id: uuid.UUID, run_id: uuid.UUID,
        context: AuthContext = Depends(require_auth_context),
        db: Session = Depends(database_session)):
    _owned_project(db, project_id, context.user.id)
    run = _owned_run(db, project_id, run_id)
    return Response(content=_pdf(_report_lines(run)), media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="picking-{run_id}.pdf"'})


@router.get('/v2/projects/{project_id}/picking-runs/{run_id}/report.csv')
def csv_report(project_id: uuid.UUID, run_id: uuid.UUID,
               context: AuthContext = Depends(require_auth_context),
               db: Session = Depends(database_session)):
    _owned_project(db, project_id, context.user.id)
    run = _owned_run(db, project_id, run_id)
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=';')
    writer.writerow(['section', 'key', 'value'])
    result = run.result_snapshot
    for key, value in run.input_snapshot.items():
        writer.writerow(['input', key, _csv_value(value)])
    for key, value in result['capacity'].items():
        writer.writerow(['capacity', key, _csv_value(value)])
    for role in result['labour']['roles']:
        for key, value in role.items():
            writer.writerow([role['role_code'], key, _csv_value(value)])
    for acquisition, finance in result['financial'].items():
        for key, value in finance.items():
            writer.writerow([acquisition, key, _csv_value(value)])
    return Response(content='\ufeff' + stream.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="picking-{run_id}.csv"'})


@router.get('/v2/projects/{project_id}/picking-runs/{run_id}/archive.zip')
def archive(project_id: uuid.UUID, run_id: uuid.UUID,
            context: AuthContext = Depends(require_auth_context),
            db: Session = Depends(database_session)):
    _owned_project(db, project_id, context.user.id)
    run = _owned_run(db, project_id, run_id)
    stream = io.BytesIO()
    with ZipFile(stream, 'w', compression=ZIP_DEFLATED) as output:
        for name, value in [('input.json', run.input_snapshot), ('result.json', run.result_snapshot),
                            ('manifest.json', {'run_id': str(run.id), 'engine_version': result_version(run),
                                               'input_sha256': run.input_sha256,
                                               'result_sha256': run.result_sha256})]:
            output.writestr(name, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
    return Response(content=stream.getvalue(), media_type='application/zip',
                    headers={'Content-Disposition': f'attachment; filename="picking-{run_id}.zip"'})


def result_version(run: PickingProjectRun) -> str:
    return str(run.result_snapshot['engine_version'])
