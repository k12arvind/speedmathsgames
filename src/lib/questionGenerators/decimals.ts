import { mulberry32, seededInt } from '@/lib/rng';

type Rules = {
  operands?: { dp?: number, range?: [number, number] }[];
  operations?: ('+'|'-'|'×'|'÷')[];
};

type Validation = { mode?: 'exact'|'tolerance', dp?: number, tolerance?: number };

export function generateDecimals(rules: Rules = {}, validation: Validation = { mode:'exact', dp: 2 }, rng: () => number = Math.random) {
  const ops = rules.operands ?? [
    { dp: 1, range: [0.1, 99.9] },
    { dp: 2, range: [0.01, 99.99] }
  ];
  const opers = rules.operations ?? ['+'];
  const op = opers[0];

  const a = seededInt(rng, 1, 999) / 10; // 1dp approx
  const b = seededInt(rng, 1, 9999) / 100; // 2dp approx

  let correctNum = 0;
  if (op === '+') correctNum = a + b;
  if (op === '-') correctNum = a - b;
  if (op === '×') correctNum = a * b;
  if (op === '÷') correctNum = b !== 0 ? a / b : a;

  const dp = validation.dp ?? 2;
  const prompt = `${a.toFixed(1)} ${op} ${b.toFixed(2)} = ? (exact to ${dp} dp)`;
  const correct = dp >= 0 ? correctNum.toFixed(dp) : correctNum.toString();

  return {
    topic: 'decimals',
    difficulty: 'medium' as const,
    prompt,
    payload: {
      operands: [a, op, b],
      correctAnswer: { kind: 'number' as const, value: correct, dp, validation: validation.mode || 'exact' }
    }
  };
}
