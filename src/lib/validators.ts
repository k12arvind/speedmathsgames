import { z } from 'zod';

export const StartGameSchema = z.object({
  presetId: z.string().uuid().optional(),
  timeLimitSec: z.number().int().min(30).max(3600).optional(),
  selectedTopics: z.array(z.enum(['addition','subtraction','multiplication','division','fractions','decimals','percentages','bodmas'])).optional(),
  difficulty: z.enum(['easy','medium','hard']).optional(),
});

export const AnswerSchema = z.object({
  sessionId: z.string().uuid(),
  questionId: z.string().uuid(),
  userAnswer: z.string(),
  timeTakenMs: z.number().int().min(100).max(60000),
});

export const SkipSchema = z.object({
  sessionId: z.string().uuid(),
  questionId: z.string().uuid(),
  timeTakenMs: z.number().int().min(100).max(60000),
});
