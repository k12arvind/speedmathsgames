import { mulberry32, seededInt } from '@/lib/rng';

export type GeneratedQuestion = {
  topic: string;
  difficulty: 'easy'|'medium'|'hard';
  prompt: string;
  payload: {
    operands: any;
    correctAnswer: { kind: 'number'|'fraction'; value: string; dp?: number; validation?: string; requireLowestTerms?: boolean };
    meta?: Record<string, any>;
  };
};

type TopicConfig = any;

import { generateAddition } from './addition';
import { generateDecimals } from './decimals';
import { generateMultiplication } from './multiplication';
import { generateFractions } from './fractions';
import { generateBodmas } from './bodmas';

export function generateQuestion(topic: string, cfg: TopicConfig, seed: number, index: number): GeneratedQuestion {
  const rng = mulberry32(seed + index + 1);
  switch (topic) {
    case 'addition':
      return generateAddition(cfg?.rules, rng);
    case 'multiplication':
      return generateMultiplication(cfg?.rules, rng);
    case 'decimals':
      return generateDecimals(cfg?.rules, cfg?.validation, rng);
    case 'fractions':
      return generateFractions(cfg?.rules, rng);
    case 'bodmas':
      return generateBodmas(cfg?.rules, rng);
    default:
      // fallback: simple addition
      return generateAddition(cfg?.rules, rng);
  }
}
