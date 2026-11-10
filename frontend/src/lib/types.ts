/* Types mirroring the FastAPI response shapes.
 *
 * Hand-written rather than generated from /openapi.json: only the fields the UI actually
 * reads are modelled, so the surface stays small and a backend addition does not break
 * the build. Field names match the API exactly — no camelCase remapping, which would
 * create a second vocabulary for the same data.
 */

export type NutrientStatus = 'low' | 'adequate' | 'high';
export type PhStatus = 'acidic' | 'neutral' | 'alkaline';
export type HealthBand = 'good' | 'moderate' | 'poor' | 'critical';
export type RiskBand = 'low' | 'moderate' | 'high' | 'severe';

export interface Farm {
  id: number;
  name: string;
  owner_name: string | null;
  location: string | null;
  created_at: string;
}

export interface Field {
  id: number;
  farm_id: number;
  name: string;
  area_hectares: number | null;
  latitude: number | null;
  longitude: number | null;
  created_at: string;
}

export interface SoilRecord {
  id: number;
  field_id: number;
  nitrogen: number | null;
  phosphorus: number | null;
  potassium: number | null;
  ph: number | null;
  organic_matter: number | null;
  moisture: number | null;
  temperature: number | null;
  humidity: number | null;
  rainfall: number | null;
  sampled_at: string;
  created_at: string;
}

export interface ImageMeta {
  id: number;
  field_id: number | null;
  original_filename: string | null;
  content_type: string | null;
  source: 'upload' | 'camera';
  file_size: number | null;
  width: number | null;
  height: number | null;
  created_at: string;
}

export interface SoilTypeClassification {
  soil_type: string;
  confidence: number;
  reliability: string;
  class_recall: number | null;
  boundary_warning?: string;
  source_used: string;
  image_id: number;
}

export interface DegradationRisk {
  index: number;
  band: RiskBand;
  basis: 'current_condition_only' | 'current_condition_and_trend';
  trend_slope: number | null;
  records_used: number;
  note: string;
}

export interface FertilizerRecommendation {
  recommended?: string | { product?: string; kg_per_hectare?: number; [key: string]: unknown }[];
  advisory?: string;
  alternatives?: { fertilizer: string; confidence: number; advisory: string }[];
}

export interface Diagnosis {
  nitrogen: NutrientStatus;
  phosphorus: NutrientStatus;
  potassium: NutrientStatus;
  ph: PhStatus;
  // Micronutrients: only present when submitted inline to /analyze (SoilRecord
  // does not carry them, so a diagnosis reconstructed from a bare stored record
  // will lack these). Optional rather than required for that reason.
  EC?: NutrientStatus;
  S?: NutrientStatus;
  Cu?: NutrientStatus;
  Fe?: NutrientStatus;
  Mn?: NutrientStatus;
  Zn?: NutrientStatus;
  B?: NutrientStatus;
}

export interface FusionResult {
  applied: boolean;
  reason?: string;
  soil_type?: string;
  diagnosis?: Diagnosis;
  soil_health_score?: number;
  score_delta?: number;
  changes_vs_structured_only?: Record<string, { from: string; to: string }>;
  changed_any?: boolean;
  ph_context?: string | null;
}

export interface Analysis {
  analysis_id: number | null;
  field_id: number;
  soil_record_id: number | null;
  persisted: boolean;
  soil_health_score: number;
  health_band: HealthBand;
  diagnosis: Diagnosis;
  degradation_risk: DegradationRisk;
  fertilizer_recommendation: FertilizerRecommendation;
  inputs_used: Record<string, number>;
  imputed_features: string[];
  soil_type_classification?: SoilTypeClassification;
  fusion?: FusionResult;
}

export interface ScheduleSplit {
  stage: string;
  day: number;
  share: number;
  kg: number | null;
}

export interface RecommendedProduct {
  product: string;
  kind: string;
  targets: string[];
  kg_per_hectare: number;
  total_product_kg: number | null;
  schedule: ScheduleSplit[];
  schedule_basis: string;
  advisory: string;
  supplies_kg_per_ha: Record<string, number>;
}

export interface Amendment {
  product: string;
  reason: string;
  kg_per_hectare: number;
  timing: string;
  note: string;
}

export interface Recommendations {
  analysis_id: number;
  field_id: number;
  field_area_hectares: number | null;
  deficient_nutrients: string[];
  products: RecommendedProduct[];
  amendments: Amendment[];
  warnings: string[];
  caveat: string;
}

export interface RankedCrop {
  crop: string;
  suitability: number;
  band: 'excellent' | 'good' | 'moderate' | 'marginal' | 'poor';
  parameter_scores: Record<string, number>;
  limiting_factor: string | null;
}

export interface CropSuitability {
  field_id: number;
  based_on: { soil_record_id: number; sampled_at: string };
  ranked_crops: RankedCrop[];
  top_crops: string[];
  parameters_used: string[];
  parameters_missing: string[];
  caveat: string;
}

export interface TrendProjection {
  horizon: string;
  seasons_ahead: number;
  predicted_score: number;
  range: [number, number];
}

export interface Trend {
  field_id?: number;
  sufficient: boolean;
  records_used: number;
  records_required?: number;
  reason?: string;
  current_score?: number;
  history: { record_id?: number; sampled_at?: string; date?: string; score: number }[];
  model?: { type: string; slope_per_record: number; r_squared: number };
  projection: TrendProjection[];
  verdict?: 'declining' | 'stable' | 'improving';
  projection_confidence?: 'good' | 'moderate' | 'low' | 'very_low';
  /** An integer, the literal string "already", or null. See API docs §9. */
  seasons_to_critical?: number | 'already' | null;
  interpretation?: string;
  caveat?: string;
  chart_png?: string | null;
}

/** Shape returned when the service worker queues a write while offline. */
export interface QueuedResponse {
  queued: true;
  detail: string;
}

export function isQueued(value: unknown): value is QueuedResponse {
  return typeof value === 'object' && value !== null && 'queued' in value;
}