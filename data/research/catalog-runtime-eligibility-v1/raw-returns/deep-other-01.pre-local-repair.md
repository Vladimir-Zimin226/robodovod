| Модель (organizer_id)                                      | Статус идентичности          | Verified / NotFound | Конфликты | Источники                                   |
|-----------------------------------------------------------|------------------------------|---------------------|-----------|---------------------------------------------|
| Роботизированный комплекс по укладке заготовок (22b5ba99…) | MODEL_NOT_FOUND              | 0 / 7              | 0         | –                                           |
| Белка (cdf80f5b…)                                         | EXACT_MODEL_MATCH            | 8 / 6              | 0         | РобоТренды                    |
| ARIPIX А1 (d55f507b…)                                     | EXACT_MODEL_MATCH            | 3 / 4              | 0         | Робот.Москва                  |

CATALOG_RESULT_JSON_BEGIN
```json
{
  "batch_id": "deep-other-01",
  "research_completed_at": "2026-09-18T15:48:27+09:00",
  "model_results": [
    {
      "organizer_id": "22b5ba99-bc4f-46a7-9a9b-e4475ecd9fc7",
      "model_name": "Роботизированный комплекс по укладке заготовок",
      "identity_status": "MODEL_NOT_FOUND",
      "field_results": [
        {
          "field_path": "specs.dimensions",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Проверено описание модели, значение не найдено"
        },
        {
          "field_path": "specs.integrations",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Проверено описание модели, значение не найдено"
        },
        {
          "field_path": "specs.operating_conditions",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Проверено описание модели, значение не найдено"
        },
        {
          "field_path": "specs.payload",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Проверено описание модели, значение не найдено"
        },
        {
          "field_path": "specs.positioning_accuracy",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Проверено описание модели, значение не найдено"
        },
        {
          "field_path": "specs.service_requirements",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Проверено описание модели, значение не найдено"
        },
        {
          "field_path": "specs.throughput",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Проверено описание модели, значение не найдено"
        }
      ]
    },
    {
      "organizer_id": "cdf80f5b-c60a-447b-af30-2c8a44480f98",
      "model_name": "Белка",
      "identity_status": "EXACT_MODEL_MATCH",
      "field_results": [
        {
          "field_path": "capacity.elevator_compatibility",
          "normalized_value": "да",
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://robotrends.ru/pub/2530/v-dronshab-razrabotali-belku---robokurera-dlya-ispolzovaniya-v-pomesheniyah",
              "title": "В Дронсхаб разработали Белку - робокурьера для использования в помещениях",
              "publisher": "РобоТренды",
              "locator": "Вызывает лифты",
              "publication_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "включая домофоны и лифты"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        },
        {
          "field_path": "capacity.exchange_time_s",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Информация о времени обмена не найдена в официальных источниках"
        },
        {
          "field_path": "capacity.units_per_trip",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Информация о количестве единиц за один рейс не найдена"
        },
        {
          "field_path": "specs.autonomy",
          "normalized_value": "6",
          "normalized_unit": "h",
          "evidence": [
            {
              "source_url": "https://robotrends.ru/pub/2530/v-dronshab-razrabotali-belku---robokurera-dlya-ispolzovaniya-v-pomesheniyah",
              "title": "В Дронсхаб разработали Белку - робокурьера для использования в помещениях",
              "publisher": "РобоТренды",
              "locator": "Автономная работа ≥6 часов",
              "publication_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "не менее 6 часов"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        },
        {
          "field_path": "specs.charging_requirements",
          "normalized_value": "возвращается на док-станцию",
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://robotrends.ru/pub/2530/v-dronshab-razrabotali-belku---robokurera-dlya-ispolzovaniya-v-pomesheniyah",
              "title": "В Дронсхаб разработали Белку - робокурьера для использования в помещениях",
              "publisher": "РобоТренды",
              "locator": "Док-станция для зарядки",
              "publication_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "возвращается на док-станцию для подзарядки"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        },
        {
          "field_path": "specs.connectivity",
          "normalized_value": "облачные сервисы",
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://robotrends.ru/pub/2530/v-dronshab-razrabotali-belku---robokurera-dlya-ispolzovaniya-v-pomesheniyah",
              "title": "В Дронсхаб разработали Белку - робокурьера для использования в помещениях",
              "publisher": "РобоТренды",
              "locator": "Подключение к облаку",
              "publication_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "подключении к облачным сервисам диспетчеризации"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        },
        {
          "field_path": "specs.integrations",
          "normalized_value": "лифт, двери",
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://robotrends.ru/pub/2530/v-dronshab-razrabotali-belku---robokurera-dlya-ispolzovaniya-v-pomesheniyah",
              "title": "В Дронсхаб разработали Белку - робокурьера для использования в помещениях",
              "publisher": "РобоТренды",
              "locator": "Открывает двери, вызывает лифты",
              "publication_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "вызывать лифты и открывать двери"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        },
        {
          "field_path": "specs.max_speed",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Информация о максимальной скорости не найдена"
        },
        {
          "field_path": "specs.min_aisle_width",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Информация о минимальной ширине прохода не найдена"
        },
        {
          "field_path": "specs.navigation",
          "normalized_value": "лидар, машинное зрение",
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://robotrends.ru/pub/2530/v-dronshab-razrabotali-belku---robokurera-dlya-ispolzovaniya-v-pomesheniyah",
              "title": "В Дронсхаб разработали Белку - робокурьера для использования в помещениях",
              "publisher": "РобоТренды",
              "locator": "Лидар и машинное зрение",
              "publication_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "лидарную навигацию и машинное зрение"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        },
        {
          "field_path": "specs.operating_conditions",
          "normalized_value": "только дома без ступенек",
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://robotrends.ru/pub/2530/v-dronshab-razrabotali-belku---robokurera-dlya-ispolzovaniya-v-pomesheniyah",
              "title": "В Дронсхаб разработали Белку - робокурьера для использования в помещениях",
              "publisher": "РобоТренды",
              "locator": "Современные здания",
              "publication_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "в современных домах без перепадов высот полов"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        },
        {
          "field_path": "specs.payload",
          "normalized_value": "30",
          "normalized_unit": "kg",
          "evidence": [
            {
              "source_url": "https://robotrends.ru/pub/2530/v-dronshab-razrabotali-belku---robokurera-dlya-ispolzovaniya-v-pomesheniyah",
              "title": "В Дронсхаб разработали Белку - робокурьера для использования в помещениях",
              "publisher": "РобоТренды",
              "locator": "Грузоподъемность 30 кг",
              "publication_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "грузы массой до 30 кг"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        },
        {
          "field_path": "specs.service_requirements",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Требования к сервисному обслуживанию не найдены"
        },
        {
          "field_path": "specs.surface_requirements",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://robotrends.ru/pub/2530/v-dronshab-razrabotali-belku---robokurera-dlya-ispolzovaniya-v-pomesheniyah",
              "title": "В Дронсхаб разработали Белку - робокурьера для использования в помещениях",
              "publisher": "РобоТренды",
              "locator": "Ровный пол",
              "publication_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "современных домах без перепадов высот полов"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        }
      ]
    },
    {
      "organizer_id": "d55f507b-b3f2-4666-b3f4-dd3d48813e9d",
      "model_name": "ARIPIX А1",
      "identity_status": "EXACT_MODEL_MATCH",
      "field_results": [
        {
          "field_path": "specs.dimensions",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Информация о габаритах не найдена"
        },
        {
          "field_path": "specs.integrations",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Интеграции не указаны в открытых данных"
        },
        {
          "field_path": "specs.operating_conditions",
          "normalized_value": "-30...+40",
          "normalized_unit": "°C",
          "evidence": [
            {
              "source_url": "https://robot.moscow/robots/aripix-a1",
              "title": "ARIPIX А1 — робот-укладчик",
              "publisher": "Робот.Москва",
              "locator": "Рабочие температуры",
              "publication_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "-30…+40 °C"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        },
        {
          "field_path": "specs.payload",
          "normalized_value": "10",
          "normalized_unit": "kg",
          "evidence": [
            {
              "source_url": "https://robot.moscow/robots/aripix-a1",
              "title": "ARIPIX А1 — робот-укладчик",
              "publisher": "Робот.Москва",
              "locator": "Грузоподъёмность 10 кг",
              "publication_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Грузоподъёмность 10 кг"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        },
        {
          "field_path": "specs.positioning_accuracy",
          "normalized_value": "0.3",
          "normalized_unit": "mm",
          "evidence": [
            {
              "source_url": "https://robot.moscow/robots/aripix-a1",
              "title": "ARIPIX А1 — робот-укладчик",
              "publisher": "Робот.Москва",
              "locator": "Точность 0,3 мм",
              "publication_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Точность 0,3 мм"
            }
          ],
          "status": "VERIFIED_OFFICIAL"
        },
        {
          "field_path": "specs.service_requirements",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Данные о сервисном обслуживании не найдены"
        },
        {
          "field_path": "specs.throughput",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "status": "NOT_FOUND",
          "notes": "Данные о производительности не найдены"
        }
      ]
    }
  ]
}
```
CATALOG_RESULT_JSON_END