'use client';

/* The headline number. A ring rather than a bar: it reads as a gauge at a glance, and the
 * numeral stays legible at small sizes where a bar's fill would not. */

import { BAND_HEX, HEALTH_BAND } from '@/lib/status';
import { useLocale } from '@/lib/LocaleProvider';
import type { HealthBand } from '@/lib/types';

export function ScoreDial({ score, band }: { score: number; band: HealthBand }) {
  const { t } = useLocale();
  const style = HEALTH_BAND[band];

  const size = 168;
  const stroke = 14;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (Math.max(0, Math.min(100, score)) / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} role="img" aria-label={`${score} / 100`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth={stroke}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={BAND_HEX[band]}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference}`}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-5xl font-bold leading-none">{Math.round(score)}</span>
          <span className="mt-1 text-sm text-muted">{t('outOf100')}</span>
        </div>
      </div>

      <span
        className={`inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-base font-bold text-white ${style.bg}`}
        >
        <span aria-hidden>{style.icon}</span>
        {t(style.labelKey)}
      </span>
    </div>
  );
}
