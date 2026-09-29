export function cargoLabel(units, template) {
  if (template !== 'warehouse') return `${units} ${template === 'hospital' ? 'порций' : 'ед. груза'}`;
  const count = Number(units), ending = count % 10, teens = count % 100;
  const word = teens >= 11 && teens <= 14 ? 'паллет' : ending === 1 ? 'паллета' : ending >= 2 && ending <= 4 ? 'паллеты' : 'паллет';
  return `${units} ${word}`;
}
