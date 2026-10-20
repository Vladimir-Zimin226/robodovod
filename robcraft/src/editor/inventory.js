export class EditorInventory {
  constructor(slots = Array(9).fill(null), active = 0) {
    if (!Array.isArray(slots) || slots.length !== 9 || slots.some(item => item !== null && typeof item !== 'string')) throw new TypeError('Хотбар должен содержать 9 слотов');
    this.slots = [...slots];
    this.active = active === null ? null : Number(active);
    this.explicitSlot = false;
    if (this.active !== null && (!Number.isInteger(this.active) || this.active < 0 || this.active > 8)) throw new TypeError('Неверный активный слот');
  }

  get held() { return this.active === null ? null : this.slots[this.active]; }
  select(index) {
    if (index !== null && (!Number.isInteger(index) || index < 0 || index > 8)) return false;
    this.active = index;
    this.explicitSlot = index !== null;
    return true;
  }
  assign(kind) {
    if (typeof kind !== 'string' || !kind) return false;
    let index = this.explicitSlot ? this.active : this.slots.indexOf(null);
    if (index === null || index < 0) return false;
    this.slots[index] = kind;
    this.active = index;
    this.explicitSlot = false;
    return true;
  }
  cycle(direction) {
    this.active = ((this.active ?? (direction > 0 ? -1 : 0)) + direction + 9) % 9;
    return this.active;
  }
  toJSON() { return { slots: [...this.slots], active: this.active }; }
}
