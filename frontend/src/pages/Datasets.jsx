import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Upload, Database, Plus, Trash2, Play, FileText, Loader2 } from 'lucide-react';
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
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [conversations, setConversations] = useState(null);
  const [convLoading, setConvLoading] = useState(false);

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
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`glass-card p-8 border-2 border-dashed transition-colors text-center ${
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
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    // delete not in spec but placeholder
                  }}
                  className="text-slate-600 hover:text-red-400 transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">{ds.name}</h3>
              {ds.description && <p className="text-xs text-slate-500 mb-2 line-clamp-2">{ds.description}</p>}
              <div className="flex gap-3 text-xs text-slate-500">
                {ds.row_count != null && <span>{ds.row_count} rows</span>}
                {ds.conversation_count != null && <span>{ds.conversation_count} conversations</span>}
                {ds.created_at && <span>{new Date(ds.created_at).toLocaleDateString()}</span>}
              </div>
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
            <div className="max-h-80 overflow-y-auto space-y-2">
              {(Array.isArray(conversations) ? conversations : []).map((conv, i) => (
                <div key={conv.id || i} className="flex items-center justify-between bg-slate-800/40 rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2">
                    <FileText size={14} className="text-slate-500" />
                    <span className="text-sm text-slate-300">
                      {conv.conversation_id || conv.id || `Conversation ${i + 1}`}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500">
                    {conv.turn_count || conv.turns?.length || '?'} turns
                  </span>
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
