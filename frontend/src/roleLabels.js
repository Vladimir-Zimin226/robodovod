export const ROLE_LABELS = Object.freeze({
  forklift_driver: 'Водитель погрузчика', loader: 'Грузчик', storekeeper: 'Кладовщик', picker: 'Отборщик',
  sorter: 'Сортировщик', packer: 'Упаковщик', cleaner: 'Уборщик', inventory_worker: 'Инвентаризатор',
  baggage_handler: 'Обработчик багажа', trolley_operator: 'Оператор тележек',
  special_equipment_driver: 'Водитель спецтехники', terminal_cleaner: 'Уборщик терминала',
  perron_cleaner: 'Уборщик перрона', runway_inspector: 'Инспектор ВПП', security_guard: 'Охранник',
  passenger_assistant: 'Помощник пассажиров', courier: 'Курьер', ramp_worker: 'Сотрудник перрона',
  ground_support_worker: 'Сотрудник наземного обслуживания', catering_worker: 'Сотрудник пищеблока',
  laundry_worker: 'Сотрудник прачечной', sanitary: 'Санитар', porter: 'Носильщик',
  lab_assistant: 'Лаборант', sterile_supply_worker: 'Сотрудник стерилизации',
  consumable_worker: 'Сотрудник расходных материалов', lab_result_courier: 'Курьер лаборатории',
  tech_support: 'Технический специалист', control_operator: 'Диспетчер роботов',
});

export function roleLabel(code) { return ROLE_LABELS[code] || code || 'Неизвестная роль'; }
