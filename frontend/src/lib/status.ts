/* Mapping from API status strings to colour, icon and localised label.
 *
 * Every status carries THREE redundant signals — colour, icon, and the label — so the
 * meaning survives greyscale, colour-vision deficiency, and low literacy. This is the
 * single place that mapping lives; components never hardcode a colour.
 */

import type { TKey } from './tkey';
import type { HealthBand, NutrientStatus, PhStatus, RiskBand } from './types';

export interface StatusStyle {
  /** Tailwind background class. */
  bg: string;
  /** Tailwind text colour class for use on a light surface. */
  fg: string;
  /** Redundant non-colour signal. */
  icon: string;
  labelKey: TKey;
}

export const NUTRIENT_STATUS: Record<NutrientStatus, StatusStyle> = {
  low: { bg: 'bg-low', fg: 'text-low-text', icon: '▼', labelKey: 'statusLow' },
  adequate: { bg: 'bg-ok', fg: 'text-ok-text', icon: '✓', labelKey: 'statusAdequate' },
  high: { bg: 'bg-caution', fg: 'text-caution-text', icon: '▲', labelKey: 'statusHigh' },
};

export const PH_STATUS: Record<PhStatus, StatusStyle> = {
  acidic: { bg: 'bg-low', fg: 'text-low-text', icon: '▼', labelKey: 'statusAcidic' },
  neutral: { bg: 'bg-ok', fg: 'text-ok-text', icon: '✓', labelKey: 'statusNeutral' },
  alkaline: { bg: 'bg-caution', fg: 'text-caution-text', icon: '▲', labelKey: 'statusAlkaline' },
};

export const HEALTH_BAND: Record<HealthBand, StatusStyle> = {
  good: { bg: 'bg-ok', fg: 'text-ok-text', icon: '✓', labelKey: 'bandGood' },
  moderate: { bg: 'bg-caution', fg: 'text-caution-text', icon: '!', labelKey: 'bandModerate' },
  poor: { bg: 'bg-low', fg: 'text-low-text', icon: '!!', labelKey: 'bandPoor' },
  critical: { bg: 'bg-low', fg: 'text-low-text', icon: '⚠', labelKey: 'bandCritical' },
};

export const RISK_BAND: Record<RiskBand, StatusStyle> = {
  low: { bg: 'bg-ok', fg: 'text-ok-text', icon: '✓', labelKey: 'riskLow' },
  moderate: { bg: 'bg-caution', fg: 'text-caution-text', icon: '!', labelKey: 'riskModerate' },
  high: { bg: 'bg-low', fg: 'text-low-text', icon: '!!', labelKey: 'riskHigh' },
  severe: { bg: 'bg-low', fg: 'text-low-text', icon: '⚠', labelKey: 'riskSevere' },
};

/** Localised nutrient name for one of the thirteen parameters. */
export const NUTRIENT_LABEL: Record<string, TKey> = {
  nitrogen: 'nitrogen',
  phosphorus: 'phosphorus',
  potassium: 'potassium',
  ph: 'ph',
  organic_matter: 'organicMatter',
  moisture: 'moisture',
  EC: 'ec',
  S: 'sulfur',
  Cu: 'copper',
  Fe: 'iron',
  Mn: 'manganese',
  Zn: 'zinc',
  B: 'boron',
};

export const NUTRIENT_UNIT: Record<string, TKey | null> = {
  // 'soilIndex', not 'kgPerHa': these are the soil-test index the models were trained on
  // (N 0-140, P 5-145, K 5-205). Labelling them kg/ha invited farmers to enter Soil Health
  // Card figures on a ~4x larger scale, which the diagnosis then read as HIGH.
  // Fertilizer OUTPUT rates are genuinely kg/ha and still use 'kgPerHa'.
  nitrogen: 'soilIndex',
  phosphorus: 'soilIndex',
  potassium: 'soilIndex',
  ph: null,
  organic_matter: 'percent',
  moisture: 'percent',
  // Micronutrients: the PDF report shows these as bare numbers with no unit label
  // (see report.py), so no unit is asserted here rather than guessing one.
  EC: null,
  S: null,
  Cu: null,
  Fe: null,
  Mn: null,
  Zn: null,
  B: null,
};

/* Raw hex for the same palette, for the few places that cannot use a Tailwind class:
 * SVG `stroke`/`fill` attributes and canvas drawing.
 *
 * These MUST stay in step with tailwind.config.ts. Keeping them here rather than inline in
 * each component is what stops them drifting — `ScoreDial` previously hardcoded
 * `poor: '#e07a3f'`, an orange that existed nowhere in the config, so the dial ring and the
 * band chip directly beneath it rendered different colours for the same band.
 */
export const HEX = {
  low: '#d64545',
  caution: '#e8a33d',
  ok: '#2f9e44',
  muted: '#6b7280',
} as const;

/** Ring/stroke colour per health band, derived from the same mapping as the chip. */
export const BAND_HEX: Record<string, string> = {
  good: HEX.ok,
  moderate: HEX.caution,
  poor: HEX.low,
  critical: HEX.low,
};