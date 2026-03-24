import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Bot, ChevronDown, ChevronUp } from 'lucide-react';
import IntentBadge from './IntentBadge';
import { cleanHtml } from '../utils/cleanHtml';


function SpeakerIcon({ speaker }) {
  const s = (speaker || '').toLowerCase();
  const isUser = s === 'user' || s === 'customer';
  return (
    <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
      isUser ? 'bg-cyan-400/15 text-cyan-400' : 'bg-violet-400/15 text-violet-400'
    }`}>
      {isUser ? <User size={16} /> : <Bot size={16} />}
    </div>
  );
}

function TurnCard({ turn, index }) {
  const [expanded, setExpanded] = useState(false);
  const speaker = (turn.speaker || turn.role || '').toLowerCase();
  const isUser = speaker === 'user' || speaker === 'customer';
  const cleanText = cleanHtml(turn.text || '');
  const isLong = cleanText.length > 150;

  return (
    <motion.div
      initial={{ opacity: 0, x: isUser ? -20 : 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08 }}
      className={`flex gap-3 ${isUser ? 'flex-row' : 'flex-row-reverse'}`}
    >
      <SpeakerIcon speaker={turn.speaker || turn.role} />

      <div
        className={`max-w-[75%] glass-card p-3 cursor-pointer ${
          isUser ? 'border-cyan-400/10' : 'border-violet-400/10'
        }`}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
          <span className={`text-[10px] font-mono uppercase ${isUser ? 'text-cyan-400/70' : 'text-violet-400/70'}`}>
            {isUser ? 'User' : 'Assistant'}
          </span>
          <span className="text-xs text-slate-600">|</span>
          <span className="text-xs text-slate-500">
            Turn {turn.turn_index ?? index + 1}
          </span>
          {(turn.intent || turn.intent_label) && (
            <IntentBadge label={turn.intent || turn.intent_label} parentLabel={intentHierarchy[turn.intent || turn.intent_label]} size="xs" />
          )}
          {turn.confidence != null && (
            <span className="text-[9px] text-slate-600 font-mono">
              {(turn.confidence * 100).toFixed(0)}%
            </span>
          )}
          {isLong && (
            <span className="ml-auto">
              {expanded ? <ChevronUp size={12} className="text-slate-500" /> : <ChevronDown size={12} className="text-slate-500" />}
            </span>
          )}
        </div>

        <p className="text-sm text-slate-300 leading-relaxed">
          {expanded || !isLong ? cleanText : cleanText.slice(0, 150) + '...'}
        </p>
        {isLong && !expanded && (
          <span className="text-[10px] text-cyan-400/60 hover:text-cyan-400">Show More</span>
        )}
        {isLong && expanded && (
          <span className="text-[10px] text-cyan-400/60 hover:text-cyan-400">Show Less</span>
        )}

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="mt-2 pt-2 border-t border-slate-700/50 space-y-1.5 overflow-hidden"
            >
              {turn.confidence != null && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">Confidence:</span>
                  <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden max-w-[120px]">
                    <div
                      className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 rounded-full"
                      style={{ width: `${(turn.confidence * 100).toFixed(0)}%` }}
                    />
                  </div>
                  <span className="text-xs text-slate-400">{(turn.confidence * 100).toFixed(1)}%</span>
                </div>
              )}
              {turn.method && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">Method:</span>
                  <span className="text-xs px-1.5 py-0.5 bg-slate-800 rounded text-slate-400">{turn.method}</span>
                </div>
              )}
              {turn.explanation && (
                <div className="text-[10px] text-slate-600 leading-relaxed">{turn.explanation}</div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

export default function ConversationTimeline({ turns = [], intentHierarchy = {} }) {
  if (!turns.length) {
    return (
      <div className="text-center py-12 text-slate-500">
        No turns to display
      </div>
    );
  }

  return (
    <div className="space-y-3 py-4">
      {turns.map((turn, i) => (
        <TurnCard key={turn.id || i} turn={turn} index={i} />
      ))}
    </div>
  );
}
