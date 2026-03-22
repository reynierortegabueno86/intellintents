import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Tags, Plus, Trash2, ChevronRight, ChevronDown, Palette, FolderTree,
  Upload, FileJson, AlertCircle, CheckCircle, Download, BookOpen,
  Edit3, Save, X, ArrowRight, Hash, Link, Loader2,
} from 'lucide-react';
import { useApi } from '../hooks/useApi';
import * as api from '../utils/api';
import IntentBadge from '../components/IntentBadge';
import { formatCategoryName, toCategoryStorageName } from '../utils/formatCategoryName';

function Skeleton({ className }) {
  return <div className={`skeleton ${className}`} />;
}

function buildTree(categories) {
  const map = {};
  const roots = [];
  for (const cat of categories) {
    map[cat.id] = { ...cat, children: [] };
  }
  for (const cat of categories) {
    if (cat.parent_id && map[cat.parent_id]) {
      map[cat.parent_id].children.push(map[cat.id]);
    } else {
      roots.push(map[cat.id]);
    }
  }
  // Sort by priority then name
  const sortNodes = (nodes) => {
    nodes.sort((a, b) => (a.priority || 0) - (b.priority || 0) || a.name.localeCompare(b.name));
    nodes.forEach(n => sortNodes(n.children));
  };
  sortNodes(roots);
  return roots;
}

function validateTaxonomyJson(data) {
  const errors = [];
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return { valid: false, errors: ['File must contain a JSON object'], stats: null };
  }
  if (!data.name || typeof data.name !== 'string' || !data.name.trim()) {
    errors.push('Missing or empty "name" field (string required)');
  } else if (data.name.trim().length > 255) {
    errors.push('"name" must be 255 characters or fewer');
  }
  if (data.description != null && typeof data.description !== 'string') {
    errors.push('"description" must be a string if provided');
  }
  if (!Array.isArray(data.categories)) {
    errors.push('Missing or invalid "categories" field (array required)');
    return { valid: false, errors, stats: null };
  }
  if (data.categories.length === 0) {
    errors.push('"categories" array is empty — at least one category is required');
  }

  let totalCategories = 0;
  let totalChildren = 0;
  const names = new Set();

  const validateNode = (node, path) => {
    if (!node || typeof node !== 'object') {
      errors.push(`${path}: must be an object`);
      return;
    }
    if (!node.name || typeof node.name !== 'string' || !node.name.trim()) {
      errors.push(`${path}: missing or empty "name"`);
    } else {
      if (names.has(node.name.trim().toLowerCase())) {
        errors.push(`${path}: duplicate name "${node.name}"`);
      }
      names.add(node.name.trim().toLowerCase());
    }
    // Validate examples constraint
    const hasChildren = Array.isArray(node.children) && node.children.length > 0;
    if (hasChildren && Array.isArray(node.examples) && node.examples.length > 0) {
      errors.push(`${path}: has both children and examples (examples only on leaf nodes)`);
    }
    if (node.children != null) {
      if (!Array.isArray(node.children)) {
        errors.push(`${path}.children: must be an array`);
      } else {
        for (let j = 0; j < node.children.length; j++) {
          totalChildren++;
          validateNode(node.children[j], `${path}.children[${j}]`);
        }
      }
    }
  };

  for (let i = 0; i < data.categories.length; i++) {
    totalCategories++;
    validateNode(data.categories[i], `categories[${i}]`);
  }

  return {
    valid: errors.length === 0,
    errors,
    stats: { categories: totalCategories, children: totalChildren, total: totalCategories + totalChildren },
  };
}

