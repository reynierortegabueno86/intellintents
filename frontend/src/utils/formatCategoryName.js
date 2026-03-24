/**
 * Convert an underscore-separated DB category name to display text.
 *
 * Root categories (UPPER_CASE in DB) → Title Case:
 *   ONBOARDING_KYC  → "Onboarding Kyc"
 *   PRODUCT_DISCOVERY → "Product Discovery"
 *
 * Subcategories (lower_case in DB) → lowercase:
 *   open_account     → "open account"
 *   state_risk_tolerance → "state risk tolerance"
 *
 * Detection: if the name (ignoring underscores) is all uppercase → root.
 */
export function formatCategoryName(name) {
  if (!name) return '';
  const stripped = name.replace(/_/g, '');
  const isRoot = stripped === stripped.toUpperCase() && stripped !== stripped.toLowerCase();
  const spaced = name.replace(/_/g, ' ');
  if (isRoot) {
    return spaced.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return spaced.toLowerCase();
}

/**
 * Generate a 3-letter uppercase code from a category name.
 *
 *   ONBOARDING_KYC      → "ONK"
 *   INVESTOR_PROFILING   → "INP"
 *   PRODUCT_DISCOVERY    → "PRD"
 *   COMPLAINT            → "COM"
 *   GREETING             → "GRE"
 */
export function getCategoryCode(name) {
  if (!name) return '';
  const words = name.replace(/_/g, ' ').trim().split(/\s+/);
  if (words.length >= 3) {
    return (words[0][0] + words[1][0] + words[2][0]).toUpperCase();
  }
  if (words.length === 2) {
    return (words[0].slice(0, 2) + words[1][0]).toUpperCase();
  }
  return words[0].slice(0, 3).toUpperCase();
}

/**
 * Returns true if name is an UPPER_CASE root category (e.g., "ONBOARDING_KYC").
 */
export function isRootCategory(name) {
  if (!name) return false;
  const stripped = name.replace(/_/g, '');
  return stripped === stripped.toUpperCase() && stripped !== stripped.toLowerCase();
}

/**
 * Compact intent label for charts, tables, and tooltips.
 *
 *   formatIntentCompact("open_account", hierarchy)   → "ONK: open account"
 *   formatIntentCompact("ONBOARDING_KYC", hierarchy) → "ONK: general"
 *   formatIntentCompact("UNKNOWN", {})               → "UNK: general"
 *
 * Returns a short string suitable for axis labels, table headers, etc.
 */
export function formatIntentCompact(label, hierarchy = {}) {
  if (!label) return '';
  const parent = hierarchy[label];
  if (parent) {
    return `${getCategoryCode(parent)}: ${formatCategoryName(label)}`;
  }
  if (isRootCategory(label)) {
    return `${getCategoryCode(label)}: general`;
  }
  return formatCategoryName(label);
}

/**
 * Convert user input to DB storage format.
 *   "Open Account" → "OPEN_ACCOUNT" (root) or "open_account" (child)
 */
export function toCategoryStorageName(name, isRoot) {
  if (!name) return '';
  const normalized = name.trim().replace(/\s+/g, '_');
  return isRoot ? normalized.toUpperCase() : normalized.toLowerCase();
}
