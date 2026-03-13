import { useEffect, useState, useRef } from 'react';
import { motion } from 'framer-motion';

function AnimatedCounter({ value, duration = 1.2 }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef(null);

  useEffect(() => {
    const num = typeof value === 'number' ? value : parseFloat(value);
    if (isNaN(num)) {
      setDisplay(value);
      return;
    }

    let start = 0;
    const startTime = performance.now();
    const isFloat = !Number.isInteger(num);

    function animate(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / (duration * 1000), 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + (num - start) * eased;
      setDisplay(isFloat ? current.toFixed(2) : Math.round(current));
      if (progress < 1) {
        ref.current = requestAnimationFrame(animate);
      }
    }

    ref.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(ref.current);
  }, [value, duration]);

  return <span>{typeof display === 'number' ? display.toLocaleString() : display}</span>;
}

export default function KPICard({ title, value, icon: Icon, trend, color = 'cyan', index = 0 }) {
  const colorMap = {
    cyan: { text: 'text-cyan-400', bg: 'bg-cyan-400/10', border: 'border-cyan-400/20', glow: 'shadow-cyan-400/10' },
    violet: { text: 'text-violet-400', bg: 'bg-violet-400/10', border: 'border-violet-400/20', glow: 'shadow-violet-400/10' },
    emerald: { text: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-400/20', glow: 'shadow-emerald-400/10' },
    pink: { text: 'text-pink-400', bg: 'bg-pink-400/10', border: 'border-pink-400/20', glow: 'shadow-pink-400/10' },
    orange: { text: 'text-orange-400', bg: 'bg-orange-400/10', border: 'border-orange-400/20', glow: 'shadow-orange-400/10' },
  };

  const c = colorMap[color] || colorMap.cyan;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, delay: index * 0.1, ease: 'easeOut' }}
      className={`glass-card p-5 kpi-pulse shadow-lg ${c.glow}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-lg ${c.bg} flex items-center justify-center`}>
          {Icon && <Icon size={20} className={c.text} />}
        </div>
        {trend !== undefined && trend !== null && (
          <span className={`text-xs font-semibold ${trend >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {trend >= 0 ? '+' : ''}{trend}%
          </span>
        )}
      </div>
      <div className="text-2xl font-bold text-white mb-1">
        <AnimatedCounter value={value} />
      </div>
      <div className="text-sm text-slate-400">{title}</div>
    </motion.div>
  );
}
