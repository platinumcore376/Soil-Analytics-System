'use client';

/* Screen 4 — Results. The spec asks for "a results screen displaying the soil health
 * score, deficiency diagnosis, and crop recommendations as colour-coded cards".
 */

import Link from 'next/link';
import { use, useCallback, useEffect, useState } from 'react';

import {
  getCropSuitability,
  downloadReport,
  getRecommendations,
  getStoredAnalysis,
  listSoilRecords,
  type StoredAnalysis,
} from '@/lib/api';
import { useLocale } from '@/lib/LocaleProvider';
import {
  HEALTH_BAND,
  NUTRIENT_LABEL,
  NUTRIENT_STATUS,
  PH_STATUS,
  RISK_BAND,
} from '@/lib/status';
import type {
  CropSuitability,
  Diagnosis,
  HealthBand,
  NutrientStatus,
  PhStatus,
  Recommendations,
  RiskBand,
} from '@/lib/types';
import { ScoreDial } from '@/components/ScoreDial';
import { SpeakButton } from '@/components/SpeakButton';
import {
  BigButton,
  Card,
  ErrorNote,
  SectionTitle,
  Skeleton,
  Spinner,
  StatusChip,
} from '@/components/ui';

const TREND_MIN_RECORDS = 3;
const NUTRIENT_KEYS = ['nitrogen', 'phosphorus', 'potassium', 'EC', 'S', 'Cu', 'Fe', 'Mn', 'Zn', 'B'] as const;

function healthBand(score: number): HealthBand {
  if (score >= 80) return 'good';
  if (score >= 60) return 'moderate';
  if (score >= 40) return 'poor';
  return 'critical';
}

function riskBand(index: number): RiskBand {
  if (index < 0.25) return 'low';
  if (index < 0.5) return 'moderate';
  if (index < 0.75) return 'high';
  return 'severe';
}

