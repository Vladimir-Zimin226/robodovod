const LABELS = {
  manual_units_per_shift: 'Ручная производительность', control_headcount: 'Диспетчеры сейчас',
  control_monthly_gross: 'Зарплата диспетчера gross', technician_headcount: 'Техники сейчас',
  technician_monthly_gross: 'Зарплата техника gross', implementation_cost_total_gross: 'Внедрение и интеграция',
  annual_service_per_robot_gross: 'Сервис одного робота', warranty_years: 'Гарантия', average_power_w: 'Средняя мощность робота',
  shared_site_capital_gross: 'Общие разовые расходы площадки', shared_annual_cost_gross: 'Общие ежегодные расходы площадки',
  horizon_years: 'Горизонт оценки', discount_rate: 'Ставка дисконтирования', raas_monthly_per_robot_gross: 'Тариф RaaS',
  raas_contract_months: 'Срок договора RaaS', start_seconds_from_midnight: 'Начало смены', timezone: 'Часовой пояс',
  evaluation_date: 'Дата оценки', role_salaries_confirmed_as_monthly_gross: 'Подтверждение monthly gross',
  organizer_price_currency_rub_confirmed: 'Подтверждение валюты цены', initial_battery_in_robot_price_confirmed: 'Батарея в цене',
  battery_replacements_in_service_confirmed: 'Замена батареи в сервисе', raas_vendor_scope_confirmed: 'Состав RaaS',
  raas_infrastructure_owner: 'Плательщик инфраструктуры', primary_role_id: 'Основная роль',
  role_pool: 'Роли C03', capacity_run_id: 'Расчёт C11', capacity_technical_result: 'Доступный технический результат C11', catalog_position: 'Позиция каталога',
  organizer_price: 'Исходная цена каталога', input_revision: 'Версия входа', labour: 'Данные труда',
};
export function economicsFieldLabel(server) {
  if (server.startsWith('role_pool.')) return `зарплата роли C03 (${server.split('.')[1]})`;
  return LABELS[server] || server;
}
