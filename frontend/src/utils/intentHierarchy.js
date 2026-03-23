/**
 * Build a lookup map from leaf intent label → parent category name.
 *
 * Input: flat array of categories from GET /taxonomies/{id}
 *   [{ id: 1, name: "ONBOARDING_KYC", parent_id: null },
 *    { id: 5, name: "open_account", parent_id: 1 }, ...]
 *
 * Output: { "open_account": "ONBOARDING_KYC", "verify_identity": "ONBOARDING_KYC", ... }
 */
export function buildIntentHierarchy(categories) {
  if (!categories || !categories.length) return {};

  const byId = {};
  for (const cat of categories) byId[cat.id] = cat;

  const map = {};
  for (const cat of categories) {
    if (cat.parent_id && byId[cat.parent_id]) {
      map[cat.name] = byId[cat.parent_id].name;
    }
  }
  return map;
}

/**
 * Group a flat intent_distribution { label: count } by parent category.
 *
 * Returns: [{ parent: "ONBOARDING_KYC", total: 245, children: [{ label: "open_account", count: 120 }, ...] }, ...]
 * Labels without a parent are grouped under their own name.
 */
export function groupDistributionByParent(distribution, hierarchy) {
  if (!distribution) return [];

  const groups = {};
  for (const [label, count] of Object.entries(distribution)) {
    const parent = hierarchy[label] || label;
    if (!groups[parent]) groups[parent] = { parent, total: 0, children: [] };
    groups[parent].total += count;
    if (hierarchy[label]) {
      groups[parent].children.push({ label, count });
    }
  }

  // Sort groups by total descending, children by count descending
  const result = Object.values(groups).sort((a, b) => b.total - a.total);
  for (const g of result) g.children.sort((a, b) => b.count - a.count);
  return result;
}