export default function ResultsPage({
  params,
}: {
  params: Promise<{ analysisId: string }>;
}) {
  const { analysisId } = use(params);
  const id = Number(analysisId);
  const { t, locale, tError } = useLocale();

  const [analysis, setAnalysis] = useState<StoredAnalysis | null>(null);
  const [recs, setRecs] = useState<Recommendations | null>(null);
  const [crops, setCrops] = useState<CropSuitability | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recordCount, setRecordCount] = useState<number | null>(null);
  const [advisoryPending, setAdvisoryPending] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setAdvisoryPending(true);
    try {
      const stored = await getStoredAnalysis(id);
      setAnalysis(stored);
      setLoading(false);

      const [r, c, h] = await Promise.allSettled([
        getRecommendations(id),
        getCropSuitability(stored.field_id, 3),
        listSoilRecords(stored.field_id),
      ]);
      if (r.status === 'fulfilled') setRecs(r.value);
      if (c.status === 'fulfilled') setCrops(c.value);
      if (h.status === 'fulfilled') setRecordCount(h.value.length);
    } catch (err) {
      setError(tError(err));
      setLoading(false);
    } finally {
      setAdvisoryPending(false);
    }
  }, [id, tError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Spinner label={t('loading')} />;
  if (error || !analysis) {
    return (
      <ErrorNote
        message={error ?? t('somethingWrong')}
        onRetry={load}
        retryLabel={t('retry')}
      />
    );
  }

  let diagnosis: Diagnosis;
  try {
    diagnosis = JSON.parse(analysis.diagnosis) as Diagnosis;
  } catch {
    diagnosis = {} as Diagnosis;
  }

  const score = analysis.soil_health_score;
  const band = healthBand(score);
  const risk = analysis.degradation_risk_index;

  const hasProducts = Array.isArray(recs?.products) && recs.products.length > 0;
  const hasAmendments = Array.isArray(recs?.amendments) && recs.amendments.length > 0;

  const spoken = [
    `${t('soilHealth')}: ${Math.round(score)} ${t('outOf100')}, ${t(HEALTH_BAND[band].labelKey)}.`,
    ...NUTRIENT_KEYS
      .filter((n) => diagnosis[n])
      .map((n) => `${t(NUTRIENT_LABEL[n])}: ${t(NUTRIENT_STATUS[diagnosis[n] as NutrientStatus].labelKey)}.`),
    diagnosis.ph ? `${t('ph')}: ${t(PH_STATUS[diagnosis.ph].labelKey)}.` : '',
    hasProducts && recs?.products[0]
      ? `${t('whatToApply')}: ${recs.products[0].product}, ${
          recs.products[0].total_product_kg ?? recs.products[0].kg_per_hectare
        } kg.`
      : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className="space-y-4">
      {/* ---------------------------------------------------------------- score */}
      <Card>
        <div className="mb-3 flex items-start justify-between gap-2">
          <SectionTitle>{t('soilHealth')}</SectionTitle>
          <SpeakButton text={spoken} />
        </div>
        <ScoreDial score={score} band={band} />
      </Card>

      {/* ----------------------------------------------------------------- risk */}
      {risk !== null && (
        <Card>
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium">{t('degradationRisk')}</span>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold">{risk.toFixed(2)}</span>
              <StatusChip
                bg={RISK_BAND[riskBand(risk)].bg}
                icon={RISK_BAND[riskBand(risk)].icon}
                label={t(RISK_BAND[riskBand(risk)].labelKey)}
              />
            </div>
          </div>
        </Card>
      )}

      {/* ------------------------------------------------------------ nutrients */}
      <Card>
        <SectionTitle>{t('nutrientLevels')}</SectionTitle>
        <ul className="divide-y divide-black/5">
          {NUTRIENT_KEYS.map((key) => {
            const status = diagnosis[key] as NutrientStatus | undefined;
            if (!status) return null;
            const style = NUTRIENT_STATUS[status];
            return (
              <li key={key} className="flex items-center gap-3 py-3">
                <span aria-hidden className={`text-xl ${style.fg}`}>
                  {style.icon}
                </span>
                <span className="flex-1 font-medium">{t(NUTRIENT_LABEL[key])}</span>
                <StatusChip
                  bg={style.bg}
                  icon={style.icon}
                  label={t(style.labelKey)}
                />
              </li>
            );
          })}

          {diagnosis.ph && (
            <li className="flex items-center gap-3 py-3">
              <span
                aria-hidden
                className={`text-xl ${PH_STATUS[diagnosis.ph as PhStatus].fg}`}
              >
                {PH_STATUS[diagnosis.ph as PhStatus].icon}
              </span>
              <span className="flex-1 font-medium">{t('ph')}</span>
              <StatusChip
                bg={PH_STATUS[diagnosis.ph as PhStatus].bg}
                icon={PH_STATUS[diagnosis.ph as PhStatus].icon}
                label={t(PH_STATUS[diagnosis.ph as PhStatus].labelKey)}
              />
            </li>
          )}
        </ul>
      </Card>

      {/* Advisory skeleton while loading */}
      {advisoryPending && (
        <Card>
          <div aria-busy="true" data-testid="advisory-skeleton">
            <Skeleton className="mb-4 h-5 w-36" />
            <div className="space-y-3">
              <Skeleton className="h-12" />
              <Skeleton className="h-12" />
              <Skeleton className="h-12 w-3/4" />
            </div>
          </div>
        </Card>
      )}

      {/* ----------------------------------------------------------- fertilizer & amendments */}
      {recs && (hasProducts || hasAmendments) ? (
        <Card>
          <div className="flex items-center justify-between mb-2">
            <SectionTitle>{t('whatToApply')}</SectionTitle>
            <span className="text-xs font-semibold px-2.5 py-1 bg-black/5 rounded-full text-muted">
              {((recs?.products?.length) || 0) + ((recs?.amendments?.length) || 0)}{' '}
              {(((recs?.products?.length) || 0) + ((recs?.amendments?.length) || 0)) === 1 ? 'Action' : 'Actions'} Required
            </span>
          </div>
          <ul className="space-y-3">
            {hasProducts &&
              recs.products.map((product, idx) => (
                <li key={product.product} className="rounded-xl bg-surface p-3.5 border border-black/5 shadow-sm">
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ok/20 text-ok-text text-xs font-bold">
                        {idx + 1}
                      </span>
                      <span className="font-semibold text-ink">{product.product}</span>
                    </div>
                    <span className="text-lg font-bold text-ok-text">
                      {product.total_product_kg ?? product.kg_per_hectare} {t('unit_kg')}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted pl-8">
                    {product.total_product_kg === null && t('perHectare')}
                  </p>

                  <details className="mt-2 pl-8">
                    <summary className="cursor-pointer text-sm font-medium text-ok-text">
                      {t('fullSchedule')} ({product.schedule?.length ?? 0} split stages)
                    </summary>
                    <ul className="mt-2 space-y-1.5 text-sm bg-black/5 p-2.5 rounded-lg">
                      {product.schedule?.map((split) => (
                        <li key={split.stage} className="flex justify-between gap-2">
                          <span className="text-muted font-medium">
                            {split.stage}: {split.day === 0 ? t('now') : `${t('day')} ${split.day}`}
                          </span>
                          <span className="font-bold text-ink">
                            {split.kg} {t('unit_kg')}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </details>
                </li>
              ))}

            {hasAmendments &&
              recs.amendments.map((amendment, idx) => (
                <li
                  key={amendment.product}
                  className="rounded-xl border-2 border-caution/35 bg-caution/10 p-4 shadow-sm"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-caution/30 text-caution-text text-xs font-bold">
                        {(recs?.products?.length || 0) + idx + 1}
                      </span>
                      <span className="font-bold text-base text-ink">{amendment.product}</span>
                    </div>
                    <span className="text-lg font-bold text-caution-text">
                      {amendment.kg_per_hectare} {t('kgPerHa')}
                    </span>
                  </div>
                  <p className="mt-1 text-sm font-medium text-ink/90 pl-8">{amendment.reason}</p>
                  <p className="mt-1 text-xs font-semibold text-muted pl-8">⏱ {amendment.timing}</p>
                  {amendment.note && (
                    <p className="mt-1.5 text-xs text-muted italic bg-black/5 p-2 rounded-lg ml-8">{amendment.note}</p>
                  )}
                </li>
              ))}
          </ul>
        </Card>
      ) : !advisoryPending ? (
        <Card>
          <SectionTitle>{t('whatToApply')}</SectionTitle>
          <p className="flex items-center gap-2 text-ok-text">
            <span aria-hidden>✓</span>
            {t('noRecommendations')}
          </p>
        </Card>
      ) : null}

      {/* ---------------------------------------------------------------- crops */}
      {crops && crops.ranked_crops && crops.ranked_crops.length > 0 && (
        <Card>
          <SectionTitle>{t('bestCrops')}</SectionTitle>
          <ul className="mb-3 space-y-2">
            {crops.ranked_crops.map((crop: any, index) => {
              const cropName = crop.crop || crop.name || crop.crop_name || 'Unknown Crop';
              const rawVal = Number(crop.suitability ?? crop.score) || 0;
              const percentage = rawVal <= 1 ? rawVal * 100 : rawVal;
              return (
                <li key={`${cropName}-${index}`} className="flex items-center gap-3">
                  <span aria-hidden className="text-xl">
                    🌱
                  </span>
                  <span className="flex-1 font-medium capitalize">{cropName}</span>
                  <span className="font-bold text-ok-text">
                    {Math.round(percentage)}%
                  </span>
                </li>
              );
            })}
          </ul>
          <Link
            href={`/results/${id}/crops`}
            className="text-sm font-semibold text-ok-text underline"
          >
            {t('seeAllCrops')} ›
          </Link>
        </Card>
      )}

      {/* -------------------------------------------------------------- actions */}
      <div className="space-y-2 pt-2">
        {recordCount === null || recordCount >= TREND_MIN_RECORDS ? (
          <BigButton href={`/results/${id}/trend`} variant="secondary" icon="📈">
            {t('trend')}
          </BigButton>
        ) : (
          <Card className="border-black/10">
            <p className="flex items-start gap-2 text-sm text-muted">
              <span aria-hidden className="text-lg">
                📈
              </span>
              <span>
                <span className="block font-semibold text-ink">{t('trend')}</span>
                {t('needMoreRecords', {
                  have: recordCount,
                  need: TREND_MIN_RECORDS,
                })}
              </span>
            </p>
          </Card>
        )}

        <BigButton
          variant="secondary"
          icon="📄"
          disabled={downloading}
          onClick={() => {
            setDownloadError(null);
            setDownloading(true);
            void downloadReport(id, locale, analysis.image_id !== null)
              .catch((err) => setDownloadError(tError(err)))
              .finally(() => setDownloading(false));
          }}
        >
          {downloading ? t('preparingReport') : t('downloadReport')}
        </BigButton>

        {downloadError && <ErrorNote message={downloadError} />}
      </div>
    </div>
  );
}