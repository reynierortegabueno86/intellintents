import { motion } from 'framer-motion';
import { getIntentColor, getIntentColorWithAlpha } from '../utils/colors';
import { formatCategoryName } from '../utils/formatCategoryName';

/**
 * Minimalist fancy visualization of an intent sequence.
 * Shows colored dots connected by thin lines, with a subtle glow.
 * Each dot represents a turn's intent, laid out horizontally.
 */
export function IntentDotSequence({ intents, size = 8, gap = 2 }) {
  if (!intents || intents.length === 0) return null;

  const dotSize = size;
  const spacing = dotSize + gap;
  const totalWidth = intents.length * spacing - gap;

  return (
    <svg
      width={Math.min(totalWidth, 320)}
      height={dotSize + 4}
      viewBox={`0 0 ${totalWidth} ${dotSize + 4}`}
      className="flex-shrink-0"
    >
      {/* Connecting line */}
      <line
        x1={dotSize / 2}
        y1={(dotSize + 4) / 2}
        x2={totalWidth - dotSize / 2}
        y2={(dotSize + 4) / 2}
        stroke="#334155"
        strokeWidth={1}
        strokeDasharray="2,2"
      />
      {/* Dots */}
      {intents.map((intent, i) => {
        const color = getIntentColor(intent);
        const cx = i * spacing + dotSize / 2;
        const cy = (dotSize + 4) / 2;
        return (
          <g key={i}>
            <circle
              cx={cx}
              cy={cy}
              r={dotSize / 2}
              fill={color}
              opacity={0.9}
            />
            <circle
              cx={cx}
              cy={cy}
              r={dotSize / 2 + 2}
              fill="none"
              stroke={color}
              strokeWidth={0.5}
              opacity={0.3}
            />
          </g>
        );
      })}
    </svg>
  );
}

/**
 * Shows intent sequences per speaker as horizontal lane-style strips.
 * Each speaker gets a labeled row with colored intent dots.
 */
export function SpeakerIntentLanes({ turns, intentHierarchy = {} }) {
  if (!turns || turns.length === 0) return null;

  // Group turns by speaker preserving order
  const speakers = {};
  for (const t of turns) {
    const spk = t.speaker || 'unknown';
    if (!speakers[spk]) speakers[spk] = [];
    speakers[spk].push(t.intent_label);
  }

  const speakerEntries = Object.entries(speakers);

  return (
    <div className="space-y-1.5">
      {speakerEntries.map(([speaker, intents], idx) => (
        <motion.div
          key={speaker}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: idx * 0.05 }}
          className="flex items-center gap-2"
        >
          <span className={`text-[10px] font-mono uppercase tracking-wider w-16 text-right flex-shrink-0 ${
            speaker === 'user' ? 'text-cyan-400/70' : 'text-violet-400/70'
          }`}>
            {speaker}
          </span>
          <div className="flex items-center gap-0.5">
            {intents.map((intent, i) => {
              const colorKey = intentHierarchy[intent] || intent;
              const color = getIntentColor(colorKey);
              const parentName = intentHierarchy[intent];
              const tooltip = parentName
                ? `${formatCategoryName(parentName)}: ${formatCategoryName(intent)}`
                : formatCategoryName(intent);
              return (
                <motion.div
                  key={i}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: idx * 0.05 + i * 0.02, type: 'spring', stiffness: 500 }}
                  className="group relative"
                >
                  <div
                    className="w-5 h-2 rounded-sm"
                    style={{ backgroundColor: color, opacity: 0.85 }}
                  />
                  {/* Tooltip */}
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10">
                    <div className="px-2 py-1 rounded bg-slate-800 border border-slate-700 text-[10px] text-white whitespace-nowrap shadow-lg">
                      {tooltip}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      ))}
    </div>
  );
}

/**
 * Compact conversation summary strip: shows all intents as a continuous
 * gradient-like bar of colored segments.
 */
export function IntentStrip({ turns, height = 6, intentHierarchy = {} }) {
  if (!turns || turns.length === 0) return null;

  const segWidth = 100 / turns.length;

  return (
    <div className="flex w-full rounded-full overflow-hidden" style={{ height }}>
      {turns.map((t, i) => {
        const colorKey = intentHierarchy[t.intent_label] || t.intent_label;
        const color = getIntentColor(colorKey);
        const parentName = intentHierarchy[t.intent_label];
        const intentDisplay = parentName
          ? `${formatCategoryName(parentName)}: ${formatCategoryName(t.intent_label)}`
          : formatCategoryName(t.intent_label);
        return (
          <div
            key={i}
            className="group relative"
            style={{
              width: `${segWidth}%`,
              backgroundColor: color,
              opacity: 0.8,
            }}
          >
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10">
              <div className="px-2 py-1 rounded bg-slate-800 border border-slate-700 text-[10px] text-white whitespace-nowrap shadow-lg">
                <span className="font-medium">{t.speaker}</span>: {intentDisplay}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
