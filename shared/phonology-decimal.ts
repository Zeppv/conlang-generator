/** Decimal arithmetic at Python decimal's default 28-digit precision. */
const power = (n: number) => 10n ** BigInt(n);
const nearest = (n: bigint, d: bigint) => {
  const q = n / d, r = n % d;
  return q + (r * 2n > d || (r * 2n === d && q % 2n !== 0n) ? 1n : 0n);
};
export class Decimal {
  coefficient: bigint;
  exponent: number;
  constructor(coefficient: bigint, exponent = 0, round = false) {
    this.coefficient = coefficient; this.exponent = exponent;
    if (round && coefficient !== 0n) {
      const extra = coefficient.toString().length - 28;
      if (extra > 0) { this.coefficient = nearest(coefficient, power(extra)); this.exponent += extra; }
    }
  }
  static from(value: number | string) {
    const [mantissa, exponent = '0'] = String(value).toLowerCase().split('e');
    const parts = mantissa.split('.');
    return new Decimal(BigInt(parts.join('')), Number(exponent) - (parts[1]?.length ?? 0));
  }
  add(other: Decimal) {
    const exponent = Math.min(this.exponent, other.exponent);
    return new Decimal(this.coefficient * power(this.exponent - exponent) + other.coefficient * power(other.exponent - exponent), exponent, true);
  }
  multiply(other: Decimal) { return new Decimal(this.coefficient * other.coefficient, this.exponent + other.exponent, true); }
  divide(other: Decimal) {
    let order = this.coefficient.toString().length - other.coefficient.toString().length;
    if (this.coefficient * power(Math.max(0, -order)) < other.coefficient * power(Math.max(0, order))) order--;
    const digits = 27 - order;
    const n = this.coefficient * power(Math.max(0, digits));
    const d = other.coefficient * power(Math.max(0, -digits));
    return new Decimal(nearest(n, d), this.exponent - other.exponent - digits, true);
  }
  less(other: Decimal) {
    const exponent = Math.min(this.exponent, other.exponent);
    return this.coefficient * power(this.exponent - exponent) < other.coefficient * power(other.exponent - exponent);
  }
  number() { return Number(`${this.coefficient}e${this.exponent}`); }
}

/** Match Python round(x, 8), including ties, from the exact binary64 input. */
export function round8(value: number): number {
  const bytes = new DataView(new ArrayBuffer(8)); bytes.setFloat64(0, Math.abs(value));
  const bits = bytes.getBigUint64(0), exp = Number((bits >> 52n) & 2047n);
  const mantissa = (bits & ((1n << 52n) - 1n)) + (exp ? 1n << 52n : 0n);
  const exponent = (exp || 1) - 1023 - 52;
  const numerator = mantissa * 100000000n * (exponent >= 0 ? 1n << BigInt(exponent) : 1n);
  const denominator = exponent < 0 ? 1n << BigInt(-exponent) : 1n;
  return Math.sign(value) * Number(nearest(numerator, denominator)) / 1e8;
}
