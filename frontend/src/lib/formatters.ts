export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return 'N/A';
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value}`;
}

export function formatEmployeeCount(count: number | null | undefined): string {
  if (count == null) return 'N/A';
  if (count >= 10_000) return `${(count / 1_000).toFixed(0)}K+`;
  return count.toLocaleString();
}

export function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleString();
}

export function formatScore(score: number): string {
  return score.toFixed(1);
}
