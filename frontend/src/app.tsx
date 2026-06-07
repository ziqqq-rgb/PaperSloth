import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  Fragment,
} from 'react'
import BrowsePage from './BrowsePage'
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Link,
  useNavigate,
  useLocation,
} from 'react-router-dom'
import {
  Search,
  BookOpen,
  LogOut,
  MessageSquare,
  ChevronDown,
  Loader2,
  AlertCircle,
  Send,
  Sparkles,
  FileText,
  X,
  Filter,
  Hash,
  Eye,
  ChevronRight,
  Database,
  BarChart3,
  Star,
  PanelLeftClose,
  PanelLeftOpen,
  Clock,
  Layers,
  ImageIcon,
  CheckCircle2,
  Zap,
  BookMarked,
  Download,
} from 'lucide-react'
import { useAuthStore } from './authStore'
import { authApi } from './auth'
import {
  searchApi,
  streamSearch,
  type SearchFilters,
  type Source,
} from './search'

import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import logo from './assets/logo.svg'

// ─── Types ────────────────────────────────────────────────────────────────────

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  isStreaming?: boolean
  timestamp: Date
}

interface Paper {
  course_code: string
  subject_name: string
  semester: string
  year: number
  total_questions: number
  total_marks: number
  questions_with_images: number
  has_pdf: boolean
  file_size_kb: number
}

interface Question {
  parent_id: string
  question_number: string
  full_text: string
  total_marks: number
  children: unknown
  image_urls: Record<string, string>
}

// ─── Utils ────────────────────────────────────────────────────────────────────

const uid = () => Math.random().toString(36).slice(2)

const cx = (...args: (string | false | null | undefined)[]) =>
  args.filter(Boolean).join(' ')

const cleanSemester = (sem: string, year: number): string => {
  let s = sem
    .replace(/\bSEMESTER\b/gi, '')
    .replace(new RegExp(`\\b${year}\\b`, 'g'), '')
    .trim()
  s = s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()
  return `${s} ${year}`
}

const fmtSize = (kb: number): string => {
  if (!kb) return ''
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

// ─── Auth Page ────────────────────────────────────────────────────────────────

function AuthPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res =
        mode === 'login'
          ? await authApi.login(email, password)
          : await authApi.register(email, password, name)
      setAuth(res.access_token, res.user)
      navigate('/chat')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Something went wrong'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const features = [
    {
      icon: Search,
      title: 'Semantic search',
      desc: 'Find questions by topic, concept, or question type — not just keywords.',
    },
    {
      icon: Sparkles,
      title: 'AI-powered answers',
      desc: 'Ask naturally and get cited responses from real past year papers.',
    },
    {
      icon: BarChart3,
      title: 'Trend analysis',
      desc: 'See which topics appear most and how exam patterns shift over time.',
    },
    {
      icon: Layers,
      title: 'Practice generation',
      desc: 'Build custom mock exams from any subject, year, or topic combination.',
    },
  ]

  return (
    <div className="min-h-screen bg-base flex">
      {/* ── Left branding panel ── */}
      <div className="hidden lg:flex lg:w-[52%] bg-surface border-r border-border flex-col">
        <div className="flex items-center gap-3 px-10 pt-10">
            <img src={logo} alt="PaperSloth" className="w-14 h-14 object-contain" />
          <span className="font-display text-xl text-text tracking-tight">
            PaperSloth
          </span>
        </div>

        <div className="flex-1 flex flex-col justify-center px-12">
          <p className="font-mono text-xs text-amber/70 uppercase tracking-[0.2em] mb-4">
            UTP Past Year Exam Assistant
          </p>
          <h1 className="font-display text-[2.8rem] leading-[1.1] text-text mb-6">
            Study smarter,
            <br />
            <em className="text-amber not-italic">not harder.</em>
          </h1>
          <p className="text-muted text-base leading-relaxed max-w-sm mb-12">
            Every UTP past year paper, semantically indexed and instantly
            searchable. Just ask.
          </p>

          <div className="grid grid-cols-2 gap-4">
            {features.map(({ icon: Icon, title, desc }) => (
              <div
                key={title}
                className="p-4 rounded-xl border border-border bg-base/40"
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon size={14} className="text-amber" />
                  <span className="text-xs font-medium text-text">{title}</span>
                </div>
                <p className="text-xs text-muted leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="px-12 pb-8 flex items-center gap-2 text-muted/40">
          <div className="w-1.5 h-1.5 rounded-full bg-amber/40" />
          <span className="text-xs font-mono">
            Powered by Gemini + Pinecone RAG
          </span>
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div className="flex-1 flex items-center justify-center p-8 bg-base">
        <div className="w-full max-w-[360px]">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-10">
              <img src={logo} alt="PaperSloth" className="w-14 h-14 rounded-lg object-contain" />
            <span className="font-display text-xl text-text">PaperSloth</span>
          </div>

          <h2 className="font-display text-[2rem] text-text mb-1.5 leading-tight">
            {mode === 'login' ? 'Welcome back' : 'Get started'}
          </h2>
          <p className="text-muted text-sm mb-8">
            {mode === 'login'
              ? 'Sign in to access your papers'
              : 'Create your free account'}
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-[11px] font-mono text-muted/70 uppercase tracking-widest mb-1.5">
                  Full name
                </label>
                <input
                  className="input-base"
                  placeholder="Ahmad Razif"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
            )}

            <div>
              <label className="block text-[11px] font-mono text-muted/70 uppercase tracking-widest mb-1.5">
                Email
              </label>
              <input
                className="input-base"
                type="email"
                placeholder="you@utp.edu.my"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-mono text-muted/70 uppercase tracking-widest mb-1.5">
                Password
              </label>
              <input
                className="input-base"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 text-red-400 text-xs bg-red-400/8 border border-red-400/20 rounded-lg px-3 py-2.5">
                <AlertCircle size={13} className="shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 mt-1"
            >
              {loading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <CheckCircle2 size={14} />
              )}
              {mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <p className="text-center text-sm text-muted mt-6">
            {mode === 'login'
              ? "Don't have an account? "
              : 'Already have an account? '}
            <button
              className="text-amber hover:text-amber/80 transition-colors"
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login')
                setError('')
              }}
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

