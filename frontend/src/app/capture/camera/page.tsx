'use client';

/* Screen 2a — soil photo capture (Weeks 5-6: "soil photo capture using the browser
 * MediaDevices camera API").
 *
 * THREE CONSTRAINTS THE SPEC CALLS OUT, AND HOW THEY ARE HANDLED
 *
 * 1. getUserMedia needs a secure context. Works on localhost and https; fails on plain
 * http to a device IP. Detected up front and reported, rather than showing a dead
 * preview.
 * 2. Android Chrome 60+. Older browsers and permission refusals fall back to
 * <input capture="environment">, which opens the native camera app.
 * 3. Low-end devices. The canvas grab is downscaled to 1024 px before upload — posting a
 * 12 MP frame over rural 4G would time out, and the backend resizes to 1024 anyway.
 */

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';

import { uploadImage } from '@/lib/api';
import { useLocale } from '@/lib/LocaleProvider';
import { useField } from '@/lib/useField';
import { Spinner } from '@/components/ui';

/** Longest edge sent to the server. Matches the backend's TARGET_IMAGE_SIZE. */
const MAX_EDGE = 1024;
const JPEG_QUALITY = 0.85;

type Mode = 'checking' | 'live' | 'fallback' | 'preview' | 'uploading';

export default function CameraPage() {
  const { t, tError, locale, setLocale } = useLocale();
  const router = useRouter();
  const { field, ready } = useField();

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  /* True once the component is gone. `getUserMedia` is async, so it can resolve AFTER
   * unmount — at which point storing the stream would leave the camera on with nothing left
   * to stop it. Checked on resolve and the stream stopped immediately. */
  const unmountedRef = useRef(false);
  /** Current mode, readable from event listeners without re-subscribing them. */
  const modeRef = useRef<Mode>('checking');
  /** True when the camera was stopped by backgrounding, so it should resume on return. */
  const suspendedRef = useRef(false);

  const [mode, setModeState] = useState<Mode>('checking');
  /* Mirror every mode change into a ref so the visibility listener can read the current
   * value without being re-subscribed on each change. */
  const setMode = useCallback((next: Mode) => {
    modeRef.current = next;
    setModeState(next);
  }, []);
  const [notice, setNotice] = useState<string | null>(null);
  /** Result of the pre-upload quality check; null when fine or not checked. */
  const [quality, setQuality] = useState<'dark' | 'blurry' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ url: string; blob: Blob } | null>(null);
  /** True while waiting for the first decoded frame, so Capture shows it is working. */
  const [capturing, setCapturing] = useState(false);
  /** Flips once the video reports real dimensions — gates the Capture button. */
  const [frameReady, setFrameReady] = useState(false);

  /* Stops the live camera and releases the hardware.
   *
   * Detaching srcObject matters as well as stopping the tracks: on some Android builds the
   * <video> holds the last frame and the indicator light stays on until the element lets go.
   */
  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const startCamera = useCallback(async () => {
    // A secure context is required. Checking first turns a silent failure into a clear
    // message — this is the single most common reason camera capture "doesn't work".
    if (!window.isSecureContext) {
      setNotice(t('cameraNeedsHttps'));
      setMode('fallback');
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setNotice(t('cameraUnavailable'));
      setMode('fallback');
      return;
    }

    // Never hold two streams at once. Without this, a second call orphans the first —
    // its tracks stay live and the camera light stays on with no reference left to stop it.
    stopStream();
    setFrameReady(false);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        // Rear camera, and a resolution hint rather than a hard constraint so low-end
        // devices are not rejected outright.
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 } },
        audio: false,
      });

      // Resolved after the screen was left, or after another start superseded this one.
      if (unmountedRef.current || streamRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      streamRef.current = stream;

      /* Switch to 'live' FIRST so the <video> is mounted, then attach in an effect.
       *
       * Attaching here is a race that loses: on the first visit mode is 'checking', so no
       * <video> exists yet and `videoRef.current` is null. The stream was therefore never
       * attached — the camera turned on (indicator lit) but the preview stayed black and
       * `capture()` bailed on `videoWidth === 0`, which is exactly the dead capture button.
       */
      setMode('live');
    } catch (err) {
      const name = err instanceof DOMException ? err.name : '';
      setNotice(
        name === 'NotAllowedError' ? t('cameraDenied') : t('cameraUnavailable'),
      );
      setMode('fallback');
    }
  }, [t, stopStream]);

  /* Attach the stream once the <video> is actually in the DOM.
   *
   * Runs whenever we enter 'live', which is the point at which the element exists. Also
   * covers a re-render that swapped the element out from under us.
   */
  useEffect(() => {
    const video = videoRef.current;
    const stream = streamRef.current;
    if (mode !== 'live' || !video || !stream) return;
    if (video.srcObject === stream) return;

    video.srcObject = stream;
    // Autoplay can be blocked; `playsInline muted autoPlay` on the element makes that
    // unlikely, and the user can still tap the frame.
    void video.play().catch(() => {});

    /* Gate Capture on a real frame. Without this the button is tappable while videoWidth is
     * still 0 — which is what made it feel broken. */
    const onReady = () => {
      if (video.videoWidth > 0) setFrameReady(true);
    };
    onReady();
    video.addEventListener('loadedmetadata', onReady);
    video.addEventListener('playing', onReady);
    return () => {
      video.removeEventListener('loadedmetadata', onReady);
      video.removeEventListener('playing', onReady);
    };
  }, [mode]);

  /* Mount/unmount only.
   *
   * `startCamera` is deliberately NOT a dependency. It closes over `t`, so listing it here
   * re-ran this effect on every language change: the cleanup stopped the OLD stream while a
   * second getUserMedia had already replaced streamRef, leaving the first one running with
   * the camera light on. The camera needs starting once per visit, not once per locale.
   */
  useEffect(() => {
    unmountedRef.current = false;
    void startCamera();
    return () => {
      unmountedRef.current = true;
      stopStream();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Belt-and-braces release. An unmount cleanup does not run if the tab is discarded or the
   * page is torn down (bfcache eviction, Android killing a backgrounded tab), which would
   * leave the camera active. `pagehide` covers those; `visibilitychange` releases the camera
   * when the farmer switches away, which is also what a user expects from a camera screen.
   */
  useEffect(() => {
    const release = () => stopStream();
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') {
        // Only a live preview is worth suspending. On the preview/upload step there is no
        // camera running, and touching mode there would discard the farmer's photo.
        if (modeRef.current === 'live') {
          stopStream();
          suspendedRef.current = true;
          setMode('checking');
        }
        return;
      }
      // Back in the foreground: revive the preview we suspended, and only that.
      if (suspendedRef.current) {
        suspendedRef.current = false;
        void startCamera();
      }
    };
    window.addEventListener('pagehide', release);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('pagehide', release);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [stopStream, startCamera]);

  /* Cheap image-quality check on the captured frame.
   *
   * The CNN was trained on reasonably lit, in-focus soil; a dark or motion-blurred photo
   * yields a confident-looking prediction from an image a human could not classify either.
   * Warning before upload is the only point at which a retake is free.
   *
   * Brightness is the mean of the luma channel. Focus uses the variance of a 4-neighbour
   * Laplacian, the standard cheap sharpness proxy — low variance means few sharp edges.
   * Both run on the already-downscaled canvas over a subsample, so the cost is a few ms
   * even on a low-end phone. Thresholds are deliberately permissive: this advises, and the
   * farmer can always override.
   */
  const assessQuality = (
    ctx: CanvasRenderingContext2D,
    w: number,
    h: number,
  ): 'dark' | 'blurry' | null => {
    const { data } = ctx.getImageData(0, 0, w, h);
    const luma = new Float32Array(w * h);
    let sum = 0;
    for (let i = 0, p = 0; p < luma.length; i += 4, p++) {
      // Rec. 601 luma; good enough and cheaper than a colour-space conversion.
      const y = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
      luma[p] = y;
      sum += y;
    }
    const mean = sum / luma.length;
    if (mean < 40) return 'dark';

    // Laplacian variance, sampling every other pixel to halve the work.
    let lSum = 0;
    let lSqSum = 0;
    let n = 0;
    for (let y = 1; y < h - 1; y += 2) {
      for (let x = 1; x < w - 1; x += 2) {
        const p = y * w + x;
        const lap =
          4 * luma[p] - luma[p - 1] - luma[p + 1] - luma[p - w] - luma[p + w];
        lSum += lap;
        lSqSum += lap * lap;
        n++;
      }
    }
    if (n === 0) return null;
    const variance = lSqSum / n - (lSum / n) ** 2;
    return variance < 60 ? 'blurry' : null;
  };

  /** Grab the current video frame, downscaled, as a JPEG blob. */
  const capture = useCallback(async () => {
    const video = videoRef.current;
    if (!video) return;

    /* Wait briefly for the first decoded frame instead of returning silently.
     *
     * `videoWidth` is 0 until metadata arrives. The old code bailed on that with no feedback,
     * so tapping Capture appeared to do nothing at all. Give it up to ~1s, then say what
     * happened rather than leaving the farmer pressing a dead button.
     */
    if (!video.videoWidth) {
      setCapturing(true);
      for (let i = 0; i < 20 && !video.videoWidth; i++) {
        await new Promise((r) => setTimeout(r, 50));
      }
      setCapturing(false);
      if (!video.videoWidth) {
        setError(t('cameraNotReady'));
        return;
      }
    }

    const scale = Math.min(1, MAX_EDGE / Math.max(video.videoWidth, video.videoHeight));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const verdict = assessQuality(ctx, canvas.width, canvas.height);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY),
    );
    if (!blob) return;

    stopStream();
    setError(null);
    setQuality(verdict);
    setPreview({ url: URL.createObjectURL(blob), blob });
    setMode('preview');
  }, [stopStream, t]);

  /** Fallback path: the native camera app or gallery, via a file input. */
  const onFilePicked = (file: File | undefined) => {
    if (!file) return;
    // A gallery/native-camera file is not on a canvas, so it is not quality-checked. Better
    // no warning than a wrong one.
    setQuality(null);
    setPreview({ url: URL.createObjectURL(file), blob: file });
    setMode('preview');
  };

  const submit = async () => {
    if (!preview || !field) return;
    setMode('uploading');
    setError(null);
    try {
      const image = await uploadImage(preview.blob, {
        field_id: field.fieldId,
        source: 'camera',
      });

      // A photo alone cannot produce a diagnosis — the score comes from lab chemistry.
      // Send the farmer to the manual form carrying the image id, so the photo is
      // attached to the analysis and fusion can use the soil type.
      router.push(`/capture/manual?image=${image.id}`);
    } catch (err) {
      setError(tError(err));
      setMode('preview');
    }
  };

  if (!ready) {
    return (
      <div className="fixed inset-0 w-screen h-screen bg-[#2D231B] flex items-center justify-center text-[#FFF9F0]">
        <Spinner label={t('loading')} />
      </div>
    );
  }

  if (!field) {
    router.replace('/');
    return null;
  }

  return (
    <div className="fixed inset-0 w-screen h-screen bg-[#2D231B] text-[#F3EFEA] overflow-y-auto flex flex-col">
      {/* Background Image matching Welcome and Signin */}
      <div 
        className="absolute inset-0 bg-cover bg-center pointer-events-none z-0 filter brightness-[0.5] contrast-[1.1] fixed"
        style={{
          backgroundImage: `url('https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?q=80&w=2000&auto=format&fit=crop')`
        }}
      />
      <div className="absolute inset-0 bg-black/55 pointer-events-none z-0 fixed" />

      {/* Top Header Bar */}
      <header className="relative z-10 flex items-center justify-between px-6 py-6 max-w-7xl mx-auto w-full">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#4A6B37] text-white text-lg shadow-md border border-[#658C4E]">🌱</span>
          <span className="font-bold tracking-wide text-xl text-[#FFF9F0] drop-shadow-md">Soil Health</span>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as any)}
            aria-label={t('selectLanguage' as any)}
            className="rounded-full bg-[#4E3D2F] border border-[#785F4A] px-4 py-2 text-xs font-medium text-[#FFF9F0] shadow-md outline-none cursor-pointer hover:bg-[#5C4837]"
          >
            <option value="en" className="bg-[#3D3025]">English</option>
            <option value="hi" className="bg-[#3D3025]">हिन्दी</option>
            <option value="kn" className="bg-[#3D3025]">ಕನ್ನಡ</option>
            <option value="te" className="bg-[#3D3025]">తెలుగు</option>
          </select>
        </div>
      </header>

      {/* Main Container */}
      <main className="relative z-10 flex-1 max-w-xl mx-auto w-full px-6 py-8 space-y-6">
        <Link
          href="/capture"
          className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-wider uppercase text-[#DCC7B0] hover:text-[#FFF9F0] transition-colors"
        >
          ← {t('back')}
        </Link>

        {notice && (
          <div className="rounded-2xl bg-[#5A452E]/90 border border-[#8C6D4A] p-4 text-[#FFD89B] text-sm shadow-xl">
            {notice}
          </div>
        )}

        {mode === 'checking' && (
          <div className="py-20 text-center">
            <Spinner label={t('startingCamera')} />
          </div>
        )}

        {mode === 'live' && (
          <div className="space-y-6">
            <div className="relative overflow-hidden rounded-3xl bg-black border border-[#6E5441] shadow-2xl">
              <video
                ref={videoRef}
                playsInline
                muted
                autoPlay
                className="aspect-[3/4] w-full object-cover"
              />
              {!frameReady && (
                <div
                  role="status"
                  className="absolute inset-0 flex items-center justify-center px-4 text-center text-sm text-[#FFF9F0] bg-black/60 backdrop-blur-sm"
                >
                  <Spinner label={t('startingCamera')} />
                </div>
              )}
            </div>

            {error && (
              <div className="rounded-2xl bg-[#5A2E2E]/80 border border-[#8C4E4E] p-4 text-[#FFB4AB] text-sm text-center">
                {error}
              </div>
            )}

            <button
              type="button"
              onClick={capture}
              disabled={!frameReady || capturing}
              className="w-full flex items-center justify-center gap-2 rounded-2xl bg-[#4A6B37] hover:bg-[#3D5A2E] text-white py-4 font-semibold shadow-xl shadow-black/30 transition-all hover:scale-[1.01] active:scale-[0.98] border border-[#658C4E] disabled:opacity-50 text-lg"
            >
              <span>📸 {capturing ? t('loading') : t('capture')}</span>
            </button>

            <div className="rounded-3xl bg-[#362B22]/90 backdrop-blur-xl border border-[#6E5441] p-6 shadow-2xl space-y-2">
              <p className="text-sm font-semibold text-[#FFF9F0]">💡 {t('photoTips')}</p>
              <ul className="space-y-1 text-sm text-[#D1C2B4]">
                <li>• {t('tipLight')}</li>
                <li>• {t('tipClose')}</li>
                <li>• {t('tipSteady')}</li>
                <li>• {t('tipClear')}</li>
              </ul>
            </div>
          </div>
        )}

        {mode === 'fallback' && (
          <div className="py-12 text-center">
            <label className="flex w-full cursor-pointer items-center justify-center gap-3 rounded-2xl bg-[#4A6B37] hover:bg-[#3D5A2E] px-6 py-5 text-lg font-semibold text-white shadow-xl border border-[#658C4E] transition-all">
              <span aria-hidden className="text-3xl">🖼</span>
              <span>{t('choosePhoto')}</span>
              <input
                type="file"
                accept="image/jpeg,image/png"
                capture="environment"
                className="hidden"
                onChange={(e) => onFilePicked(e.target.files?.[0])}
              />
            </label>
          </div>
        )}

        {(mode === 'preview' || mode === 'uploading') && preview && (
          <div className="space-y-6">
            <div className="overflow-hidden rounded-3xl bg-black border border-[#6E5441] shadow-2xl">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview.url}
                alt=""
                className="aspect-[3/4] w-full object-cover"
              />
            </div>

            {error && (
              <div className="rounded-2xl bg-[#5A2E2E]/80 border border-[#8C4E4E] p-4 text-[#FFB4AB] text-sm text-center">
                {error}
              </div>
            )}

            {quality && (
              <div className="rounded-2xl bg-[#5A452E]/90 border border-[#8C6D4A] p-4 text-[#FFD89B] text-sm shadow-xl">
                <p role="status" className="flex items-start gap-2">
                  <span aria-hidden>⚠</span>
                  <span>{quality === 'dark' ? t('photoDark') : t('photoBlurry')}</span>
                </p>
              </div>
            )}

            {mode === 'uploading' ? (
              <div className="py-10 text-center">
                <Spinner label={t('analysing')} />
              </div>
            ) : (
              <div className="space-y-3 pb-12">
                <button
                  type="button"
                  onClick={submit}
                  className="w-full flex items-center justify-center gap-2 rounded-2xl bg-[#4A6B37] hover:bg-[#3D5A2E] text-white py-4 font-semibold shadow-xl shadow-black/30 transition-all hover:scale-[1.01] active:scale-[0.98] border border-[#658C4E]"
                >
                  <span>✓ {quality ? t('useAnyway') : t('usePhoto')}</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    URL.revokeObjectURL(preview.url);
                    setPreview(null);
                    setQuality(null);
                    void startCamera();
                  }}
                  className="w-full flex items-center justify-center gap-2 rounded-2xl bg-[#4E3D2F] hover:bg-[#5C4837] text-[#FFF9F0] py-4 font-semibold border border-[#785F4A] transition-all"
                >
                  <span>↺ {t('retake')}</span>
                </button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}