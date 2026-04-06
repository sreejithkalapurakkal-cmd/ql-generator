import type { ICPDefinition } from '../types';

export interface SalesNavFilter {
  type: string;
  values: string[];
}

export interface SalesNavExtraction {
  isParseable: boolean;
  isSavedList: boolean;
  filters: SalesNavFilter[];
  keywords: string[];
  icpPartial: Partial<ICPDefinition>;
  summary: string;
  missingFields: string[];
}

const HEADCOUNT_PATTERN = /^([\d,]+)\s*[-–]\s*([\d,]+)$/;
const HEADCOUNT_PLUS_PATTERN = /^([\d,]+)\+$/;

function parseNumber(text: string): number {
  return parseInt(text.replace(/,/g, ''), 10) || 0;
}

function parseHeadcountRange(texts: string[]): { min: number; max: number } | null {
  let globalMin = Infinity;
  let globalMax = 0;

  for (const text of texts) {
    const trimmed = text.trim();
    const rangeMatch = trimmed.match(HEADCOUNT_PATTERN);
    if (rangeMatch) {
      const lo = parseNumber(rangeMatch[1]);
      const hi = parseNumber(rangeMatch[2]);
      globalMin = Math.min(globalMin, lo);
      globalMax = Math.max(globalMax, hi);
      continue;
    }
    const plusMatch = trimmed.match(HEADCOUNT_PLUS_PATTERN);
    if (plusMatch) {
      const lo = parseNumber(plusMatch[1]);
      globalMin = Math.min(globalMin, lo);
      globalMax = Math.max(globalMax, 100000);
      continue;
    }
    // Try single number
    const num = parseNumber(trimmed);
    if (num > 0) {
      globalMin = Math.min(globalMin, num);
      globalMax = Math.max(globalMax, num);
    }
  }

  if (globalMin === Infinity || globalMax === 0) return null;
  return { min: globalMin, max: globalMax };
}

function parseRevenueText(text: string): number | null {
  const cleaned = text.replace(/[$€£,]/g, '').trim().toLowerCase();
  const match = cleaned.match(/([\d.]+)\s*(b|m|k|billion|million|thousand)?/);
  if (!match) return null;
  const num = parseFloat(match[1]);
  const suffix = match[2] || '';
  if (suffix.startsWith('b')) return num * 1_000_000_000;
  if (suffix.startsWith('m')) return num * 1_000_000;
  if (suffix.startsWith('k') || suffix.startsWith('t')) return num * 1_000;
  return num;
}

function parseRevenueRange(texts: string[]): { min: number; max: number } | null {
  let globalMin = Infinity;
  let globalMax = 0;

  for (const text of texts) {
    // Try range format: "$1M - $10M" or "1M-10M"
    const rangeMatch = text.match(/([$€£]?[\d.,]+\s*[BMKbmk]?(?:illion|ousand)?)\s*[-–]\s*([$€£]?[\d.,]+\s*[BMKbmk]?(?:illion|ousand)?)/);
    if (rangeMatch) {
      const lo = parseRevenueText(rangeMatch[1]);
      const hi = parseRevenueText(rangeMatch[2]);
      if (lo !== null) globalMin = Math.min(globalMin, lo);
      if (hi !== null) globalMax = Math.max(globalMax, hi);
      continue;
    }
    // Try "X+" format
    const plusMatch = text.match(/([$€£]?[\d.,]+\s*[BMKbmk]?(?:illion|ousand)?)\+/);
    if (plusMatch) {
      const lo = parseRevenueText(plusMatch[1]);
      if (lo !== null) {
        globalMin = Math.min(globalMin, lo);
        globalMax = Math.max(globalMax, lo * 10);
      }
      continue;
    }
    // Single value
    const val = parseRevenueText(text);
    if (val !== null) {
      globalMin = Math.min(globalMin, val);
      globalMax = Math.max(globalMax, val);
    }
  }

  if (globalMin === Infinity || globalMax === 0) return null;
  return { min: globalMin, max: globalMax };
}

