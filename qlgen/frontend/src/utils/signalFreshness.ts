/**
 * Signal freshness utilities.
 *
 * Freshness is based on when the real-world event occurred (evidence_date),
 * NOT when qlGen discovered it (detected_at). A CEO change from a year ago
 * detected today is stale intelligence — it shouldn't rank alongside
 * a funding round announced yesterday.
 */

export type FreshnessTier = 'fresh' | 'recent' | 'aging' | 'stale' | 'old';

export interface FreshnessInfo {
  /** Human-readable relative time (e.g. "2d ago", "3mo ago") */
  label: string;
  /** CSS color for the freshness indicator */
  color: string;
  /** Background color (15% opacity) for badges */
  bgColor: string;
  /** Tier name */
  tier: FreshnessTier;
  /** Age in days */
  days: number;
}

/**
 * Freshness tiers (based on actual event age):
 * - fresh:  < 7 days   — green  (actionable now)
 * - recent: < 30 days  — blue   (still relevant)
 * - aging:  < 90 days  — amber  (losing relevance)
 * - stale:  < 180 days — orange (low relevance)
 * - old:    >= 180 days — gray  (likely outdated)
 */
export function getSignalFreshness(evidenceDate: string | null | undefined, detectedAt?: string | null): FreshnessInfo {
  // Use evidence_date (actual event time) first, fall back to detected_at
  const dateToUse = evidenceDate || detectedAt;

  if (!dateToUse) {
    return { label: 'Unknown age', color: '#bfbfbf', bgColor: 'rgba(191,191,191,0.15)', tier: 'old', days: Infinity };
  }

  const diff = Date.now() - new Date(dateToUse).getTime();
  const mins = Math.floor(diff / 60_000);
  const hrs = Math.floor(mins / 60);
  const days = Math.floor(hrs / 24);
  const months = Math.floor(days / 30);
  const years = Math.floor(days / 365);

  let label: string;
  if (mins < 1) label = 'Just now';
  else if (mins < 60) label = `${mins}m ago`;
  else if (hrs < 24) label = `${hrs}h ago`;
  else if (days < 30) label = `${days}d ago`;
  else if (months < 12) label = `${months}mo ago`;
  else if (years === 1) label = '1y ago';
  else label = `${years}y ago`;

  if (days < 7) {
    return { label, color: '#52c41a', bgColor: 'rgba(82,196,26,0.12)', tier: 'fresh', days };
  }
  if (days < 30) {
    return { label, color: '#1890ff', bgColor: 'rgba(24,144,255,0.10)', tier: 'recent', days };
  }
  if (days < 90) {
    return { label, color: '#faad14', bgColor: 'rgba(250,173,20,0.12)', tier: 'aging', days };
  }
  if (days < 180) {
    return { label, color: '#fa541c', bgColor: 'rgba(250,84,28,0.12)', tier: 'stale', days };
  }
  return { label, color: '#8c8c8c', bgColor: 'rgba(140,140,140,0.10)', tier: 'old', days };
}

/** Tier description for tooltips */
export const FRESHNESS_DESCRIPTIONS: Record<FreshnessTier, string> = {
  fresh: 'Fresh — event occurred within the last week',
  recent: 'Recent — event occurred within the last month',
  aging: 'Aging — event occurred 1-3 months ago',
  stale: 'Stale — event occurred 3-6 months ago',
  old: 'Old — event occurred over 6 months ago',
};
