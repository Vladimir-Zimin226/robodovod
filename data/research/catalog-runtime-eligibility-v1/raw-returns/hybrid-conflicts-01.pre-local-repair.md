## Резюме исследований

| **Model** (ID)                          | **Identity Status**                     | **Verified / NotFound / Conflict** | **#Conflicts** | **Sources**                                                |
|-----------------------------------------|-----------------------------------------|-----------------------------------|----------------|------------------------------------------------------------|
| SmartCube (0ece582a-084c-4a8b-99f4-576f0e01b7c8) | EXACT_MODEL_MATCH_WITH_CONFLICTS         | 0 / 0 / 1                         | 1              | [ARS Smart Robotics – SmartCube Robot]               |
| Робот-штабелёр RoboCV (2ffc706d-fe43-4c2b-baad-a624a95ad3ce) | EXACT_MODEL_MATCH_WITH_CONFLICTS         | 2 / 7 / 1                         | 1              | [RoboCV Стекер, Спецификация]                  |
| Ronavi H1500 (5760e938-9a43-45a7-b8e8-f4f2e6383930) | EXACT_MODEL_MATCH                        | 1 / 3 / 0                         | 0              | [Ronavi Robotics – H1500]                            |
| AMR 100 (89ffd69f-f07b-4bf2-8023-1fd765a2b6ff)      | EXACT_MODEL_MATCH                        | 7 / 7 / 0                         | 0              | [КиберМеханика – AMR100]                             |
| Робот-тягач RoboCV (b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1) | EXACT_MODEL_MATCH                        | 4 / 6 / 0                         | 0              | [RoboCV Тягач]                                       |

