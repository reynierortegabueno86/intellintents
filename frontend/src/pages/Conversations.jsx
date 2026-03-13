import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Search, ChevronRight, Hash, Loader2 } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import * as api from '../utils/api';
import ConversationTimeline from '../components/ConversationTimeline';
import ConversationGraph from '../components/ConversationGraph';
import IntentBadge from '../components/IntentBadge';

function Skeleton({ className }) {
  return <div className={`skeleton ${className}`} />;
}

export default function Conversations() {
  const { data: datasets } = useApi(api.getDatasets, []);
  const [searchParams, setSearchParams] = useSearchParams();
  const [datasetId, setDatasetId] = useState('');
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [graphData, setGraphData] = useState(null);
  const [viewMode, setViewMode] = useState('timeline'); // timeline | graph
  const pendingConversationId = useRef(searchParams.get('conversationId'));

  useEffect(() => {
    if (!datasets?.length) return;
    const paramDataset = searchParams.get('datasetId');
    if (paramDataset && datasets.some(d => String(d.id) === paramDataset)) {
      setDatasetId(Number(paramDataset));
    } else if (!datasetId) {
      setDatasetId(datasets[0].id);
    }
  }, [datasets]);

  useEffect(() => {
    if (!datasetId) return;
    const currentDatasetId = datasetId; // capture for async callback
    setLoading(true);
    api.getConversations(currentDatasetId)
      .then((data) => {
        const convs = Array.isArray(data) ? data : data.conversations || [];
        setConversations(convs);

        // Auto-select conversation from URL param
        const targetId = pendingConversationId.current;
        if (targetId) {
          pendingConversationId.current = null;
          // Try to find in loaded list first; if not found (e.g. beyond pagination),
          // create a minimal stub — the detail API will fetch the full data.
          const match = convs.find(c =>
            String(c.conversation_id ?? c.id) === String(targetId)
          );
          loadConversationDetail(
            match || { id: Number(targetId) },
            currentDatasetId,
          );
          // Clean the query params after consuming them
          setSearchParams({}, { replace: true });
        }
      })
      .catch(() => setConversations([]))
      .finally(() => setLoading(false));
  }, [datasetId]);

  const loadConversationDetail = async (conv, dsId) => {
    const convId = conv.conversation_id || conv.id;
    setSelected(conv);
    setDetailLoading(true);
    setGraphData(null);

    try {
      const d = await api.getConversation(dsId, convId);
      setDetail(d);
    } catch {
      setDetail(null);
    }

    try {
      const g = await api.getConversationGraph(convId);
      setGraphData(g);
    } catch {
      setGraphData(null);
    }

    setDetailLoading(false);
  };

  const viewConversation = (conv) => {
    loadConversationDetail(conv, datasetId);
  };

  const filteredConversations = conversations.filter((c) => {
    if (!search) return true;
    const id = (c.conversation_id || c.id || '').toString().toLowerCase();
    return id.includes(search.toLowerCase());
  });

  const turns = detail?.turns || detail?.messages || (Array.isArray(detail) ? detail : []);
  const intentsInConv = [...new Set(turns.map((t) => t.intent).filter(Boolean))];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="space-y-6"
    >
      <div>
        <h1 className="text-2xl font-bold text-white">Conversations</h1>
        <p className="text-sm text-slate-500 mt-1">Explore individual conversations and their intent flows</p>
      </div>

      {/* Controls */}
      <div className="flex gap-3 flex-wrap">
        <select
          value={datasetId}
          onChange={(e) => { setDatasetId(e.target.value); setSelected(null); setDetail(null); }}
          className="bg-slate-800/80 border border-slate-700/50 rounded-lg px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
        >
          <option value="">Select dataset...</option>
          {datasets?.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>

        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-2.5 text-slate-500" />
          <input
            placeholder="Search conversations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-800/80 border border-slate-700/50 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-cyan-400/50"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Conversation List */}
        <div className="space-y-2 max-h-[calc(100vh-250px)] overflow-y-auto">
          {loading ? (
            [...Array(5)].map((_, i) => <Skeleton key={i} className="h-16" />)
          ) : filteredConversations.length > 0 ? (
            filteredConversations.map((conv, i) => {
              const convId = conv.conversation_id || conv.id;
              const isSelected = (selected?.conversation_id || selected?.id) === convId;
              return (
                <motion.div
                  key={convId || i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: Math.min(i * 0.03, 0.3) }}
                  onClick={() => viewConversation(conv)}
                  className={`glass-card p-3 cursor-pointer ${isSelected ? 'border-cyan-400/40 glow-cyan' : ''}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <MessageSquare size={14} className="text-cyan-400" />
                      <span className="text-sm font-medium text-white font-mono">
                        {convId?.toString().slice(0, 12)}
                      </span>
                    </div>
                    <ChevronRight size={14} className="text-slate-600" />
                  </div>
                  <div className="flex gap-3 mt-1 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <Hash size={10} />
                      {conv.turn_count || conv.turns?.length || '?'} turns
                    </span>
                    {conv.intents && (
                      <span>{conv.intents.length} intents</span>
                    )}
                  </div>
                </motion.div>
              );
            })
          ) : (
            <div className="text-center py-12 text-slate-600 text-sm">
              {datasetId ? 'No conversations found' : 'Select a dataset'}
            </div>
          )}
        </div>

        {/* Conversation Detail */}
        <div className="lg:col-span-2">
          {selected ? (
            <div className="space-y-4">
              {/* Header */}
              <div className="glass-card p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-white">
                    Conversation: {(selected.conversation_id || selected.id)?.toString().slice(0, 20)}
                  </h3>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setViewMode('timeline')}
                      className={`px-3 py-1 text-xs rounded-md ${viewMode === 'timeline' ? 'bg-cyan-400/15 text-cyan-400' : 'text-slate-500'}`}
                    >
                      Timeline
                    </button>
                    <button
                      onClick={() => setViewMode('graph')}
                      className={`px-3 py-1 text-xs rounded-md ${viewMode === 'graph' ? 'bg-cyan-400/15 text-cyan-400' : 'text-slate-500'}`}
                    >
                      Graph
                    </button>
                  </div>
                </div>
                {intentsInConv.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {intentsInConv.map((intent) => (
                      <IntentBadge key={intent} label={intent} size="xs" />
                    ))}
                  </div>
                )}
              </div>

              {/* Content */}
              {detailLoading ? (
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-16" />)}
                </div>
              ) : viewMode === 'timeline' ? (
                <div className="glass-card p-4 max-h-[calc(100vh-350px)] overflow-y-auto">
                  <ConversationTimeline turns={turns} />
                </div>
              ) : (
                <div className="glass-card p-4">
                  {graphData ? (
                    <ConversationGraph data={graphData} />
                  ) : (
                    <div className="h-80 flex items-center justify-center text-slate-600 text-sm">
                      No graph data available
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="glass-card p-12 text-center text-slate-600">
              <MessageSquare className="mx-auto mb-3" size={32} />
              <p>Select a conversation to explore</p>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
