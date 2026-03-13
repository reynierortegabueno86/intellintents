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
 * Convert user input to DB storage format.
 *   "Open Account" → "OPEN_ACCOUNT" (root) or "open_account" (child)
 */
export function toCategoryStorageName(name, isRoot) {
  if (!name) return '';
  const normalized = name.trim().replace(/\s+/g, '_');
  return isRoot ? normalized.toUpperCase() : normalized.toLowerCase();
}
