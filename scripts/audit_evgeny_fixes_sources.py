"""Record exact local source identities used for the fixes review."""

from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'Разобрать/Версии проекта от Жени/Референсы/reference v2'
TARGET = ROOT / 'docs/planning/evgeny-fixes-source-manifest-2026-09-29.json'


def build() -> dict:
    paths = sorted((ROOT / 'Разобрать/Версии проекта от Жени/фиксы').glob('*'))
    paths += [REFERENCE / name for name in ['00_METHODOLOGY.md', '02_CONSTANTS.md',
        '03_FORMULAS.md', '04_DECISIONS.md', '06_EXPERT.md',
        '09_OPEN_QUESTIONS.md', '13_RECONCILIATION.md']]
    paths += sorted((ROOT / 'Разобрать/Материалы от организаторов/ТЗ').glob('*.pdf'))
    paths += [ROOT / name for name in ['data/calculation/registry-v1.json',
        'data/calculation/registry-v1.manifest.json',
        'docs/planning/calculation-policy-decisions-v1.md',
        'docs/planning/zhenya-reference-v2-delta.md']]
    manifest = json.loads((ROOT / 'data/calculation/registry-v1.manifest.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((ROOT / 'data/calculation/registry-v1.json').read_bytes()).hexdigest() == manifest['registry_sha256']
    return {'schema_version': 'evgeny-fixes-source-manifest-v1', 'review_date': '2026-09-29',
        'sources': [{'path': p.relative_to(ROOT).as_posix(),
                     'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}


if __name__ == '__main__':
    TARGET.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('Recorded local sources; registry SHA-256 matches its manifest')
