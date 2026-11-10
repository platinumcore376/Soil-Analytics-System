/* Catalogue parity check.
 *
 * TypeScript types keys against the ENGLISH catalogue, so `t('typo')` is a build error. What
 * it cannot see is a key that exists in English but is missing from Hindi, Kannada or Telugu —
 * i18next would fall back to the English string (or the key itself), and a farmer using Telugu
 * would get an English sentence with no warning anywhere.
 *
 * This closes that hole. It also checks that interpolation placeholders match across
 * languages: `{{min}}` present in English but written `{min}` or omitted in Telugu renders as
 * a literal brace or drops the number entirely.
 *
 * Wired into `npm run typecheck` and `npm run build`, so it gates the same things tsc does.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const LOCALES_DIR = new URL('../src/app/i18n/locales/', import.meta.url).pathname.replace(
  /^\/([A-Za-z]:)/,
  '$1',
);
const REFERENCE = 'en';

const langs = readdirSync(LOCALES_DIR, { withFileTypes: true })
  .filter((d) => d.isDirectory())
  .map((d) => d.name);

if (!langs.includes(REFERENCE)) {
  console.error(`check-locales: reference catalogue '${REFERENCE}' not found`);
  process.exit(1);
}

const load = (lang) =>
  JSON.parse(readFileSync(join(LOCALES_DIR, lang, 'common.json'), 'utf8'));

const placeholders = (value) =>
  new Set([...String(value).matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]));

const reference = load(REFERENCE);
const referenceKeys = Object.keys(reference);
const problems = [];

for (const lang of langs) {
  if (lang === REFERENCE) continue;
  const cat = load(lang);

  for (const key of referenceKeys) {
    if (!(key in cat)) {
      problems.push(`${lang}: missing key '${key}'`);
      continue;
    }
    if (String(cat[key]).trim() === '') {
      problems.push(`${lang}: empty value for '${key}'`);
      continue;
    }
    const want = placeholders(reference[key]);
    const got = placeholders(cat[key]);
    for (const p of want) {
      if (!got.has(p)) problems.push(`${lang}: '${key}' is missing placeholder {{${p}}}`);
    }
    for (const p of got) {
      if (!want.has(p)) problems.push(`${lang}: '${key}' has unexpected placeholder {{${p}}}`);
    }
  }

  for (const key of Object.keys(cat)) {
    if (!(key in reference)) {
      problems.push(`${lang}: key '${key}' is not in the ${REFERENCE} catalogue`);
    }
  }

  // A single-brace placeholder is almost always a leftover from the pre-i18next syntax.
  for (const [key, value] of Object.entries(cat)) {
    if (/(?<!\{)\{\w+\}(?!\})/.test(String(value))) {
      problems.push(`${lang}: '${key}' uses {single} braces; i18next needs {{double}}`);
    }
  }
}

if (problems.length) {
  console.error('check-locales: FAILED');
  for (const p of problems) console.error('  ' + p);
  process.exit(1);
}

console.log(
  `check-locales: OK — ${referenceKeys.length} keys x ${langs.length} languages (${langs.join(', ')})`,
);