/**
 * Extract filter blocks from decoded Sales Navigator query string.
 * The format is: (type:FILTER_NAME,values:List((id:X,text:Y,selectionType:Z),...))
 */
function extractFilters(decoded: string): SalesNavFilter[] {
  const filters: SalesNavFilter[] = [];

  // Match each filter block: (type:XXX,values:List(...))
  const filterBlockRegex = /\(type:([A-Z_]+),values:List\(([^)]*(?:\([^)]*\)[^)]*)*)\)\)/g;
  let match;

  while ((match = filterBlockRegex.exec(decoded)) !== null) {
    const filterType = match[1];
    const valuesBlock = match[2];

    // Extract text values from the values block
    const textRegex = /text:([^,)]+)/g;
    const values: string[] = [];
    let textMatch;
    while ((textMatch = textRegex.exec(valuesBlock)) !== null) {
      values.push(textMatch[1].trim());
    }

    if (values.length > 0) {
      filters.push({ type: filterType, values });
    }
  }

  return filters;
}

/**
 * Extract keywords from the query param (outside of filters)
 */
function extractKeywords(decoded: string): string[] {
  const keywordsMatch = decoded.match(/keywords:([^,)]+)/);
  if (!keywordsMatch) return [];
  return keywordsMatch[1]
    .trim()
    .split(/\s+AND\s+|\s+OR\s+/)
    .map((k) => k.replace(/^["']|["']$/g, '').trim())
    .filter(Boolean);
}

const INDUSTRY_FILTERS = new Set(['INDUSTRY']);
const GEOGRAPHY_FILTERS = new Set(['GEOGRAPHY', 'REGION']);
const HEADCOUNT_FILTERS = new Set(['COMPANY_HEADCOUNT']);
const REVENUE_FILTERS = new Set(['ANNUAL_REVENUE', 'REVENUE']);
const TITLE_FILTERS = new Set(['CURRENT_JOB_TITLE', 'TITLE']);
const SENIORITY_FILTERS = new Set(['SENIORITY_LEVEL']);
const FUNCTION_FILTERS = new Set(['FUNCTION']);

function mapFiltersToICP(
  filters: SalesNavFilter[],
  keywords: string[]
): { icpPartial: Partial<ICPDefinition>; summary: string; missingFields: string[] } {
  const industries: { vertical: string; sub_vertical: string | null }[] = [];
  const countries: string[] = [];
  let employeeRange: { min: number; max: number } | null = null;
  let revenueRange: { min: number; max: number } | null = null;
  const targetRoles: string[] = [];
  const offerings: string[] = [];
  const summaryParts: string[] = [];

  for (const filter of filters) {
    if (INDUSTRY_FILTERS.has(filter.type)) {
      for (const v of filter.values) {
        industries.push({ vertical: v, sub_vertical: null });
      }
      summaryParts.push(`INDUSTRY: ${filter.values.join(', ')}`);
    } else if (GEOGRAPHY_FILTERS.has(filter.type)) {
      countries.push(...filter.values);
      summaryParts.push(`GEOGRAPHY: ${filter.values.join(', ')}`);
    } else if (HEADCOUNT_FILTERS.has(filter.type)) {
      employeeRange = parseHeadcountRange(filter.values);
      summaryParts.push(`HEADCOUNT: ${filter.values.join(', ')}`);
    } else if (REVENUE_FILTERS.has(filter.type)) {
      revenueRange = parseRevenueRange(filter.values);
      summaryParts.push(`REVENUE: ${filter.values.join(', ')}`);
    } else if (TITLE_FILTERS.has(filter.type)) {
      targetRoles.push(...filter.values);
      summaryParts.push(`TITLES: ${filter.values.join(', ')}`);
    } else if (SENIORITY_FILTERS.has(filter.type)) {
      targetRoles.push(...filter.values.map((v) => `${v} level`));
      summaryParts.push(`SENIORITY: ${filter.values.join(', ')}`);
    } else if (FUNCTION_FILTERS.has(filter.type)) {
      offerings.push(...filter.values);
      summaryParts.push(`FUNCTION: ${filter.values.join(', ')}`);
    }
  }

  if (keywords.length > 0) {
    offerings.push(...keywords);
    summaryParts.push(`KEYWORDS: ${keywords.join(', ')}`);
  }

  // Build partial ICP
  const icpPartial: Partial<ICPDefinition> = {};

  const hasFirmographics = industries.length > 0 || countries.length > 0 || employeeRange || revenueRange;
  if (hasFirmographics) {
    icpPartial.firmographic_details = {
      industry_types: industries.length > 0 ? industries : [],
      geography: { countries: countries.length > 0 ? countries : [] },
      employee_range: employeeRange || { min: 50, max: 1500 },
      revenue_range: revenueRange
        ? { min: revenueRange.min, max: revenueRange.max, currency: 'USD' }
        : { min: 10000000, max: 500000000, currency: 'USD' },
      low_cost_center: false,
    };
  }

  if (offerings.length > 0) {
    icpPartial.target_capability = { offerings, condition: 'OR' };
  }

  if (targetRoles.length > 0) {
    icpPartial.authority_roles = { target_roles: targetRoles };
  }

  // Determine missing fields
  const missingFields: string[] = [];
  if (industries.length === 0) missingFields.push('Industries');
  if (countries.length === 0) missingFields.push('Geography');
  if (!employeeRange) missingFields.push('Employee Range');
  if (!revenueRange) missingFields.push('Revenue Range');
  if (offerings.length === 0) missingFields.push('Offerings');
  // These are always missing from URLs
  missingFields.push('Urgency Signals');
  missingFields.push('Budget Signals');
  if (targetRoles.length === 0) missingFields.push('Target Roles');

  return {
    icpPartial,
    summary: summaryParts.join(' | '),
    missingFields,
  };
}

export function parseSalesNavUrl(url: string): SalesNavExtraction {
  const empty: SalesNavExtraction = {
    isParseable: false,
    isSavedList: false,
    filters: [],
    keywords: [],
    icpPartial: {},
    summary: '',
    missingFields: [],
  };

  if (!url || !url.includes('linkedin.com/sales/')) {
    return empty;
  }

  // Detect saved list
  if (url.includes('/sales/lists/') || url.includes('/sales/list/')) {
    return { ...empty, isSavedList: true };
  }

  // Only parse search URLs
  if (!url.includes('/sales/search/')) {
    return empty;
  }

  try {
    const urlObj = new URL(url);
    const queryParam = urlObj.searchParams.get('query');
    if (!queryParam) {
      return { ...empty, isParseable: true };
    }

    const decoded = decodeURIComponent(queryParam);
    const filters = extractFilters(decoded);
    const keywords = extractKeywords(decoded);

    if (filters.length === 0 && keywords.length === 0) {
      return { ...empty, isParseable: true };
    }

    const { icpPartial, summary, missingFields } = mapFiltersToICP(filters, keywords);

    return {
      isParseable: true,
      isSavedList: false,
      filters,
      keywords,
      icpPartial,
      summary,
      missingFields,
    };
  } catch {
    return empty;
  }
}

/**
 * Generate a name from extracted ICP partial data
 */
export function generateNameFromExtraction(icpPartial: Partial<ICPDefinition>): string {
  const parts: string[] = [];

  const industries = icpPartial.firmographic_details?.industry_types;
  if (industries && industries.length > 0) {
    parts.push(industries.slice(0, 2).map((i) => i.vertical).join(' & '));
  }

  const countries = icpPartial.firmographic_details?.geography?.countries;
  if (countries && countries.length > 0) {
    parts.push(countries.slice(0, 2).join(' & '));
  }

  const emp = icpPartial.firmographic_details?.employee_range;
  if (emp && (emp.min !== 50 || emp.max !== 1500)) {
    parts.push(`${emp.min}-${emp.max} emp`);
  }

  if (parts.length === 0) return 'Sales Nav Search';
  return parts.join(' - ');
}
