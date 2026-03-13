import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Cpu, Play, Loader2, CheckCircle, AlertCircle,
  ChevronDown, ChevronRight, MessageSquare, Hash, Sparkles
} from 'lucide-react';
import { useApi } from '../hooks/useApi';
import * as api from '../utils/api';
import IntentBadge from '../components/IntentBadge';
import { SpeakerIntentLanes, IntentStrip } from '../components/IntentSequence';
import { getIntentColor } from '../utils/colors';

function Skeleton({ className }) {
  return <div className={`skeleton ${className}`} />;
}

// Dynamic config form based on method's config_schema
function ConfigForm({ schema, config, onChange }) {
  if (!schema || schema.length === 0) {
    return (
      <div className="text-xs text-slate-600 italic py-2">
        No configuration needed for this method.
      </div>
    );
  }

  const handleChange = (key, value) => {
    onChange({ ...config, [key]: value });
  };

  return (
    <div className="space-y-3">
      {schema.map((field) => (
        <div key={field.key}>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs text-slate-400 font-medium">{field.label}</label>
            {field.type === 'range' && (
              <span className="text-xs font-mono text-cyan-400">
                {config[field.key] ?? field.default ?? field.min}
              </span>
            )}
          </div>
          {field.description && (
            <p className="text-[10px] text-slate-600 mb-1.5">{field.description}</p>
          )}
          {field.type === 'checkbox' ? (
            <label className="inline-flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={!!(config[field.key] ?? field.default)}
                onChange={(e) => handleChange(field.key, e.target.checked)}
                className="sr-only peer"
              />
              <div className="relative w-9 h-5 bg-slate-700/80 rounded-full peer peer-checked:bg-cyan-500/40 transition-colors
                after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-slate-400 after:rounded-full after:h-4 after:w-4 after:transition-all
                peer-checked:after:translate-x-4 peer-checked:after:bg-cyan-400" />
              <span className="text-xs text-slate-500 group-hover:text-slate-400 transition-colors">
                {config[field.key] ?? field.default ? 'Enabled' : 'Disabled'}
              </span>
            </label>
          ) : field.type === 'range' ? (
            <input
              type="range"
              min={field.min}
              max={field.max}
              step={field.step}
              value={config[field.key] ?? field.default ?? field.min}
              onChange={(e) => handleChange(field.key, parseFloat(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-full appearance-none cursor-pointer
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-cyan-400 [&::-webkit-slider-thumb]:shadow-lg
                [&::-webkit-slider-thumb]:shadow-cyan-400/30"
            />
          ) : field.type === 'number' ? (
            <input
              type="number"
              value={config[field.key] ?? ''}
              placeholder={field.default != null ? String(field.default) : 'Optional'}
              onChange={(e) => handleChange(field.key, e.target.value ? parseInt(e.target.value) : undefined)}
              className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 font-mono focus:outline-none focus:border-cyan-400/50"
            />
          ) : field.type === 'select' ? (
            <select
              value={config[field.key] ?? field.default ?? ''}
              onChange={(e) => handleChange(field.key, e.target.value)}
              className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
            >
              {(field.options || []).map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          ) : field.type === 'password' ? (
            <input
              type="password"
              value={config[field.key] ?? ''}
              placeholder={field.default != null ? String(field.default) : 'Optional'}
              onChange={(e) => handleChange(field.key, e.target.value || undefined)}
              className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 font-mono focus:outline-none focus:border-cyan-400/50"
            />
          ) : field.type === 'json' ? (
            <textarea
              value={config[field.key] != null ? (typeof config[field.key] === 'string' ? config[field.key] : JSON.stringify(config[field.key], null, 2)) : ''}
              placeholder='{"intent_name": ["keyword1", "keyword2"]}'
              onChange={(e) => {
                try { handleChange(field.key, JSON.parse(e.target.value)); } catch {
                  handleChange(field.key, e.target.value);
                }
              }}
              rows={3}
              className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-xs text-slate-300 font-mono focus:outline-none focus:border-cyan-400/50 resize-none"
            />
          ) : (
            <input
              type="text"
              value={config[field.key] ?? ''}
              onChange={(e) => handleChange(field.key, e.target.value)}
              className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
            />
          )}
        </div>
      ))}
    </div>
  );
}

// Single collapsible conversation card
function ConversationCard({ conversation, index }) {
  const [expanded, setExpanded] = useState(false);
  const turns = conversation.turns || [];
  const turnCount = turns.length;
  const uniqueIntents = [...new Set(turns.map(t => t.intent_label))];
  const avgConfidence = turns.reduce((s, t) => s + (t.confidence || 0), 0) / (turnCount || 1);

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.02 }}
      className="glass-card overflow-hidden"
    >
      {/* Collapsed header - always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-slate-800/30 transition-colors text-left"
      >
        {/* Expand icon */}
        <div className="text-slate-500 flex-shrink-0">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>

        {/* Conversation ID */}
        <span className="text-xs font-mono text-slate-500 w-20 flex-shrink-0">
          #{conversation.conversation_id}
        </span>

        {/* Stats pills */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-slate-800/80 text-slate-400">
            <MessageSquare size={10} />
            {turnCount} turns
          </span>
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-slate-800/80 text-slate-400">
            <Hash size={10} />
            {uniqueIntents.length} intents
          </span>
          <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-slate-800/80 text-slate-400">
            <Sparkles size={10} />
            {(avgConfidence * 100).toFixed(0)}% avg
          </span>
        </div>

        {/* Intent strip - the fancy minimalist sequence viz */}
        <div className="flex-1 min-w-0 mx-3">
          <IntentStrip turns={turns} height={6} />
        </div>

        {/* Unique intent badges (compact) */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {uniqueIntents.slice(0, 4).map((intent) => (
            <div
              key={intent}
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ backgroundColor: getIntentColor(intent) }}
              title={intent}
            />
          ))}
          {uniqueIntents.length > 4 && (
            <span className="text-[9px] text-slate-600">+{uniqueIntents.length - 4}</span>
          )}
        </div>
      </button>

      {/* Expanded content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-slate-800/50 px-4 py-3 space-y-4">
              {/* Speaker intent lanes */}
              <div className="bg-slate-800/20 rounded-lg p-3">
                <p className="text-[10px] text-slate-600 uppercase tracking-wider mb-2 font-semibold">
                  Intent Sequence by Speaker
                </p>
                <SpeakerIntentLanes turns={turns} />
              </div>

              {/* Turn-by-turn details */}
              <div className="space-y-1">
                {turns.map((turn, ti) => (
                  <motion.div
                    key={turn.turn_id || ti}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: ti * 0.03 }}
                    className={`flex gap-3 py-2 px-3 rounded-lg transition-colors hover:bg-slate-800/20 ${
                      turn.speaker === 'user'
                        ? 'border-l-2 border-cyan-400/30'
                        : 'border-l-2 border-violet-400/30'
                    }`}
                  >
                    {/* Turn index */}
                    <span className="text-[10px] font-mono text-slate-600 w-5 flex-shrink-0 pt-1 text-right">
                      {turn.turn_index ?? ti + 1}
                    </span>

                    {/* Speaker label */}
                    <span className={`text-[10px] font-mono uppercase w-14 flex-shrink-0 pt-1 ${
                      turn.speaker === 'user' ? 'text-cyan-400/70' : 'text-violet-400/70'
                    }`}>
                      {turn.speaker}
                    </span>

                    {/* Text */}
                    <p className="text-xs text-slate-300 flex-1 min-w-0 leading-relaxed">
                      {turn.text}
                    </p>

                    {/* Intent + confidence */}
                    <div className="flex items-start gap-2 flex-shrink-0">
                      <IntentBadge label={turn.intent_label} size="xs" />
                      <div className="flex items-center gap-1 pt-0.5">
                        <div className="w-10 h-1 bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${(turn.confidence * 100).toFixed(0)}%`,
                              backgroundColor: getIntentColor(turn.intent_label),
                              opacity: 0.7,
                            }}
                          />
                        </div>
                        <span className="text-[9px] text-slate-600 font-mono w-7">
                          {(turn.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function Classification() {
  const { data: datasets } = useApi(api.getDatasets, []);
  const { data: taxonomies } = useApi(api.getTaxonomies, []);
  const { data: methods } = useApi(api.getClassifyMethods, []);

  const [selectedDataset, setSelectedDataset] = useState('');
  const [selectedTaxonomy, setSelectedTaxonomy] = useState('');
  const [selectedMethod, setSelectedMethod] = useState('');
  const [config, setConfig] = useState({});
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState(null);
  const [results, setResults] = useState(null);
  const [loadingResults, setLoadingResults] = useState(false);

  // Auto-select first options
  useEffect(() => {
    if (datasets?.length && !selectedDataset) setSelectedDataset(datasets[0].id);
  }, [datasets]);
  useEffect(() => {
    if (taxonomies?.length && !selectedTaxonomy) setSelectedTaxonomy(taxonomies[0].id);
  }, [taxonomies]);
  useEffect(() => {
    if (methodList.length && !selectedMethod) setSelectedMethod(methodList[0].id);
  }, [methods]);

  const methodList = useMemo(() => {
    if (!methods) return [];
    return Array.isArray(methods) ? methods : methods.methods || [];
  }, [methods]);

  const selectedMethodObj = useMemo(
    () => methodList.find(m => (m.id || m.name || m) === selectedMethod),
    [methodList, selectedMethod]
  );

  // Reset config when method changes
  useEffect(() => {
    if (selectedMethodObj?.config_schema) {
      const defaults = {};
      for (const field of selectedMethodObj.config_schema) {
        if (field.default != null) defaults[field.key] = field.default;
      }
      setConfig(defaults);
    } else {
      setConfig({});
    }
  }, [selectedMethod]);

  const handleClassify = async () => {
    if (!selectedDataset || !selectedTaxonomy || !selectedMethod) return;
    setRunning(true);
    setStatus(null);
    try {
      // Clean config: remove undefined/empty values
      const cleanConfig = {};
      for (const [k, v] of Object.entries(config)) {
        if (v !== undefined && v !== '' && v !== null) cleanConfig[k] = v;
      }
      await api.classify({
        dataset_id: selectedDataset,
        taxonomy_id: selectedTaxonomy,
        method: selectedMethod,
        config: Object.keys(cleanConfig).length > 0 ? cleanConfig : undefined,
      });
      setStatus({ type: 'success', message: 'Classification completed successfully!' });
      setLoadingResults(true);
      const res = await api.getClassifyResults(selectedDataset, selectedTaxonomy);
      setResults(res);
    } catch (err) {
      setStatus({ type: 'error', message: err.message });
    } finally {
      setRunning(false);
      setLoadingResults(false);
    }
  };

  const loadResults = async () => {
    if (!selectedDataset || !selectedTaxonomy) return;
    setLoadingResults(true);
    try {
      const res = await api.getClassifyResults(selectedDataset, selectedTaxonomy);
      setResults(res);
    } catch {
      setResults(null);
    } finally {
      setLoadingResults(false);
    }
  };

  // Results are now grouped by conversation
  const conversations = useMemo(() => {
    if (!results) return [];
    if (Array.isArray(results) && results[0]?.turns) return results;
    // Fallback: flat results -> group by conversation_id
    if (Array.isArray(results) && results[0]?.conversation_id) {
      const map = {};
      for (const r of results) {
        const cid = r.conversation_id;
        if (!map[cid]) map[cid] = { conversation_id: cid, turns: [] };
        map[cid].turns.push(r);
      }
      return Object.values(map);
    }
    return [];
  }, [results]);

  const totalTurns = conversations.reduce((s, c) => s + (c.turns?.length || 0), 0);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      <div>
        <h1 className="text-2xl font-bold text-white">Classification</h1>
        <p className="text-sm text-slate-500 mt-1">Run intent classification on your datasets</p>
      </div>

      {/* Control Panel */}
      <div className="glass-card p-6 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Dataset</label>
            <select
              value={selectedDataset}
              onChange={(e) => setSelectedDataset(e.target.value)}
              className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2.5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
            >
              <option value="">Select dataset...</option>
              {datasets?.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Taxonomy</label>
            <select
              value={selectedTaxonomy}
              onChange={(e) => setSelectedTaxonomy(e.target.value)}
              className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2.5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
            >
              <option value="">Select taxonomy...</option>
              {taxonomies?.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Classification Method</label>
            <select
              value={selectedMethod}
              onChange={(e) => setSelectedMethod(e.target.value)}
              className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2.5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
            >
              <option value="">Select method...</option>
              {methodList.map((m) => {
                const id = m.id || m.name || m;
                const label = m.name || m;
                return <option key={id} value={id}>{label}</option>;
              })}
            </select>
          </div>
        </div>

        {/* Method description */}
        {selectedMethodObj && (
          <div className="text-xs text-slate-500 bg-slate-800/30 rounded-lg px-3 py-2 border border-slate-800/50">
            <span className="text-slate-400 font-medium">{selectedMethodObj.name}:</span>{' '}
            {selectedMethodObj.description}
          </div>
        )}

        {/* Dynamic Config Form */}
        {selectedMethodObj && (
          <div className="bg-slate-800/20 rounded-lg p-4 border border-slate-800/30">
            <h4 className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-3">
              Configuration
            </h4>
            <ConfigForm
              schema={selectedMethodObj.config_schema || []}
              config={config}
              onChange={setConfig}
            />
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleClassify}
            disabled={running || !selectedDataset || !selectedTaxonomy || !selectedMethod}
            className="flex items-center gap-2 bg-gradient-to-r from-cyan-500/20 to-violet-500/20 hover:from-cyan-500/30 hover:to-violet-500/30 text-white border border-cyan-400/30 rounded-lg px-5 py-2.5 text-sm font-medium transition-all disabled:opacity-50"
          >
            {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {running ? 'Classifying...' : 'Run Classification'}
          </button>
          <button
            onClick={loadResults}
            disabled={!selectedDataset || !selectedTaxonomy}
            className="flex items-center gap-2 bg-slate-800/50 hover:bg-slate-700/50 text-slate-400 border border-slate-700/50 rounded-lg px-4 py-2.5 text-sm transition-colors disabled:opacity-50"
          >
            Load Existing Results
          </button>
        </div>

        {/* Status */}
        {status && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm ${
              status.type === 'success'
                ? 'bg-emerald-400/10 text-emerald-400 border border-emerald-400/20'
                : 'bg-red-400/10 text-red-400 border border-red-400/20'
            }`}
          >
            {status.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
            {status.message}
          </motion.div>
        )}
      </div>

      {/* Results - Grouped by Conversation */}
      {loadingResults ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-14" />)}
        </div>
      ) : conversations.length > 0 ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">
              Classification Results
            </h3>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span>{conversations.length} conversations</span>
              <span className="text-slate-700">|</span>
              <span>{totalTurns} turns classified</span>
            </div>
          </div>

          {/* Intent legend */}
          <div className="flex items-center gap-2 flex-wrap">
            {(() => {
              const allIntents = new Set();
              conversations.forEach(c => c.turns?.forEach(t => allIntents.add(t.intent_label)));
              return [...allIntents].map(intent => (
                <div key={intent} className="flex items-center gap-1">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: getIntentColor(intent) }}
                  />
                  <span className="text-[10px] text-slate-500">{intent}</span>
                </div>
              ));
            })()}
          </div>

          {/* Conversation cards */}
          <div className="space-y-2">
            {conversations.map((conv, i) => (
              <ConversationCard
                key={conv.conversation_id}
                conversation={conv}
                index={i}
              />
            ))}
          </div>
        </div>
      ) : null}
    </motion.div>
  );
}
