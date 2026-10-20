export const DEFAULT_WHAT_IF = Object.freeze({
  pricePercent: 0, laborPercent: 0, speedPercent: 0, servicePercent: 0,
  volumePercent: 0, discountPoints: 0, laborSharePercent: null,
  integrationPercent: 0, rentPercent: 0, reservePercent: null, horizonYears: null,
});

export function whatIfChanged(controls) {
  return Object.keys(DEFAULT_WHAT_IF).some((key) => controls[key] !== DEFAULT_WHAT_IF[key]);
}

export function scaleDecimal(value, percent, places = 6) {
  if (value == null || percent === 0) return value;
  const source = String(value);
  if (!/^\d+(\.\d+)?$/.test(source) || !Number.isInteger(percent) || percent <= -100)
    throw new RangeError('Invalid what-if decimal or percentage');
  const [whole, fraction = ''] = source.split('.');
  const digits = Math.max(places, fraction.length);
  const base = BigInt(whole + fraction.padEnd(digits, '0'));
  const scaled = (base * BigInt(100 + percent) + 50n) / 100n;
  const padded = scaled.toString().padStart(digits + 1, '0');
  const integer = padded.slice(0, -digits);
  const decimals = padded.slice(-digits).replace(/0+$/, '');
  return decimals ? `${integer}.${decimals}` : integer;
}

function adjustedRate(simulation, percent) {
  if (!simulation || !percent) return;
  if (simulation.speed_loaded_mps != null)
    simulation.speed_loaded_mps = scaleDecimal(simulation.speed_loaded_mps, percent);
  if (simulation.speed_empty_mps != null)
    simulation.speed_empty_mps = scaleDecimal(simulation.speed_empty_mps, percent);
}

export function buildWhatIfInput(input, report, controls) {
  const next = structuredClone(input);
  const general = next.general;
  general.annual_service_share = scaleDecimal(general.annual_service_share, controls.servicePercent);
  general.integration_share = scaleDecimal(general.integration_share, controls.integrationPercent);
  general.discount_rate = String(Math.max(0, Math.min(1,
    Number(general.discount_rate) + controls.discountPoints / 100)));
  if (controls.laborSharePercent != null) general.realizable_labor_share = String(controls.laborSharePercent / 100);
  if (controls.reservePercent != null) general.fleet_reserve_share = String(controls.reservePercent / 100);
  if (controls.horizonYears != null) general.horizon_years = controls.horizonYears;
  if (report.kind) {
    for (const role of next.roles) {
      role.monthly_employer_cost_rub = scaleDecimal(role.monthly_employer_cost_rub, controls.laborPercent, 2);
      if (controls.laborSharePercent != null) role.realizable_labor_share = String(controls.laborSharePercent / 100);
      for (const work of role.works) {
        work.daily_volume = scaleDecimal(work.daily_volume, controls.volumePercent);
        work.robot_units_per_hour = scaleDecimal(work.robot_units_per_hour, controls.speedPercent);
        work.scenario_purchase_price_rub = scaleDecimal(work.scenario_purchase_price_rub, controls.pricePercent, 2);
        if (work.raas_mode === 'PERCENT')
          work.raas_percent_monthly = scaleDecimal(work.raas_percent_monthly, controls.rentPercent);
        else work.scenario_raas_monthly_rub = scaleDecimal(work.scenario_raas_monthly_rub, controls.rentPercent, 2);
        adjustedRate(work.simulation, controls.speedPercent);
        if (controls.speedPercent) work.rate_source = 'USER';
        if (controls.pricePercent && work.scenario_purchase_price_rub != null) work.price_source = 'USER';
      }
    }
  } else {
    for (const role of next.roles) {
      role.monthly_employer_cost_rub = scaleDecimal(role.monthly_employer_cost_rub, controls.laborPercent, 2);
      role.daily_volume = scaleDecimal(role.daily_volume, controls.volumePercent);
      if (controls.laborSharePercent != null) role.realizable_labor_share = String(controls.laborSharePercent / 100);
      adjustedRate(role.simulation, controls.speedPercent);
      const resultRole = report.roles.find((item) => item.role_code === role.role_code);
      const selected = resultRole?.candidates.find((item) => item.position_id === resultRole.selected_position_id);
      if (!selected) continue;
      let override = next.overrides.find((item) => item.role_code === role.role_code
        && item.position_id === selected.position_id);
      if (!override) {
        override = { role_code: role.role_code, position_id: selected.position_id };
        next.overrides.push(override);
      }
      if (controls.pricePercent && selected.price_rub != null) {
        override.price_rub = scaleDecimal(selected.price_rub, controls.pricePercent, 2);
        override.omit_purchase_price = false;
      }
      if (controls.speedPercent && selected.robot_units_per_hour != null)
        override.units_per_hour = scaleDecimal(selected.robot_units_per_hour, controls.speedPercent);
      if (controls.rentPercent) {
        if (selected.raas_mode === 'PERCENT' && selected.raas_percent_monthly != null)
          override.raas_percent_monthly = scaleDecimal(selected.raas_percent_monthly, controls.rentPercent);
        else if (selected.raas_mode === 'FIXED' && selected.raas_monthly_rub != null)
          override.raas_monthly_rub = scaleDecimal(selected.raas_monthly_rub, controls.rentPercent, 2);
        override.omit_raas_tariff = false;
      }
    }
  }
  return next;
}

export function whatIfSummary(report) {
  if (report.kind) {
    const total = report.base_total;
    return { fleet: total.fleet, fte: total.fte_equivalent,
      purchase: { capex: total.purchase.capex_rub, npv: total.purchase.npv_rub,
        roi: total.purchase.roi_percent, payback: total.purchase.payback_years },
      raas: { capex: total.raas.capex_rub, npv: total.raas.npv_rub,
        roi: total.raas.roi_percent, roiStatus: total.raas.roi_status },
      simulations: report.roles.flatMap((role) => role.works.map((work) => work.simulation).filter(Boolean)) };
  }
  const total = report.portfolio;
  const selected = report.roles.flatMap((role) => role.candidates.filter((candidate) =>
    candidate.position_id === role.selected_position_id));
  return { fleet: total.selected_robot_allocations, fte: total.fte_equivalent,
    purchase: { capex: total.capex_rub, npv: total.npv_rub,
      roi: total.purchase_roi_percent, payback: total.purchase_payback_years },
    raas: { capex: total.raas_capex_rub, npv: total.raas_npv_rub,
      roi: total.raas_roi_percent, roiStatus: total.raas_capex_rub == null ? 'NEEDS_INPUT'
        : Number(total.raas_capex_rub) === 0 ? 'N/A' : 'DEFINED' },
    simulations: selected.map((candidate) => candidate.simulation).filter(Boolean) };
}
