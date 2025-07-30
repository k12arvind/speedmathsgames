import { seededInt } from '@/lib/rng';

type Rules = {
  operands?: { range?: [number, number] }[];
  difficulty?: 'easy'|'medium'|'hard';
};

export function generateMultiplication(rules: Rules = {}, rng: () => number = Math.random) {
  const difficulty = rules.difficulty ?? 'medium';
  
  let aRange: [number, number], bRange: [number, number];
  
  switch (difficulty) {
    case 'easy':
      aRange = [2, 12];
      bRange = [2, 12];
      break;
    case 'medium':
      aRange = [10, 99];
      bRange = [10, 99];
      break;
    case 'hard':
      aRange = [100, 999];
      bRange = [10, 99];
      break;
    default:
      aRange = [10, 99];
      bRange = [10, 99];
  }

  if (rules.operands) {
    aRange = rules.operands[0]?.range ?? aRange;
    bRange = rules.operands[1]?.range ?? bRange;
  }

  const a = seededInt(rng, aRange[0], aRange[1]);
  const b = seededInt(rng, bRange[0], bRange[1]);
  
  const prompt = `${a} × ${b} = ?`;
  const correct = (a * b).toString();
  
  return { 
    topic: 'multiplication', 
    difficulty, 
    prompt, 
    payload: { 
      operands: [a, b], 
      correctAnswer: { kind: 'number', value: correct, validation: 'exact' } 
    } 
  };
}
