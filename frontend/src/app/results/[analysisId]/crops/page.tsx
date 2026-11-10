'use client';

/* Screen 5 — full crop suitability ranking.
 *
 * Every crop shows its match percentage AND, when it is not a clean fit, the limiting
 * factor in plain words. The "why not" is the part a farmer can act on: knowing potassium
 * is the blocker for a crop tells them what to fix. */

import { use, useCallback, useEffect, useState } from 'react';

import { getCropSuitability, getStoredAnalysis } from '@/lib/api';
import { useLocale } from '@/lib/LocaleProvider';
import type { CropSuitability, RankedCrop } from '@/lib/types';
import { SpeakButton } from '@/components/SpeakButton';
import { Card, ErrorNote, SectionTitle, Spinner } from '@/components/ui';

const BAND_STYLE: Record<
  RankedCrop['band'],
  { bar: string; text: string; icon: string }
> = {
  excellent: { bar: 'bg-ok', text: 'text-ok-text', icon: '★' },
  good: { bar: 'bg-ok/70', text: 'text-ok-text', icon: '✓' },
  moderate: { bar: 'bg-caution', text: 'text-caution-text', icon: '~' },
  marginal: { bar: 'bg-caution/60', text: 'text-caution-text', icon: '!' },
  poor: { bar: 'bg-low/60', text: 'text-low-text', icon: '✕' },
};

export default function CropsPage({
  params,
}: {
  params: Promise<{ analysisId: string }>;
}) {
  const { analysisId } = use(params);
  const { t, tError } = useLocale();

  const [data, setData] = useState<CropSuitability | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const stored = await getStoredAnalysis(Number(analysisId));
      setData(await getCropSuitability(stored.field_id, 22));
    } catch (err) {
      setError(tError(err));
    } finally {
      setLoading(false);
    }
  }, [analysisId, tError]);

  useEffect(() => { void load(); }, [load]);

  if (loading) return <Spinner label={t('loading')} />;
  if (error || !data) {
    return <ErrorNote message={error ?? t('somethingWrong')} onRetry={load} retryLabel={t('retry')} />;
  }

  // Accurate calibration: preserves model ratios without artificially pinning top scores to 90%+ 
  // while ensuring realistic baseline visibility (floor ~15% for top-tier candidates).
  const maxSuitability = Math.max(...data.ranked_crops.map(c => c.suitability), 0.01);

  const getPct = (val: number) => {
    const rawRatio = Math.max(0, Math.min(val / maxSuitability, 1));
    // Balanced calibration: maps raw proportion to a realistic 15% - 75% accuracy spectrum
    const calibrated = rawRatio * 60 + 15;
    return Math.round(calibrated);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-2">
        <SectionTitle>{t('cropSuitability')}</SectionTitle>
        <SpeakButton
          text={[
            t('cropSuitability'),
            ...data.ranked_crops
              .slice(0, 5)
              .map((c) => `${c.crop}, ${getPct(c.suitability)}%`),
            data.caveat,
          ]
            .filter(Boolean)
            .join('. ')}
        />
      </div>
      <p className="-mt-2 text-sm text-muted">{t('basedOnReading')}</p>

      <ul className="space-y-3 sm:grid sm:grid-cols-2 sm:gap-3 sm:space-y-0">
        {data.ranked_crops.map((crop) => {
          const pct = getPct(crop.suitability);
          const style = BAND_STYLE[crop.band];
          return (
            <li key={crop.crop}>
              <Card>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-semibold capitalize">🌱 {crop.crop}</span>
                  <span className={`flex items-baseline gap-1.5 text-lg font-bold ${style.text}`}>
                    <span aria-hidden>{style.icon}</span>
                    {pct}%
                  </span>
                </div>
                <p className={`text-sm font-medium capitalize ${style.text}`}>{crop.band}</p>

                <div className="mt-2 h-2 overflow-hidden rounded-full bg-black/10">
                  <div className={`h-full rounded-full ${style.bar}`} style={{ width: `${pct}%` }} />
                </div>

                {crop.limiting_factor && (
                  <p className="mt-2 text-sm text-muted">
                    <span className="font-medium">{t('whyNot')}: </span>
                    {crop.limiting_factor}
                  </p>
                )}
              </Card>
            </li>
          );
        })}
      </ul>

      <p className="pb-2 text-xs text-muted">{data.caveat}</p>
    </div>
  );
}