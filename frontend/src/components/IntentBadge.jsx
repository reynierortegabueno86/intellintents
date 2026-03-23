import { getIntentColor, getIntentColorWithAlpha } from '../utils/colors';
import { formatCategoryName, getCategoryCode } from '../utils/formatCategoryName';

export default function IntentBadge({ label, parentLabel, size = 'sm' }) {
  const colorKey = parentLabel || label;
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
  if (parentLabel) {
    const code = getCategoryCode(parentLabel);
    return (
      <span className="inline-flex items-stretch rounded-md overflow-hidden" style={{ border: `1px solid ${getIntentColorWithAlpha(colorKey, 0.2)}` }}>
        <span
          className={`font-mono font-bold tracking-wider flex items-center ${codeSizes[size] || codeSizes.sm}`}
          style={{
            backgroundColor: getIntentColorWithAlpha(colorKey, 0.3),
            color,
            opacity: 0.7,
          }}
          title={formatCategoryName(parentLabel)}
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
          {formatCategoryName(label) || 'Unknown'}
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