function Sidebar() {
  const { user, logout } = useAuthStore()
  const location = useLocation()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)

  const nav = [
    { path: '/chat', icon: MessageSquare, label: 'Ask AI' },
    { path: '/browse', icon: BookOpen, label: 'Browse Papers' },
  ]

  return (
    <aside
      className={cx(
        'h-screen bg-surface border-r border-border flex flex-col shrink-0 transition-all duration-200 ease-in-out',
        collapsed ? 'w-[56px]' : 'w-[220px]'
      )}
    >
      {/* Logo */}
      <div
        className={cx(
          'flex items-center h-[52px] border-b border-border px-3.5 shrink-0',
          collapsed ? 'justify-center' : 'gap-2.5'
        )}
      >
          <img src={logo} alt="PaperSloth" className="w-14 h-14 rounded-lg object-contain" />
        
        {!collapsed && (
          <span className="font-display text-[1.1rem] text-text leading-none">
            PaperSloth
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 p-2 space-y-0.5">
        {nav.map(({ path, icon: Icon, label }) => {
          const active = location.pathname === path
          return (
            <Link
              key={path}
              to={path}
              title={collapsed ? label : undefined}
              className={cx(
                'flex items-center rounded-lg text-sm transition-all duration-100',
                collapsed ? 'justify-center h-9 w-9 mx-auto' : 'gap-2.5 px-3 py-2',
                active
                  ? 'bg-amber/10 text-amber'
                  : 'text-muted hover:text-text hover:bg-border/60'
              )}
            >
              <Icon size={15} className="shrink-0" />
              {!collapsed && <span className="font-medium">{label}</span>}
            </Link>
          )
        })}
      </nav>

      {/* Bottom */}
      <div className="p-2 border-t border-border space-y-0.5">
        {!collapsed && user && (
          <div className="px-3 py-2 mb-1">
            <p className="text-xs font-medium text-text truncate">
              {user.name || user.email}
            </p>
            <p className="text-[11px] text-muted truncate font-mono">
              {user.email}
            </p>
          </div>
        )}

        <button
          onClick={() => setCollapsed(!collapsed)}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={cx(
            'flex items-center rounded-lg text-muted hover:text-text hover:bg-border/60 text-sm transition-all duration-100',
            collapsed ? 'justify-center h-9 w-9 mx-auto' : 'gap-2.5 px-3 py-2 w-full'
          )}
        >
          {collapsed ? (
            <PanelLeftOpen size={15} />
          ) : (
            <>
              <PanelLeftClose size={15} className="shrink-0" />
              <span>Collapse</span>
            </>
          )}
        </button>

        <button
          onClick={() => {
            logout()
            navigate('/login')
          }}
          title="Sign out"
          className={cx(
            'flex items-center rounded-lg text-muted hover:text-red-400 hover:bg-red-400/8 text-sm transition-all duration-100',
            collapsed ? 'justify-center h-9 w-9 mx-auto' : 'gap-2.5 px-3 py-2 w-full'
          )}
        >
          <LogOut size={15} className="shrink-0" />
          {!collapsed && <span>Sign out</span>}
        </button>
      </div>
    </aside>
  )
}

// ─── App Shell ────────────────────────────────────────────────────────────────

function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-base overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-hidden min-w-0">{children}</main>
    </div>
  )
}

