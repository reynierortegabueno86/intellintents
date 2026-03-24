import { getIntentColor, getIntentColorWithAlpha } from '../utils/colors';
import { formatCategoryName, getCategoryCode, isRootCategory } from '../utils/formatCategoryName';

export default function IntentBadge({ label, parentLabel, size = 'sm' }) {
  // Auto-detect: if label is a root category with no explicit parentLabel,
  // treat it as a parent with "general" as the sub-intent display name.
  const isAutoRoot = !parentLabel && isRootCategory(label);
  const effectiveParent = parentLabel || (isAutoRoot ? label : null);
  const colorKey = effectiveParent || label;
  const color = getIntentColor(colorKey);

  const childSizes = {
    xs: 'text-[10px] px-1.5 py-0.5',
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-2.5 py-1',
  };
  const codeSizes = {
    xs: 'text-[8px] px-1 py-0.5',
    sm: 'text-[9px] px-1.5 py-0.5',
    md: 'text-[10px] px-2 py-1',
  };

  // Hierarchical: two-segment layered badge [CODE | sub-intent]
  if (effectiveParent) {
    const code = getCategoryCode(effectiveParent);
    const displayName = isAutoRoot ? 'general' : (formatCategoryName(label) || 'Unknown');
    return (
      <span className="inline-flex items-stretch rounded-md overflow-hidden" style={{ border: `1px solid ${getIntentColorWithAlpha(colorKey, 0.2)}` }}>
        <span
          className={`font-mono font-bold tracking-wider flex items-center ${codeSizes[size] || codeSizes.sm}`}
          style={{
            backgroundColor: getIntentColorWithAlpha(colorKey, 0.3),
            color,
            opacity: 0.7,
          }}
          title={formatCategoryName(effectiveParent)}
        >
          {code}
        </span>
        <span
          className={`flex items-center ${childSizes[size] || childSizes.sm}`}
          style={{
            backgroundColor: getIntentColorWithAlpha(colorKey, 0.1),
            color,
          }}
        >
          {displayName}
        </span>
      </span>
    );
  }

  // Flat: single badge (no parent)
  return (
    <span
      className={`intent-badge ${childSizes[size] || childSizes.sm}`}
      style={{
        color,
        backgroundColor: getIntentColorWithAlpha(colorKey, 0.15),
        border: `1px solid ${getIntentColorWithAlpha(colorKey, 0.3)}`,
      }}
    >
      {formatCategoryName(label) || 'Unknown'}
    </span>
  );
}
