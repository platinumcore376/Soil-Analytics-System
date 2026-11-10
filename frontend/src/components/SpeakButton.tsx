'use client';

/* Read-aloud for AI-generated text (Weeks 5-6 requirement: "integrate Sarvam AI for
 * reading AI-generated diagnostic results and recommendations aloud in the farmer's
 * regional language").
 *
 * Two-tier strategy:
 *
 *   1. POST /api/tts  — the backend proxies Sarvam AI. The key stays server-side; calling
 *      Sarvam from the browser would ship it to every device.
 *   2. Web Speech API — built into Android Chrome, works offline, no key. Used when the
 *      proxy is absent (it is not implemented yet) or returns an error.
 *
 * Tier 2 means the feature is usable today and degrades rather than disappears. Hindi and
 * Kannada voice availability varies by device, so the button reports when neither tier can
 * speak instead of silently doing nothing.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { SPEECH_LANG } from '@/lib/i18n';
import { getToken } from '@/lib/api';
import { useLocale } from '@/lib/LocaleProvider';

type State = 'idle' | 'loading' | 'speaking' | 'unsupported';

export function SpeakButton({ text }: { text: string }) {
  const { locale, t } = useLocale();
  const [state, setState] = useState<State>('idle');
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const stop = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setState('idle');
  }, []);

  // Speech must not continue after the screen is gone.
  useEffect(() => stop, [stop]);

  const speakLocally = useCallback((): boolean => {
    if (!('speechSynthesis' in window)) return false;

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = SPEECH_LANG[locale];
    // Slightly slower than default: agronomic terms in a second language need it.
    utterance.rate = 0.92;
    utterance.onend = () => setState('idle');
    utterance.onerror = () => setState('idle');

    // Prefer a voice that actually matches the locale; otherwise the browser reads Hindi
    // text with an English voice, which is unintelligible.
    const voices = window.speechSynthesis.getVoices();
    const match = voices.find((v) => v.lang === SPEECH_LANG[locale])
      ?? voices.find((v) => v.lang.startsWith(locale));
    if (match) utterance.voice = match;

    window.speechSynthesis.speak(utterance);
    setState('speaking');
    return true;
  }, [locale, text]);

  const speak = useCallback(async () => {
    if (state === 'speaking' || state === 'loading') {
      stop();
      return;
    }

    setState('loading');

    // Tier 1: Sarvam via the backend proxy.
    try {
      // The proxy requires a signed-in user — TTS costs money per call, so it must not be
      // an open relay. Without the token every request would 401 and silently fall through.
      const token = getToken();
      const response = await fetch('/api/tts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text, language: locale }),
      });

      if (response.ok && response.headers.get('content-type')?.startsWith('audio')) {
        const url = URL.createObjectURL(await response.blob());
        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onended = () => {
          URL.revokeObjectURL(url);
          setState('idle');
        };
        audio.onerror = () => {
          URL.revokeObjectURL(url);
          if (!speakLocally()) setState('unsupported');
        };
        await audio.play();
        setState('speaking');
        return;
      }
    } catch {
      /* Proxy unreachable or not implemented — fall through to the device voice. */
    }

    // Tier 2: on-device speech synthesis.
    if (!speakLocally()) setState('unsupported');
  }, [locale, speakLocally, state, stop, text]);

  if (state === 'unsupported') {
    return (
      <span className="text-sm text-muted" role="status">
        🔇 {t('notAvailable')}
      </span>
    );
  }

  const active = state === 'speaking' || state === 'loading';

  return (
    <button
      onClick={speak}
      aria-pressed={active}
      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-base font-semibold transition ${
        active ? 'bg-ok text-white' : 'border-2 border-ok/30 bg-white text-ok-text'
      }`}
      data-compact
    >
      <span aria-hidden>{state === 'loading' ? '⏳' : active ? '⏹' : '🔊'}</span>
      {active ? t('stopReading') : t('readAloud')}
    </button>
  );
}
