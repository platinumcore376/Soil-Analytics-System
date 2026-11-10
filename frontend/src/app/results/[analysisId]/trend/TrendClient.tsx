'use client';

import { useCallback, useEffect, useState } from 'react';

import { getStoredAnalysis, getTrend, downloadTrendPdf } from '@/lib/api';
import { HEX } from '@/lib/status';
import { useLocale } from '@/lib/LocaleProvider';
import type { Trend } from '@/lib/types';
import { SpeakButton } from '@/components/SpeakButton';
import { Card, ErrorNote, SectionTitle, Spinner } from '@/components/ui';

const VERDICT_STYLE = {
  declining: { bg: 'bg-low', icon: '▼', key: 'verdictDeclining' },
  stable: { bg: 'bg-ok', icon: '→', key: 'verdictStable' },
  improving: { bg: 'bg-ok', icon: '▲', key: 'verdictImproving' },
} as const;

export default function TrendClient({ analysisId }: { analysisId: string }) {
  const { t, tError } = useLocale();

  const [data, setData] = useState<Trend | null>(null);
  const [fieldId, setFieldId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const stored = await getStoredAnalysis(Number(analysisId));
      setFieldId(stored.field_id);
      setData(await getTrend(stored.field_id));
    } catch (err) {
      setError(tError(err));
    } finally {
      setLoading(false);
    }
  }, [analysisId, tError]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDownload = async () => {
    if (!fieldId || downloading) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadTrendPdf(fieldId);
    } catch (err) {
      setDownloadError(tError(err));
    } finally {
      setDownloading(false);
    }
  };

  if (loading) return <Spinner label={t('loading')} />;
  if (error || !data) {
    return (
      <ErrorNote
        message={error ?? t('somethingWrong')}
        onRetry={load}
        retryLabel={t('retry')}
      />
    );
  }

  if (!data.sufficient) {
    return (
      <div className="space-y-4">
        <SectionTitle>{t('trend')}</SectionTitle>
        <Card className="border-caution/40 bg-caution/10">
          <p>
            📊{' '}
            {t('needMoreRecords', {
              have: data.records_used,
              need: data.records_required ?? 3,
            })}
          </p>
        </Card>
      </div>
    );
  }

  const verdict = VERDICT_STYLE[data.verdict ?? 'stable'];
  const weak =
    data.projection_confidence === 'very_low' || data.projection_confidence === 'low';

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-2">
        <SectionTitle>{t('trend')}</SectionTitle>
        <SpeakButton
          text={[
            t('currentScore'),
            String(data.current_score),
            t(verdict.key),
            data.interpretation,
            data.caveat,
          ]
            .filter(Boolean)
            .join('. ')}
        />
      </div>

      <Card>
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm text-muted">{t('currentScore')}</p>
            <p className="text-4xl font-bold">{data.current_score}</p>
          </div>
          <span
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 font-bold text-white ${verdict.bg}`}
          >
            <span aria-hidden>{verdict.icon}</span>
            {t(verdict.key)}
          </span>
        </div>

        <HistoryChart trend={data} />

        {data.interpretation && (
          <p className="mt-3 text-sm text-muted">{data.interpretation}</p>
        )}
      </Card>

      {data.seasons_to_critical === 'already' && (
        <Card className="border-low/40 bg-low/10">
          <p className="font-semibold text-low-text">⚠ {t('alreadyCritical')}</p>
        </Card>
      )}

      {typeof data.seasons_to_critical === 'number' && (
        <Card className="border-low/40 bg-low/10">
          <p className="font-semibold text-low-text">
            ⏳ {t('reachesCritical', { n: data.seasons_to_critical })}
          </p>
        </Card>
      )}

      {data.projection && data.projection.length > 0 && (
        <Card>
          <SectionTitle>{t('projection')}</SectionTitle>
          {weak && (
            <p className="mb-3 rounded-xl bg-caution/10 p-3 text-sm text-caution-text">
              ⚠ {t('lowConfidence')}
            </p>
          )}
          <ul className="divide-y divide-black/5">
            {data.projection.map((p, idx) => (
              <li key={`${p.horizon}-${idx}`} className="flex items-baseline justify-between py-2">
                <span className="text-muted">+{p.seasons_ahead}</span>
                <span className="text-right">
                  <span className="text-xl font-bold">{p.predicted_score}</span>
                  <span className="block text-xs text-muted">
                    {Array.isArray(p?.range) && p.range.length >= 2
                      ? `${p.range[0]} – ${p.range[1]}`
                      : 'N/A'}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {data.caveat && <p className="pb-2 text-xs text-muted">{data.caveat}</p>}

      {/* Prominent Download Button moved to the lowest section */}
      {downloadError && (
        <ErrorNote
          message={downloadError}
          onRetry={handleDownload}
          retryLabel={t('retry')}
        />
      )}
      {fieldId && (
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="w-full flex items-center justify-center gap-2 rounded-2xl bg-[#4A6B37] text-white py-4 font-semibold shadow-md hover:bg-[#3d582d] active:scale-[0.98] transition-all disabled:opacity-50 mt-6"
        >
          <span>📥</span>
          <span>{downloading ? t('loading') : 'Download Multi-Panel Trend Report (PDF)'}</span>
        </button>
      )}
    </div>
  );
}

function HistoryChart({ trend }: { trend: Trend }) {
  const { t } = useLocale();
  const history = (trend?.history || []).map((h) => h.score);
  const projected = (trend?.projection || []).map((p) => p.predicted_score);
  const all = [...history, ...projected];

  if (all.length === 0) return <p className="text-xs text-muted py-4 text-center">No history data available</p>;

  const width = 300;
  const height = 110;
  const pad = 8;

  const x = (i: number) =>
    all.length === 1 ? width / 2 : pad + (i / (all.length - 1)) * (width - 2 * pad);
  const y = (score: number) =>
    height - pad - (Math.max(0, Math.min(100, score)) / 100) * (height - 2 * pad);

  const line = (points: number[], offset = 0) =>
    points.map((s, i) => `${i === 0 ? 'M' : 'L'} ${x(i + offset)} ${y(s)}`).join(' ');

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      role="img"
      aria-label={t('chartLabel')}
    >
      <line
        x1={pad}
        x2={width - pad}
        y1={y(40)}
        y2={y(40)}
        stroke={HEX.low}
        strokeWidth="1"
        strokeDasharray="3 3"
        opacity="0.5"
      />
      {history.length > 1 && (
        <path d={line(history)} fill="none" stroke={HEX.ok} strokeWidth="2.5" />
      )}
      {projected.length > 0 && history.length > 0 && (
        <path
          d={line([history[history.length - 1], ...projected], history.length - 1)}
          fill="none"
          stroke={HEX.muted}
          strokeWidth="2"
          strokeDasharray="5 4"
        />
      )}
      {history.map((s, i) => (
        <circle key={i} cx={x(i)} cy={y(s)} r="4" fill={HEX.ok} />
      ))}
    </svg>
  );
}