import { getIntentColor, getIntentColorWithAlpha } from '../utils/colors';
import { formatCategoryName } from '../utils/formatCategoryName';

export default function IntentBadge({ label, size = 'sm' }) {
  const color = getIntentColor(label);
  const bgColor = getIntentColorWithAlpha(label, 0.15);
  const borderColor = getIntentColorWithAlpha(label, 0.3);

  const sizeClasses = {
    xs: 'text-[10px] px-1.5 py-0.5',
    sm: 'text-xs px-2.5 py-0.5',
    md: 'text-sm px-3 py-1',
  };

  return (
    <span
      className={`intent-badge ${sizeClasses[size] || sizeClasses.sm}`}
      style={{
        color,
        backgroundColor: bgColor,
        border: `1px solid ${borderColor}`,
      }}
    >
      {formatCategoryName(label) || 'Unknown'}
    </span>
  );
}
