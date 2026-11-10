/* The set of valid translation keys, derived from the English catalogue.
 *
 * Its own module so both client components (`LocaleProvider`) and plain data modules
 * (`status.ts`) can use it without pulling in `'use client'` code or the i18next runtime.
 *
 * WHY THIS MATTERS
 * i18next resolves keys at runtime and returns the key itself on a miss, so `t('helpNitrogn')`
 * would silently render the literal string `helpNitrogn` to a farmer. Typing keys against the
 * English JSON turns that into a build error, and because `next-i18next-lint.ts` also checks
 * the other three catalogues have identical keys, a missing Telugu translation fails the build
 * too — not just a missing English one.
 */
import type en from '@/app/i18n/locales/en/common.json';

export type TKey = keyof typeof en;
