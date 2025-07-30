import { seededInt } from '@/lib/rng';

type Rules = {
  operands?: { digits?: number, range?: [number, number] }[];
  carryBias?: 'forceCarry'|'avoidCarry'|'mixed';
};

export function generateAddition(rules: Rules = {}, rng: () => number = Math.random) {
  const ops = rules.operands ?? [
    { digits: 3, range: [100, 999] },
    { digits: 4, range: [1000, 9999] }
  ];
  const [o1, o2] = ops;
  const a = seededInt(rng, o1.range ? o1.range[0] : 100, o1.range ? o1.range[1] : 999);
  const b = seededInt(rng, o2.range ? o2.range[0] : 1000, o2.range ? o2.range[1] : 9999);

  let A = a, B = b;
  const bias = rules.carryBias ?? 'mixed';

  // enforce/avoid carry on ones place as a simple example
  const onesA = A % 10, onesB = B % 10;
  if (bias === 'forceCarry' && (onesA + onesB) < 10) {
    // tweak B's ones digit to force carry
    const delta = 10 - (onesA + onesB);
    B += delta;
  } else if (bias === 'avoidCarry' && (onesA + onesB) >= 10) {
    // tweak B's ones digit to avoid carry
    const delta = (onesA + onesB) - 9;
    B -= delta;
  }

  const prompt = `${A} + ${B} = ?`;
  const correct = (A + B).toString();
  return { topic: 'addition', difficulty: 'medium', prompt, payload: { operands:[A,B], correctAnswer: { kind: 'number', value: correct, validation: 'exact' } } };
}
