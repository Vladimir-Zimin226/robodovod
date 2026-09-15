const PROFILES = {
  'pallet-amr': { robotType: 'pallet-amr', modelCode: 'RC-P1200', label: 'Паллетный AMR', process: 'Паллетные перемещения', color: [.08, .55, .42], radius: .61, maxLoadKg: 1200, drive: 'electric', cargoLabel: 'Паллета', speedFactor: 1, energyPerMeter: .12 },
  forklift: { robotType: 'forklift', modelCode: 'RC-F1500', label: 'Автономный погрузчик', process: 'Подъём и перевозка паллет', color: [.92, .55, .08], radius: .67, maxLoadKg: 1500, drive: 'traction', cargoLabel: 'Паллета на вилах', speedFactor: .82, energyPerMeter: .16 },
  'tow-amr': { robotType: 'tow-amr', modelCode: 'RC-T2000', label: 'Автономный тягач', process: 'Буксировка грузовых тележек', color: [.30, .48, .82], radius: .64, maxLoadKg: 2000, drive: 'traction', cargoLabel: 'Грузовая тележка', speedFactor: .90, energyPerMeter: .15 },
  'baggage-tug': { robotType: 'baggage-tug', modelCode: 'RC-B800', label: 'Багажный тягач', process: 'Сортировка и доставка багажа', color: [.10, .53, .72], radius: .64, maxLoadKg: 800, drive: 'traction', cargoLabel: 'Багажный контейнер', speedFactor: .90, energyPerMeter: .14 },
  'cargo-amr': { robotType: 'cargo-amr', modelCode: 'RC-C600', label: 'Грузовой AMR', process: 'Контейнерные перевозки терминала', color: [.24, .65, .84], radius: .59, maxLoadKg: 600, drive: 'electric', cargoLabel: 'Багаж', speedFactor: 1.08, energyPerMeter: .11 },
  'medical-cart': { robotType: 'medical-cart', modelCode: 'RC-M120', label: 'Медицинский шкаф-робот', process: 'Защищённая доставка расходников', color: [.12, .67, .53], radius: .43, maxLoadKg: 120, drive: 'quiet', cargoLabel: 'Расходники', speedFactor: .82, energyPerMeter: .075 },
  'service-robot': { robotType: 'service-robot', modelCode: 'RC-S40', label: 'Сервисный робот', process: 'Мелкие внутрибольничные доставки', color: [.38, .62, .72], radius: .44, maxLoadKg: 40, drive: 'quiet', cargoLabel: 'Закрытый контейнер', speedFactor: 1.05, energyPerMeter: .065 },
  'cleaning-robot': { robotType: 'cleaning-robot', modelCode: 'RC-CLN', label: 'Уборочный робот', process: 'Автономное покрытие зоны', color: [.10,.62,.52], radius: .55, maxLoadKg: 0, drive: 'electric', cargoLabel: 'Уборочный модуль', speedFactor: 1, energyPerMeter: .10 },
  'palletizer-cell': { robotType: 'palletizer-cell', modelCode: 'RC-PAL', label: 'Ячейка паллетизации', process: 'Стационарный цикл укладки', color: [.92,.48,.10], radius: .58, maxLoadKg: 21, drive: 'fixed', cargoLabel: 'Короба', speedFactor: 0, energyPerMeter: 0 }
};

export function robotProfile(type) {
  return { ...(PROFILES[type] || PROFILES['pallet-amr']) };
}

export function robotTypesForTemplate(template) {
  if (template === 'airport') return ['baggage-tug', 'cargo-amr'];
  if (template === 'hospital') return ['medical-cart', 'service-robot'];
  return ['pallet-amr', 'forklift', 'tow-amr'];
}

export const ROBOT_PROFILES = Object.freeze(PROFILES);
