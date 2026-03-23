import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Filter, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, X, User, Bot, ExternalLink, Check, Minus } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import * as api from '../utils/api';
import IntentBadge from '../components/IntentBadge';
import { getIntentColor } from '../utils/colors';
import { cleanHtml } from '../utils/cleanHtml';
import { formatCategoryName, getCategoryCode } from '../utils/formatCategoryName';
import { buildIntentHierarchy, groupIntentsByParent } from '../utils/intentHierarchy';

function HighlightText({ text, keyword, maxLen = 200 }) {
  const clean = cleanHtml(text);
  const display = clean.length > maxLen ? clean.slice(0, maxLen) + '...' : clean;
  if (!keyword) return <span>{display}</span>;
  const regex = new RegExp(`(${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  const parts = display.split(regex);
  return (
    <span>
      {parts.map((part, i) =>
        regex.test(part)
          ? <mark key={i} className="bg-yellow-400/30 text-yellow-200 rounded px-0.5">{part}</mark>
          : <span key={i}>{part}</span>
      )}
    </span>
  );
}

function SpeakerIcon({ speaker }) {
  const isUser = /user|customer|client/i.test(speaker);
  return isUser
    ? <User size={14} className="text-cyan-400 flex-shrink-0" />
    : <Bot size={14} className="text-violet-400 flex-shrink-0" />;
}

function ConfidenceBar({ value }) {
  if (value == null) return <span className="text-slate-600 text-xs">-</span>;
  const pct = Math.round(value * 100);
  const color = value >= 0.8 ? 'bg-emerald-400' : value >= 0.6 ? 'bg-yellow-400' : 'bg-red-400';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-slate-400 font-mono">{pct}%</span>
    </div>
  );
}

const SEARCH_STATE_KEY = 'turnSearch:state';

function saveSearchState(state) {
  try { sessionStorage.setItem(SEARCH_STATE_KEY, JSON.stringify(state)); } catch { /* quota */ }
}

function loadSearchState() {
  try {
    const raw = sessionStorage.getItem(SEARCH_STATE_KEY);
    if (!raw) return null;
    sessionStorage.removeItem(SEARCH_STATE_KEY);
    return JSON.parse(raw);
  } catch { return null; }
}

export default function TurnSearch() {
  const navigate = useNavigate();
  const { data: datasets } = useApi(api.getDatasets, []);
  const { data: taxonomies } = useApi(api.getTaxonomies, []);
  const { data: experiments } = useApi(api.getExperiments, []);

  // Try to restore saved state (from returning after viewing a conversation)
  const [restored] = useState(() => loadSearchState());

  const [datasetId, setDatasetId] = useState(restored?.datasetId ?? null);
  const [taxonomyId, setTaxonomyId] = useState(restored?.taxonomyId ?? null);
  const [runId, setRunId] = useState(restored?.runId ?? null);
  const [availableRuns, setAvailableRuns] = useState([]);
  const [filterOptions, setFilterOptions] = useState(null);
  const [filtersOpen, setFiltersOpen] = useState(restored?.filtersOpen ?? true);

  // Filters
  const [keyword, setKeyword] = useState(restored?.keyword ?? '');
  const [speaker, setSpeaker] = useState(restored?.speaker ?? '');
  const [selectedIntents, setSelectedIntents] = useState(restored?.selectedIntents ?? []);
  const [minConf, setMinConf] = useState(restored?.minConf ?? '');
  const [maxConf, setMaxConf] = useState(restored?.maxConf ?? '');
  const [groundTruth, setGroundTruth] = useState(restored?.groundTruth ?? '');

  // Taxonomy hierarchy for grouping intent labels
  const [intentHierarchy, setIntentHierarchy] = useState({});
  const [expandedGroups, setExpandedGroups] = useState({});

  // Results
  const [results, setResults] = useState(restored?.results ?? null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(restored?.page ?? 1);
  const pageSize = 30;

  // Debounce ref for keyword
  const debounceRef = useRef(null);
  // Skip the auto-search on mount when we already have restored results
  const restoredRef = useRef(!!restored);

  // Derive whether we have classification labels to show (only when a run is selected)
  const hasLabels = runId != null;

  // Navigate to conversation and save current state
  const goToConversation = (conversationId) => {
    saveSearchState({
      datasetId, taxonomyId, runId, filtersOpen,
      keyword, speaker, selectedIntents, minConf, maxConf, groundTruth,
      page, results,
    });
    navigate(`/conversations?datasetId=${datasetId}&conversationId=${conversationId}`);
  };

  // Auto-select dataset/taxonomy with experiment data (skip if restored)
  useEffect(() => {
    if (!datasets?.length || !taxonomies?.length) return;
    if (datasetId != null && taxonomyId != null) return;
    const expWithRuns = experiments?.find(e => e.run_count > 0);
    if (expWithRuns) {
      setDatasetId(expWithRuns.dataset_id);
      setTaxonomyId(expWithRuns.taxonomy_id);
    } else {
      setDatasetId(datasets[0].id);
      setTaxonomyId(taxonomies[0].id);
    }
  }, [datasets, taxonomies, experiments]);

  // Load available runs when dataset changes
  useEffect(() => {
    if (datasetId == null) { setAvailableRuns([]); return; }
    api.getDatasetRuns(datasetId)
      .then(runs => {
        setAvailableRuns(runs || []);
        // Auto-select the latest run if we have no restored run and no current selection
        if (!restoredRef.current && runId == null && runs?.length > 0) {
          setRunId(runs[0].run_id);
          setTaxonomyId(runs[0].taxonomy_id);
        }
      })
      .catch(() => setAvailableRuns([]));
  }, [datasetId]);

  // Load filter options when dataset/taxonomy/run changes
  useEffect(() => {
    if (datasetId == null) return;
    api.getTurnFilterOptions(datasetId, runId ? null : taxonomyId, runId)
      .then(setFilterOptions).catch(() => setFilterOptions(null));
  }, [datasetId, taxonomyId, runId]);

  // Load taxonomy hierarchy for grouping intent labels
  useEffect(() => {
    if (!taxonomyId) { setIntentHierarchy({}); return; }
    api.getTaxonomy(taxonomyId)
      .then(t => setIntentHierarchy(buildIntentHierarchy(t.categories || [])))
      .catch(() => setIntentHierarchy({}));
  }, [taxonomyId]);

  // Reset filters and page when dataset/taxonomy/run changes
  useEffect(() => {
    setSelectedIntents([]);
    setSpeaker('');
    setMinConf('');
    setMaxConf('');
    setGroundTruth('');
    setPage(1);
  }, [datasetId, taxonomyId, runId]);

  // Execute search
  const doSearch = useCallback((pg = page) => {
    if (datasetId == null) return;
    setLoading(true);
    const params = {
      page: pg,
      page_size: pageSize,
    };
    if (runId != null) {
      params.run_id = runId;
    } else if (taxonomyId != null) {
      params.taxonomy_id = taxonomyId;
    }
    if (keyword.trim()) params.keyword = keyword.trim();
    if (speaker) params.speaker = speaker;
    if (selectedIntents.length > 0) params.intent_labels = selectedIntents;
    if (minConf !== '') params.min_confidence = parseFloat(minConf);
    if (maxConf !== '') params.max_confidence = parseFloat(maxConf);
    if (groundTruth) params.ground_truth_intent = groundTruth;

    api.searchTurns(datasetId, params)
      .then(data => { setResults(data); setLoading(false); })
      .catch(() => { setResults(null); setLoading(false); });
  }, [datasetId, taxonomyId, runId, keyword, speaker, selectedIntents, minConf, maxConf, groundTruth, page]);

  // Search on filter changes (debounced for keyword)
  useEffect(() => {
    if (datasetId == null) return;
    // Skip the first auto-search when we restored state with results
    if (restoredRef.current) {
      restoredRef.current = false;
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPage(1);
      doSearch(1);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [datasetId, taxonomyId, runId, keyword, speaker, selectedIntents, minConf, maxConf, groundTruth]);

  // Search on page change (immediate)
  useEffect(() => {
    if (datasetId == null || page === 1) return;
    doSearch(page);
  }, [page]);

  const clearFilters = () => {
    setKeyword('');
    setSpeaker('');
    setSelectedIntents([]);
    setMinConf('');
    setMaxConf('');
    setGroundTruth('');
  };

  const hasActiveFilters = keyword || speaker || selectedIntents.length > 0 || minConf || maxConf || groundTruth;

  const toggleIntent = (intent) => {
    setSelectedIntents(prev =>
      prev.includes(intent) ? prev.filter(i => i !== intent) : [...prev, intent]
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-4"
    >
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Turn Search</h1>
        <p className="text-sm text-slate-500 mt-1">Search and filter turns across datasets by keyword, intent, speaker, and more</p>
      </div>

      {/* Dataset / Run selectors */}
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Dataset</label>
          <select
            value={datasetId ?? ''}
            onChange={(e) => { setDatasetId(e.target.value ? Number(e.target.value) : null); setRunId(null); setTaxonomyId(null); }}
            className="bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50 min-w-[180px]"
          >
            <option value="">Select dataset...</option>
            {(datasets || []).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Classification Run</label>
          <select
            value={runId ?? ''}
            onChange={(e) => {
              const val = e.target.value ? Number(e.target.value) : null;
              setRunId(val);
              if (val) {
                // Auto-set taxonomy from the selected run
                const run = availableRuns.find(r => r.run_id === val);
                if (run) setTaxonomyId(run.taxonomy_id);
              } else {
                // "No labels" — clear taxonomy so no labels are fetched
                setTaxonomyId(null);
              }
            }}
            className="bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50 min-w-[260px]"
          >
            <option value="">No labels (text only)</option>
            {availableRuns.map(r => {
              const date = r.execution_date ? new Date(r.execution_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
              return (
                <option key={r.run_id} value={r.run_id}>
                  {r.experiment_name} — {r.classification_method} ({date})
                </option>
              );
            })}
          </select>
        </div>
      </div>

      {/* Search bar + filter toggle */}
      <div className="flex gap-3 items-stretch">
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="Search turns by keyword or phrase..."
            className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg pl-10 pr-10 py-2.5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50 placeholder:text-slate-600"
          />
          {keyword && (
            <button onClick={() => setKeyword('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
              <X size={14} />
            </button>
          )}
        </div>
        <button
          onClick={() => setFiltersOpen(!filtersOpen)}
          className={`flex items-center gap-2 px-4 rounded-lg border text-sm font-medium transition-colors ${
            hasActiveFilters
              ? 'bg-cyan-400/10 border-cyan-400/30 text-cyan-400'
              : 'bg-slate-800/80 border-slate-700/50 text-slate-400 hover:text-slate-300'
          }`}
        >
          <Filter size={14} />
          Filters
          {hasActiveFilters && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-cyan-400/20">{
              [speaker, ...selectedIntents, minConf, maxConf, groundTruth].filter(Boolean).length
            }</span>
          )}
          {filtersOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* Filter panel */}
      <AnimatePresence>
        {filtersOpen && filterOptions && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="glass-card p-4 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                {/* Speaker */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Speaker</label>
                  <select
                    value={speaker}
                    onChange={(e) => setSpeaker(e.target.value)}
                    className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                  >
                    <option value="">All speakers</option>
                    {filterOptions.speakers.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>

                {/* Confidence range */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Min Confidence</label>
                  <input
                    type="number"
                    min="0" max="1" step="0.05"
                    value={minConf}
                    onChange={(e) => setMinConf(e.target.value)}
                    placeholder={filterOptions.confidence_range.min.toString()}
                    className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Max Confidence</label>
                  <input
                    type="number"
                    min="0" max="1" step="0.05"
                    value={maxConf}
                    onChange={(e) => setMaxConf(e.target.value)}
                    placeholder={filterOptions.confidence_range.max.toString()}
                    className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                  />
                </div>

                {/* Ground truth */}
                {filterOptions.ground_truth_intents.length > 0 && (
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Ground Truth</label>
                    <select
                      value={groundTruth}
                      onChange={(e) => setGroundTruth(e.target.value)}
                      className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                    >
                      <option value="">All</option>
                      {filterOptions.ground_truth_intents.map(g => <option key={g} value={g}>{g}</option>)}
                    </select>
                  </div>
                )}
              </div>

              {/* Intent label multi-select — grouped by parent category */}
              {filterOptions.intent_labels.length > 0 && (() => {
                const { groups, standalone } = groupIntentsByParent(filterOptions.intent_labels, intentHierarchy);
                const parentNames = Object.keys(groups).sort();
                const hasGroups = parentNames.length > 0;

                return (
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">
                      Intent Labels
                      {selectedIntents.length > 0 && (
                        <span className="ml-2 text-cyan-400">({selectedIntents.length} selected)</span>
                      )}
                    </label>
                    <div className="bg-slate-800/40 rounded-lg p-2 max-h-48 overflow-y-auto space-y-1">
                      {/* Grouped categories */}
                      {parentNames.map(parent => {
                        const children = groups[parent];
                        const isExpanded = !!expandedGroups[parent];
                        const selectedCount = children.filter(c => selectedIntents.includes(c)).length;
                        const allSelected = selectedCount === children.length;
                        const someSelected = selectedCount > 0 && !allSelected;
                        const color = getIntentColor(parent);
                        const code = getCategoryCode(parent);

                        const toggleAll = () => {
                          if (allSelected) {
                            setSelectedIntents(prev => prev.filter(i => !children.includes(i)));
                          } else {
                            setSelectedIntents(prev => [...new Set([...prev, ...children])]);
                          }
                        };

                        return (
                          <div key={parent}>
                            <div className="flex items-center gap-1.5">
                              <button
                                onClick={() => setExpandedGroups(prev => ({ ...prev, [parent]: !prev[parent] }))}
                                className="text-slate-500 hover:text-slate-300 flex-shrink-0"
                              >
                                {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                              </button>
                              <button
                                onClick={toggleAll}
                                className="w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0 transition-colors"
                                style={{
                                  borderColor: allSelected || someSelected ? color : 'rgb(51 65 85 / 0.5)',
                                  backgroundColor: allSelected ? color : 'transparent',
                                }}
                                title={allSelected ? 'Deselect all' : 'Select all'}
                              >
                                {allSelected && <Check size={10} className="text-slate-900" />}
                                {someSelected && <Minus size={10} style={{ color }} />}
                              </button>
                              <button
                                onClick={() => setExpandedGroups(prev => ({ ...prev, [parent]: !prev[parent] }))}
                                className="flex items-center gap-1.5 text-[11px] hover:opacity-80 transition-opacity"
                                style={{ color }}
                              >
                                <span className="font-mono font-bold text-[9px] opacity-70">{code}</span>
                                <span>{formatCategoryName(parent)}</span>
                                <span className="text-slate-600">({children.length})</span>
                                {selectedCount > 0 && !allSelected && (
                                  <span className="text-[9px] opacity-60">{selectedCount} sel</span>
                                )}
                              </button>
                            </div>
                            {isExpanded && (
                              <div className="ml-6 mt-0.5 flex flex-wrap gap-1 mb-1">
                                {children.map(child => {
                                  const isSelected = selectedIntents.includes(child);
                                  return (
                                    <button
                                      key={child}
                                      onClick={() => toggleIntent(child)}
                                      className={`text-[10px] px-1.5 py-0.5 rounded border transition-all ${
                                        isSelected ? 'opacity-100' : 'opacity-40 hover:opacity-70'
                                      }`}
                                      style={{
                                        color,
                                        borderColor: isSelected ? color : 'rgb(51 65 85 / 0.5)',
                                        backgroundColor: isSelected ? `${color}15` : 'transparent',
                                      }}
                                    >
                                      {formatCategoryName(child)}
                                    </button>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                      {/* Standalone labels (no parent) — shown as single-row toggles in same style */}
                      {standalone.map(intent => {
                        const isSelected = selectedIntents.includes(intent);
                        const color = getIntentColor(intent);
                        return (
                          <div key={intent} className="flex items-center gap-1.5">
                            <div className="w-3 flex-shrink-0" />
                            <button
                              onClick={() => toggleIntent(intent)}
                              className="w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0 transition-colors"
                              style={{
                                borderColor: isSelected ? color : 'rgb(51 65 85 / 0.5)',
                                backgroundColor: isSelected ? color : 'transparent',
                              }}
                            >
                              {isSelected && <Check size={10} className="text-slate-900" />}
                            </button>
                            <button
                              onClick={() => toggleIntent(intent)}
                              className={`text-[11px] transition-opacity ${isSelected ? 'opacity-100' : 'opacity-50 hover:opacity-75'}`}
                              style={{ color }}
                            >
                              {formatCategoryName(intent)}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}

              {/* Clear all */}
              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
                >
                  Clear all filters
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results */}
      {loading ? (
        <div className="glass-card p-8 text-center">
          <div className="inline-block w-6 h-6 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" />
          <p className="text-sm text-slate-500 mt-2">Searching...</p>
        </div>
      ) : results ? (
        <div className="space-y-3">
          {/* Summary */}
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>
              Showing {results.results.length > 0 ? ((results.page - 1) * results.page_size + 1) : 0}
              -{Math.min(results.page * results.page_size, results.total)} of <span className="text-slate-300">{results.total}</span> turns
            </span>
            <span>Page {results.page} of {results.total_pages}</span>
          </div>

          {/* Results table */}
          {results.results.length > 0 ? (
            <div className="glass-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700/50">
                      <th className="text-left px-3 py-2.5 text-xs text-slate-500 font-medium" title="Click to view full conversation">Conv</th>
                      <th className="text-left px-3 py-2.5 text-xs text-slate-500 font-medium">Turn</th>
                      <th className="text-left px-3 py-2.5 text-xs text-slate-500 font-medium">Speaker</th>
                      <th className="text-left px-3 py-2.5 text-xs text-slate-500 font-medium">Text</th>
                      {hasLabels && <th className="text-left px-3 py-2.5 text-xs text-slate-500 font-medium">Intent</th>}
                      {hasLabels && <th className="text-left px-3 py-2.5 text-xs text-slate-500 font-medium">Confidence</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {results.results.map((row, i) => (
                      <tr
                        key={`${row.turn_id}-${i}`}
                        className="border-b border-slate-800/30 hover:bg-slate-800/20 transition-colors"
                      >
                        <td className="px-3 py-2 text-xs font-mono whitespace-nowrap">
                          <button
                            onClick={() => goToConversation(row.conversation_id)}
                            title="View full conversation"
                            className="inline-flex items-center gap-1 text-cyan-400/70 hover:text-cyan-400 transition-colors group"
                          >
                            {row.conversation_external_id
                              ? row.conversation_external_id.slice(0, 8) + '..'
                              : `#${row.conversation_id}`}
                            <ExternalLink size={10} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                          </button>
                        </td>
                        <td className="px-3 py-2 text-xs text-slate-400 font-mono text-center">
                          {row.turn_index}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <SpeakerIcon speaker={row.speaker} />
                            <span className="text-xs text-slate-400">{row.speaker}</span>
                          </div>
                        </td>
                        <td className="px-3 py-2 text-xs text-slate-300 max-w-md">
                          <HighlightText text={row.text} keyword={keyword} />
                        </td>
                        {hasLabels && (
                          <td className="px-3 py-2 whitespace-nowrap">
                            {row.intent_label ? <IntentBadge label={row.intent_label} parentLabel={intentHierarchy[row.intent_label]} size="xs" /> : <span className="text-slate-600 text-xs">-</span>}
                          </td>
                        )}
                        {hasLabels && (
                          <td className="px-3 py-2">
                            <ConfidenceBar value={row.confidence} />
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="glass-card p-8 text-center text-slate-600 text-sm">
              No turns found matching your filters.
            </div>
          )}

          {/* Pagination */}
          {results.total_pages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={results.page <= 1}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/80 border border-slate-700/50 text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft size={14} /> Previous
              </button>
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(results.total_pages, 7) }, (_, i) => {
                  let pageNum;
                  if (results.total_pages <= 7) {
                    pageNum = i + 1;
                  } else if (results.page <= 4) {
                    pageNum = i + 1;
                  } else if (results.page >= results.total_pages - 3) {
                    pageNum = results.total_pages - 6 + i;
                  } else {
                    pageNum = results.page - 3 + i;
                  }
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setPage(pageNum)}
                      className={`w-8 h-8 rounded-lg text-xs font-medium transition-colors ${
                        pageNum === results.page
                          ? 'bg-cyan-400/15 text-cyan-400 border border-cyan-400/30'
                          : 'text-slate-500 hover:text-white hover:bg-slate-800/80'
                      }`}
                    >
                      {pageNum}
                    </button>
                  );
                })}
              </div>
              <button
                onClick={() => setPage(p => Math.min(results.total_pages, p + 1))}
                disabled={results.page >= results.total_pages}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/80 border border-slate-700/50 text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          )}
        </div>
      ) : datasetId == null ? (
        <div className="glass-card p-8 text-center text-slate-600 text-sm">
          Select a dataset to start searching turns.
        </div>
      ) : null}
    </motion.div>
  );
}
