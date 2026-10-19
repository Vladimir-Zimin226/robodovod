"""Inspect interrupted analyses; mark one reviewed run failed by explicit ID.

Usage in backend container:
  python inspect_stale_runs.py
  python inspect_stale_runs.py --apply --run-id UUID --reason reviewed_interrupted_request
"""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from database import get_database
from persistence_models import AnalysisRun, AuditEntry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--older-than-hours', type=int, default=24)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--run-id', type=uuid.UUID)
    parser.add_argument('--reason', choices=['reviewed_interrupted_request'])
    args = parser.parse_args()
    if args.older_than_hours < 1:
        parser.error('older-than-hours must be at least one')
    if args.apply and (not args.run_id or not args.reason):
        parser.error('--apply requires --run-id and --reason')
    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.older_than_hours)
    with get_database().session() as session:
        query = select(AnalysisRun).where(AnalysisRun.status == 'RUNNING', AnalysisRun.started_at < cutoff)
        if args.run_id:
            query = query.where(AnalysisRun.id == args.run_id)
        if args.apply:
            query = query.with_for_update()
        runs = session.scalars(query.order_by(AnalysisRun.started_at)).all()
        for run in runs:
            events = session.scalars(select(AuditEntry).where(
                AuditEntry.project_subject_id == run.project_id,
                AuditEntry.aggregate['run_id'].astext == str(run.id),
            ).order_by(AuditEntry.created_at.desc())).all()
            related = [event.event_type for event in events]
            print(f'{run.id} project={run.project_id} kind={run.run_kind} '
                  f'started={run.started_at.isoformat()} related_audit={related}')
        if args.apply:
            if len(runs) != 1:
                raise SystemExit('Expected exactly one stale RUNNING run; no change made')
            run = runs[0]
            if run.result_snapshot is not None or run.trace_snapshot is not None:
                raise SystemExit('Run has a result; no change made')
            run.status = 'FAILED'
            run.finished_at = datetime.now(timezone.utc)
            run.diagnostics = {**run.diagnostics, 'error_code': 'INTERRUPTED_REQUEST_REVIEWED',
                               'review_reason': args.reason}
            session.add(AuditEntry(id=uuid.uuid4(), event_type='STALE_ANALYSIS_RUN_MARKED_FAILED',
                                   project_subject_id=run.project_id,
                                   aggregate={'run_id': str(run.id), 'reason': args.reason}))
            session.commit()
            print(f'Marked {run.id} FAILED')


if __name__ == '__main__':
    main()
