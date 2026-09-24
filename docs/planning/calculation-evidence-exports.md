# Calculation evidence exports

Статус: **IMPLEMENTED**, C26 `report/calculation-evidence-exports`, 2026-09-23.

Живое уточнение 2026-09-24: C26 API/builder существует, но браузерный экспорт
`v0.5.9` не принят — `EvidenceExportSession` вызывает `Window.fetch` с неверным
receiver (`Illegal invocation`), поэтому ZIP до API не запрашивается.
`Report.pdf` внутри ZIP — машинный snapshot dump с `\u`-экранированием кириллицы,
а не читаемый самостоятельный отчёт; C23 section остаётся `NOT_AVAILABLE`,
поскольку simulation report не сохранён в AnalysisRun. См.
[план исправления](live-calculation-remediation-2026-09-24.md).

## Результат

C26 добавляет воспроизводимый evidence export только из сохранённого успешного
`AnalysisRun`. Builder не запрашивает live catalog/prices и не выполняет
capacity, ranking, finance, SLA либо simulation formulas. Перед сериализацией
он пересчитывает canonical SHA-256 для input, result, ScenarioSpec, trace и
version bindings и прекращает export при расхождении с persisted checksum.

Архив содержит strict `calculation-evidence-export-manifest-v1`, offline
text-extractable `Report.pdf`, полный `Snapshot.json` и CSV-разделы `Inputs`,
`Selection`, `Scenarios`, `CashFlow`, `Sensitivity`, `Sources`, `Trace`,
`Simulation`, `Versions`. Manifest связывает project/run/revision, snapshot
time, policy/generator versions, source snapshot digests, availability,
artifact byte sizes/SHA-256 и общий content digest. ZIP имеет фиксированные
timestamps и стабильный порядок файлов, поэтому одинаковый run даёт одинаковые
байты.

Каждая отображаемая leaf-value CSV имеет explicit trace/source reference либо
immutable fallback reference вида `snapshot:<part>:<digest>#<path>`.
Отсутствующая экономика, sensitivity или simulation не исчезает: соответствующий
CSV и PDF section содержат `NOT_AVAILABLE` с reason code. Значения decimal
передаются как сохранённый текст; отрицательные суммы не меняются. Строки,
начинающиеся с `=`, `+`, `-` или `@` и не являющиеся canonical decimal,
получают spreadsheet-safe apostrophe prefix.

PDF использует встроенный Courier и не требует CDN, сети или remote fonts.
Он явно маркирован `PRELIMINARY ANALYSIS; NOT ENGINEERING CERTIFICATION`.
Browser получает готовый artifact и не строит вторую финансовую модель.

## API и isolation

- `GET /api/projects/{project_id}/analysis-runs/{run_id}/exports/manifest`;
- `GET /api/projects/{project_id}/analysis-runs/{run_id}/exports/evidence.zip`.

Оба route требуют authenticated session и выбирают только `SUCCEEDED` run
в активном проекте текущего владельца. Missing, inactive и принадлежащий
другому пользователю run имеют одинаковый 404. Это read-only GET, поэтому
CSRF mutation token не применяется. Integrity failure возвращает 409 без
частичного архива. ZIP response несёт тот же manifest digest в
`X-Export-Manifest-Digest` и `ETag`.

Frontend panel сначала строго валидирует schema и project/run binding, затем
скачивает ZIP только при совпадении response digest. Sequence guard отбрасывает
stale manifest/bundle после смены run или unmount; error не запускает download.
Показаны revision, manifest digest и `AVAILABLE`/`NOT_AVAILABLE` каждого
раздела. Старые client PDF utilities оставлены тонкими compatibility adapters
к этому API и больше не содержат расчётов или remote asset loading.

## Контракты и проверки

- schema `contracts/calculation-evidence-export-manifest-v1.schema.json`;
- deterministic manifest и CashFlow CSV golden fixtures;
- reproducible builder `scripts/build_evidence_export_contract.py`;
- backend tests: deterministic ZIP, artifact hashes, PDF text extraction,
  golden amounts/source refs, capacity-only old run, visible unavailable
  sections, malicious cells, tamper rejection, strict version/fields,
  owner isolation и header binding;
- frontend tests: strict parsing, same-origin relative routes/credentials,
  error/stale handling, digest mismatch и отсутствие browser report math/CDN;
- C25 origin/source/two-phase и C24 deterministic 2D regressions;
- frontend lint и production build.

DB/Docker/full suites не требовались: схема хранения и migrations не менялись.
ScenarioSpec v1/v2, C23–C25 contracts, immutable registry v1, catalog/pool
membership, economics snapshots и production runtime остались неизменными.

Следующий этап — C27 `catalog/capacity-runtime-dual-run-rollout`. C27,
economics migration C28, acceptance C29 и production deployment C30 в C26 не
выполнялись.
