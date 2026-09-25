const normalize = (value) => String(value ?? '').toLocaleLowerCase('ru-RU')
  .replace(/ё/g, 'е').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();

export function searchEconomicsEntries(entries, query) {
  const terms = normalize(query).split(/\s+/).filter(Boolean);
  if (!terms.length) return entries;
  return entries.filter((entry) => {
    const text = normalize([
      entry.title, entry.notation, ...entry.synonyms,
      ...entry.formula_ids, ...entry.inputs.map((input) => input.label),
    ].join(' '));
    return terms.every((term) => text.includes(term));
  });
}
