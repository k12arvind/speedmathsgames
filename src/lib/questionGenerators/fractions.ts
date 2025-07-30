import { seededInt } from '@/lib/rng';

function gcd(x: number, y: number): number { 
  return y === 0 ? Math.abs(x) : gcd(y, x % y); 
}

type Rules = {
  operation?: 'add'|'subtract'|'multiply'|'divide';
  difficulty?: 'easy'|'medium'|'hard';
  denominators?: number[];
};

export function generateFractions(rules: Rules = {}, rng: () => number = Math.random) {
  const operation = rules.operation ?? 'add';
  const difficulty = rules.difficulty ?? 'medium';
  
  let denominators: number[];
  switch (difficulty) {
    case 'easy':
      denominators = [4, 5, 6, 8, 10, 12];
      break;
    case 'medium':
      denominators = [4, 5, 6, 8, 10, 12, 16, 20, 25];
      break;
    case 'hard':
      denominators = [4, 5, 6, 8, 10, 12, 16, 20, 25, 40, 50, 80, 100];
      break;
    default:
      denominators = [4, 5, 6, 8, 10, 12, 16, 20, 25];
  }
  
  if (rules.denominators) {
    denominators = rules.denominators;
  }

  const d1 = denominators[Math.floor(rng() * denominators.length)];
  const d2 = denominators[Math.floor(rng() * denominators.length)];
  const n1 = seededInt(rng, 1, d1 - 1);
  const n2 = seededInt(rng, 1, d2 - 1);

  let num: number, den: number, operatorSymbol: string;
  
  switch (operation) {
    case 'add':
      num = n1 * d2 + n2 * d1;
      den = d1 * d2;
      operatorSymbol = '+';
      break;
    case 'subtract':
      num = n1 * d2 - n2 * d1;
      den = d1 * d2;
      operatorSymbol = '−';
      break;
    case 'multiply':
      num = n1 * n2;
      den = d1 * d2;
      operatorSymbol = '×';
      break;
    case 'divide':
      num = n1 * d2;
      den = d1 * n2;
      operatorSymbol = '÷';
      break;
    default:
      num = n1 * d2 + n2 * d1;
      den = d1 * d2;
      operatorSymbol = '+';
  }

  const g = gcd(Math.abs(num), Math.abs(den));
  const cn = Math.floor(num / g);
  const cd = Math.floor(den / g);
  
  const prompt = `(${n1}/${d1}) ${operatorSymbol} (${n2}/${d2}) = ? (lowest terms)`;
  const correct = cd === 1 ? cn.toString() : `${cn}/${cd}`;
  
  return { 
    topic: 'fractions', 
    difficulty: difficulty as 'easy'|'medium'|'hard', 
    prompt, 
    payload: { 
      operands: [n1, d1, n2, d2], 
      correctAnswer: { 
        kind: 'fraction' as const, 
        value: correct, 
        requireLowestTerms: true,
        validation: 'fraction' 
      } 
    } 
  };
}
