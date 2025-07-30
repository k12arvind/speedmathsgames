import { seededInt } from '@/lib/rng';

type Rules = {
  difficulty?: 'easy'|'medium'|'hard';
  operations?: string[];
  brackets?: boolean;
};

export function generateBodmas(rules: Rules = {}, rng: () => number = Math.random) {
  const difficulty = rules.difficulty ?? 'medium';
  const useBrackets = rules.brackets ?? true;
  
  let range: [number, number];
  switch (difficulty) {
    case 'easy':
      range = [1, 20];
      break;
    case 'medium':
      range = [1, 50];
      break;
    case 'hard':
      range = [1, 100];
      break;
    default:
      range = [1, 50];
  }

  const a = seededInt(rng, range[0], range[1]);
  const b = seededInt(rng, range[0], range[1]);
  const c = seededInt(rng, range[0], range[1]);
  const d = seededInt(rng, 1, 20);

  let prompt: string;
  let result: number;

  if (useBrackets) {
    // Various BODMAS patterns
    const patterns = [
      () => {
        const res = a + (b * c) - d;
        return [`${a} + (${b} × ${c}) - ${d} = ?`, res];
      },
      () => {
        const res = (a + b) * c - d;
        return [`(${a} + ${b}) × ${c} - ${d} = ?`, res];
      },
      () => {
        const res = a * (b + c) / 2;
        return [`${a} × (${b} + ${c}) ÷ 2 = ?`, res];
      }
    ];
    
    const selected = patterns[Math.floor(rng() * patterns.length)]();
    prompt = selected[0] as string;
    result = selected[1] as number;
  } else {
    // Simple order of operations without brackets
    result = a + b * c - d;
    prompt = `${a} + ${b} × ${c} - ${d} = ?`;
  }

  return { 
    topic: 'bodmas', 
    difficulty, 
    prompt, 
    payload: { 
      operands: [a, b, c, d], 
      correctAnswer: { 
        kind: 'number', 
        value: result.toString(), 
        validation: 'exact' 
      },
      meta: { 
        requiresOrderOfOperations: true,
        hasBrackets: useBrackets 
      }
    } 
  };
}
