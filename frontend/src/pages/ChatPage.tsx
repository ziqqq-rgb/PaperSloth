import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
} from 'react'
import {
  BarChart3,
  BookMarked,
  Filter,
  Hash,
  Loader2,
  MessageSquare,
  Search,
  Send,
  Sparkles,
  X,
  Zap,
} from 'lucide-react'
import { searchApi, streamSearch, type SearchFilters } from '../api/search'
import { historyApi } from '../api/search'
import { cx, uid } from '../utils/helpers'
import FilterChip from '../components/ui/FilterChip'
import MessageBubble from '../components/ui/MessageBubble'
import type { Message } from '../types'
import logo3 from '../assets/logo3.png'

const SUGGESTIONS = [
  { icon: Search,     text: 'Give me all questions on binary search trees from Data Structures' },
  { icon: BarChart3,  text: 'What topics appear most often in CS301 finals?' },
  { icon: Hash,       text: 'Show me recursion questions worth more than 10 marks' },
  { icon: BookMarked, text: 'Find all SQL JOIN questions from the last 3 years' },
  { icon: Zap,        text: 'What chapters should I prioritise for Operating Systems?' },
  { icon: Sparkles,   text: 'Show me Fourier Transform questions from Signals and Systems' },
]

const YEARS     = Array.from({ length: 9 }, (_, i) => 2025 - i)
const SEMESTERS = ['January', 'May', 'August', 'September']

