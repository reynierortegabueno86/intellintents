import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FlaskConical, Plus, Play, Pause, Trash2, Star, ChevronRight, ChevronDown,
  Loader2, CheckCircle, AlertCircle, XCircle, Clock, Copy,
  Bot, User, ArrowRightLeft, Hash, MessageSquare, Sparkles,
  Settings2, ListChecks, Eye, Pencil, X,
} from 'lucide-react';
import { useApi } from '../hooks/useApi';
import * as api from '../utils/api';
import IntentBadge from '../components/IntentBadge';
import { SpeakerIntentLanes, IntentStrip } from '../components/IntentSequence';
import { getIntentColor } from '../utils/colors';
import { buildIntentHierarchy, groupDistributionByParent } from '../utils/intentHierarchy';
import { formatCategoryName } from '../utils/formatCategoryName';

function Skeleton({ className }) {
  return <div className={`skeleton ${className}`} />;
}

function SpeakerIcon({ speaker }) {
  const s = (speaker || '').toLowerCase();
  const isBot = s === 'agent' || s === 'assistant' || s === 'bot';
  return (
    <div className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center ${
      isBot ? 'bg-violet-400/15' : 'bg-cyan-400/15'
    }`}>
      {isBot
        ? <Bot size={14} className="text-violet-400" />
        : <User size={14} className="text-cyan-400" />
      }
    </div>
  );
}

function CollapsibleText({ text, maxLength = 120 }) {
  const [expanded, setExpanded] = useState(false);
  if (!text) return null;
  const isLong = text.length > maxLength;
  return (
    <div>
      <p className="text-xs text-slate-300 leading-relaxed">
        {expanded || !isLong ? text : text.slice(0, maxLength) + '...'}
      </p>
      {isLong && (
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
          className="text-[10px] text-cyan-400/70 hover:text-cyan-400 mt-0.5 transition-colors"
        >
          {expanded ? 'Show Less' : 'Show More'}
        </button>
      )}
    </div>
  );
}

function StatusBadge({ status }) {
  const cfg = {
    completed: { cls: 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20', icon: <CheckCircle size={10} /> },
    running:   { cls: 'bg-cyan-400/10 text-cyan-400 border-cyan-400/20', icon: <Loader2 size={10} className="animate-spin" /> },
    pending:   { cls: 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20', icon: <Clock size={10} /> },
    paused:    { cls: 'bg-amber-400/10 text-amber-400 border-amber-400/20', icon: <Pause size={10} /> },
    failed:    { cls: 'bg-red-400/10 text-red-400 border-red-400/20', icon: <XCircle size={10} /> },
  };
  const c = cfg[status] || cfg.pending;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border ${c.cls}`}>
      {c.icon}{status}
    </span>
  );
}