// ─── Exam Image ───────────────────────────────────────────────────────────────

function ExamImage({ url, label }: { url: string; label: string }) {
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading');

  return (
    <div className="relative flex items-center justify-center">
      {status === 'loading' && (
        <div className="w-64 h-40 rounded-xl bg-border/40 border border-border animate-pulse flex items-center justify-center">
          <Loader2 size={16} className="text-muted/40 animate-spin" />
        </div>
      )}

      {status === 'error' && (
        <div className="w-64 h-40 rounded-xl bg-border/30 border border-dashed border-border/60 flex flex-col items-center justify-center gap-2">
          <ImageIcon size={20} className="text-muted/30" />
          <span className="text-[10px] text-muted/40 font-mono text-center px-3">{label}</span>
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="text-[10px] text-amber/60 hover:text-amber font-mono underline"
            onClick={e => e.stopPropagation()}
          >
            Open image ↗
          </a>
        </div>
      )}

      <img
        src={url}
        alt={label}
        onLoad={() => setStatus('ok')}
        onError={() => setStatus('error')}
        className={cx(
          'max-w-full max-h-80 rounded-xl border border-border object-contain',
          status !== 'ok' && 'hidden'
        )}
      />
    </div>
  );
}

// ─── Source Card ──────────────────────────────────────────────────────────────

