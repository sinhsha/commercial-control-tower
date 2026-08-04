/**
 * CopilotPanel — Revenue Manager Copilot UI
 *
 * Two surfaces:
 *   1. Executive Summary — auto-loaded, shows the LLM-generated narrative.
 *   2. Q&A Chat — text input, fires on submit, shows grounded answer.
 *
 * Constraints honoured:
 * - ExplainabilityPanel (demand-event rationale) is NOT touched.
 * - LLM explanation text comes exclusively from the API; no client-side
 *   generation or hallucination possible here.
 * - Panel degrades silently when status=unavailable or status=error:
 *   shows structured fallback text returned by the backend.
 */
import { useState, useRef, useEffect } from 'react';
import { Spinner } from '@/components/ui/Spinner';
import type {
  CopilotResponse,
  DashboardSummary,
  GuestPersona,
  RecommendationResponse,
  AncillaryRecommendationResponse,
} from '@/types/api';
import { useExecutiveSummary, useCopilotAsk } from '@/hooks/useCopilot';

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusPill({ status }: { status: CopilotResponse['status'] }) {
  const map = {
    ok:          { label: 'AI',        bg: '#eff6ff', color: '#1d4ed8' },
    unavailable: { label: 'Fallback',  bg: '#fef9c3', color: '#854d0e' },
    error:       { label: 'Error',     bg: '#fee2e2', color: '#991b1b' },
  } as const;
  const s = map[status] ?? map.unavailable;
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        padding: '2px 7px',
        borderRadius: 4,
        background: s.bg,
        color: s.color,
        letterSpacing: '0.05em',
        textTransform: 'uppercase' as const,
      }}
    >
      {s.label}
    </span>
  );
}

// ── Explanation card ──────────────────────────────────────────────────────────

function ExplanationCard({
  response,
  loading,
}: {
  response: CopilotResponse | undefined;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 0' }}>
        <Spinner size={16} />
        <span style={{ fontSize: 13, color: '#57606a' }}>Generating executive summary…</span>
      </div>
    );
  }
  if (!response) return null;

  return (
    <div
      style={{
        background: '#f7f8fa',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        padding: '14px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#1f2328' }}>
          Executive Summary
        </span>
        <StatusPill status={response.status} />
        {response.model_used && (
          <span style={{ fontSize: 10, color: '#57606a', marginLeft: 'auto' }}>
            {response.model_used}
            {response.tokens_used > 0 ? ` · ${response.tokens_used} tokens` : ''}
          </span>
        )}
      </div>
      <p style={{ fontSize: 13, lineHeight: 1.65, color: '#1f2328', margin: 0 }}>
        {response.explanation || '—'}
      </p>
    </div>
  );
}

// ── Chat message ──────────────────────────────────────────────────────────────

interface Message {
  role: 'user' | 'assistant';
  text: string;
  status?: CopilotResponse['status'];
}

function ChatBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 8,
      }}
    >
      <div
        style={{
          maxWidth: '82%',
          padding: '9px 12px',
          borderRadius: isUser ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
          background: isUser ? '#1e3a5f' : '#f7f8fa',
          border: isUser ? 'none' : '1px solid #e5e7eb',
          fontSize: 13,
          lineHeight: 1.6,
          color: isUser ? '#e2e8f0' : '#1f2328',
        }}
      >
        {msg.text}
        {!isUser && msg.status && msg.status !== 'ok' && (
          <span style={{ marginLeft: 6 }}>
            <StatusPill status={msg.status} />
          </span>
        )}
      </div>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

interface CopilotPanelProps {
  hotelId: string;
  dashboard: DashboardSummary;
  recommendations: RecommendationResponse | undefined;
  ancillaryRecommendations: AncillaryRecommendationResponse | undefined;
  persona: GuestPersona;
}

export function CopilotPanel({
  hotelId,
  dashboard,
  recommendations,
  ancillaryRecommendations,
  persona,
}: CopilotPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll when new messages arrive
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Executive summary (auto-fetched)
  const summaryState = useExecutiveSummary(hotelId, persona);
  const summaryLoading = summaryState.status === 'loading';
  const summaryData = summaryState.status === 'success' ? summaryState.data : undefined;

  // Q&A ask
  const { state: askState, ask } = useCopilotAsk(
    hotelId,
    dashboard,
    recommendations,
    ancillaryRecommendations,
    persona
  );

  // Push answer into messages when ask completes
  useEffect(() => {
    if (askState.status === 'success') {
      setMessages((prev) => {
        // Don't duplicate if already added
        const last = prev[prev.length - 1];
        if (last?.role === 'assistant' && last.text === askState.data.explanation) return prev;
        return [
          ...prev,
          {
            role: 'assistant' as const,
            text: askState.data.explanation,
            status: askState.data.status,
          },
        ];
      });
    } else if (askState.status === 'error') {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant' as const, text: `Error: ${askState.error}`, status: 'error' },
      ]);
    }
  }, [askState]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || askState.status === 'loading') return;
    setMessages((prev) => [...prev, { role: 'user' as const, text: q }]);
    setInput('');
    void ask(q);
  }

  const SUGGESTIONS = [
    'Should I raise rates this weekend?',
    'What ancillary offers should I prioritise?',
    'How does the upcoming event affect my strategy?',
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Executive summary ─────────────────────────────────────────── */}
      <ExplanationCard response={summaryData} loading={summaryLoading} />

      {/* ── Divider ───────────────────────────────────────────────────── */}
      <div
        style={{
          borderTop: '1px solid #e5e7eb',
          paddingTop: 14,
          fontSize: 12,
          fontWeight: 600,
          color: '#57606a',
          textTransform: 'uppercase' as const,
          letterSpacing: '0.06em',
        }}
      >
        Revenue Manager Q&amp;A
      </div>

      {/* ── Chat history ──────────────────────────────────────────────── */}
      <div
        style={{
          minHeight: 80,
          maxHeight: 340,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {messages.length === 0 && (
          <div style={{ fontSize: 12, color: '#8b949e', padding: '4px 0 8px' }}>
            Ask a question about the commercial strategy for this property.
          </div>
        )}
        {messages.map((m, i) => (
          <ChatBubble key={i} msg={m} />
        ))}
        {askState.status === 'loading' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 0' }}>
            <Spinner size={14} />
            <span style={{ fontSize: 12, color: '#57606a' }}>Thinking…</span>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* ── Suggestion chips (only when no messages yet) ──────────────── */}
      {messages.length === 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6 }}>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setInput(s)}
              style={{
                fontSize: 11,
                padding: '4px 10px',
                borderRadius: 14,
                border: '1px solid #d1d5db',
                background: '#fff',
                color: '#374151',
                cursor: 'pointer',
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* ── Input form ────────────────────────────────────────────────── */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8 }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          maxLength={500}
          style={{
            flex: 1,
            fontSize: 13,
            padding: '8px 12px',
            border: '1px solid #d1d5db',
            borderRadius: 6,
            outline: 'none',
            color: '#1f2328',
          }}
        />
        <button
          type="submit"
          disabled={!input.trim() || askState.status === 'loading'}
          style={{
            fontSize: 13,
            fontWeight: 600,
            padding: '8px 16px',
            borderRadius: 6,
            border: 'none',
            background: '#1e3a5f',
            color: '#fff',
            cursor: input.trim() && askState.status !== 'loading' ? 'pointer' : 'not-allowed',
            opacity: !input.trim() || askState.status === 'loading' ? 0.5 : 1,
          }}
        >
          Ask
        </button>
      </form>
    </div>
  );
}
