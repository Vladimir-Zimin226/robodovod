# Зарегистрированные маршруты FastAPI

Сгенерировано из `backend/main.py`; схема: [openapi.json](openapi.json).

| Метод | Путь | Операция |
| --- | --- | --- |
| GET | `/` | Root |
| GET | `/api/admin/catalog` | Listing |
| GET | `/api/admin/catalog/audit` | History |
| POST | `/api/admin/catalog/import` | Upload |
| POST | `/api/admin/catalog/versions` | Create |
| GET | `/api/admin/catalog/versions/{code}` | Read |
| PUT | `/api/admin/catalog/versions/{code}` | Update |
| POST | `/api/admin/catalog/versions/{code}/activate` | Activate |
| POST | `/api/admin/catalog/versions/{code}/publish` | Publish |
| GET | `/api/admin/catalog/versions/{code}/sections/{section}` | Read Section |
| PUT | `/api/admin/catalog/versions/{code}/sections/{section}` | Write Section |
| POST | `/api/admin/catalog/versions/{code}/validate` | Check |
| POST | `/api/admin/diagnostics/export` | Export Diagnostics |
| GET | `/api/admin/users` | List Users |
| POST | `/api/admin/users` | Create User |
| PATCH | `/api/admin/users/{user_id}` | Update User |
| DELETE | `/api/admin/users/{user_id}` | Delete User |
| POST | `/api/admin/users/{user_id}/reset-password` | Reset Password |
| POST | `/api/assistant/catalog` | Catalog |
| GET | `/api/assistant/projects/{project_id}/profile` | Read Profile |
| PUT | `/api/assistant/projects/{project_id}/profile` | Save Profile |
| POST | `/api/assistant/service` | Service |
| POST | `/api/assistant/web` | Web |
| POST | `/api/audit` | Audit |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/auth/me` | Me |
| GET | `/api/auth/privacy-consent` | Privacy Consent |
| POST | `/api/auth/register` | Register |
| GET | `/api/brain/projects/{project_id}` | Read |
| POST | `/api/brain/projects/{project_id}/catalog-default` | Propose Default |
| POST | `/api/brain/projects/{project_id}/confirm` | Confirm |
| POST | `/api/brain/projects/{project_id}/edit` | Edit |
| POST | `/api/brain/projects/{project_id}/retry` | Retry |
| POST | `/api/brain/projects/{project_id}/runs` | Bind |
| POST | `/api/brain/projects/{project_id}/select-process` | Select Process |
| POST | `/api/brain/projects/{project_id}/turn` | Turn |
| POST | `/api/calculate` | Calculate |
| POST | `/api/candidate-comparisons/preview` | Preview |
| POST | `/api/candidate-comparisons/projects/{project_id}` | Compare |
| GET | `/api/candidate-comparisons/projects/{project_id}/sources/{run_id}` | Options |
| GET | `/api/catalog/defaults` | Defaults |
| GET | `/api/catalog/media/{catalog_code}/{sha256}` | Catalog Media |
| GET | `/api/catalog/models` | Discover Catalog Models |
| GET | `/api/catalog/positions/{position_id}` | Get Catalog Position |
| GET | `/api/catalog/status` | Catalog Status |
| GET | `/api/facility-layout/projects/{project_id}/runs/{run_id}` | Read |
| POST | `/api/facility-layout/projects/{project_id}/runs/{run_id}` | Save |
| GET | `/api/object-profiles` | List Object Profiles |
| GET | `/api/object-profiles/{object_type}` | Get Object Profile |
| GET | `/api/object-profiles/{object_type}/preset` | Get Structured Preset |
| GET | `/api/presets/{object_type}` | Get Preset |
| GET | `/api/project-file-templates/{profile_code}.csv` | Download Project File Template |
| GET | `/api/project-workbooks/{profile_code}/{variant}.{extension}` | Download Project Workbook |
| GET | `/api/projects` | List Projects |
| POST | `/api/projects` | Create Project |
| GET | `/api/projects/{project_id}` | Get Project |
| PATCH | `/api/projects/{project_id}` | Update Project |
| DELETE | `/api/projects/{project_id}` | Remove Project |
| POST | `/api/projects/{project_id}/analysis-runs` | Create Analysis Run |
| GET | `/api/projects/{project_id}/analysis-runs` | List Analysis Runs |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}` | Get Analysis Run |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}/exports/comparison.csv` | Download Comparison Csv |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}/exports/evidence.zip` | Download Bundle |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}/exports/investor-report-preview.pdf` | Investor Report |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}/exports/investor-report.pdf` | Investor Report |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}/exports/manifest` | Get Manifest |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}/exports/report-preview.pdf` | Preview Readable Report |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}/exports/report.pdf` | Download Readable Report |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}/exports/result.xlsx` | Download Result Xlsx |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}/exports/visualization.svg` | Download Visualization Svg |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}/legacy-replay` | Replay Legacy Analysis |
| GET | `/api/projects/{project_id}/analysis-runs/{run_id}/manual-productivity-estimate` | Get Manual Productivity Estimate |
| POST | `/api/projects/{project_id}/analysis-runs/{run_id}/rerun` | Rerun Analysis |
| POST | `/api/projects/{project_id}/copy` | Copy Project |
| GET | `/api/projects/{project_id}/files` | List Project Files |
| POST | `/api/projects/{project_id}/files/apply` | Apply Project File |
| POST | `/api/projects/{project_id}/files/preview` | Preview Project File |
| GET | `/api/projects/{project_id}/files/{file_id}` | Download Project File |
| GET | `/api/projects/{project_id}/robcraft-scene` | Read |
| PUT | `/api/projects/{project_id}/robcraft-scene` | Save |
| POST | `/api/projects/{project_id}/robcraft-scene/save-as` | Save As |
| GET | `/api/projects/{project_id}/robcraft-scene/versions/{revision}` | Read Version |
| PATCH | `/api/projects/{project_id}/scenarios/{scenario_id}` | Update Scenario |
| POST | `/api/readiness` | Process Readiness |
| POST | `/api/roboexpert/compare` | Compare |
| GET | `/api/roboexpert/options` | Get Options |
| POST | `/api/roboexpert/summary` | Summary |
| POST | `/api/roboexpert/web` | Web |
| GET | `/api/robots` | List Robots |
| GET | `/api/robots/by-category` | List Robots By Category |
| GET | `/api/robots/categories` | List Categories |
| GET | `/api/robots/{robot_id}` | Get Robot |
| GET | `/api/sources` | Sources |
| POST | `/api/v2/calculation-intake/normalize` | Normalize Calculation Intake |
| POST | `/api/v2/capacity-analyses` | Create Capacity Analysis |
| GET | `/api/v2/capacity-analyses/{run_id}` | Get Capacity Analysis |
| GET | `/api/v2/capacity-catalog/positions` | Capacity Catalog Positions |
| GET | `/api/v2/capacity-catalog/positions/{position_id}` | Capacity Catalog Position Detail |
| POST | `/api/v2/object-roles/{kind}/preview` | Guest Preview |
| POST | `/api/v2/object-roles/{kind}/report.pdf` | Guest Report |
| POST | `/api/v2/object-roles/{kind}/route-preview` | Guest Route Preview |
| GET | `/api/v2/object-roles/{kind}/template` | Template |
| POST | `/api/v2/procurement-reports` | Procurement Report |
| POST | `/api/v2/projects/{project_id}/economics-runs` | Create Economics V2 Run |
| POST | `/api/v2/projects/{project_id}/economics-runs/preview` | Preview Economics V2 Run |
| POST | `/api/v2/projects/{project_id}/economics-runs/{run_id}/replay` | Replay Economics V2 Run |
| GET | `/api/v2/projects/{project_id}/object-roles/{kind}` | Latest |
| POST | `/api/v2/projects/{project_id}/object-roles/{kind}` | Save |
| POST | `/api/v2/projects/{project_id}/object-roles/{kind}/preview` | Preview |
| POST | `/api/v2/projects/{project_id}/operation-batches` | Create Operation Batch |
| GET | `/api/v2/projects/{project_id}/operation-batches` | List Operation Batches |
| GET | `/api/v2/projects/{project_id}/operation-batches/{batch_id}` | Get Operation Batch |
| GET | `/api/v2/projects/{project_id}/operation-batches/{batch_id}/archive.zip` | Operation Batch Archive |
| POST | `/api/v2/projects/{project_id}/operation-batches/{batch_id}/project-economics` | Create Project Portfolio |
| GET | `/api/v2/projects/{project_id}/operation-batches/{batch_id}/report.pdf` | Operation Batch Pdf |
| POST | `/api/v2/projects/{project_id}/picking-runs` | Save |
| GET | `/api/v2/projects/{project_id}/picking-runs` | List Runs |
| POST | `/api/v2/projects/{project_id}/picking-runs/preview` | Preview |
| GET | `/api/v2/projects/{project_id}/picking-runs/{run_id}` | Get Run |
| GET | `/api/v2/projects/{project_id}/picking-runs/{run_id}/archive.zip` | Archive |
| POST | `/api/v2/projects/{project_id}/picking-runs/{run_id}/replay` | Replay |
| GET | `/api/v2/projects/{project_id}/picking-runs/{run_id}/report.csv` | Csv Report |
| GET | `/api/v2/projects/{project_id}/picking-runs/{run_id}/report.pdf` | Pdf |
| POST | `/api/v2/projects/{project_id}/picking-study/preview` | Preview Picking Study |
| GET | `/api/v2/projects/{project_id}/warehouse-roles` | Latest |
| POST | `/api/v2/projects/{project_id}/warehouse-roles` | Save |
| POST | `/api/v2/projects/{project_id}/warehouse-roles/preview` | Preview |
| POST | `/api/v2/simulations` | Start Simulation |
| POST | `/api/v2/simulations/projects/{project_id}/analysis-runs/{run_id}` | Start Saved Simulation |
| GET | `/api/v2/simulations/projects/{project_id}/analysis-runs/{run_id}/evidence` | List Saved Evidence |
| GET | `/api/v2/simulations/projects/{project_id}/analysis-runs/{run_id}/{request_id}` | Saved Simulation Progress |
| POST | `/api/v2/simulations/projects/{project_id}/analysis-runs/{run_id}/{request_id}/cancel` | Cancel Saved Simulation |
| GET | `/api/v2/simulations/projects/{project_id}/analysis-runs/{run_id}/{request_id}/evidence.json` | Download Simulation Evidence |
| GET | `/api/v2/simulations/{request_id}` | Simulation Progress |
| POST | `/api/v2/simulations/{request_id}/cancel` | Cancel Simulation |
| POST | `/api/v2/warehouse-roles/preview` | Guest Preview |
| POST | `/api/v2/warehouse-roles/report.pdf` | Guest Report |
| POST | `/api/v2/warehouse-roles/route-preview` | Guest Route Preview |
| GET | `/api/v2/warehouse-roles/template` | Template |
| GET | `/api/warehouse-chain/projects/{project_id}` | Read |
| POST | `/api/warehouse-chain/projects/{project_id}/versions` | Save |
| GET | `/health` | Health |
| GET | `/ready` | Readiness |