// ── Collapsible section wrapper ─────────────────────────────────
function Section({ title, icon: Icon, count, defaultOpen = false, actions, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="glass-card overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-slate-800/20 transition-colors text-left"
      >
        <div className="text-slate-500 flex-shrink-0 transition-transform" style={{ transform: open ? 'rotate(90deg)' : 'rotate(0)' }}>
          <ChevronRight size={14} />
        </div>
        {Icon && <Icon size={15} className="text-violet-400 flex-shrink-0" />}
        <span className="text-sm font-medium text-slate-200">{title}</span>
        {count != null && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-500 font-mono">{count}</span>
        )}
        {actions && (
          <div className="ml-auto flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
            {actions}
          </div>
        )}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-slate-800/50 px-5 py-4">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Conversation card in run results ────────────────────────────
function RunConversationCard({ conversation, index, intentHierarchy = {} }) {
  const [expanded, setExpanded] = useState(false);
  const turns = conversation.turns || [];
  const uniqueIntents = [...new Set(turns.map(t => t.intent_label))];
  const avgConf = turns.reduce((s, t) => s + (t.confidence || 0), 0) / (turns.length || 1);

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.015 }}
      className="bg-slate-800/20 rounded-lg overflow-hidden"
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3 py-2.5 flex items-center gap-3 hover:bg-slate-800/30 transition-colors text-left"
      >
        <div className="text-slate-600 flex-shrink-0 transition-transform" style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0)' }}>
          <ChevronRight size={12} />
        </div>
        <span className="text-[10px] font-mono text-slate-600 w-12 flex-shrink-0">#{conversation.conversation_id}</span>
        <span className="flex items-center gap-1 text-[10px] text-slate-500">
          <MessageSquare size={9} />{turns.length}
        </span>
        <span className="flex items-center gap-1 text-[10px] text-slate-500">
          <Hash size={9} />{uniqueIntents.length}
        </span>
        <span className="flex items-center gap-1 text-[10px] text-slate-500">
          <Sparkles size={9} />{(avgConf * 100).toFixed(0)}%
        </span>
        <div className="flex-1 min-w-0 mx-2">
          <IntentStrip turns={turns} height={4} intentHierarchy={intentHierarchy} />
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t border-slate-800/30 px-3 py-3 space-y-3">
              <div className="bg-slate-900/40 rounded-lg p-2.5">
                <SpeakerIntentLanes turns={turns} intentHierarchy={intentHierarchy} />
              </div>
              <div className="space-y-0.5">
                {turns.map((turn, ti) => {
                  const isUser = (turn.speaker || '').toLowerCase() === 'customer' || (turn.speaker || '').toLowerCase() === 'user';
                  return (
                    <div
                      key={turn.turn_id || ti}
                      className={`flex gap-2 py-1.5 px-2.5 rounded-lg hover:bg-slate-800/20 border-l-2 ${
                        isUser ? 'border-cyan-400/30' : 'border-violet-400/30'
                      }`}
                    >
                      <SpeakerIcon speaker={turn.speaker} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className={`text-[10px] font-mono uppercase ${isUser ? 'text-cyan-400/70' : 'text-violet-400/70'}`}>
                            {turn.speaker}
                          </span>
                          <IntentBadge label={turn.intent_label} parentLabel={intentHierarchy[turn.intent_label]} size="xs" />
                          <span className="text-[9px] text-slate-600 font-mono">{(turn.confidence * 100).toFixed(0)}%</span>
                        </div>
                        <CollapsibleText text={turn.text} maxLength={140} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Label Mapping Panel (inline collapsible) ────────────────────
function LabelMappingContent({ experimentId, onSaved }) {
  const [validation, setValidation] = useState(null);
  const [mappings, setMappings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [val, existing] = await Promise.all([
          api.validateExperimentLabels(experimentId),
          api.getExperimentLabelMapping(experimentId),
        ]);
        setValidation(val);
        if (existing?.length > 0) {
          setMappings(existing.map(m => ({ classifier_label: m.classifier_label, taxonomy_label: m.taxonomy_label })));
        } else if (val.mismatches?.length > 0) {
          setMappings(val.mismatches.map(m => ({ classifier_label: m, taxonomy_label: '' })));
        }
      } catch {
        setValidation({ compatible: true, mismatches: [], taxonomy_labels: [], classifier_labels: [] });
      } finally {
        setLoading(false);
      }
    })();
  }, [experimentId]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.setExperimentLabelMapping(experimentId, mappings.filter(m => m.classifier_label && m.taxonomy_label));
      onSaved?.();
    } catch (err) {
      alert('Failed: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Skeleton className="h-20" />;

  if (validation?.compatible) {
    return (
      <div className="flex items-center gap-2 text-emerald-400 text-xs bg-emerald-400/10 rounded-lg px-3 py-2 border border-emerald-400/20">
        <CheckCircle size={14} />
        All classifier labels match the taxonomy. No mapping needed.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-yellow-400 text-xs bg-yellow-400/10 rounded-lg px-3 py-2 border border-yellow-400/20">
        <AlertCircle size={14} />
        {validation?.mismatches?.length || 0} label(s) need mapping.
      </div>
      <div className="space-y-2">
        {mappings.map((m, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              value={m.classifier_label}
              onChange={(e) => { const u = [...mappings]; u[i] = { ...u[i], classifier_label: e.target.value }; setMappings(u); }}
              placeholder="Classifier label"
              className="flex-1 bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50"
            />
            <ArrowRightLeft size={12} className="text-slate-600 flex-shrink-0" />
            <select
              value={m.taxonomy_label}
              onChange={(e) => { const u = [...mappings]; u[i] = { ...u[i], taxonomy_label: e.target.value }; setMappings(u); }}
              className="flex-1 bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50"
            >
              <option value="">Map to...</option>
              {(validation?.taxonomy_labels || []).map(l => <option key={l} value={l}>{l}</option>)}
            </select>
            <button onClick={() => setMappings(mappings.filter((_, j) => j !== i))} className="text-slate-600 hover:text-red-400"><Trash2 size={11} /></button>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <button onClick={() => setMappings([...mappings, { classifier_label: '', taxonomy_label: '' }])} className="text-[10px] text-slate-500 hover:text-slate-300">+ Add</button>
        <button onClick={handleSave} disabled={saving} className="px-3 py-1 text-[10px] bg-violet-400/10 text-violet-400 border border-violet-400/20 rounded-lg hover:bg-violet-400/20 disabled:opacity-50">
          {saving ? 'Saving...' : 'Save Mapping'}
        </button>
      </div>
    </div>
  );
}

// ── Experiment Form (inline collapsible) ────────────────────────
function ExperimentForm({ datasets, taxonomies, methods, initial, onSubmit, onCancel }) {
  const [form, setForm] = useState({
    name: initial?.name || '',
    description: initial?.description || '',
    dataset_id: initial?.dataset_id || '',
    taxonomy_id: initial?.taxonomy_id || '',
    classification_method: initial?.classification_method || '',
    classifier_parameters: initial?.classifier_parameters || {},
    created_by: initial?.created_by || '',
  });
  const [submitting, setSubmitting] = useState(false);
  const methodList = Array.isArray(methods) ? methods : methods?.methods || [];
  const selectedMethodObj = methodList.find(m => (m.id || m.name) === form.classification_method);

  const handleSubmit = async () => {
    if (!form.name || !form.dataset_id || !form.taxonomy_id || !form.classification_method) return;
    setSubmitting(true);
    try {
      await onSubmit({
        ...form,
        dataset_id: Number(form.dataset_id),
        taxonomy_id: Number(form.taxonomy_id),
        classifier_parameters: Object.keys(form.classifier_parameters).length > 0 ? form.classifier_parameters : null,
      });
    } finally { setSubmitting(false); }
  };

  const inputCls = 'w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50';

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Name *</label>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputCls} placeholder="My Experiment" />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Dataset *</label>
          <select value={form.dataset_id} onChange={(e) => setForm({ ...form, dataset_id: e.target.value })} className={inputCls}>
            <option value="">Select...</option>
            {(datasets || []).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Taxonomy *</label>
          <select value={form.taxonomy_id} onChange={(e) => setForm({ ...form, taxonomy_id: e.target.value })} className={inputCls}>
            <option value="">Select...</option>
            {(taxonomies || []).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Method *</label>
          <select value={form.classification_method} onChange={(e) => setForm({ ...form, classification_method: e.target.value, classifier_parameters: {} })} className={inputCls}>
            <option value="">Select...</option>
            {methodList.map(m => <option key={m.id || m.name} value={m.id || m.name}>{m.name || m.id}</option>)}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Description</label>
          <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} className={`${inputCls} resize-none`} />
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Created By</label>
            <input value={form.created_by} onChange={(e) => setForm({ ...form, created_by: e.target.value })} className={inputCls} placeholder="Optional" />
          </div>
          {selectedMethodObj?.config_schema?.length > 0 && (
            <div className="space-y-2">
              {selectedMethodObj.config_schema.map(field => (
                <div key={field.key} className="flex items-center gap-3">
                  <label className="text-xs text-slate-400 w-28 flex-shrink-0">{field.label}</label>
                  {field.type === 'checkbox' ? (
                    <label className="flex-1 inline-flex items-center gap-2 cursor-pointer group">
                      <input
                        type="checkbox"
                        checked={!!(form.classifier_parameters[field.key] ?? field.default)}
                        onChange={(e) => setForm({ ...form, classifier_parameters: { ...form.classifier_parameters, [field.key]: e.target.checked } })}
                        className="sr-only peer"
                      />
                      <div className="relative w-9 h-5 bg-slate-700/80 rounded-full peer peer-checked:bg-cyan-500/40 transition-colors
                        after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-slate-400 after:rounded-full after:h-4 after:w-4 after:transition-all
                        peer-checked:after:translate-x-4 peer-checked:after:bg-cyan-400" />
                      <span className="text-xs text-slate-500 group-hover:text-slate-400 transition-colors">
                        {form.classifier_parameters[field.key] ?? field.default ? 'Enabled' : 'Disabled'}
                      </span>
                    </label>
                  ) : field.type === 'range' ? (
                    <div className="flex-1 flex items-center gap-2">
                      <input type="range" min={field.min} max={field.max} step={field.step}
                        value={form.classifier_parameters[field.key] ?? field.default ?? field.min}
                        onChange={(e) => setForm({ ...form, classifier_parameters: { ...form.classifier_parameters, [field.key]: parseFloat(e.target.value) } })}
                        className="flex-1 h-1.5 bg-slate-800 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-cyan-400"
                      />
                      <span className="text-xs font-mono text-cyan-400 w-8 text-right">{form.classifier_parameters[field.key] ?? field.default ?? field.min}</span>
                    </div>
                  ) : field.type === 'number' ? (
                    <input type="number" value={form.classifier_parameters[field.key] ?? ''} placeholder={field.default != null ? String(field.default) : ''}
                      onChange={(e) => setForm({ ...form, classifier_parameters: { ...form.classifier_parameters, [field.key]: e.target.value ? Number(e.target.value) : undefined } })}
                      className="flex-1 bg-slate-800/80 border border-slate-700/50 rounded-lg px-2 py-1 text-xs text-slate-300 font-mono focus:outline-none focus:border-cyan-400/50"
                    />
                  ) : field.type === 'select' ? (
                    <select value={form.classifier_parameters[field.key] ?? field.default ?? ''}
                      onChange={(e) => setForm({ ...form, classifier_parameters: { ...form.classifier_parameters, [field.key]: e.target.value } })}
                      className="flex-1 bg-slate-800/80 border border-slate-700/50 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50">
                      {(field.options || []).map(opt => <option key={opt} value={opt}>{opt}</option>)}
                    </select>
                  ) : field.type === 'password' ? (
                    <input type="password" value={form.classifier_parameters[field.key] ?? ''} placeholder="From env var if empty"
                      onChange={(e) => setForm({ ...form, classifier_parameters: { ...form.classifier_parameters, [field.key]: e.target.value || undefined } })}
                      className="flex-1 bg-slate-800/80 border border-slate-700/50 rounded-lg px-2 py-1 text-xs text-slate-300 font-mono focus:outline-none focus:border-cyan-400/50"
                    />
                  ) : field.type === 'json' ? (
                    <textarea value={form.classifier_parameters[field.key] != null ? (typeof form.classifier_parameters[field.key] === 'string' ? form.classifier_parameters[field.key] : JSON.stringify(form.classifier_parameters[field.key], null, 2)) : ''}
                      placeholder='{"key": "value"}'
                      onChange={(e) => { try { setForm({ ...form, classifier_parameters: { ...form.classifier_parameters, [field.key]: JSON.parse(e.target.value) } }); } catch { setForm({ ...form, classifier_parameters: { ...form.classifier_parameters, [field.key]: e.target.value } }); } }}
                      rows={2}
                      className="flex-1 bg-slate-800/80 border border-slate-700/50 rounded-lg px-2 py-1 text-xs text-slate-300 font-mono focus:outline-none focus:border-cyan-400/50 resize-none"
                    />
                  ) : (
                    <input type="text" value={form.classifier_parameters[field.key] ?? field.default ?? ''}
                      placeholder={field.default != null ? String(field.default) : ''}
                      onChange={(e) => setForm({ ...form, classifier_parameters: { ...form.classifier_parameters, [field.key]: e.target.value } })}
                      className="flex-1 bg-slate-800/80 border border-slate-700/50 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50"
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-2 justify-end">
        {onCancel && <button onClick={onCancel} className="px-4 py-2 text-xs text-slate-400 hover:text-white">Cancel</button>}
        <button onClick={handleSubmit} disabled={submitting || !form.name || !form.dataset_id || !form.taxonomy_id || !form.classification_method}
          className="px-5 py-2 text-xs bg-cyan-400/10 text-cyan-400 border border-cyan-400/20 rounded-lg hover:bg-cyan-400/20 disabled:opacity-50 font-medium">
          {submitting ? 'Saving...' : initial ? 'Update' : 'Create Experiment'}
        </button>
      </div>
    </motion.div>
  );
}

// ── Experiment row (horizontal card) ────────────────────────────
function ExperimentRow({ exp, isSelected, onSelect, onFavorite, onDuplicate, onRun, onDelete, onEdit, runningExp, runProgress }) {
  const isRunning = runningExp === exp.id;
  const pct = runProgress && runProgress.total > 0 ? Math.round((runProgress.current / runProgress.total) * 100) : 0;
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      onClick={() => onSelect(exp)}
      className={`rounded-xl cursor-pointer group transition-all ${
        isSelected
          ? 'bg-cyan-400/5 border border-cyan-400/30 shadow-lg shadow-cyan-400/5'
          : 'bg-slate-800/20 border border-transparent hover:bg-slate-800/40 hover:border-slate-700/40'
      }`}
    >
      <div className="flex items-center gap-4 px-4 py-3">
      {/* Favorite */}
      <button onClick={(e) => { e.stopPropagation(); onFavorite(exp); }} className="flex-shrink-0">
        <Star size={14} className={exp.is_favorite ? 'text-yellow-400 fill-yellow-400' : 'text-slate-700 hover:text-yellow-400 transition-colors'} />
      </button>

      {/* Icon + Name */}
      <div className="flex items-center gap-2 min-w-0 w-52 flex-shrink-0">
        <FlaskConical size={14} className="text-violet-400 flex-shrink-0" />
        <span className="text-sm font-medium text-white truncate">{exp.name}</span>
      </div>

      {/* Method badge */}
      <span className="text-[10px] px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 font-mono flex-shrink-0">
        {exp.classification_method}
      </span>

      {/* Dataset / Taxonomy */}
      <div className="hidden md:flex items-center gap-1 text-[10px] text-slate-600 min-w-0 flex-1 truncate">
        <span className="truncate">{exp.dataset_name}</span>
        <span className="text-slate-800">/</span>
        <span className="truncate">{exp.taxonomy_name}</span>
      </div>

      {/* Run count + last run */}
      <div className="flex items-center gap-3 text-[10px] text-slate-500 flex-shrink-0">
        <span className="flex items-center gap-1">
          <ListChecks size={10} />{exp.run_count || 0}
        </span>
        {exp.last_run_date && (
          <span>{new Date(exp.last_run_date).toLocaleDateString()}</span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-0.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <button onClick={(e) => { e.stopPropagation(); onEdit(exp); }} className="p-1.5 text-slate-600 hover:text-slate-300 rounded-md hover:bg-slate-800/60">
          <Pencil size={12} />
        </button>
        <button onClick={(e) => { e.stopPropagation(); onDuplicate(exp); }} className="p-1.5 text-slate-600 hover:text-slate-300 rounded-md hover:bg-slate-800/60">
          <Copy size={12} />
        </button>
        <button onClick={(e) => { e.stopPropagation(); onRun(exp.id); }} disabled={isRunning} className="p-1.5 text-emerald-400/60 hover:text-emerald-400 rounded-md hover:bg-emerald-400/5">
          {isRunning ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
        </button>
        <button onClick={(e) => { e.stopPropagation(); onDelete(exp); }} className="p-1.5 text-slate-600 hover:text-red-400 rounded-md hover:bg-red-400/5">
          <Trash2 size={12} />
        </button>
      </div>
      </div>
      {/* Progress bar */}
      {isRunning && runProgress && runProgress.total > 0 && (
        <div className="px-4 pb-2.5">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1 rounded-full bg-slate-800 overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-cyan-400"
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.4, ease: 'easeOut' }}
              />
            </div>
            <span className="text-[10px] text-slate-500 tabular-nums flex-shrink-0">
              {runProgress.current} / {runProgress.total} turns · {pct}%
            </span>
          </div>
        </div>
      )}
    </motion.div>
  );
}

// ── Main Experiments Page ────────────────────────────────────────
export default function Experiments() {
  const { data: experiments, loading, execute: reload } = useApi(api.getExperiments, []);
  const { data: datasets } = useApi(api.getDatasets, []);
  const { data: taxonomies } = useApi(api.getTaxonomies, []);
  const { data: methods } = useApi(api.getClassifyMethods, []);

  const [showCreate, setShowCreate] = useState(false);
  const [editingExp, setEditingExp] = useState(null);
  const [selectedExp, setSelectedExp] = useState(null);
  const [selectedExpDetail, setSelectedExpDetail] = useState(null);
  const [runs, setRuns] = useState([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runningExp, setRunningExp] = useState(null);
  const [runProgress, setRunProgress] = useState(null); // { current, total }
  const [viewingRun, setViewingRun] = useState(null);
  const [runResults, setRunResults] = useState(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [intentHierarchy, setIntentHierarchy] = useState({});
  const [resultsPage, setResultsPage] = useState(1);
  const RESULTS_PAGE_SIZE = 20;

  const loadRuns = async (expId) => {
    setRunsLoading(true);
    try { setRuns(await api.getExperimentRuns(expId)); } catch { setRuns([]); }
    finally { setRunsLoading(false); }
  };

  const selectExperiment = async (exp) => {
    if (selectedExp === exp.id) { setSelectedExp(null); setSelectedExpDetail(null); setRuns([]); setViewingRun(null); return; }
    setSelectedExp(exp.id);
    setSelectedExpDetail(exp);
    setViewingRun(null);
    setRunResults(null);
    await loadRuns(exp.id);
  };

  const handleCreate = async (data) => { await api.createExperiment(data); setShowCreate(false); await reload(); };
  const handleUpdate = async (data) => {
    await api.updateExperiment(editingExp.id, data);
    setEditingExp(null);
    await reload();
    if (selectedExp === editingExp.id) setSelectedExpDetail(await api.getExperiment(editingExp.id));
  };
  const handleDelete = async (exp) => {
    if (!confirm(`Delete "${exp.name}"?`)) return;
    await api.deleteExperiment(exp.id);
    if (selectedExp === exp.id) { setSelectedExp(null); setSelectedExpDetail(null); setRuns([]); }
    await reload();
  };
  const handleDuplicate = async (exp) => {
    await api.createExperiment({ name: `${exp.name} (copy)`, description: exp.description, dataset_id: exp.dataset_id, taxonomy_id: exp.taxonomy_id, classification_method: exp.classification_method, classifier_parameters: exp.classifier_parameters, created_by: exp.created_by });
    await reload();
  };
  const pollRef = useRef(null);

  // Clean up polling on unmount
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const handleRun = async (expId) => {
    setRunningExp(expId);
    setRunProgress(null);
    try {
      const runData = await api.runExperiment(expId);
      const runId = runData?.id;
      if (!runId) { setRunningExp(null); return; }

      // Poll for run completion every 2 seconds
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const status = await api.getRun(runId);
          // Update progress
          if (status.progress_total > 0) {
            setRunProgress({ current: status.progress_current || 0, total: status.progress_total });
          }
          if (status.status === 'completed' || status.status === 'failed' || status.status === 'paused') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setRunningExp(null);
            setRunProgress(null);
            if (selectedExp === expId) await loadRuns(expId);
            await reload();
          }
        } catch {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setRunningExp(null);
          setRunProgress(null);
        }
      }, 2000);
    } catch (err) {
      alert('Run failed: ' + err.message);
      setRunningExp(null);
      setRunProgress(null);
    }
  };
  const handlePause = async (runId, expId) => {
    try {
      await api.pauseRun(runId);
      // Polling will pick up the "paused" status and stop
    } catch (err) {
      alert('Pause failed: ' + err.message);
    }
  };

  const handleResume = async (run) => {
    const expId = run.experiment_id;
    setRunningExp(expId);
    setRunProgress(run.progress_total > 0 ? { current: run.progress_current || 0, total: run.progress_total } : null);
    try {
      const resumed = await api.resumeRun(run.id);
      const runId = resumed?.id || run.id;

      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const status = await api.getRun(runId);
          if (status.progress_total > 0) {
            setRunProgress({ current: status.progress_current || 0, total: status.progress_total });
          }
          if (status.status === 'completed' || status.status === 'failed' || status.status === 'paused') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setRunningExp(null);
            setRunProgress(null);
            if (selectedExp === expId) await loadRuns(expId);
            await reload();
          }
        } catch {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setRunningExp(null);
          setRunProgress(null);
        }
      }, 2000);
    } catch (err) {
      alert('Resume failed: ' + err.message);
      setRunningExp(null);
      setRunProgress(null);
    }
  };

  const handleToggleFavorite = async (exp) => { await api.updateExperiment(exp.id, { is_favorite: !exp.is_favorite }); await reload(); };
  const handleViewRun = async (run) => {
    if (viewingRun?.id === run.id) { setViewingRun(null); setRunResults(null); return; }
    setViewingRun(run); setResultsLoading(true); setResultsPage(1);
    try {
      const [results, taxonomy] = await Promise.all([
        api.getRunResults(run.id),
        selectedExpDetail?.taxonomy_id ? api.getTaxonomy(selectedExpDetail.taxonomy_id) : null,
      ]);
      setRunResults(results);
      setIntentHierarchy(taxonomy ? buildIntentHierarchy(taxonomy.categories || []) : {});
    } catch { setRunResults([]); setIntentHierarchy({}); }
    finally { setResultsLoading(false); }
  };
  const handleDeleteRun = async (run) => {
    if (!confirm('Delete this run?')) return;
    await api.deleteRun(run.id);
    if (viewingRun?.id === run.id) { setViewingRun(null); setRunResults(null); }
    if (selectedExp) await loadRuns(selectedExp);
    await reload();
  };

  const sorted = useMemo(() => {
    if (!experiments) return [];
    return [...experiments].sort((a, b) => (b.is_favorite ? 1 : 0) - (a.is_favorite ? 1 : 0));
  }, [experiments]);

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }} className="space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Experiments</h1>
          <p className="text-sm text-slate-500 mt-1">Classification experiment management & runs</p>
        </div>
        <button
          onClick={() => { setShowCreate(!showCreate); setEditingExp(null); }}
          className="flex items-center gap-2 bg-cyan-400/10 hover:bg-cyan-400/20 text-cyan-400 border border-cyan-400/20 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
        >
          {showCreate ? <X size={16} /> : <Plus size={16} />}
          {showCreate ? 'Close' : 'New Experiment'}
        </button>
      </div>

      {/* ── Create / Edit Form (collapsible) ───────────────────── */}
      <AnimatePresence>
        {(showCreate || editingExp) && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <Settings2 size={14} className="text-cyan-400" />
                {editingExp ? 'Edit Experiment' : 'New Experiment'}
              </h3>
              <ExperimentForm
                datasets={datasets || []} taxonomies={taxonomies || []} methods={methods || []}
                initial={editingExp}
                onSubmit={editingExp ? handleUpdate : handleCreate}
                onCancel={() => { setShowCreate(false); setEditingExp(null); }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Experiment List (horizontal rows) ──────────────────── */}
      <Section title="Experiments" icon={FlaskConical} count={sorted.length} defaultOpen={true}>
        {loading ? (
          <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : sorted.length > 0 ? (
          <div className="space-y-1.5">
            {sorted.map(exp => (
              <ExperimentRow
                key={exp.id} exp={exp}
                isSelected={selectedExp === exp.id}
                onSelect={selectExperiment}
                onFavorite={handleToggleFavorite}
                onDuplicate={handleDuplicate}
                onRun={handleRun}
                onDelete={handleDelete}
                onEdit={(e) => { setEditingExp(e); setShowCreate(false); }}
                runningExp={runningExp}
                runProgress={runningExp === exp.id ? runProgress : null}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-6 text-slate-600 text-sm">No experiments yet.</div>
        )}
      </Section>

      {/* ── Selected Experiment Detail ─────────────────────────── */}
      <AnimatePresence>
        {selectedExpDetail && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="space-y-4"
          >
            {/* Experiment summary bar */}
            <div className="glass-card px-5 py-3 flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2">
                <FlaskConical size={16} className="text-violet-400" />
                <span className="text-sm font-semibold text-white">{selectedExpDetail.name}</span>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-slate-500 flex-wrap">
                <span>Method: <span className="text-slate-300">{selectedExpDetail.classification_method}</span></span>
                <span>Dataset: <span className="text-slate-300">{selectedExpDetail.dataset_name}</span></span>
                <span>Taxonomy: <span className="text-slate-300">{selectedExpDetail.taxonomy_name}</span></span>
                {selectedExpDetail.created_by && <span>By: <span className="text-slate-300">{selectedExpDetail.created_by}</span></span>}
              </div>
              <div className="ml-auto flex items-center gap-2">
                {runningExp === selectedExp && runProgress && runProgress.total > 0 && (
                  <div className="flex items-center gap-2 mr-2">
                    <div className="w-24 h-1 rounded-full bg-slate-800 overflow-hidden">
                      <div className="h-full rounded-full bg-cyan-400 transition-all duration-500" style={{ width: `${Math.round((runProgress.current / runProgress.total) * 100)}%` }} />
                    </div>
                    <span className="text-[10px] text-slate-500 tabular-nums">{Math.round((runProgress.current / runProgress.total) * 100)}%</span>
                  </div>
                )}
                <button onClick={() => handleRun(selectedExp)} disabled={runningExp === selectedExp}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-emerald-400/10 text-emerald-400 border border-emerald-400/20 rounded-lg hover:bg-emerald-400/20 disabled:opacity-50">
                  {runningExp === selectedExp ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                  Run
                </button>
              </div>
            </div>

            {/* Label Mapping (collapsible section) */}
            <Section title="Label Mapping" icon={ArrowRightLeft}>
              <LabelMappingContent experimentId={selectedExp} onSaved={() => {}} />
            </Section>

            {/* Runs (collapsible section) */}
            <Section title="Runs" icon={ListChecks} count={runs.length} defaultOpen={true}
              actions={
                <button onClick={() => handleRun(selectedExp)} disabled={runningExp === selectedExp}
                  className="text-[10px] px-2 py-1 bg-emerald-400/10 text-emerald-400 rounded-md hover:bg-emerald-400/20 disabled:opacity-50">
                  {runningExp === selectedExp ? <Loader2 size={10} className="animate-spin" /> : <Play size={10} />}
                </button>
              }
            >
              {runsLoading ? (
                <Skeleton className="h-16" />
              ) : runs.length > 0 ? (
                <div className="space-y-1.5">
                  {runs.map((run, i) => (
                    <motion.div
                      key={run.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.03 }}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all ${
                        viewingRun?.id === run.id
                          ? 'bg-cyan-400/5 border border-cyan-400/20'
                          : 'bg-slate-800/20 hover:bg-slate-800/40 border border-transparent'
                      }`}
                      onClick={() => handleViewRun(run)}
                    >
                      <StatusBadge status={run.status} />
                      <span className="text-xs text-slate-400 font-mono">#{run.id}</span>
                      {run.execution_date && <span className="text-[10px] text-slate-500">{new Date(run.execution_date).toLocaleString()}</span>}
                      {run.runtime_duration != null && <span className="text-[10px] text-slate-600">{run.runtime_duration.toFixed(2)}s</span>}
                      {run.status === 'failed' && run.results_summary?.error ? (
                        <div className="flex items-center gap-1.5 ml-auto text-[10px] text-red-400 max-w-[50%] truncate" title={run.results_summary.error}>
                          <AlertCircle size={10} className="flex-shrink-0" />
                          <span className="truncate">{run.results_summary.error}</span>
                        </div>
                      ) : run.results_summary && !run.results_summary.error ? (
                        <div className="flex items-center gap-3 ml-auto text-[10px] text-slate-500">
                          <span>{run.results_summary.total_conversations || 0} conv</span>
                          <span>{run.results_summary.total_turns || 0} turns</span>
                          <span>{run.results_summary.unique_intents || 0} intents</span>
                          <span>{((run.results_summary.avg_confidence || 0) * 100).toFixed(0)}%</span>
                        </div>
                      ) : run.status === 'paused' && run.progress_total > 0 ? (
                        <div className="flex items-center gap-2 ml-auto text-[10px] text-amber-400">
                          <Pause size={10} />
                          <span>{run.progress_current || 0} / {run.progress_total} turns</span>
                        </div>
                      ) : null}
                      {run.status === 'running' && (
                        <button onClick={(e) => { e.stopPropagation(); handlePause(run.id, run.experiment_id); }}
                          className="text-slate-600 hover:text-amber-400 transition-colors" title="Pause">
                          <Pause size={11} />
                        </button>
                      )}
                      {run.status === 'paused' && (
                        <button onClick={(e) => { e.stopPropagation(); handleResume(run); }}
                          className="text-slate-600 hover:text-emerald-400 transition-colors" title="Resume">
                          <Play size={11} />
                        </button>
                      )}
                      <button onClick={(e) => { e.stopPropagation(); handleDeleteRun(run); }} className="text-slate-700 hover:text-red-400 transition-colors">
                        <Trash2 size={11} />
                      </button>
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-4 text-slate-600 text-xs">No runs yet.</div>
              )}
            </Section>

            {/* Run Results (collapsible section, only when a run is selected) */}
            <AnimatePresence>
              {viewingRun && (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  <Section title={`Run #${viewingRun.id} Results`} icon={Eye} defaultOpen={true}
                    actions={<StatusBadge status={viewingRun.status} />}
                  >
                    {/* Error detail for failed runs */}
                    {viewingRun.status === 'failed' && viewingRun.results_summary?.error && (
                      <div className="mb-4 px-3 py-2.5 rounded-lg bg-red-400/5 border border-red-400/20">
                        <div className="flex items-center gap-1.5 text-xs font-medium text-red-400 mb-1">
                          <AlertCircle size={12} />
                          Run Failed
                        </div>
                        <pre className="text-[11px] text-red-300/80 whitespace-pre-wrap break-words font-mono leading-relaxed">{viewingRun.results_summary.error}</pre>
                      </div>
                    )}

                    {/* KPI row */}
                    {viewingRun.results_summary && !viewingRun.results_summary.error && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                        {[
                          { label: 'Conversations', value: viewingRun.results_summary.total_conversations || 0 },
                          { label: 'Turns', value: viewingRun.results_summary.total_turns || 0 },
                          { label: 'Intents', value: viewingRun.results_summary.unique_intents || 0 },
                          { label: 'Avg Confidence', value: `${((viewingRun.results_summary.avg_confidence || 0) * 100).toFixed(1)}%` },
                        ].map(kpi => (
                          <div key={kpi.label} className="bg-slate-800/30 rounded-lg p-3 text-center">
                            <div className="text-lg font-bold text-white">{kpi.value}</div>
                            <div className="text-[10px] text-slate-500">{kpi.label}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Intent distribution legend */}
                    {viewingRun.results_summary?.intent_distribution && (() => {
                      const groups = groupDistributionByParent(viewingRun.results_summary.intent_distribution, intentHierarchy);
                      return (
                        <div className="flex flex-wrap gap-x-4 gap-y-1.5 mb-4">
                          {groups.map(group => (
                            <div key={group.parent} className="flex items-center gap-1.5 text-[10px]">
                              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: getIntentColor(group.parent) }} />
                              <span className="text-slate-400 font-medium">{formatCategoryName(group.parent)}: {group.total}</span>
                              {group.children.length > 0 && (
                                <span className="text-slate-600">
                                  ({group.children.map(c => `${formatCategoryName(c.label)}: ${c.count}`).join(', ')})
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      );
                    })()}

                    {/* Conversations (paginated) */}
                    {resultsLoading ? (
                      <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
                    ) : runResults?.length > 0 ? (
                      <>
                        <div className="space-y-1.5">
                          {runResults
                            .slice((resultsPage - 1) * RESULTS_PAGE_SIZE, resultsPage * RESULTS_PAGE_SIZE)
                            .map((conv, i) => (
                              <RunConversationCard key={conv.conversation_id} conversation={conv} index={i} intentHierarchy={intentHierarchy} />
                            ))}
                        </div>
                        {runResults.length > RESULTS_PAGE_SIZE && (
                          <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-800/50">
                            <span className="text-[10px] text-slate-600">
                              {(resultsPage - 1) * RESULTS_PAGE_SIZE + 1}–{Math.min(resultsPage * RESULTS_PAGE_SIZE, runResults.length)} of {runResults.length} conversations
                            </span>
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => setResultsPage(p => Math.max(1, p - 1))}
                                disabled={resultsPage === 1}
                                className="px-2 py-1 text-[10px] rounded bg-slate-800/40 text-slate-400 hover:bg-slate-800/60 disabled:opacity-30 disabled:cursor-not-allowed"
                              >
                                Prev
                              </button>
                              <span className="text-[10px] text-slate-500 px-2">
                                {resultsPage} / {Math.ceil(runResults.length / RESULTS_PAGE_SIZE)}
                              </span>
                              <button
                                onClick={() => setResultsPage(p => Math.min(Math.ceil(runResults.length / RESULTS_PAGE_SIZE), p + 1))}
                                disabled={resultsPage >= Math.ceil(runResults.length / RESULTS_PAGE_SIZE)}
                                className="px-2 py-1 text-[10px] rounded bg-slate-800/40 text-slate-400 hover:bg-slate-800/60 disabled:opacity-30 disabled:cursor-not-allowed"
                              >
                                Next
                              </button>
                            </div>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="text-center py-4 text-slate-600 text-xs">No results</div>
                    )}
                  </Section>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