export default function ChatPage() {
  const [messages,    setMessages]    = useState<Message[]>([])
  const [input,       setInput]       = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [filters,     setFilters]     = useState<SearchFilters>({})
  const [showFilters, setShowFilters] = useState(false)
  const [subjects,    setSubjects]    = useState<string[]>([])

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLTextAreaElement>(null)
  const abortRef  = useRef(false)

  useEffect(() => {
    searchApi
      .subjects()
      .then((data: { course_code: string }[]) => setSubjects(data.map(s => s.course_code)))
      .catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
  historyApi.get().then(({ messages: history }) => {
    if (!history.length) return
    setMessages(
      history.map(m => ({
        id:        uid(),
        role:      m.role as 'user' | 'assistant',
        content:   m.content,
        timestamp: new Date(m.created_at),
      }))
    )
  }).catch(() => {})
}, [])

  const send = useCallback(
    async (query: string = input) => {
      if (!query.trim() || isStreaming) return
      setInput('')
      setIsStreaming(true)
      abortRef.current = false

      const userMsg: Message = { id: uid(), role: 'user',      content: query, timestamp: new Date() }
      const aiMsgId = uid()
      const aiMsg:  Message = { id: aiMsgId, role: 'assistant', content: '', sources: [], isStreaming: true, timestamp: new Date() }

      setMessages(prev => [...prev, userMsg, aiMsg])
      historyApi.save('user', query)

      try {
        for await (const event of streamSearch(query, filters)) {
          if (abortRef.current) break
          if (event.type === 'sources') {
            setMessages(prev =>
              prev.map(m => m.id === aiMsgId ? { ...m, sources: event.sources } : m)
            )
          } else if (event.type === 'token') {
            setMessages(prev =>
              prev.map(m => m.id === aiMsgId ? { ...m, content: m.content + event.token } : m)
            )
          } else if (event.type === 'done') {
              setMessages(prev => {
                const final = prev.find(m => m.id === aiMsgId)
                if (final?.content) historyApi.save('assistant', final.content)
                return prev.map(m => m.id === aiMsgId ? { ...m, isStreaming: false } : m)
              })
              setIsStreaming(false)
          } else if (event.type === 'error') {
            setMessages(prev =>
              prev.map(m => m.id === aiMsgId ? { ...m, content: `Error: ${event.message}`, isStreaming: false } : m)
            )
            setIsStreaming(false)
          }
        }
      } catch {
        setMessages(prev =>
          prev.map(m =>
            m.id === aiMsgId
              ? { ...m, content: 'Search failed. Check your connection and try again.', isStreaming: false }
              : m
          )
        )
        setIsStreaming(false)
      }
    },
    [input, filters, isStreaming]
  )

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const removeFilter = (key: keyof SearchFilters) =>
    setFilters(prev => { const n = { ...prev }; delete n[key]; return n })

  const activeFilters = Object.entries(filters).filter(([, v]) => v !== undefined && v !== null && v !== '')

  return (
    <div className="flex flex-col h-full">
      {/* ── Top bar ── */}
      <div className="flex items-center justify-between px-5 h-[52px] border-b border-border bg-surface shrink-0 gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <MessageSquare size={14} className="text-amber shrink-0" />
          <span className="font-medium text-sm text-text">Ask AI</span>
          {activeFilters.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              {activeFilters.map(([k, v]) => (
                <FilterChip
                  key={k}
                  label={`${k.replace('_', ' ')}: ${v}`}
                  onRemove={() => removeFilter(k as keyof SearchFilters)}
                />
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {messages.length > 0 && (
            <button
              onClick={() => {
                historyApi.clear()
                setMessages([])
              }}
              className="text-[11px] text-muted/60 hover:text-muted font-mono transition-colors px-2"
            >
              Clear
            </button>
          )}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cx(
              'btn-ghost text-xs py-1.5 px-3 flex items-center gap-1.5',
              showFilters && 'border-amber/30 text-amber bg-amber/5'
            )}
          >
            <Filter size={12} />
            Filters
            {activeFilters.length > 0 && (
              <span className="w-4 h-4 rounded-full bg-amber text-base text-[10px] flex items-center justify-center font-bold">
                {activeFilters.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* ── Filter panel ── */}
      {showFilters && (
        <div className="border-b border-border bg-surface/80 px-5 py-3 flex flex-wrap gap-3 items-end animate-fade-in shrink-0">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono text-muted/60 uppercase tracking-widest">Subject</label>
            <select
              className="input-base text-xs py-1.5 w-36"
              value={filters.course_code ?? ''}
              onChange={e => setFilters(p => ({ ...p, course_code: e.target.value || undefined }))}
            >
              <option value="">All subjects</option>
              {subjects.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono text-muted/60 uppercase tracking-widest">Year</label>
            <select
              className="input-base text-xs py-1.5 w-28"
              value={filters.year ?? ''}
              onChange={e => setFilters(p => ({ ...p, year: e.target.value ? +e.target.value : undefined }))}
            >
              <option value="">All years</option>
              {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono text-muted/60 uppercase tracking-widest">Semester</label>
            <select
              className="input-base text-xs py-1.5 w-36"
              value={filters.semester ?? ''}
              onChange={e => setFilters(p => ({ ...p, semester: e.target.value || undefined }))}
            >
              <option value="">All semesters</option>
              {SEMESTERS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono text-muted/60 uppercase tracking-widest">Min marks</label>
            <input
              type="number"
              placeholder="e.g. 10"
              className="input-base text-xs py-1.5 w-24"
              value={filters.min_marks ?? ''}
              onChange={e => setFilters(p => ({ ...p, min_marks: e.target.value ? +e.target.value : undefined }))}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono text-muted/60 uppercase tracking-widest">Type</label>
            <select
              className="input-base text-xs py-1.5 w-32"
              value={filters.question_type ?? ''}
              onChange={e => setFilters(p => ({ ...p, question_type: e.target.value || undefined }))}
            >
              <option value="">All types</option>
              <option value="calculation">Calculation</option>
              <option value="theory">Theory</option>
              <option value="diagram">Diagram</option>
              <option value="table">Table</option>
            </select>
          </div>

          {activeFilters.length > 0 && (
            <button
              onClick={() => setFilters({})}
              className="self-end btn-ghost text-xs py-1.5 px-3 text-muted hover:text-red-400"
            >
              Clear all
            </button>
          )}
        </div>
      )}

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center px-6">
            <img src={logo3} alt="PaperSloth" className="w-44 h-44 object-contain opacity-100" />
            <h2 className="font-display text-[2rem] text-text text-center -mt-8">
              What do you want to study?
            </h2>
          </div>
        ) : (
          <div className="max-w-5xl mx-auto px-5 py-6 space-y-6">
            {messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isStreaming && messages[messages.length - 1]?.role === 'user' && (
              <div className="flex gap-3 animate-slide-up">
                <div className="w-8 h-8 rounded-xl bg-amber/8 border border-amber/20 flex items-center justify-center shrink-0">
                  <Loader2 size={13} className="text-amber animate-spin" />
                </div>
                <div className="bg-surface border border-border rounded-xl px-4 py-3 text-sm text-muted/60">
                  Searching papers…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* ── Input ── */}
      <div className="px-5 pb-5 pt-2 shrink-0">
        <div className="max-w-3xl mx-auto">
          <div className="relative flex items-end bg-surface border border-border rounded-xl transition-all focus-within:border-amber/40 focus-within:shadow-[0_0_0_3px_rgba(245,158,11,0.06)]">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about any past year exam topic…"
              rows={1}
              disabled={isStreaming}
              className="flex-1 bg-transparent text-text text-sm px-4 py-3.5 resize-none outline-none placeholder:text-muted/50 max-h-40"
              style={{ minHeight: '52px' }}
            />
            <div className="flex items-center gap-2 px-3 pb-[10px]">
              {isStreaming ? (
                <button
                  onClick={() => { abortRef.current = true; setIsStreaming(false) }}
                  title="Stop generating"
                  className="w-8 h-8 rounded-lg bg-border hover:bg-border/80 flex items-center justify-center transition-colors"
                >
                  <X size={13} className="text-muted" />
                </button>
              ) : (
                <button
                  onClick={() => send()}
                  disabled={!input.trim()}
                  title="Send (Enter)"
                  className="w-8 h-8 rounded-lg bg-amber hover:bg-amber/85 disabled:opacity-25 disabled:cursor-not-allowed flex items-center justify-center transition-all active:scale-95"
                >
                  <Send size={12} className="text-base" strokeWidth={2.5} />
                </button>
              )}
            </div>
          </div>
          <p className="text-[11px] text-muted/35 text-center mt-1.5 font-mono">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  )
}