function SourceCard({ source, index }: { source: Source; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const imageEntries = Object.entries(source.image_urls ?? {})
  const hasImages = imageEntries.length > 0

  return (
    <div className="card animate-fade-in border-border/70 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start justify-between gap-3 text-left"
      >
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="shrink-0 w-5 h-5 rounded-md bg-amber/10 border border-amber/20 flex items-center justify-center text-[10px] font-mono font-bold text-amber">
            {index + 1}
          </span>
          <span className="font-mono text-[11px] font-medium text-amber bg-amber/5 border border-amber/15 px-1.5 py-0.5 rounded">
            {source.course_code}
          </span>
          <span className="text-[11px] text-muted font-mono">
            {cleanSemester(source.semester, source.year)}
          </span>
          {source.question_number && (
            <span className="text-[11px] text-muted/70 font-mono">
              Q{source.question_number}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {source.total_marks != null && (
            <span className="text-[11px] text-muted font-mono">
              {source.total_marks}m
            </span>
          )}
          {hasImages && (
            <ImageIcon size={11} className="text-muted/60" />
          )}
          <ChevronDown
            size={13}
            className={cx(
              'text-muted/60 transition-transform',
              expanded && 'rotate-180'
            )}
          />
        </div>
      </button>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-border/60 animate-fade-in">
          {source.full_text ? (
            <p className="text-[14px] text-muted leading-relaxed font-mono whitespace-pre-wrap">
              {source.full_text}
            </p>
          ) : (
            <p className="text-[14px] text-muted/50 italic">
              Full text not available
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Message Bubble ───────────────────────────────────────────────────────────
function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div className={cx('flex gap-3 animate-slide-up', isUser && 'flex-row-reverse')}>
      <div
        className={cx(
          'w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-0.5 border',
          isUser ? 'bg-border/60 border-border' : 'bg-amber/8 border-amber/20'
        )}
      >
        {isUser ? (
          <span className="text-[10px] text-muted font-mono font-semibold">you</span>
        ) : (
          <Sparkles size={13} className="text-amber" />
        )}
      </div>

      <div className={cx('flex-1 max-w-[92%]', isUser && 'flex flex-col items-end')}>
        <div
            className={cx(
              'rounded-xl px-4 py-3 text-base leading-relaxed',
              isUser
                ? 'bg-amber/8 border border-amber/20 text-text whitespace-pre-wrap'
                : 'bg-surface border border-border text-text prose prose-invert max-w-none'
            )}
          >
            {isUser ? (
              <>
                {message.content}
                {message.isStreaming && (
                  <span className="inline-block w-[3px] h-[1em] bg-amber animate-blink rounded-sm ml-0.5 align-middle" />
                )}
              </>
            ) : (
              <>
                {message.content ? (
                  <ReactMarkdown
                    remarkPlugins={[remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                  >
                    {message.content}
                  </ReactMarkdown>
                ) : !message.isStreaming ? (
                  <span className="text-muted/50 italic text-xs">No response</span>
                ) : null}
                {message.isStreaming && (
                  <span className="inline-block w-[3px] h-[1em] bg-amber animate-blink rounded-sm ml-0.5 align-middle" />
                )}
              </>
            )}
          </div>

        {!isUser && !message.isStreaming && message.sources && message.sources.length > 0 && (() => {
          const images = Object.entries(message.sources[0].image_urls ?? {})
          if (images.length === 0) return null
          return (
            <div className="mt-4 flex flex-col items-center gap-2">
              {images.map(([label, url]) => (
                <ExamImage key={label} url={url} label={label} />
              ))}
            </div>
          )
        })()}
      </div>
    </div>
  )
}

// ─── Chat Page ────────────────────────────────────────────────────────────────

const SUGGESTIONS = [
  {
    icon: Search,
    text: 'Give me all questions on binary search trees from Data Structures',
  },
  {
    icon: BarChart3,
    text: 'What topics appear most often in CS301 finals?',
  },
  {
    icon: Hash,
    text: 'Show me recursion questions worth more than 10 marks',
  },
  {
    icon: BookMarked,
    text: 'Find all SQL JOIN questions from the last 3 years',
  },
  {
    icon: Zap,
    text: 'What chapters should I prioritise for Operating Systems?',
  },
  {
    icon: Sparkles,
    text: 'Show me Fourier Transform questions from Signals and Systems',
  },
]

function FilterChip({
  label,
  onRemove,
}: {
  label: string
  onRemove: () => void
}) {
  return (
    <span className="inline-flex items-center gap-1 bg-amber/8 border border-amber/20 text-amber text-[11px] font-mono px-2 py-0.5 rounded-full">
      {label}
      <button onClick={onRemove} className="hover:opacity-70 transition-opacity">
        <X size={10} />
      </button>
    </span>
  )
}

function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [filters, setFilters] = useState<SearchFilters>({})
  const [showFilters, setShowFilters] = useState(false)
  const [subjects, setSubjects] = useState<string[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef(false)

  const YEARS = Array.from({ length: 9 }, (_, i) => 2025 - i)
  const SEMESTERS = ['January', 'May', 'August', 'September']

  useEffect(() => {
    searchApi
      .subjects()
      .then((data: { course_code: string }[]) =>
        setSubjects(data.map((s) => s.course_code))
      )
      .catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = useCallback(
    async (query: string = input) => {
      if (!query.trim() || isStreaming) return
      setInput('')
      setIsStreaming(true)
      abortRef.current = false

      const userMsg: Message = {
        id: uid(),
        role: 'user',
        content: query,
        timestamp: new Date(),
      }
      const aiMsgId = uid()
      const aiMsg: Message = {
        id: aiMsgId,
        role: 'assistant',
        content: '',
        sources: [],
        isStreaming: true,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, userMsg, aiMsg])

      try {
        for await (const event of streamSearch(query, filters)) {
          if (abortRef.current) break
          if (event.type === 'sources') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === aiMsgId ? { ...m, sources: event.sources } : m
              )
            )
          } else if (event.type === 'token') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === aiMsgId
                  ? { ...m, content: m.content + event.token }
                  : m
              )
            )
          } else if (event.type === 'done') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === aiMsgId ? { ...m, isStreaming: false } : m
              )
            )
            setIsStreaming(false)
          } else if (event.type === 'error') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === aiMsgId
                  ? {
                      ...m,
                      content: `Error: ${event.message}`,
                      isStreaming: false,
                    }
                  : m
              )
            )
            setIsStreaming(false)
          }
        }
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMsgId
              ? {
                  ...m,
                  content: 'Search failed. Check your connection and try again.',
                  isStreaming: false,
                }
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
    setFilters((prev) => {
      const n = { ...prev }
      delete n[key]
      return n
    })

  const activeFilters = Object.entries(filters).filter(
    ([, v]) => v !== undefined && v !== null && v !== ''
  )

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
              onClick={() => setMessages([])}
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
            <label className="text-[10px] font-mono text-muted/60 uppercase tracking-widest">
              Subject
            </label>
            <select
              className="input-base text-xs py-1.5 w-36"
              value={filters.course_code ?? ''}
              onChange={(e) =>
                setFilters((p) => ({
                  ...p,
                  course_code: e.target.value || undefined,
                }))
              }
            >
              <option value="">All subjects</option>
              {subjects.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono text-muted/60 uppercase tracking-widest">
              Year
            </label>
            <select
              className="input-base text-xs py-1.5 w-28"
              value={filters.year ?? ''}
              onChange={(e) =>
                setFilters((p) => ({
                  ...p,
                  year: e.target.value ? +e.target.value : undefined,
                }))
              }
            >
              <option value="">All years</option>
              {YEARS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono text-muted/60 uppercase tracking-widest">
              Semester
            </label>
            <select
              className="input-base text-xs py-1.5 w-36"
              value={filters.semester ?? ''}
              onChange={(e) =>
                setFilters((p) => ({
                  ...p,
                  semester: e.target.value || undefined,
                }))
              }
            >
              <option value="">All semesters</option>
              {SEMESTERS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono text-muted/60 uppercase tracking-widest">
              Min marks
            </label>
            <input
              type="number"
              placeholder="e.g. 10"
              className="input-base text-xs py-1.5 w-24"
              value={filters.min_marks ?? ''}
              onChange={(e) =>
                setFilters((p) => ({
                  ...p,
                  min_marks: e.target.value ? +e.target.value : undefined,
                }))
              }
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono text-muted/60 uppercase tracking-widest">
              Type
            </label>
            <select
              className="input-base text-xs py-1.5 w-32"
              value={filters.question_type ?? ''}
              onChange={(e) =>
                setFilters((p) => ({
                  ...p,
                  question_type: e.target.value || undefined,
                }))
              }
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
            <div className="w-16 h-16 rounded-2xl bg-amber/8 border border-amber/20 flex items-center justify-center mb-6">
              <Sparkles size={26} className="text-amber" />
            </div>
            <h2 className="font-display text-[2rem] text-text text-center">
              What do you want to study?
            </h2>
          </div>
        ) : (
          <div className="max-w-5xl mx-auto px-5 py-6 space-y-6">
            {messages.map((msg) => (
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
              onChange={(e) => setInput(e.target.value)}
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
                  onClick={() => {
                    abortRef.current = true
                    setIsStreaming(false)
                  }}
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

// ─── Paper Detail Modal ───────────────────────────────────────────────────────

function PaperDetailModal({
  paper,
  onClose,
}: {
  paper: Paper
  onClose: () => void
}) {
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [downloading, setDownloading] = useState(false)
  const [dlError, setDlError] = useState('')

  useEffect(() => {
    searchApi
      .getPaper(paper.course_code, paper.year, paper.semester)
      .then((data: { questions: Question[] }) =>
        setQuestions(data.questions ?? [])
      )
      .catch(() => setError('Failed to load questions'))
      .finally(() => setLoading(false))
  }, [paper])

  const toggle = (id: string) =>
    setExpanded((prev) => {
      const n = new Set(prev)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setDownloading(true)
    setDlError('')
    try {
      const info = await searchApi.downloadPaper(
        paper.course_code, paper.year, paper.semester
      )
      // Open signed URL in a new tab — browser handles the PDF download
      window.open(info.url, '_blank', 'noopener,noreferrer')
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Download failed'
      setDlError(detail)
    } finally {
      setDownloading(false)
    }
  }

  const totalImages = questions.reduce(
    (sum, q) => sum + Object.keys(q.image_urls ?? {}).length,
    0
  )

  return (
    <div
      className="fixed inset-0 bg-base/75 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-surface border border-border rounded-2xl w-full max-w-xl max-h-[82vh] flex flex-col animate-slide-up shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-border">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="font-mono text-sm font-semibold text-amber bg-amber/8 border border-amber/20 px-2 py-0.5 rounded">
                {paper.course_code}
              </span>
              <span className="text-text font-medium text-sm">
                {paper.semester} {paper.year}
              </span>
            </div>
            {paper.subject_name && paper.subject_name !== paper.course_code && (
              <p className="text-[12px] text-muted mb-1.5 truncate">{paper.subject_name}</p>
            )}
            <div className="flex items-center gap-4 text-[11px] text-muted font-mono">
              <span className="flex items-center gap-1">
                <Hash size={10} />
                {paper.total_questions} questions
              </span>
              <span className="flex items-center gap-1">
                <Star size={10} />
                {paper.total_marks} marks
              </span>
              {totalImages > 0 && (
                <span className="flex items-center gap-1">
                  <ImageIcon size={10} />
                  {totalImages} images
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 ml-3 shrink-0">
            {/* Download button — only shown when PDF exists */}
            {paper.has_pdf && (
              <button
                onClick={handleDownload}
                disabled={downloading}
                title="Download PDF"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber/10 border border-amber/25 text-amber text-xs font-medium hover:bg-amber/20 transition-all disabled:opacity-50"
              >
                {downloading ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Download size={12} />
                )}
                PDF
                {paper.file_size_kb > 0 && (
                  <span className="text-amber/60 font-mono text-[10px]">
                    {fmtSize(paper.file_size_kb)}
                  </span>
                )}
              </button>
            )}

            <button
              onClick={onClose}
              className="text-muted hover:text-text transition-colors p-1 -mr-1 -mt-0.5"
            >
              <X size={17} />
            </button>
          </div>
        </div>

        {/* Download error */}
        {dlError && (
          <div className="mx-5 mt-3 flex items-center gap-2 text-red-400 text-xs bg-red-400/8 border border-red-400/20 rounded-lg px-3 py-2">
            <AlertCircle size={12} className="shrink-0" />
            {dlError}
          </div>
        )}

        {/* Questions */}
        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-2">
          {loading && (
            <div className="flex items-center justify-center py-16 text-muted gap-2">
              <Loader2 size={18} className="animate-spin" />
              <span className="text-sm">Loading questions…</span>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm py-8 justify-center">
              <AlertCircle size={15} />
              {error}
            </div>
          )}

          {!loading &&
            !error &&
            questions.map((q) => {
              const open = expanded.has(q.parent_id)
              const hasImages = Object.keys(q.image_urls ?? {}).length > 0
              return (
                <button
                  key={q.parent_id}
                  onClick={() => toggle(q.parent_id)}
                  className="w-full text-left card border-border/60 hover:border-border transition-all"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-mono text-xs text-amber shrink-0">
                        Q{q.question_number}
                      </span>
                      <p
                        className={cx(
                          'text-sm text-text leading-snug',
                          !open && 'line-clamp-2'
                        )}
                      >
                        {q.full_text}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 mt-0.5">
                      {hasImages && (
                        <ImageIcon size={11} className="text-muted/50" />
                      )}
                      <span className="text-[11px] text-muted font-mono">
                        {q.total_marks}m
                      </span>
                      <ChevronDown
                        size={13}
                        className={cx(
                          'text-muted/50 transition-transform',
                          open && 'rotate-180'
                        )}
                      />
                    </div>
                  </div>

                  {open && hasImages && (
                    <div className="mt-3 flex flex-wrap gap-2 pt-3 border-t border-border/60">
                      {Object.entries(q.image_urls).map(([label, url]: [string, string]) => (
                        <ExamImage key={label} url={url} label={label} />
                      ))}
                    </div>
                  )}
                </button>
              )
            })}

          {!loading && !error && questions.length === 0 && (
            <div className="py-16 text-center text-muted text-sm">
              No questions found for this paper.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Browse Page — see BrowsePage.tsx ────────────────────────────────────────

function _BrowsePageUnused() {
  const [papers, setPapers] = useState<Paper[]>([])
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<SearchFilters>({})
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null)
  const [subjects, setSubjects] = useState<{ course_code: string; subject_name: string }[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const YEARS = Array.from({ length: 9 }, (_, i) => 2025 - i)
  const SEMESTERS = ['January', 'May', 'August', 'September']

  useEffect(() => {
    searchApi
      .subjects()
      .then((data: { course_code: string; subject_name: string }[]) =>
        setSubjects(data)
      )
      .catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    searchApi
      .papers(filters)
      .then(setPapers)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [filters])

  const filteredPapers = searchQuery
    ? papers.filter((p) =>
        p.course_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.subject_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.semester.toLowerCase().includes(searchQuery.toLowerCase()) ||
        String(p.year).includes(searchQuery)
      )
    : papers

  const grouped = filteredPapers.reduce<Record<string, Paper[]>>((acc, p) => {
    acc[p.course_code] = acc[p.course_code] ?? []
    acc[p.course_code].push(p)
    return acc
  }, {})

  const semesterOrder: Record<string, number> = {
    January: 0, May: 1, August: 2, September: 3,
  }

  const totalPapers = filteredPapers.length
  const totalQuestions = filteredPapers.reduce(
    (s, p) => s + (p.total_questions ?? 0),
    0
  )

  // Download directly from the card (without opening modal)
  const handleCardDownload = async (
    e: React.MouseEvent,
    paper: Paper
  ) => {
    e.stopPropagation()
    const id = `${paper.course_code}-${paper.year}-${paper.semester}`
    setDownloadingId(id)
    try {
      const info = await searchApi.downloadPaper(
        paper.course_code, paper.year, paper.semester
      )
      window.open(info.url, '_blank', 'noopener,noreferrer')
    } catch {
      // fallback — open modal so user sees the error
      setSelectedPaper(paper)
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* ── Header ── */}
      <div className="bg-surface border-b border-border px-5 pt-4 pb-3 shrink-0">
        <div className="flex items-center gap-2 mb-3">
          <img src={logo} alt="PaperSloth" className="w-14 h-14 rounded-lg object-contain" />
          <span className="font-medium text-sm text-text">Browse Papers</span>
          {!loading && (
            <span className="text-[11px] text-muted font-mono">
              {totalPapers} papers · {totalQuestions} questions
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-2.5 items-center">
          {/* Search */}
          <div className="relative flex-1 min-w-[160px] max-w-[220px]">
            <Search
              size={12}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted/60 pointer-events-none"
            />
            <input
              className="input-base text-xs py-1.5 pl-7"
              placeholder="Search subjects…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <select
            className="input-base text-xs py-1.5 w-40"
            value={filters.course_code ?? ''}
            onChange={(e) =>
              setFilters((p) => ({
                ...p,
                course_code: e.target.value || undefined,
              }))
            }
          >
            <option value="">All subjects</option>
            {subjects.map((s) => (
              <option key={s.course_code} value={s.course_code}>
                {s.course_code}{s.subject_name && s.subject_name !== s.course_code ? ` — ${s.subject_name}` : ''}
              </option>
            ))}
          </select>

          <select
            className="input-base text-xs py-1.5 w-24"
            value={filters.year ?? ''}
            onChange={(e) =>
              setFilters((p) => ({
                ...p,
                year: e.target.value ? +e.target.value : undefined,
              }))
            }
          >
            <option value="">All years</option>
            {YEARS.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>

          <select
            className="input-base text-xs py-1.5 w-32"
            value={filters.semester ?? ''}
            onChange={(e) =>
              setFilters((p) => ({
                ...p,
                semester: e.target.value || undefined,
              }))
            }
          >
            <option value="">All semesters</option>
            {SEMESTERS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          {Object.values(filters).some(Boolean) && (
            <button
              onClick={() => setFilters({})}
              className="btn-ghost text-xs py-1.5 px-3 text-muted/70"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto px-5 py-5">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-muted gap-2">
            <Loader2 size={18} className="animate-spin" />
            <span className="text-sm">Loading papers…</span>
          </div>
        ) : filteredPapers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <FileText size={30} className="text-border mb-4" />
            <p className="text-muted text-sm mb-1">No papers found</p>
            <p className="text-muted/50 text-xs">
              Try adjusting your filters or search query
            </p>
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(grouped)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([code, paperList]) => {
                const subjectName = paperList[0]?.subject_name
                return (
                  <div key={code}>
                    {/* Subject header */}
                    <div className="flex items-center gap-3 mb-3">
                      <span className="font-mono text-sm font-semibold text-amber">
                        {code}
                      </span>
                      {subjectName && subjectName !== code && (
                        <span className="text-xs text-muted/80 truncate max-w-[260px]">
                          {subjectName}
                        </span>
                      )}
                      <span className="text-[11px] text-muted/50">
                        {paperList.length} paper{paperList.length !== 1 ? 's' : ''}
                      </span>
                      <div className="flex-1 h-px bg-border" />
                    </div>

                    {/* Paper cards */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2">
                      {paperList
                        .sort(
                          (a, b) =>
                            b.year - a.year ||
                            (semesterOrder[a.semester] ?? 0) -
                              (semesterOrder[b.semester] ?? 0)
                        )
                        .map((p) => {
                          const cardId = `${p.course_code}-${p.year}-${p.semester}`
                          const isDlLoading = downloadingId === cardId
                          return (
                            <div
                              key={cardId}
                              className="group card border-border/60 hover:border-amber/30 hover:bg-amber/3 transition-all duration-150 cursor-pointer space-y-2.5"
                              onClick={() => setSelectedPaper(p)}
                            >
                              {/* Year / semester row */}
                              <div className="flex items-start justify-between">
                                <div>
                                  <p className="text-xs font-semibold text-text font-mono">
                                    {p.year}
                                  </p>
                                  <p className="text-[11px] text-muted">
                                    {p.semester}
                                  </p>
                                </div>
                                <ChevronRight
                                  size={12}
                                  className="text-muted/40 group-hover:text-amber transition-colors mt-0.5"
                                />
                              </div>

                              {/* Stats row */}
                              <div className="flex flex-wrap gap-x-3 gap-y-1">
                                <span className="flex items-center gap-1 text-[10px] text-muted/70 font-mono">
                                  <Hash size={9} />
                                  {p.total_questions}Q
                                </span>
                                <span className="flex items-center gap-1 text-[10px] text-muted/70 font-mono">
                                  <Star size={9} />
                                  {p.total_marks}m
                                </span>
                                {p.questions_with_images > 0 && (
                                  <span className="flex items-center gap-1 text-[10px] text-muted/70 font-mono">
                                    <ImageIcon size={9} />
                                    {p.questions_with_images}
                                  </span>
                                )}
                              </div>

                              {/* Download row — shown only when PDF is available */}
                              {p.has_pdf && (
                                <button
                                  onClick={(e) => handleCardDownload(e, p)}
                                  disabled={isDlLoading}
                                  className="w-full flex items-center justify-center gap-1.5 py-1 rounded-md bg-amber/8 border border-amber/20 text-amber text-[10px] font-medium hover:bg-amber/15 transition-all disabled:opacity-50 mt-1"
                                >
                                  {isDlLoading ? (
                                    <Loader2 size={9} className="animate-spin" />
                                  ) : (
                                    <Download size={9} />
                                  )}
                                  {isDlLoading ? 'Getting link…' : 'Download PDF'}
                                  {p.file_size_kb > 0 && (
                                    <span className="text-amber/50 font-mono">
                                      {fmtSize(p.file_size_kb)}
                                    </span>
                                  )}
                                </button>
                              )}
                            </div>
                          )
                        })}
                    </div>
                  </div>
                )
              })}
          </div>
        )}
      </div>

      {selectedPaper && (
        <PaperDetailModal
          paper={selectedPaper}
          onClose={() => setSelectedPaper(null)}
        />
      )}
    </div>
  )
}

// ─── Route Guards ─────────────────────────────────────────────────────────────

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthed } = useAuthStore()
  return isAuthed() ? <>{children}</> : <Navigate to="/login" replace />
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function App() {
  const { isAuthed } = useAuthStore()

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            isAuthed() ? <Navigate to="/chat" replace /> : <AuthPage />
          }
        />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <AppShell>
                <Routes>
                  <Route path="/chat" element={<ChatPage />} />
                  <Route path="/browse" element={<BrowsePage />} />
                  <Route path="*" element={<Navigate to="/chat" replace />} />
                </Routes>
              </AppShell>
            </RequireAuth>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}