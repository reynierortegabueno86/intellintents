import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Upload, Database, Plus, Trash2, Play, FileText, Loader2, Link, ChevronRight, ChevronDown, User, Bot, Pencil, Check, X } from 'lucide-react';
import { useApi, useLazyApi } from '../hooks/useApi';
import * as api from '../utils/api';

function Skeleton({ className }) {
  return <div className={`skeleton ${className}`} />;
}

export default function Datasets() {
  const { data: datasets, loading, execute: reload } = useApi(api.getDatasets, []);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [uploadName, setUploadName] = useState('');
  const [uploadDesc, setUploadDesc] = useState('');
  const [uploadMode, setUploadMode] = useState('file');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceLoading, setSourceLoading] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [conversations, setConversations] = useState(null);
  const [convLoading, setConvLoading] = useState(false);
  const [expandedConv, setExpandedConv] = useState(null);
  const [turns, setTurns] = useState([]);
  const [turnsLoading, setTurnsLoading] = useState(false);
  const [editingDataset, setEditingDataset] = useState(null);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editSaving, setEditSaving] = useState(false);

  const handleFile = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadDataset(file, uploadName || file.name, uploadDesc);
      setUploadName('');
      setUploadDesc('');
      await reload();
    } catch (err) {
      alert('Upload failed: ' + err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  };

  const handleSeed = async () => {
    setSeeding(true);
    try {
      await api.seedDemo();
      await reload();
    } catch (err) {
      alert('Seed failed: ' + err.message);
    } finally {
      setSeeding(false);
    }
  };

  const viewConversations = async (ds) => {
    setSelectedDataset(ds);
    setExpandedConv(null);
    setTurns([]);
    setConvLoading(true);
    try {
      const convs = await api.getConversations(ds.id);
      setConversations(convs);
    } catch {
      setConversations([]);
    } finally {
      setConvLoading(false);
    }
  };

  const toggleConversation = async (conv) => {
    if (expandedConv === conv.id) {
      setExpandedConv(null);
      setTurns([]);
      return;
    }
    setExpandedConv(conv.id);
    setTurnsLoading(true);
    try {
      const detail = await api.getConversation(selectedDataset.id, conv.id);
      setTurns(detail.turns || []);
    } catch {
      setTurns([]);
    } finally {
      setTurnsLoading(false);
    }
  };

  const startEditing = (e, ds) => {
    e.stopPropagation();
    setEditingDataset(ds.id);
    setEditName(ds.name);
    setEditDesc(ds.description || '');
  };

  const cancelEditing = (e) => {
    e.stopPropagation();
    setEditingDataset(null);
  };

  const saveEditing = async (e, ds) => {
    e.stopPropagation();
    if (!editName.trim()) return;
    setEditSaving(true);
    try {
      const updates = {};
      if (editName.trim() !== ds.name) updates.name = editName.trim();
      if (editDesc !== (ds.description || '')) updates.description = editDesc || null;
      if (Object.keys(updates).length > 0) {
        await api.updateDataset(ds.id, updates);
        await reload();
        if (selectedDataset?.id === ds.id) {
          setSelectedDataset({ ...selectedDataset, ...updates });
        }
      }
      setEditingDataset(null);
    } catch (err) {
      alert('Update failed: ' + err.message);
    } finally {
      setEditSaving(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Datasets</h1>
          <p className="text-sm text-slate-500 mt-1">Upload and manage conversation datasets</p>
        </div>
        <button
          onClick={handleSeed}
          disabled={seeding}
          className="flex items-center gap-2 bg-emerald-400/10 hover:bg-emerald-400/20 text-emerald-400 border border-emerald-400/20 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50"
        >
          {seeding ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          Seed Demo Data
        </button>
      </div>

      {/* Upload Area */}
      <div className="glass-card p-8 text-center">
        {/* Mode toggle */}
        <div className="flex justify-center gap-1 mb-5 bg-slate-800/60 rounded-lg p-1 inline-flex mx-auto">
          <button
            onClick={() => setUploadMode('file')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              uploadMode === 'file'
                ? 'bg-cyan-400/15 text-cyan-400'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <Upload size={14} />
            Upload File
          </button>
          <button
            onClick={() => setUploadMode('source')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              uploadMode === 'source'
                ? 'bg-cyan-400/15 text-cyan-400'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <Link size={14} />
            Load from Source
          </button>
        </div>

        {uploadMode === 'file' ? (
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-lg p-6 transition-colors ${
              dragOver ? 'border-cyan-400/50 bg-cyan-400/5' : 'border-slate-700/50'
            }`}
          >
            <Upload className="mx-auto mb-3 text-slate-500" size={32} />
            <p className="text-slate-400 mb-3">
              Drag & drop a CSV/JSON file here, or click to browse
            </p>
            <div className="flex gap-3 justify-center mb-3">
              <input
                placeholder="Dataset name"
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
                className="bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50 w-48"
              />
              <input
                placeholder="Description (optional)"
                value={uploadDesc}
                onChange={(e) => setUploadDesc(e.target.value)}
                className="bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50 w-64"
              />
            </div>
            <label className="inline-flex items-center gap-2 bg-cyan-400/10 hover:bg-cyan-400/20 text-cyan-400 border border-cyan-400/20 rounded-lg px-4 py-2 text-sm font-medium cursor-pointer transition-colors">
              {uploading ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
              {uploading ? 'Uploading...' : 'Choose File'}
              <input
                type="file"
                accept=".csv,.json,.jsonl"
                className="hidden"
                onChange={(e) => handleFile(e.target.files[0])}
                disabled={uploading}
              />
            </label>
          </div>
        ) : (
          <div className="space-y-3">
            <Link className="mx-auto mb-3 text-slate-500" size={32} />
            <p className="text-slate-400 mb-3 text-sm">
              Load a dataset from a URL (HTTP/HTTPS/FTP) or server file path
            </p>
            <input
              placeholder="https://example.com/data.csv or /path/to/file.csv"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
            />
            <div className="flex gap-3 justify-center">
              <input
                placeholder="Dataset name"
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
                className="bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50 w-48"
              />
              <input
                placeholder="Description (optional)"
                value={uploadDesc}
                onChange={(e) => setUploadDesc(e.target.value)}
                className="bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50 w-64"
              />
            </div>
            <button
              onClick={async () => {
                if (!sourceUrl.trim() || !uploadName.trim()) return;
                setSourceLoading(true);
                try {
                  const ds = await api.loadDatasetFromSource(sourceUrl, uploadName, uploadDesc);
                  setSourceUrl('');
                  setUploadName('');
                  setUploadDesc('');
                  await reload();
                  // If processing in background, poll until ready
                  if (ds.status === 'processing') {
                    const poll = setInterval(async () => {
                      try {
                        const updated = await api.getDataset(ds.id);
                        if (updated.status === 'ready' || updated.status === 'failed') {
                          clearInterval(poll);
                          await reload();
                          if (updated.status === 'failed') {
                            alert('Ingestion failed: ' + (updated.status_detail || 'Unknown error'));
                          }
                        }
                      } catch { clearInterval(poll); }
                    }, 3000);
                  }
                } catch (err) {
                  alert('Load failed: ' + err.message);
                } finally {
                  setSourceLoading(false);
                }
              }}
              disabled={sourceLoading || !sourceUrl.trim() || !uploadName.trim()}
              className="inline-flex items-center gap-2 bg-cyan-400/10 hover:bg-cyan-400/20 text-cyan-400 border border-cyan-400/20 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {sourceLoading ? <Loader2 size={16} className="animate-spin" /> : <Link size={16} />}
              {sourceLoading ? 'Loading...' : 'Load'}
            </button>
          </div>
        )}
      </div>

      {/* Dataset List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-36" />)}
        </div>
      ) : datasets?.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {datasets.map((ds, i) => (
            <motion.div
              key={ds.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className={`glass-card p-4 cursor-pointer ${selectedDataset?.id === ds.id ? 'border-cyan-400/40 glow-cyan' : ''}`}
              onClick={() => viewConversations(ds)}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="w-9 h-9 rounded-lg bg-violet-400/10 flex items-center justify-center">
                  <Database size={18} className="text-violet-400" />
                </div>
                <div className="flex items-center gap-1">
                  {editingDataset !== ds.id && (
                    <button
                      onClick={(e) => startEditing(e, ds)}
                      className="text-slate-600 hover:text-cyan-400 transition-colors"
                      title="Edit dataset"
                    >
                      <Pencil size={14} />
                    </button>
                  )}
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      if (!confirm(`Delete "${ds.name}"? This will remove all conversations and turns.`)) return;
                      try {
                        await api.deleteDataset(ds.id);
                        if (selectedDataset?.id === ds.id) {
                          setSelectedDataset(null);
                          setConversations(null);
                        }
                        await reload();
                      } catch (err) {
                        alert('Delete failed: ' + err.message);
                      }
                    }}
                    className="text-slate-600 hover:text-red-400 transition-colors"
                    title="Delete dataset"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {editingDataset === ds.id ? (
                <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder="Dataset name"
                    className="w-full bg-slate-800/80 border border-slate-700/50 rounded px-2 py-1 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') saveEditing(e, ds);
                      if (e.key === 'Escape') cancelEditing(e);
                    }}
                  />
                  <textarea
                    value={editDesc}
                    onChange={(e) => setEditDesc(e.target.value)}
                    placeholder="Description (optional)"
                    rows={2}
                    className="w-full bg-slate-800/80 border border-slate-700/50 rounded px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-400/50 resize-none"
                    onKeyDown={(e) => {
                      if (e.key === 'Escape') cancelEditing(e);
                    }}
                  />
                  <div className="flex gap-1 justify-end">
                    <button
                      onClick={(e) => cancelEditing(e)}
                      className="p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-700/50 transition-colors"
                      title="Cancel"
                    >
                      <X size={14} />
                    </button>
                    <button
                      onClick={(e) => saveEditing(e, ds)}
                      disabled={editSaving || !editName.trim()}
                      className="p-1 rounded text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 transition-colors disabled:opacity-30"
                      title="Save"
                    >
                      {editSaving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <h3 className="text-sm font-semibold text-white mb-1">{ds.name}</h3>
                  {ds.description && <p className="text-xs text-slate-500 mb-2 line-clamp-2">{ds.description}</p>}
                </>
              )}
              {ds.status === 'processing' ? (
                <div className="flex items-center gap-2 text-xs text-amber-400">
                  <Loader2 size={12} className="animate-spin" />
                  Processing... large files may take a few minutes
                </div>
              ) : ds.status === 'failed' ? (
                <div className="text-xs text-red-400">
                  Failed: {ds.status_detail || 'Unknown error'}
                </div>
              ) : (
                <div className="flex gap-3 text-xs text-slate-500">
                  {ds.row_count != null && <span>{ds.row_count} rows</span>}
                  {ds.conversation_count != null && <span>{ds.conversation_count} conversations</span>}
                  {ds.created_at && <span>{new Date(ds.created_at).toLocaleDateString()}</span>}
                </div>
              )}
            </motion.div>
          ))}
        </div>
      ) : (
        <div className="glass-card p-12 text-center text-slate-500">
          <Database className="mx-auto mb-3 text-slate-600" size={32} />
          <p>No datasets yet. Upload a file or seed demo data to get started.</p>
        </div>
      )}

      {/* Conversations for selected dataset */}
      {selectedDataset && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-5"
        >
          <h2 className="text-sm font-semibold text-white mb-3">
            Conversations in "{selectedDataset.name}"
          </h2>
          {convLoading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10" />)}
            </div>
          ) : conversations?.length > 0 ? (
            <div className="max-h-[32rem] overflow-y-auto space-y-1">
              {(Array.isArray(conversations) ? conversations : []).map((conv, i) => (
                <div key={conv.id || i}>
                  <div
                    className={`flex items-center justify-between rounded-lg px-3 py-2 cursor-pointer transition-colors ${
                      expandedConv === conv.id ? 'bg-cyan-400/10 border border-cyan-400/20' : 'bg-slate-800/40 hover:bg-slate-800/60'
                    }`}
                    onClick={() => toggleConversation(conv)}
                  >
                    <div className="flex items-center gap-2">
                      {expandedConv === conv.id
                        ? <ChevronDown size={14} className="text-cyan-400" />
                        : <ChevronRight size={14} className="text-slate-500" />}
                      <FileText size={14} className="text-slate-500" />
                      <span className="text-sm text-slate-300">
                        {conv.external_id || conv.conversation_id || `Conversation ${i + 1}`}
                      </span>
                    </div>
                    <span className="text-xs text-slate-500">
                      {conv.turn_count || conv.turns?.length || '?'} turns
                    </span>
                  </div>
                  {expandedConv === conv.id && (
                    <div className="ml-6 mt-1 mb-2 border-l-2 border-slate-700/50 pl-3 space-y-1">
                      {turnsLoading ? (
                        <div className="flex items-center gap-2 py-2 text-slate-500 text-xs">
                          <Loader2 size={12} className="animate-spin" /> Loading turns...
                        </div>
                      ) : turns.length > 0 ? (
                        turns.map((turn) => (
                          <div key={turn.id} className="flex items-start gap-2 py-1.5 px-2 rounded bg-slate-800/30 text-xs">
                            <div className="flex-shrink-0 mt-0.5">
                              {turn.speaker?.toLowerCase() === 'agent' || turn.speaker?.toLowerCase() === 'assistant'
                                ? <Bot size={12} className="text-violet-400" />
                                : <User size={12} className="text-cyan-400" />}
                            </div>
                            <div className="min-w-0">
                              <span className="font-medium text-slate-400">{turn.speaker}</span>
                              <span className="text-slate-600 mx-1">·</span>
                              <span className="text-slate-500">turn {turn.turn_index}</span>
                              <p className="text-slate-300 mt-0.5 break-words">{turn.text}</p>
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="text-xs text-slate-600 py-1">No turns found.</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">No conversations found.</p>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}