CATALOG_RESULT_JSON_BEGIN
```json
{
  "batch_id": "hybrid-conflicts-01",
  "research_completed_at": "2026-09-18T16:00:23+09:00",
  "model_results": [
    {
      "organizer_id": "0ece582a-084c-4a8b-99f4-576f0e01b7c8",
      "model_name": "SmartCube",
      "identity_status": "EXACT_MODEL_MATCH_WITH_CONFLICTS",
      "field_results": [
        {
          "field_path": "specs.max_speed",
          "status": "CONFLICT",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://arobosys.ru/robot",
              "title": "Робот (CR-02) - ARS SmartCube",
              "publisher": "ООО «АРС Смарт Роботикс»",
              "locator": "L41-L43",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "2,1 м/с"
            },
            {
              "source_url": "https://arobosys.ru/robot",
              "title": "Робот (CR-02) - ARS SmartCube",
              "publisher": "ООО «АРС Смарт Роботикс»",
              "locator": "L65-L68",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "2,7 м/с"
            }
          ],
          "notes": ""
        }
      ]
    },
    {
      "organizer_id": "2ffc706d-fe43-4c2b-baad-a624a95ad3ce",
      "model_name": "Робот-штабелёр RoboCV",
      "identity_status": "EXACT_MODEL_MATCH_WITH_CONFLICTS",
      "field_results": [
        {
          "field_path": "capacity.exchange_time_s",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте или в спецификации RoboCV."
        },
        {
          "field_path": "capacity.units_per_trip",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте или в спецификации RoboCV."
        },
        {
          "field_path": "specs.aisle_requirements",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://robocv.ru/robot-shtabelyor",
              "title": "Робот-Штабелёр - RoboCV",
              "publisher": "ООО «РобоСиВи»",
              "locator": "L43-L46",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "проезд шириной не менее 1,6 м"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.autonomy",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте RoboCV."
        },
        {
          "field_path": "specs.connectivity",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте RoboCV."
        },
        {
          "field_path": "specs.max_speed",
          "status": "CONFLICT",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://robocv.ru/robot-shtabelyor",
              "title": "Робот-Штабелёр - RoboCV",
              "publisher": "ООО «РобоСиВи»",
              "locator": "L18-L19",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "2 м/с"
            },
            {
              "source_url": "https://robocv.ru/wp-content/uploads/2021/05/robot-shtabelyor-robocv-specifikaciya.pdf",
              "title": "Спецификация RoboCV Робот-Штабелёр",
              "publisher": "ООО «РобоСиВи»",
              "locator": "L27-L28",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "1,67 м/с"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.min_aisle_width",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": 2.9,
          "normalized_unit": "m",
          "evidence": [
            {
              "source_url": "https://robocv.ru/robot-shtabelyor",
              "title": "Робот-Штабелёр - RoboCV",
              "publisher": "ООО «РобоСиВи»",
              "locator": "L24-L26",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "2,9 м"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.operating_conditions",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте RoboCV."
        },
        {
          "field_path": "specs.service_requirements",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте RoboCV."
        },
        {
          "field_path": "specs.surface_requirements",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте RoboCV."
        }
      ]
    },
    {
      "organizer_id": "5760e938-9a43-45a7-b8e8-f4f2e6383930",
      "model_name": "Ronavi H1500 (грузоподъемность до 1500 кг)",
      "identity_status": "EXACT_MODEL_MATCH",
      "field_results": [
        {
          "field_path": "capacity.exchange_time_s",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте Ronavi."
        },
        {
          "field_path": "capacity.units_per_trip",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте Ronavi."
        },
        {
          "field_path": "specs.min_aisle_width",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": 0.75,
          "normalized_unit": "m",
          "evidence": [
            {
              "source_url": "https://ronavi-robotics.ru/catalogue/h1500",
              "title": "Ronavi H1500 - Ronavi Robotics",
              "publisher": "ООО «Ронави Роботикс»",
              "locator": "L136-L139",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "750 мм"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.surface_requirements",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте Ronavi."
        }
      ]
    },
    {
      "organizer_id": "89ffd69f-f07b-4bf2-8023-1fd765a2b6ff",
      "model_name": "AMR 100 (грузоподъемность до 100 кг)",
      "identity_status": "EXACT_MODEL_MATCH",
      "field_results": [
        {
          "field_path": "capacity.exchange_time_s",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на сайте производителя AMR 100."
        },
        {
          "field_path": "capacity.units_per_trip",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на сайте производителя AMR 100."
        },
        {
          "field_path": "specs.autonomy",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": 18,
          "normalized_unit": "h",
          "evidence": [
            {
              "source_url": "https://cybermech.by/amr-100/",
              "title": "AMR100 — Мобильный робот от КиберМеханика",
              "publisher": "ООО «КиберМеханика»",
              "locator": "L64-L67",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "До 18 часов"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.charging_requirements",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://cybermech.by/amr-100/",
              "title": "AMR100 — Мобильный робот от КиберМеханика",
              "publisher": "ООО «КиберМеханика»",
              "locator": "L66-L68",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "Автоматическая док-станция / ручная зарядка"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.connectivity",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на сайте производителя AMR 100."
        },
        {
          "field_path": "specs.dimensions",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": "470×450×300",
          "normalized_unit": "mm",
          "evidence": [
            {
              "source_url": "https://cybermech.by/amr-100/",
              "title": "AMR100 — Мобильный робот от КиберМеханика",
              "publisher": "ООО «КиберМеханика»",
              "locator": "L61-L64",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "470 × 450 × 300 мм"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.integrations",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://cybermech.by/amr-100/",
              "title": "AMR100 — Мобильный робот от КиберМеханика",
              "publisher": "ООО «КиберМеханика»",
              "locator": "L84-L87",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "интеграция с конвейерами, подъемниками, манипуляторами"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.max_speed",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": 0.8,
          "normalized_unit": "m/s",
          "evidence": [
            {
              "source_url": "https://cybermech.by/amr-100/",
              "title": "AMR100 — Мобильный робот от КиберМеханика",
              "publisher": "ООО «КиберМеханика»",
              "locator": "L62-L65",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "До 0,8 м/с"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.min_aisle_width",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на сайте производителя AMR 100."
        },
        {
          "field_path": "specs.navigation",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на сайте производителя AMR 100."
        },
        {
          "field_path": "specs.operating_conditions",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [
            {
              "source_url": "https://cybermech.by/amr-100/",
              "title": "AMR100 — Мобильный робот от КиберМеханика",
              "publisher": "ООО «КиберМеханика»",
              "locator": "L117-L120",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "от +5°C до +40°C; IP54 и выше"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.positioning_accuracy",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": 0.002,
          "normalized_unit": "m",
          "evidence": [
            {
              "source_url": "https://cybermech.by/amr-100/",
              "title": "AMR100 — Мобильный робот от КиберМеханика",
              "publisher": "ООО «КиберМеханика»",
              "locator": "L62-L65",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "±2 мм"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.service_requirements",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на сайте производителя AMR 100."
        },
        {
          "field_path": "specs.surface_requirements",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на сайте производителя AMR 100."
        }
      ]
    },
    {
      "organizer_id": "b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1",
      "model_name": "Робот-тягач RoboCV",
      "identity_status": "EXACT_MODEL_MATCH",
      "field_results": [
        {
          "field_path": "capacity.exchange_time_s",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте RoboCV."
        },
        {
          "field_path": "capacity.units_per_trip",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте RoboCV."
        },
        {
          "field_path": "specs.autonomy",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте RoboCV."
        },
        {
          "field_path": "specs.max_speed",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": 2.2,
          "normalized_unit": "m/s",
          "evidence": [
            {
              "source_url": "https://robocv.ru/robot-tyagach",
              "title": "Робот-тягач - RoboCV",
              "publisher": "ООО «РобоСиВи»",
              "locator": "L17-L19",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "2,2 м/с"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.min_aisle_width",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": 2.9,
          "normalized_unit": "m",
          "evidence": [
            {
              "source_url": "https://robocv.ru/robot-tyagach",
              "title": "Робот-тягач - RoboCV",
              "publisher": "ООО «РобоСиВи»",
              "locator": "L23-L24",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "2,9 м"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.operating_conditions",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте RoboCV."
        },
        {
          "field_path": "specs.payload",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": 5000,
          "normalized_unit": "kg",
          "evidence": [
            {
              "source_url": "https://robocv.ru/robot-tyagach",
              "title": "Робот-тягач - RoboCV",
              "publisher": "ООО «РобоСиВи»",
              "locator": "L17-L18",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "до 5000 кг"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.positioning_accuracy",
          "status": "VERIFIED_OFFICIAL",
          "normalized_value": 0.05,
          "normalized_unit": "m",
          "evidence": [
            {
              "source_url": "https://robocv.ru/robot-tyagach",
              "title": "Робот-тягач - RoboCV",
              "publisher": "ООО «РобоСиВи»",
              "locator": "L21-L23",
              "publication_date": null,
              "accessed_date": "2026-09-18",
              "raw_value": "5 см"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.service_requirements",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте RoboCV."
        },
        {
          "field_path": "specs.surface_requirements",
          "status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "evidence": [],
          "notes": "Не найдено на официальном сайте RoboCV."
        }
      ]
    }
  ]
}
```
CATALOG_RESULT_JSON_END