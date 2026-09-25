// Presentation only: keep Decimal strings untouched in snapshots and requests.
export function formatDecimal(value, places = 2, minPlaces = 0) {
  if (value == null) return null;
  const match = String(value).match(/^(-?)(\d+)(?:\.(\d+))?$/);
  if (!match) return null;
  const [, sign, whole, fraction = ''] = match;
  const scale = 10n ** BigInt(places);
  const kept = fraction.slice(0, places).padEnd(places, '0');
  let scaled = BigInt(whole) * scale + BigInt(kept || '0');
  if (fraction.length > places && fraction[places] >= '5') scaled += 1n;
  const integer = String(scaled / scale).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const rest = places ? String(scaled % scale).padStart(places, '0').replace(/0+$/, '').padEnd(minPlaces, '0') : '';
  return `${sign === '-' && scaled !== 0n ? '-' : ''}${integer}${rest ? `,${rest}` : ''}`;
}

export function formatPercent(value) {
  if (value == null) return '—';
  const source = String(value);
  const match = source.match(/^(-?)(\d+)(?:\.(\d+))?$/);
  if (!match) return '—';
  const [, sign, whole, fraction = ''] = match;
  const tail = fraction.slice(2);
  const scaled = `${sign}${BigInt(whole) * 100n + BigInt(fraction.slice(0, 2).padEnd(2, '0'))}${tail ? `.${tail}` : ''}`;
  const rendered = formatDecimal(scaled);
  return rendered == null ? '—' : `${rendered} %`;
}

export function formatFleet(value) {
  const rendered = formatDecimal(value, 0);
  return rendered == null ? '—' : `${rendered} роботов`;
}
