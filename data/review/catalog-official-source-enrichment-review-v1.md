# Review результатов official-source research

> Это staging/review-отчёт. Он не изменяет base, overlay, backend, fleet или runtime.

## Покрытие

- Пакеты: 6 из 6.
- Модели: 41.
- Target fields: 456.
- Отсутствующие пакеты: нет.

## Итоги полей

| Решение review | Количество |
|---|---:|
| `ACCEPT_CANDIDATE` | 116 |
| `CONFLICT_REVIEW` | 15 |
| `IDENTITY_REVIEW` | 7 |
| `REMAINS_MISSING` | 318 |

## Проекция исследовательского subset после ручной приёмки

| Статус | Модели | Позиции |
|---|---:|---:|
| `CONFLICT_REVIEW` | 10 | 11 |
| `NEEDS_FACTS` | 31 | 33 |

## По моделям

| Batch | Organizer ID | Модель | Identity | Accept | Review | Missing |
|---|---|---|---|---:|---:|---:|
| `deep-cleaning-01` | `0b9f76be-8213-4938-9661-2bb669dc3d33` | Депеша-3 | `EXACT_MODEL_MATCH` | 0 | 0 | 13 |
| `deep-cleaning-01` | `1625ac11-76d0-4994-a86a-e0a540453984` | Astramis SurfexUnit | `EXACT_MODEL_MATCH` | 2 | 0 | 11 |
| `deep-cleaning-01` | `2f46660e-ea20-4845-9620-8c743b03225b` | Пиксель | `EXACT_MODEL_MATCH_WITH_CONFLICTS` | 8 | 1 | 4 |
| `deep-cleaning-01` | `446c5207-a099-45e0-b615-afd60de08589` | MARK 2 SE | `EXACT_MODEL_MATCH` | 4 | 0 | 2 |
| `deep-cleaning-01` | `5a5b3599-bd64-4330-9bbb-4f8ce7d780b9` | Клинботикс 600 | `EXACT_MODEL_MATCH_WITH_CONFLICTS` | 7 | 3 | 3 |
| `deep-cleaning-01` | `5cecfb84-143b-4af7-89fb-afbf57403792` | МАРК | `EXACT_MODEL_MATCH` | 0 | 0 | 13 |
| `deep-cleaning-01` | `9b20417a-0ac7-4786-985b-f3459a15075d` | Unit | `EXACT_MODEL_MATCH` | 0 | 0 | 13 |
| `deep-cleaning-02` | `ba5d2051-3036-439f-8b2e-e05e26581fe6` | БРО 2.1 | `EXACT_MODEL_MATCH` | 6 | 0 | 7 |
| `deep-cleaning-02` | `d4b39362-518a-4cf2-8770-b69bc03585a0` | Веном Саранча | `EXACT_MODEL_MATCH_WITH_CONFLICTS` | 6 | 1 | 6 |
| `deep-cleaning-02` | `e2095cfe-3ce4-404e-a4bb-2f378480d7ca` | АК-SC80 | `EXACT_MODEL_MATCH` | 8 | 0 | 5 |
| `deep-cleaning-02` | `e8960183-1828-4fdb-8c39-91f5a3523a96` | РУБИ-С-03 | `EXACT_MODEL_MATCH` | 4 | 0 | 9 |
| `deep-cleaning-02` | `ef375ca1-8de1-4a8d-9262-c1a6b71f0333` | БРО 3.0 | `EXACT_MODEL_MATCH` | 7 | 0 | 6 |
| `deep-cleaning-02` | `f31223c1-44c8-4410-8381-6356e2158b61` | Клинботикс 400 PRO | `EXACT_MODEL_MATCH_WITH_CONFLICTS` | 9 | 3 | 1 |
| `deep-mobile-01` | `0265d700-534e-417e-8fde-47de88fc3ebb` | Робот для транспортировки деталей и инструментов | `EXACT_MODEL_MATCH` | 3 | 0 | 10 |
| `deep-mobile-01` | `19a68304-56f7-432f-afd8-b97b2b8466ba` | Беспилотный погрузчик | `EXACT_MODEL_MATCH` | 1 | 0 | 12 |
| `deep-mobile-01` | `28a5afa8-0473-4f80-99a9-b2922b76810f` | Беспилотный тягач (Когнитив Пилот) | `EXACT_MODEL_MATCH` | 6 | 0 | 7 |
| `deep-mobile-01` | `3f2aaa1b-2237-4d7b-b215-1ac5ec789ed5` | Ronavi SR (грузоподъемность до 50 кг) | `EXACT_MODEL_MATCH` | 7 | 0 | 5 |
| `deep-mobile-01` | `4d347e47-38f9-415b-aae1-7a6d3759a75c` | Ronavi RCM (грузоподъемность до 350 кг) | `MODEL_NOT_FOUND` | 0 | 0 | 12 |
| `deep-mobile-01` | `5a36611d-033e-4893-bd49-5d4f776f57dd` | AK-2000-2 | `EXACT_MODEL_MATCH` | 0 | 0 | 8 |
| `deep-mobile-01` | `5ec66969-8fcc-47b3-b517-a9c29372fffe` | AMR 800 (грузоподъемность до 800 кг) | `EXACT_MODEL_MATCH` | 0 | 0 | 6 |
| `deep-mobile-01` | `66d8e7ad-cdcd-4287-afb0-e2afa9ef5217` | Ronavi SD (грузоподъемность до 10 кг) | `EXACT_MODEL_MATCH` | 3 | 0 | 5 |
| `deep-mobile-01` | `6f3da854-41da-4363-8496-5487f37c845a` | Ronavi H2000 (грузоподъемность до 2 000 кг) | `EXACT_MODEL_MATCH` | 2 | 0 | 3 |
| `deep-mobile-01` | `7d5a76d2-7bf3-4a40-b6f7-64590d4d9273` | AMR 1500 (грузоподъемность до 1 500 кг) | `EXACT_MODEL_MATCH` | 6 | 0 | 6 |
| `deep-mobile-02` | `993d980e-8b91-45e0-9c98-50ffab6e11e4` | Сёмабот (грузоподъемность до 1 500 кг) | `EXACT_MODEL_MATCH` | 0 | 0 | 12 |
| `deep-mobile-02` | `a834aa03-136e-4f61-a1d6-b5563d798f68` | L5 | `EXACT_MODEL_MATCH` | 4 | 0 | 9 |
| `deep-mobile-02` | `a83abbfd-78ee-43dc-9111-f51db4938001` | DMR 300 Carrier B | `EXACT_MODEL_MATCH` | 0 | 0 | 13 |
| `deep-mobile-02` | `b86f4613-789b-4cee-9f75-5d010da90b61` | Роботизированный комплекс по обследованию грунта | `MODEL_NOT_FOUND` | 0 | 0 | 13 |
| `deep-mobile-02` | `be814758-3616-4b94-befa-9848be2ac604` | DMR 600 (грузоподъемность до 600 кг) | `EXACT_MODEL_MATCH` | 6 | 0 | 6 |
| `deep-mobile-02` | `c3d39a80-5fb9-42d3-82ae-0696fb647128` | Робот-комплектовщик | `MODEL_NOT_FOUND` | 0 | 0 | 13 |
| `deep-mobile-02` | `c9e9517c-18f0-47b4-aa05-4344566aa885` | Tagarka (грузоподъемность до 6 000 кг) | `EXACT_MODEL_MATCH` | 0 | 0 | 12 |
| `deep-mobile-02` | `cccd0c0d-8ae7-435d-a171-45f5d82886e6` | DMR 1200 (грузоподъемность до 1 200 кг) | `EXACT_MODEL_MATCH` | 1 | 0 | 11 |
| `deep-mobile-02` | `dcfd9975-81eb-49b5-a422-827a720ba582` | Ronavi M (грузоподъемность до 1200 кг) | `EXACT_MODEL_MATCH_WITH_CONFLICTS` | 9 | 1 | 2 |
| `deep-mobile-02` | `ecd7d582-b342-449a-b43b-66288d159a32` | MULE | `EXACT_MODEL_MATCH` | 5 | 0 | 8 |
| `deep-other-01` | `22b5ba99-bc4f-46a7-9a9b-e4475ecd9fc7` | Роботизированный комплекс по укладке заготовок | `MODEL_NOT_FOUND` | 0 | 0 | 7 |
| `deep-other-01` | `cdf80f5b-c60a-447b-af30-2c8a44480f98` | Белка | `MODEL_NOT_FOUND` | 0 | 0 | 14 |
| `deep-other-01` | `d55f507b-b3f2-4666-b3f4-dd3d48813e9d` | ARIPIX А1 | `MODEL_NOT_FOUND` | 0 | 0 | 7 |
| `hybrid-conflicts-01` | `0ece582a-084c-4a8b-99f4-576f0e01b7c8` | SmartCube | `EXACT_MODEL_MATCH_WITH_CONFLICTS` | 0 | 1 | 0 |
| `hybrid-conflicts-01` | `2ffc706d-fe43-4c2b-baad-a624a95ad3ce` | Робот-штабелёр RoboCV | `EXACT_MODEL_MATCH_WITH_CONFLICTS` | 1 | 2 | 7 |
| `hybrid-conflicts-01` | `5760e938-9a43-45a7-b8e8-f4f2e6383930` | Ronavi H1500 (грузоподъемность до 1 500 кг) | `AMBIGUOUS_MODEL_MATCH` | 0 | 1 | 3 |
| `hybrid-conflicts-01` | `89ffd69f-f07b-4bf2-8023-1fd765a2b6ff` | AMR 100 (грузоподъемность до 100 кг) | `AMBIGUOUS_MODEL_MATCH` | 0 | 6 | 8 |
| `hybrid-conflicts-01` | `b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1` | Робот-тягач RoboCV | `EXACT_MODEL_MATCH_WITH_CONFLICTS` | 1 | 3 | 6 |

## Ограничение

`ACCEPT_CANDIDATE` означает только пригодность для ручной приёмки evidence. Это не runtime-ready и не разрешение на импорт.
