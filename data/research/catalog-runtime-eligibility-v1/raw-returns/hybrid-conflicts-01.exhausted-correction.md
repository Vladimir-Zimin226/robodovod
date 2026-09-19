CATALOG_RESULT_JSON_BEGIN
```json
{
  "schema_version": "catalog-official-source-research-return-v1",
  "batch_id": "hybrid-conflicts-01",
  "research_completed_at": "2026-09-18T07:06:32+09:00",
  "results": [
    {
      "organizer_id": "0ece582a-084c-4a8b-99f4-576f0e01b7c8",
      "model": "SmartCube",
      "identity_status": "EXACT_MODEL_MATCH",
      "field_results": [
        {
          "field_path": "specs.max_speed",
          "evidence_status": "CONFLICT",
          "normalized_value": null,
          "normalized_unit": "m/s",
          "confidence": 0.5,
          "evidence": [
            {
              "source_title": "CR-02 — Новое поколение мобильного робота для кубической системы хранения",
              "source_type": "Web Page",
              "source_locator": "Страница «CR-02»",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Максимальная скорость движения составляет 2,1 м/с"
            },
            {
              "source_title": "CR-02 — Новое поколение мобильного робота для кубической системы хранения",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Линейная скорость 2,7 м/с"
            }
          ],
          "notes": ""
        }
      ]
    },
    {
      "organizer_id": "2ffc706d-fe43-4c2b-baad-a624a95ad3ce",
      "model": "Робот-штабелёр RoboCV",
      "identity_status": "EXACT_MODEL_MATCH",
      "field_results": [
        {
          "field_path": "capacity.exchange_time_s",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Спецификация робота-штабелёра RoboCV не содержит информации о времени замены аккумулятора."
        },
        {
          "field_path": "capacity.units_per_trip",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Спецификация робота-штабелёра RoboCV не содержит информацию о количестве перевозимых грузов за одну поездку."
        },
        {
          "field_path": "specs.aisle_requirements",
          "evidence_status": "CONFLICT",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.5,
          "evidence": [
            {
              "source_title": "Робот-штабелёр",
              "source_type": "Web Page",
              "source_locator": "Объезд препятствий",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Для объезда препятствий необходим проезд шириной не менее 1,6 м"
            },
            {
              "source_title": "Спецификация робота-штабелёра RoboCV",
              "source_type": "PDF",
              "source_locator": "Мин. ширина проезда для набора полной скорости",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Мин. ширина проезда для набора полной скорости 1800мм"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.autonomy",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": "24/7",
          "normalized_unit": null,
          "confidence": 0.9,
          "evidence": [
            {
              "source_title": "Робот-штабелёр",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Режим работы: 24/7"
            },
            {
              "source_title": "Спецификация робота-штабелёра RoboCV",
              "source_type": "PDF",
              "source_locator": "Время работы",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Время работы 24/7"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.connectivity",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "В спецификации робота-штабелёра RoboCV не указана информация о способах связи."
        },
        {
          "field_path": "specs.max_speed",
          "evidence_status": "CONFLICT",
          "normalized_value": null,
          "normalized_unit": "m/s",
          "confidence": 0.5,
          "evidence": [
            {
              "source_title": "Робот-штабелёр",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Максимальная скорость, м/с: 2"
            },
            {
              "source_title": "Спецификация робота-штабелёра RoboCV",
              "source_type": "PDF",
              "source_locator": "Макс. скорость",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Скорость 1,67 м/с"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.min_aisle_width",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": 2.9,
          "normalized_unit": "m",
          "confidence": 0.9,
          "evidence": [
            {
              "source_title": "Робот-штабелёр",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Минимальная ширина проезда для разворота, м: 2,9"
            },
            {
              "source_title": "Спецификация робота-штабелёра RoboCV",
              "source_type": "PDF",
              "source_locator": "Мин. ширина проезда для разворота",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Мин. ширина проезда для разворота 2900мм"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.operating_conditions",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "В открытых источниках нет информации об условиях эксплуатации робота-штабелёра RoboCV."
        },
        {
          "field_path": "specs.service_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "В открытых источниках нет информации о требованиях к техническому обслуживанию робота-штабелёра RoboCV."
        },
        {
          "field_path": "specs.surface_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "В открытых источниках нет информации о требованиях к поверхности пола для робота-штабелёра RoboCV."
        }
      ]
    },
    {
      "organizer_id": "5760e938-9a43-45a7-b8e8-f4f2e6383930",
      "model": "Ronavi H1500 (грузоподъемность до 1500 кг)",
      "identity_status": "EXACT_MODEL_MATCH",
      "field_results": [
        {
          "field_path": "capacity.exchange_time_s",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": 36000,
          "normalized_unit": "s",
          "confidence": 0.9,
          "evidence": [
            {
              "source_title": "Ronavi H1500",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Время автономной работы (c 80% до 20%): до 10 часов"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "capacity.units_per_trip",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Спецификация Ronavi H1500 не содержит информации о количестве грузов за одну поездку."
        },
        {
          "field_path": "specs.min_aisle_width",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": 0.75,
          "normalized_unit": "m",
          "confidence": 0.9,
          "evidence": [
            {
              "source_title": "Ronavi H1500",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Минимальная ширина проезда;750 мм"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.surface_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "В открытых источниках нет информации о требованиях к поверхности для Ronavi H1500."
        }
      ]
    },
    {
      "organizer_id": "89ffd69f-f07b-4bf2-8023-1fd765a2b6ff",
      "model": "AMR 100 (грузоподъемность до 100 кг)",
      "identity_status": "EXACT_MODEL_MATCH",
      "field_results": [
        {
          "field_path": "capacity.exchange_time_s",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Спецификация AMR100 не содержит информации о времени подзарядки или замены аккумулятора."
        },
        {
          "field_path": "capacity.units_per_trip",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "В открытых источниках не указано, сколько грузов AMR100 может перевезти за один рейс."
        },
        {
          "field_path": "specs.autonomy",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": 72000,
          "normalized_unit": "s",
          "confidence": 0.9,
          "evidence": [
            {
              "source_title": "AMR100 — Автономный мобильный робот от МОРОС",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Время работы — 20 часов (при средних нагрузках)"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.charging_requirements",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": "Автоматическая док-станция / ручная зарядка",
          "normalized_unit": null,
          "confidence": 0.9,
          "evidence": [
            {
              "source_title": "AMR100 — Автономный мобильный робот от МОРОС",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Способ зарядки — Автоматическая док-станция / ручная зарядка"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.connectivity",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Не найдено данных о средствах связи AMR100."
        },
        {
          "field_path": "specs.dimensions",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": "600×400×220",
          "normalized_unit": "mm",
          "confidence": 0.9,
          "evidence": [
            {
              "source_title": "AMR100 — Автономный мобильный робот от МОРОС",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Габаритные размеры (Д×Ш×В) — 600 × 400 × 220 мм"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.integrations",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": "Интеграция с конвейерами и манипуляторами",
          "normalized_unit": null,
          "confidence": 0.8,
          "evidence": [
            {
              "source_title": "AMR100 — Автономный мобильный робот от МОРОС",
              "source_type": "Web Page",
              "source_locator": "Ключевые функциональные возможности",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Возможность интеграции с конвейерами, подъемниками, манипуляторами."
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.max_speed",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": 3.0,
          "normalized_unit": "m/s",
          "confidence": 0.9,
          "evidence": [
            {
              "source_title": "AMR100 — Автономный мобильный робот от МОРОС",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Скорость перемещения — 3 м/с"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.min_aisle_width",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Минимальная ширина прохода не указана для AMR100."
        },
        {
          "field_path": "specs.navigation",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "В открытых источниках не найдено подробностей о системе навигации AMR100."
        },
        {
          "field_path": "specs.operating_conditions",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Условия эксплуатации AMR100 не указаны."
        },
        {
          "field_path": "specs.positioning_accuracy",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": 10,
          "normalized_unit": "mm",
          "confidence": 0.9,
          "evidence": [
            {
              "source_title": "AMR100 — Автономный мобильный робот от МОРОС",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Точность позиционирования — ±10 мм"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.service_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Сведения о требованиях к обслуживанию AMR100 не найдены."
        },
        {
          "field_path": "specs.surface_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Требования к поверхности для AMR100 не указаны."
        }
      ]
    },
    {
      "organizer_id": "b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1",
      "model": "Робот-тягач RoboCV",
      "identity_status": "EXACT_MODEL_MATCH",
      "field_results": [
        {
          "field_path": "capacity.exchange_time_s",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Информация о времени работы или зарядки робота-тягача RoboCV отсутствует."
        },
        {
          "field_path": "capacity.units_per_trip",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "В открытых источниках не указано, сколько тележек может буксировать робот-тягач RoboCV за одну поездку."
        },
        {
          "field_path": "specs.autonomy",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": "24/7",
          "normalized_unit": null,
          "confidence": 0.9,
          "evidence": [
            {
              "source_title": "Робот-тягач",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Режим работы: 24/7"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.max_speed",
          "evidence_status": "CONFLICT",
          "normalized_value": null,
          "normalized_unit": "m/s",
          "confidence": 0.5,
          "evidence": [
            {
              "source_title": "Робот-тягач",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Максимальная скорость, м/с: 2,2"
            },
            {
              "source_title": "Спецификация робота-тягача RoboCV",
              "source_type": "PDF",
              "source_locator": "Макс. скорость без груза",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Макс. скорость без груза 12 км/ч"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.min_aisle_width",
          "evidence_status": "VERIFIED_OFFICIAL",
          "normalized_value": 2.9,
          "normalized_unit": "m",
          "confidence": 0.9,
          "evidence": [
            {
              "source_title": "Робот-тягач",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Минимальная ширина проезда для разворота, м: 2,9"
            },
            {
              "source_title": "Спецификация робота-тягача RoboCV",
              "source_type": "PDF",
              "source_locator": "Мин. ширина проезда для разворота",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Мин. ширина проезда для разворота 2900мм"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.operating_conditions",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Информация об условиях эксплуатации робота-тягача RoboCV не найдена."
        },
        {
          "field_path": "specs.payload",
          "evidence_status": "CONFLICT",
          "normalized_value": null,
          "normalized_unit": "kg",
          "confidence": 0.5,
          "evidence": [
            {
              "source_title": "Робот-тягач",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Грузоподъемность, кг: до 5000"
            },
            {
              "source_title": "Спецификация робота-тягача RoboCV",
              "source_type": "PDF",
              "source_locator": "Сила тяги",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Сила тяги 4000кг"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.positioning_accuracy",
          "evidence_status": "CONFLICT",
          "normalized_value": null,
          "normalized_unit": "cm",
          "confidence": 0.5,
          "evidence": [
            {
              "source_title": "Робот-тягач",
              "source_type": "Web Page",
              "source_locator": "Технические характеристики",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Точность навигации, см: 5"
            },
            {
              "source_title": "Спецификация робота-тягача RoboCV",
              "source_type": "PDF",
              "source_locator": "Точность позиционирования",
              "publication_or_update_date": null,
              "accessed_at": "2026-09-18",
              "raw_value": "Точность позиционирования 70мм"
            }
          ],
          "notes": ""
        },
        {
          "field_path": "specs.service_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Требования к обслуживанию робота-тягача RoboCV не найдены."
        },
        {
          "field_path": "specs.surface_requirements",
          "evidence_status": "NOT_FOUND",
          "normalized_value": null,
          "normalized_unit": null,
          "confidence": 0.0,
          "evidence": [],
          "notes": "Требования к поверхности для робота-тягача RoboCV не найдены."
        }
      ]
    }
  ]
}
```
CATALOG_RESULT_JSON_END