// --- Inline Category Editor ---
function CategoryEditor({ node, taxonomyId, allCategories, onReload, onClose }) {
  const [name, setName] = useState(formatCategoryName(node.name));
  const [desc, setDesc] = useState(node.description || '');
  const [color, setColor] = useState(node.color || '#64748b');
  const [priority, setPriority] = useState(node.priority || 0);
  const [examples, setExamples] = useState((node.examples || []).join('\n'));
  const [saving, setSaving] = useState(false);
  const isLeaf = !node.children || node.children.length === 0;
  const isRoot = node.parent_id == null;

  const colorPresets = [
    '#22d3ee', '#a78bfa', '#34d399', '#f472b6', '#fb923c',
    '#facc15', '#60a5fa', '#f87171', '#4ade80', '#c084fc',
  ];

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const storageName = toCategoryStorageName(name, isRoot);
      await api.updateCategory(taxonomyId, node.id, {
        name: storageName,
        description: desc || null,
        color,
        priority,
      });
      // Save examples separately (leaf only)
      if (isLeaf) {
        const lines = examples.split('\n').map(l => l.trim()).filter(Boolean);
        if (lines.length > 0) {
          await api.setCategoryExamples(taxonomyId, node.id, lines);
        } else {
          await api.clearCategoryExamples(taxonomyId, node.id);
        }
      }
      onClose();
      onReload();
    } catch (err) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-slate-800/60 rounded-lg p-3 space-y-2 border border-cyan-400/20 my-1" onClick={e => e.stopPropagation()}>
      <div className="grid grid-cols-2 gap-2">
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Name"
          className="bg-slate-800/80 border border-slate-700/50 rounded px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50"
        />
        <input
          value={desc}
          onChange={e => setDesc(e.target.value)}
          placeholder="Description"
          className="bg-slate-800/80 border border-slate-700/50 rounded px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50"
        />
      </div>
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          {colorPresets.map(c => (
            <button
              key={c}
              onClick={() => setColor(c)}
              className={`w-4 h-4 rounded-full transition-all ${color === c ? 'ring-1 ring-white ring-offset-1 ring-offset-slate-900' : ''}`}
              style={{ backgroundColor: c }}
            />
          ))}
          <input type="color" value={color} onChange={e => setColor(e.target.value)} className="w-4 h-4 rounded cursor-pointer bg-transparent border-0 ml-1" />
        </div>
        <div className="flex items-center gap-1 ml-auto">
          <label className="text-[9px] text-slate-500">Priority:</label>
          <input
            type="number"
            min={0}
            value={priority}
            onChange={e => setPriority(parseInt(e.target.value) || 0)}
            className="w-12 bg-slate-800/80 border border-slate-700/50 rounded px-1 py-0.5 text-[10px] text-slate-300 focus:outline-none focus:border-cyan-400/50"
          />
        </div>
      </div>
      {isLeaf && (
        <div>
          <label className="text-[9px] text-slate-500 block mb-0.5">Examples (one per line)</label>
          <textarea
            value={examples}
            onChange={e => setExamples(e.target.value)}
            placeholder="One example per line..."
            rows={2}
            className="w-full bg-slate-800/80 border border-slate-700/50 rounded px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50 resize-y"
          />
        </div>
      )}
      <div className="flex gap-1">
        <button onClick={handleSave} disabled={saving} className="text-[10px] px-2 py-0.5 bg-emerald-400/10 text-emerald-400 border border-emerald-400/20 rounded hover:bg-emerald-400/20 disabled:opacity-50">
          <Save size={10} className="inline mr-0.5" /> {saving ? 'Saving...' : 'Save'}
        </button>
        <button onClick={onClose} className="text-[10px] px-2 py-0.5 bg-slate-700/50 text-slate-400 rounded hover:bg-slate-700">
          <X size={10} className="inline mr-0.5" /> Cancel
        </button>
      </div>
    </div>
  );
}

