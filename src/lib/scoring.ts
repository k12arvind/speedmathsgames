export type ScoringConfig = {
  base: number;
  timePenaltyPerSec: number;
  streakBonus: number;
};

export function computeScoreDelta(secondsTaken: number, streak: number, cfg: ScoringConfig): number {
  const penalty = Math.floor(secondsTaken * cfg.timePenaltyPerSec);
  const bonus = streak > 0 ? cfg.streakBonus : 0;
  return Math.max(0, cfg.base - penalty + bonus);
}
