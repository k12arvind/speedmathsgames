export function normalizeNumberString(s: string): string {
  return s.trim().replace(/\s+/g, '');
}

export function compareExactIntegers(userAns: string, correct: string): boolean {
  return normalizeNumberString(userAns) === normalizeNumberString(correct);
}

export function compareExactDp(userAns: string, correct: string, dp: number): boolean {
  // Compare after formatting both to dp decimals.
  const ua = Number(userAns);
  if (!Number.isFinite(ua)) return false;
  const uaStr = ua.toFixed(dp);
  return uaStr === correct;
}

function gcd(a: number, b: number): number {
  return b === 0 ? Math.abs(a) : gcd(b, a % b);
}

function parseFraction(s: string): { num: number, den: number } | null {
  const trimmed = s.trim();
  
  // Check if it's a whole number
  if (!/\//.test(trimmed)) {
    const num = parseInt(trimmed, 10);
    if (isNaN(num)) return null;
    return { num, den: 1 };
  }
  
  // Parse fraction
  const parts = trimmed.split('/');
  if (parts.length !== 2) return null;
  
  const num = parseInt(parts[0].trim(), 10);
  const den = parseInt(parts[1].trim(), 10);
  
  if (isNaN(num) || isNaN(den) || den === 0) return null;
  return { num, den };
}

function reduceFraction(num: number, den: number): { num: number, den: number } {
  const g = gcd(num, den);
  return { num: num / g, den: den / g };
}

export function compareFractions(userAns: string, correct: string, requireLowestTerms: boolean = true): boolean {
  const userFrac = parseFraction(userAns);
  const correctFrac = parseFraction(correct);
  
  if (!userFrac || !correctFrac) return false;
  
  if (requireLowestTerms) {
    const userReduced = reduceFraction(userFrac.num, userFrac.den);
    const correctReduced = reduceFraction(correctFrac.num, correctFrac.den);
    return userReduced.num === correctReduced.num && userReduced.den === correctReduced.den;
  } else {
    // Compare as equivalent fractions
    return userFrac.num * correctFrac.den === correctFrac.num * userFrac.den;
  }
}