function TreeNode({ node, depth, onDelete, allCategories, taxonomyId, onReload }) {
  const [expanded, setExpanded] = useState(true);
  const [editing, setEditing] = useState(false);
  const hasChildren = node.children && node.children.length > 0;
  const isLeaf = !hasChildren;

  return (
    <div>
      {editing ? (
        <div style={{ paddingLeft: `${depth * 24 + 8}px` }}>
          <CategoryEditor
            node={node}
            taxonomyId={taxonomyId}
            allCategories={allCategories}
            onReload={onReload}
            onClose={() => setEditing(false)}
          />
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          className="group flex items-center gap-1 py-1.5 hover:bg-slate-800/30 rounded-lg px-2 transition-colors overflow-hidden"
          style={{ paddingLeft: `${depth * 24 + 8}px` }}
        >
          {/* Expand/collapse toggle */}
          <button
            onClick={() => hasChildren && setExpanded(!expanded)}
            className={`w-5 h-5 flex items-center justify-center flex-shrink-0 ${
              hasChildren ? 'text-slate-500 hover:text-slate-300 cursor-pointer' : 'text-transparent'
            }`}
          >
            {hasChildren && (expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />)}
          </button>

          {/* Connecting line dot */}
          {depth > 0 && (
            <div className="relative flex-shrink-0 w-4 h-full">
              <div
                className="absolute left-0 top-1/2 w-3 h-px"
                style={{ backgroundColor: node.color || '#475569' }}
              />
              <div
                className="absolute left-0 w-2 h-2 rounded-full -translate-y-1/2 top-1/2"
                style={{ backgroundColor: node.color || '#475569' }}
              />
            </div>
          )}

          {/* Color indicator */}
          <div
            className="w-3 h-3 rounded-full flex-shrink-0 ring-2 ring-offset-1 ring-offset-slate-900"
            style={{
              backgroundColor: node.color || '#64748b',
              ringColor: node.color || '#64748b',
            }}
          />

          {/* Name, description, and examples */}
          <div className="flex-1 min-w-0 ml-2 overflow-hidden">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-medium text-white truncate">{formatCategoryName(node.name)}</span>
              {node.priority != null && node.priority > 0 && (
                <span className="text-[9px] px-1 py-0 rounded bg-slate-800/80 text-slate-600 font-mono">
                  #{node.priority}
                </span>
              )}
            </div>
            {node.description && (
              <div className="text-xs text-slate-500 truncate" title={node.description}>{node.description}</div>
            )}
            {/* Examples display — only on leaf nodes */}
            {isLeaf && node.examples?.length > 0 && (
              <div className="mt-0.5 space-y-0">
                {node.examples.slice(0, 2).map((ex, i) => (
                  <div key={i} className="text-[10px] text-slate-600 flex items-start gap-1">
                    <span className="text-slate-700 mt-0.5">•</span>
                    <span className="italic truncate">"{ex}"</span>
                  </div>
                ))}
                {node.examples.length > 2 && (
                  <span className="text-[9px] text-slate-700">+{node.examples.length - 2} more</span>
                )}
              </div>
            )}
          </div>

          {/* Child count badge */}
          {hasChildren && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-500 font-mono">
              {node.children.length}
            </span>
          )}

          {/* Leaf examples badge */}
          {isLeaf && node.examples?.length > 0 && (
            <span className="text-[9px] px-1 py-0.5 rounded bg-emerald-400/10 text-emerald-400/60 font-mono">
              {node.examples.length} ex
            </span>
          )}

          {/* Edit */}
          <button
            onClick={(e) => { e.stopPropagation(); setEditing(true); }}
            className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-cyan-400 transition-all p-1"
          >
            <Edit3 size={12} />
          </button>

          {/* Delete */}
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(node); }}
            className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition-all p-1"
          >
            <Trash2 size={12} />
          </button>
        </motion.div>
      )}

      {/* Children */}
      <AnimatePresence>
        {expanded && hasChildren && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div
              className="relative ml-4"
              style={{ borderLeft: `1px dashed ${node.color || '#334155'}40` }}
            >
              {node.children.map((child) => (
                <TreeNode
                  key={child.id}
                  node={child}
                  depth={depth + 1}
                  onDelete={onDelete}
                  allCategories={allCategories}
                  taxonomyId={taxonomyId}
                  onReload={onReload}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function Taxonomy() {
  const { data: taxonomies, loading, execute: reload } = useApi(api.getTaxonomies, []);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [creating, setCreating] = useState(false);

  const [showImport, setShowImport] = useState(false);
  const [importMode, setImportMode] = useState('file');
  const [importSourceUrl, setImportSourceUrl] = useState('');
  const [importSourceLoading, setImportSourceLoading] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importData, setImportData] = useState(null);
  const [importValidation, setImportValidation] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState(null);

  const [showAddCat, setShowAddCat] = useState(false);
  const [catName, setCatName] = useState('');
  const [catDesc, setCatDesc] = useState('');
  const [catColor, setCatColor] = useState('#22d3ee');
  const [catParent, setCatParent] = useState('');
  const [catPriority, setCatPriority] = useState(0);
  const [addingCat, setAddingCat] = useState(false);

  const [exporting, setExporting] = useState(false);

  // Taxonomy-level editing
  const [editingTax, setEditingTax] = useState(false);
  const [taxEditName, setTaxEditName] = useState('');
  const [taxEditDesc, setTaxEditDesc] = useState('');
  const [taxEditTags, setTaxEditTags] = useState('');
  const [savingTax, setSavingTax] = useState(false);

  const startEditTaxonomy = () => {
    setTaxEditName(selected.name || '');
    setTaxEditDesc(selected.description || '');
    setTaxEditTags((detail?.tags || []).join(', '));
    setEditingTax(true);
  };

  const handleSaveTaxonomy = async () => {
    if (!taxEditName.trim()) return;
    setSavingTax(true);
    try {
      const tags = taxEditTags.split(',').map(t => t.trim()).filter(Boolean);
      await api.updateTaxonomy(selected.id, {
        name: taxEditName,
        description: taxEditDesc || null,
        tags: tags.length > 0 ? tags : null,
      });
      const updated = { ...selected, name: taxEditName, description: taxEditDesc };
      setSelected(updated);
      setEditingTax(false);
      await reload();
      await viewTaxonomy(updated);
    } catch (err) {
      alert(err.message);
    } finally {
      setSavingTax(false);
    }
  };

  const viewTaxonomy = async (tax) => {
    setSelected(tax);
    setDetailLoading(true);
    try {
      const d = await api.getTaxonomy(tax.id);
      setDetail(d);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await api.createTaxonomy({ name: newName, description: newDesc });
      setNewName('');
      setNewDesc('');
      setShowCreate(false);
      await reload();
    } catch (err) {
      alert('Failed: ' + err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleAddCategory = async () => {
    if (!catName.trim() || !selected) return;
    setAddingCat(true);
    const isRoot = !catParent;
    const storageName = toCategoryStorageName(catName, isRoot);
    try {
      await api.addCategory(selected.id, {
        name: storageName,
        description: catDesc,
        color: catColor,
        parent_id: catParent ? parseInt(catParent) : undefined,
        priority: catPriority || 0,
      });
      setCatName('');
      setCatDesc('');
      setCatColor('#22d3ee');
      setCatParent('');
      setCatPriority(0);
      setShowAddCat(false);
      await viewTaxonomy(selected);
    } catch (err) {
      alert('Failed: ' + err.message);
    } finally {
      setAddingCat(false);
    }
  };

  const handleDeleteTaxonomy = async (tax) => {
    if (!confirm(`Delete taxonomy "${tax.name}"?`)) return;
    try {
      await api.deleteTaxonomy(tax.id);
      if (selected?.id === tax.id) {
        setSelected(null);
        setDetail(null);
      }
      await reload();
    } catch (err) {
      alert('Delete failed: ' + err.message);
    }
  };

  const handleDeleteCategory = async (cat) => {
    if (!confirm(`Delete category "${cat.name}" and its children?`)) return;
    try {
      await api.deleteCategory(selected.id, cat.id);
      await viewTaxonomy(selected);
    } catch (err) {
      alert('Delete failed: ' + err.message);
    }
  };

  const handleExport = async () => {
    if (!selected) return;
    setExporting(true);
    try {
      const data = await api.exportTaxonomy(selected.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selected.name.replace(/[^a-zA-Z0-9_-]/g, '_')}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Export failed: ' + err.message);
    } finally {
      setExporting(false);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportFile(file);
    setImportData(null);
    setImportValidation(null);
    setImportError(null);

    if (!file.name.endsWith('.json')) {
      setImportValidation({ valid: false, errors: ['File must be a .json file'], stats: null });
      return;
    }

    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const parsed = JSON.parse(evt.target.result);
        const validation = validateTaxonomyJson(parsed);
        setImportData(parsed);
        setImportValidation(validation);
      } catch {
        setImportValidation({ valid: false, errors: ['Invalid JSON — file could not be parsed'], stats: null });
      }
    };
    reader.readAsText(file);
  };

  const handleImport = async () => {
    if (!importData || !importValidation?.valid) return;
    setImporting(true);
    setImportError(null);
    try {
      await api.importTaxonomy(importData);
      setShowImport(false);
      setImportFile(null);
      setImportData(null);
      setImportValidation(null);
      await reload();
    } catch (err) {
      setImportError(err.message);
    } finally {
      setImporting(false);
    }
  };

  const resetImport = () => {
    setImportFile(null);
    setImportData(null);
    setImportValidation(null);
    setImportError(null);
  };

  const categories = detail?.categories || [];
  const tree = useMemo(() => buildTree(categories), [categories]);

  const colorPresets = [
    '#22d3ee', '#a78bfa', '#34d399', '#f472b6', '#fb923c',
    '#facc15', '#60a5fa', '#f87171', '#4ade80', '#c084fc',
    '#2dd4bf', '#818cf8',
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Taxonomy</h1>
          <p className="text-sm text-slate-500 mt-1">Manage hierarchical intent taxonomies</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setShowImport(!showImport); setShowCreate(false); }}
            className="flex items-center gap-2 bg-violet-400/10 hover:bg-violet-400/20 text-violet-400 border border-violet-400/20 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          >
            <Upload size={16} />
            Import JSON
          </button>
          <button
            onClick={() => { setShowCreate(!showCreate); setShowImport(false); }}
            className="flex items-center gap-2 bg-cyan-400/10 hover:bg-cyan-400/20 text-cyan-400 border border-cyan-400/20 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
          >
            <Plus size={16} />
            New Taxonomy
          </button>
        </div>
      </div>

      {/* Import Form */}
      <AnimatePresence>
        {showImport && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="glass-card p-5 space-y-4">
              <div className="flex items-center gap-2 mb-1">
                <FileJson size={18} className="text-violet-400" />
                <h3 className="text-sm font-semibold text-white">Import Taxonomy from JSON</h3>
              </div>

              {/* Mode toggle */}
              <div className="flex gap-1 bg-slate-800/60 rounded-lg p-1 inline-flex">
                <button
                  onClick={() => setImportMode('file')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    importMode === 'file'
                      ? 'bg-violet-400/15 text-violet-400'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  <Upload size={14} />
                  Upload File
                </button>
                <button
                  onClick={() => setImportMode('source')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    importMode === 'source'
                      ? 'bg-violet-400/15 text-violet-400'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  <Link size={14} />
                  Load from Source
                </button>
              </div>

              {importMode === 'file' ? (
                <>
                  <div className="text-xs text-slate-500 bg-slate-800/40 rounded-lg p-3 border border-slate-700/30 space-y-1">
                    <p className="font-medium text-slate-400">Expected JSON format:</p>
                    <pre className="text-[10px] text-slate-500 font-mono leading-relaxed">{`{
  "name": "My Taxonomy",
  "description": "Optional description",
  "tags": ["finance", "support"],
  "categories": [
    {
      "name": "Category",
      "description": "...",
      "priority": 0,
      "children": [
        {
          "name": "Leaf Node",
          "examples": ["example text 1", "example text 2"]
        }
      ]
    }
  ]
}`}</pre>
                    <p className="text-slate-600 mt-1">
                      Required: <span className="text-slate-400">name</span>, <span className="text-slate-400">categories</span> (non-empty).
                      Examples only allowed on leaf nodes. Unlimited nesting depth.
                    </p>
                  </div>

                  {/* File input */}
                  <div>
                    <label className="flex items-center gap-3 cursor-pointer bg-slate-800/60 border-2 border-dashed border-slate-700/50 hover:border-violet-400/40 rounded-lg p-4 transition-colors">
                      <Upload size={20} className="text-slate-500 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        {importFile ? (
                          <span className="text-sm text-slate-300">{importFile.name}</span>
                        ) : (
                          <span className="text-sm text-slate-500">Choose a .json file or drag and drop...</span>
                        )}
                      </div>
                      <input
                        type="file"
                        accept=".json,application/json"
                        onChange={handleFileSelect}
                        className="hidden"
                      />
                      {importFile && (
                        <button
                          onClick={(e) => { e.preventDefault(); resetImport(); }}
                          className="text-slate-500 hover:text-slate-300 text-xs"
                        >
                          Clear
                        </button>
                      )}
                    </label>
                  </div>

                  {/* Validation results */}
                  {importValidation && (
                    <div className={`rounded-lg p-3 border text-sm space-y-2 ${
                      importValidation.valid
                        ? 'bg-emerald-400/5 border-emerald-400/20'
                        : 'bg-red-400/5 border-red-400/20'
                    }`}>
                      {importValidation.valid ? (
                        <div className="flex items-center gap-2 text-emerald-400">
                          <CheckCircle size={16} />
                          <span className="font-medium">Valid taxonomy</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 text-red-400">
                          <AlertCircle size={16} />
                          <span className="font-medium">Validation failed</span>
                        </div>
                      )}

                      {importValidation.stats && (
                        <div className="flex items-center gap-3 text-xs text-slate-400">
                          <span>Name: <span className="text-white">{importData?.name}</span></span>
                          <span className="text-slate-700">|</span>
                          <span>{importValidation.stats.categories} categories</span>
                          <span className="text-slate-700">|</span>
                          <span>{importValidation.stats.children} sub-intents</span>
                          <span className="text-slate-700">|</span>
                          <span>{importValidation.stats.total} total</span>
                        </div>
                      )}

                      {importValidation.valid && importData?.categories?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {importData.categories.slice(0, 12).map((cat, i) => (
                            <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800/80 text-slate-400 border border-slate-700/50">
                              {cat.name}
                              {cat.children?.length > 0 && <span className="text-slate-600 ml-1">({cat.children.length})</span>}
                            </span>
                          ))}
                          {importData.categories.length > 12 && (
                            <span className="text-[10px] text-slate-600">+{importData.categories.length - 12} more</span>
                          )}
                        </div>
                      )}

                      {importValidation.errors.length > 0 && (
                        <ul className="text-xs text-red-400/80 space-y-0.5 ml-6 list-disc">
                          {importValidation.errors.slice(0, 10).map((err, i) => (
                            <li key={i}>{err}</li>
                          ))}
                          {importValidation.errors.length > 10 && (
                            <li className="text-slate-500">...and {importValidation.errors.length - 10} more errors</li>
                          )}
                        </ul>
                      )}
                    </div>
                  )}

                  {importError && (
                    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-400/10 text-red-400 border border-red-400/20 text-xs">
                      <AlertCircle size={14} />
                      {importError}
                    </div>
                  )}

                  <button
                    onClick={handleImport}
                    disabled={importing || !importValidation?.valid}
                    className="bg-violet-400/10 hover:bg-violet-400/20 text-violet-400 border border-violet-400/20 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    {importing ? 'Importing...' : 'Import Taxonomy'}
                  </button>
                </>
              ) : (
                <>
                  <p className="text-sm text-slate-400">
                    Load a taxonomy JSON from a URL (HTTP/HTTPS/FTP) or server file path
                  </p>
                  <input
                    placeholder="https://example.com/taxonomy.json or /path/to/taxonomy.json"
                    value={importSourceUrl}
                    onChange={(e) => setImportSourceUrl(e.target.value)}
                    className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-violet-400/50"
                  />

                  {importError && (
                    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-400/10 text-red-400 border border-red-400/20 text-xs">
                      <AlertCircle size={14} />
                      {importError}
                    </div>
                  )}

                  <button
                    onClick={async () => {
                      if (!importSourceUrl.trim()) return;
                      setImportSourceLoading(true);
                      setImportError(null);
                      try {
                        await api.importTaxonomyFromSource(importSourceUrl);
                        setImportSourceUrl('');
                        setShowImport(false);
                        await reload();
                      } catch (err) {
                        setImportError(err.message);
                      } finally {
                        setImportSourceLoading(false);
                      }
                    }}
                    disabled={importSourceLoading || !importSourceUrl.trim()}
                    className="inline-flex items-center gap-2 bg-violet-400/10 hover:bg-violet-400/20 text-violet-400 border border-violet-400/20 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    {importSourceLoading ? <Loader2 size={16} className="animate-spin" /> : <Link size={16} />}
                    {importSourceLoading ? 'Loading...' : 'Load & Import'}
                  </button>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create Form */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="glass-card p-5 space-y-3">
              <input
                placeholder="Taxonomy name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
              />
              <input
                placeholder="Description (optional)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
              />
              <button
                onClick={handleCreate}
                disabled={creating}
                className="bg-cyan-400/10 hover:bg-cyan-400/20 text-cyan-400 border border-cyan-400/20 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50"
              >
                {creating ? 'Creating...' : 'Create Taxonomy'}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Taxonomy List */}
        <div className="space-y-3">
          <h3 className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Taxonomies</h3>
          {loading ? (
            [...Array(3)].map((_, i) => <Skeleton key={i} className="h-16" />)
          ) : taxonomies?.length > 0 ? (
            taxonomies.map((tax, i) => (
              <motion.div
                key={tax.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                onClick={() => viewTaxonomy(tax)}
                className={`glass-card p-3 cursor-pointer flex items-center justify-between ${
                  selected?.id === tax.id ? 'border-cyan-400/40 glow-cyan' : ''
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FolderTree size={16} className="text-violet-400 flex-shrink-0" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-medium text-white truncate">{tax.name}</span>
                      {tax.version > 1 && (
                        <span className="text-[9px] px-1 py-0 rounded bg-slate-800 text-slate-600 font-mono flex-shrink-0">
                          v{tax.version}
                        </span>
                      )}
                    </div>
                    {tax.description && (
                      <div className="text-xs text-slate-500 line-clamp-1">{tax.description}</div>
                    )}
                    {tax.tags && tax.tags.length > 0 && (
                      <div className="flex gap-1 mt-0.5 flex-wrap">
                        {tax.tags.slice(0, 3).map((tag, j) => (
                          <span key={j} className="text-[9px] px-1 py-0 rounded bg-violet-400/10 text-violet-400/60">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteTaxonomy(tax); }}
                    className="text-slate-600 hover:text-red-400 transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                  <ChevronRight size={14} className="text-slate-600" />
                </div>
              </motion.div>
            ))
          ) : (
            <div className="text-center py-8 text-slate-600 text-sm">No taxonomies yet</div>
          )}
        </div>

        {/* Taxonomy Detail */}
        <div className="lg:col-span-2">
          {selected ? (
            <div className="glass-card p-5 space-y-4">
              {/* Taxonomy header — view or edit mode */}
              {editingTax ? (
                <div className="bg-slate-800/40 rounded-lg p-4 space-y-2 border border-cyan-400/20">
                  <input
                    value={taxEditName}
                    onChange={e => setTaxEditName(e.target.value)}
                    placeholder="Taxonomy name"
                    className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                  />
                  <input
                    value={taxEditDesc}
                    onChange={e => setTaxEditDesc(e.target.value)}
                    placeholder="Description"
                    className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                  />
                  <input
                    value={taxEditTags}
                    onChange={e => setTaxEditTags(e.target.value)}
                    placeholder="Tags (comma-separated)"
                    className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                  />
                  <div className="flex gap-2">
                    <button onClick={handleSaveTaxonomy} disabled={savingTax} className="text-xs px-3 py-1 bg-emerald-400/10 text-emerald-400 border border-emerald-400/20 rounded-lg hover:bg-emerald-400/20 disabled:opacity-50">
                      <Save size={12} className="inline mr-1" />{savingTax ? 'Saving...' : 'Save'}
                    </button>
                    <button onClick={() => setEditingTax(false)} className="text-xs px-3 py-1 bg-slate-700/50 text-slate-400 rounded-lg hover:bg-slate-700">
                      <X size={12} className="inline mr-1" />Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-semibold text-white">{selected.name}</h3>
                      {detail?.version > 1 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-500 font-mono">
                          v{detail.version}
                        </span>
                      )}
                      <button
                        onClick={startEditTaxonomy}
                        className="text-slate-600 hover:text-cyan-400 transition-colors p-0.5"
                        title="Edit taxonomy properties"
                      >
                        <Edit3 size={14} />
                      </button>
                    </div>
                    {selected.description && (
                      <p className="text-xs text-slate-500 mt-0.5">{selected.description}</p>
                    )}
                    {detail?.tags && detail.tags.length > 0 && (
                      <div className="flex gap-1 mt-1 flex-wrap">
                        {detail.tags.map((tag, i) => (
                          <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-violet-400/10 text-violet-400/70 border border-violet-400/20">
                            <Tags size={8} className="inline mr-0.5" />{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleExport}
                      disabled={exporting}
                      className="flex items-center gap-1 bg-emerald-400/10 hover:bg-emerald-400/20 text-emerald-400 border border-emerald-400/20 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      <Download size={14} />
                      {exporting ? 'Exporting...' : 'Export'}
                    </button>
                    <button
                      onClick={() => setShowAddCat(!showAddCat)}
                      className="flex items-center gap-1 bg-violet-400/10 hover:bg-violet-400/20 text-violet-400 border border-violet-400/20 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                    >
                      <Plus size={14} />
                      Add Category
                    </button>
                  </div>
                </div>
              )}

              {/* Add Category Form */}
              <AnimatePresence>
                {showAddCat && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="bg-slate-800/40 rounded-lg p-4 space-y-3 border border-slate-700/30">
                      <div className="grid grid-cols-2 gap-3">
                        <input
                          placeholder="Category name"
                          value={catName}
                          onChange={(e) => setCatName(e.target.value)}
                          className="bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                        />
                        <input
                          placeholder="Description"
                          value={catDesc}
                          onChange={(e) => setCatDesc(e.target.value)}
                          className="bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                        />
                      </div>

                      {/* Color picker with presets */}
                      <div className="space-y-2">
                        <label className="text-xs text-slate-500">Color</label>
                        <div className="flex items-center gap-2 flex-wrap">
                          {colorPresets.map((c) => (
                            <button
                              key={c}
                              onClick={() => setCatColor(c)}
                              className={`w-6 h-6 rounded-full transition-all ${
                                catColor === c ? 'ring-2 ring-white ring-offset-2 ring-offset-slate-900 scale-110' : 'hover:scale-110'
                              }`}
                              style={{ backgroundColor: c }}
                            />
                          ))}
                          <div className="flex items-center gap-1 ml-2">
                            <Palette size={12} className="text-slate-500" />
                            <input
                              type="color"
                              value={catColor}
                              onChange={(e) => setCatColor(e.target.value)}
                              className="w-6 h-6 rounded cursor-pointer bg-transparent border-0"
                            />
                          </div>
                        </div>
                      </div>

                      {/* Parent + priority */}
                      <div className="flex gap-3 items-end">
                        <div className="flex-1">
                          <label className="text-xs text-slate-500 block mb-1">Parent Category</label>
                          <select
                            value={catParent}
                            onChange={(e) => setCatParent(e.target.value)}
                            className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                          >
                            <option value="">Root level (no parent)</option>
                            {categories.map((c) => (
                              <option key={c.id} value={c.id}>
                                {formatCategoryName(c.name)}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="w-24">
                          <label className="text-xs text-slate-500 block mb-1">Priority</label>
                          <input
                            type="number"
                            min={0}
                            value={catPriority}
                            onChange={(e) => setCatPriority(parseInt(e.target.value) || 0)}
                            className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                          />
                        </div>
                        <button
                          onClick={handleAddCategory}
                          disabled={addingCat}
                          className="bg-violet-400/10 hover:bg-violet-400/20 text-violet-400 border border-violet-400/20 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50"
                        >
                          {addingCat ? 'Adding...' : 'Add'}
                        </button>
                        <button
                          onClick={() => { setShowAddCat(false); setCatName(''); setCatDesc(''); setCatColor('#22d3ee'); setCatParent(''); setCatPriority(0); }}
                          className="bg-slate-700/50 hover:bg-slate-700 text-slate-400 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Hierarchical Categories Tree */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <FolderTree size={14} className="text-slate-500" />
                  <h4 className="text-xs text-slate-500 uppercase tracking-wider font-semibold">
                    Category Hierarchy
                  </h4>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-500 font-mono">
                    {categories.length} total
                  </span>
                </div>

                {detailLoading ? (
                  <div className="space-y-2">
                    {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-8" />)}
                  </div>
                ) : tree.length > 0 ? (
                  <div className="bg-slate-800/20 rounded-lg py-2 overflow-x-hidden overflow-y-auto max-h-[600px]">
                    {tree.map((node) => (
                      <TreeNode
                        key={node.id}
                        node={node}
                        depth={0}
                        onDelete={handleDeleteCategory}
                        allCategories={categories}
                        taxonomyId={selected.id}
                        onReload={() => viewTaxonomy(selected)}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-600 text-sm">
                    No categories yet. Add one above to start building your taxonomy tree.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="glass-card p-12 text-center text-slate-600">
              <FolderTree className="mx-auto mb-3" size={32} />
              <p>Select a taxonomy to view its category hierarchy</p>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
