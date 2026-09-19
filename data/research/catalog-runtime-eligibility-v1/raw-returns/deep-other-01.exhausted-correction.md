# Отчет по моделям

| Организатор ID                           | Название                                  | Статус идентичности         | ✔Verified / ⚠Conflicts / ❓NotFound | Источники                                   |
|------------------------------------------|-------------------------------------------|-----------------------------|------------------------------------|---------------------------------------------|
| 22b5ba99-bc4f-46a7-9a9b-e4475ecd9fc7      | Роботизированный комплекс по укладке заготовок | EXACT_MODEL_MATCH           | 0✔ / 0⚠ / 7❓                    | –                                           |
| cdf80f5b-c60a-447b-af30-2c8a44480f98      | Белка                                     | EXACT_MODEL_MATCH           | 5✔ / 0⚠ / 9❓                    | [ComNews: Белка (24.07.2025)](https://www.comnews.ru/digital-economy/content/240352/2025-07-24/2025-w30/1012/rf-poyavilsya-robot-kotoryy-zamenit-kurerov-dostavke-do-dveri) |
| d55f507b-b3f2-4666-b3f4-dd3d48813e9d      | ARIPIX А1                                 | EXACT_MODEL_MATCH           | 0✔ / 0⚠ / 7❓                    | –                                           |

CATALOG_RESULT_JSON_BEGIN
```json
{
  "schema_version": "catalog-official-source-research-return-v1",
  "batch_id": "deep-other-01",
  "research_completed_at": "2026-09-18T16:25:29+09:00",
  "results": [
    {
      "organizer_id": "22b5ba99-bc4f-46a7-9a9b-e4475ecd9fc7",
      "fields": [
        {
          "field_path": "specs.dimensions",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.integrations",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.operating_conditions",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.payload",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.positioning_accuracy",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.service_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.throughput",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        }
      ]
    },
    {
      "organizer_id": "cdf80f5b-c60a-447b-af30-2c8a44480f98",
      "fields": [
        {
          "field_path": "capacity.elevator_compatibility",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": "Yes",
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://www.comnews.ru/digital-economy/content/240352/2025-07-24/2025-w30/1012/rf-poyavilsya-robot-kotoryy-zamenit-kurerov-dostavke-do-dveri",
              "source_title": "В РФ появился робот, который заменит курьеров в доставке \"до двери\"",
              "source_type": "news",
              "source_locator": "Л31-34",
              "publication_or_update_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "беспрепятственно использовать лифты"
            }
          ],
          "confidence": 0.8
        },
        {
          "field_path": "capacity.exchange_time_s",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Параметр не упоминается в официальных источниках"
        },
        {
          "field_path": "capacity.units_per_trip",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Параметр не упоминается в официальных источниках"
        },
        {
          "field_path": "specs.autonomy",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": "6",
          "normalized_unit": "hours",
          "evidence": [
            {
              "source_url": "https://www.comnews.ru/digital-economy/content/240352/2025-07-24/2025-w30/1012/rf-poyavilsya-robot-kotoryy-zamenit-kurerov-dostavke-do-dveri",
              "source_title": "В РФ появился робот, который заменит курьеров в доставке \"до двери\"",
              "source_type": "news",
              "source_locator": "Л35-38",
              "publication_or_update_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "более 6 часов"
            }
          ],
          "confidence": 0.8
        },
        {
          "field_path": "specs.charging_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Параметр не упоминается в официальных источниках"
        },
        {
          "field_path": "specs.connectivity",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Параметр не упоминается в официальных источниках"
        },
        {
          "field_path": "specs.integrations",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Параметр не упоминается в официальных источниках"
        },
        {
          "field_path": "specs.max_speed",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Параметр не упоминается в официальных источниках"
        },
        {
          "field_path": "specs.min_aisle_width",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Параметр не упоминается в официальных источниках"
        },
        {
          "field_path": "specs.navigation",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": "Lidar and vision",
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://www.comnews.ru/digital-economy/content/240352/2025-07-24/2025-w30/1012/rf-poyavilsya-robot-kotoryy-zamenit-kurerov-dostavke-do-dveri",
              "source_title": "В РФ появился робот, который заменит курьеров в доставке \"до двери\"",
              "source_type": "news",
              "source_locator": "Л48-50",
              "publication_or_update_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "лидарную навигацию и машинное зрение"
            }
          ],
          "confidence": 0.8
        },
        {
          "field_path": "specs.operating_conditions",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": "Indoor (residential, office, industrial)",
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://www.comnews.ru/digital-economy/content/240352/2025-07-24/2025-w30/1012/rf-poyavilsya-robot-kotoryy-zamenit-kurerov-dostavke-do-dveri",
              "source_title": "В РФ появился робот, который заменит курьеров в доставке \"до двери\"",
              "source_type": "news",
              "source_locator": "Л46-48",
              "publication_or_update_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "работать внутри жилых, офисных и производственных зданий"
            }
          ],
          "confidence": 0.8
        },
        {
          "field_path": "specs.payload",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": "30",
          "normalized_unit": "kg",
          "evidence": [
            {
              "source_url": "https://www.comnews.ru/digital-economy/content/240352/2025-07-24/2025-w30/1012/rf-poyavilsya-robot-kotoryy-zamenit-kurerov-dostavke-do-dveri",
              "source_title": "В РФ появился робот, который заменит курьеров в доставке \"до двери\"",
              "source_type": "news",
              "source_locator": "Л31-34",
              "publication_or_update_date": "2025-07-24",
              "accessed_at": "2026-09-18",
              "raw_value": "грузы массой до 30 кг"
            }
          ],
          "confidence": 0.8
        },
        {
          "field_path": "specs.service_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Параметр не упоминается в официальных источниках"
        },
        {
          "field_path": "specs.surface_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Параметр не упоминается в официальных источниках"
        }
      ]
    },
    {
      "organizer_id": "d55f507b-b3f2-4666-b3f4-dd3d48813e9d",
      "fields": [
        {
          "field_path": "specs.dimensions",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.integrations",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.operating_conditions",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.payload",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.positioning_accuracy",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.service_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        },
        {
          "field_path": "specs.throughput",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "confidence": 0.0,
          "notes": "Официальный источник не найден"
        }
      ]
    }
  ]
}
```
CATALOG_RESULT_JSON_END