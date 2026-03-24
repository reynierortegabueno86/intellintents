import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Filter, ChevronDown, ChevronUp } from 'lucide-react';
import { getIntentColor } from '../utils/colors';
import { formatIntentCompact } from '../utils/formatCategoryName';

export default function FilterPanel({
  datasets = [],
  taxonomies = [],
  intents = [],
  intentHierarchy = {},
  selectedDataset,
  selectedTaxonomy,
  onDatasetChange,
  onTaxonomyChange,
  selectedIntents = [],
  onIntentsChange,
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="glass-card overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full px-4 py-3 text-sm font-medium text-slate-300 hover:text-white transition-colors"
      >
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-cyan-400" />
          <span>Filters</span>
          {(selectedDataset || selectedTaxonomy) && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-400/10 text-cyan-400 border border-cyan-400/20">
              {[
                datasets.find((d) => String(d.id) === String(selectedDataset))?.name,
                taxonomies.find((t) => String(t.id) === String(selectedTaxonomy))?.name,
              ].filter(Boolean).join(' / ')}
            </span>
          )}
        </div>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-4 border-t border-slate-700/50 pt-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Dataset selector */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Dataset</label>
                  <select
                    value={selectedDataset ?? ''}
                    onChange={(e) => onDatasetChange?.(e.target.value)}
                    className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                  >
                    <option value="">Select dataset...</option>
                    {datasets.map((d) => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>

                {/* Taxonomy selector */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Taxonomy</label>
                  <select
                    value={selectedTaxonomy ?? ''}
                    onChange={(e) => onTaxonomyChange?.(e.target.value)}
                    className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                  >
                    <option value="">Select taxonomy...</option>
                    {taxonomies.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Intent multi-select */}
              {intents.length > 0 && onIntentsChange && (
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Filter by Intents</label>
                  <div className="flex flex-wrap gap-1.5 bg-slate-800/40 rounded-lg p-2">
                    {intents.map((intent) => {
                      const isSelected = selectedIntents.includes(intent);
                      const color = getIntentColor(intentHierarchy[intent] || intent);
                      return (
                        <button
                          key={intent}
                          onClick={() => {
                            if (isSelected) {
                              onIntentsChange(selectedIntents.filter((i) => i !== intent));
                            } else {
                              onIntentsChange([...selectedIntents, intent]);
                            }
                          }}
                          className={`text-[11px] px-2 py-1 rounded-md border transition-all ${
                            isSelected
                              ? 'border-current opacity-100'
                              : 'border-slate-700/50 opacity-50 hover:opacity-75'
                          }`}
                          style={{ color, borderColor: isSelected ? color : undefined }}
                        >
                          {formatIntentCompact(intent, intentHierarchy)}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
