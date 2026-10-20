"""Create clearly labelled local layout samples; these are not production reports."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from calculation.object_roles import ObjectRoleInput, analyze_object_roles  # noqa: E402
from calculation.role_report import role_report_pdf  # noqa: E402
from calculation.warehouse_roles import WarehouseRoleInput, analyze_warehouse_roles  # noqa: E402
from test_object_roles import catalog as object_catalog, raw  # noqa: E402
from test_warehouse_roles import catalog as warehouse_catalog, sample  # noqa: E402

OUT = Path(__file__).resolve().parent / 'evidence'
OUT.mkdir(exist_ok=True)
for kind in ('warehouse', 'airport', 'clinic'):
    if kind == 'warehouse':
        result = analyze_warehouse_roles(WarehouseRoleInput.model_validate(sample()), warehouse_catalog())
    else:
        result = analyze_object_roles(ObjectRoleInput.model_validate(raw(kind.upper())), object_catalog())
    target = OUT / f'pdf-layout-fixture-{kind}.pdf'
    target.write_bytes(role_report_pdf(result))
    print(kind, target.stat().st_size)
