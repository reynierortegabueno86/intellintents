/**
 * Strip HTML tags and decode HTML entities from a string.
 * Returns clean plain text safe for rendering.
 */
const ENTITY_MAP = {
  '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"',
  '&#39;': "'", '&apos;': "'", '&nbsp;': ' ', '&ndash;': '\u2013',
  '&mdash;': '\u2014', '&euro;': '\u20AC', '&pound;': '\u00A3',
  '&copy;': '\u00A9', '&reg;': '\u00AE', '&trade;': '\u2122',
};

export function cleanHtml(text) {
  if (!text) return '';
  // Strip HTML tags
  let clean = text.replace(/<[^>]*>/g, '');
  // Decode named entities
  clean = clean.replace(/&[a-zA-Z]+;/g, (match) => ENTITY_MAP[match] || match);
  // Decode numeric entities (&#123; and &#x1F;)
  clean = clean.replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)));
  clean = clean.replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
  return clean;
}
