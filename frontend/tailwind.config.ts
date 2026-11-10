import type { Config } from 'tailwindcss';

// Palette carries the diagnosis. Every status colour is paired with an icon and a number
// in the UI, so the meaning survives greyscale printing and colour-vision deficiency.
//
// Re-tinted to an earth palette (soil green / clay / ochre) in place of the generic
// red/amber/green triad. Every ratio below was recomputed against the new `surface`
// value — darkening surface shifts every contrast pair in this file, so a value that
// passed against the old #f7f7f5 is not guaranteed to pass against this one.
const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        /* FILL colours — used as backgrounds behind white text, or as chips and bars.
         * White on each of these clears 3:1, the bar for large text and UI components.
         *
         *   ok       #4f7942   5.07:1
         *   low      #b4482d   5.38:1
         *   caution  #c9821a   3.14:1   (amber must go quite dark to pass at all —
         *                                same constraint as the original palette)
         */
        low: '#b4482d',       // deficient / critical — clay red, not stop-sign red
        caution: '#c9821a',   // high / borderline — dark ochre
        ok: '#4f7942',        // adequate / good — sprout green

        /* TEXT colours — darkened until they clear WCAG AA 4.5:1 as coloured text on
         * `surface` (#f3ecdd). Measured on surface, not white, because that's the
         * darker of the two backgrounds these actually sit on (same reasoning as the
         * original file: darkening `ok` itself would have dulled every chip and bar).
         *
         *   ok-text      #2f4a27   8.38:1
         *   low-text     #7a2f1e   7.92:1
         *   caution-text #7a5a17   5.41:1
         */
        'ok-text': '#2f4a27',
        'low-text': '#7a2f1e',
        'caution-text': '#7a5a17',

        ink: '#2b2118',        // soil brown, 13.39:1 on surface
        muted: '#6e6152',      // 5.11:1 on surface — original was 4.51 ("only just");
                                // kept the same margin rather than tightening it
        surface: '#f3ecdd',    // warm parchment, replaces neutral #f7f7f5
      },
      fontSize: {
        // Bumped from Tailwind defaults: this is used one-handed, outdoors, on a phone.
        base: ['1.0625rem', { lineHeight: '1.6' }],
        lg: ['1.25rem', { lineHeight: '1.5' }],
      },
      minHeight: { tap: '3rem' },  // 48px minimum touch target
    },
  },
  plugins: [],
};

export default config;