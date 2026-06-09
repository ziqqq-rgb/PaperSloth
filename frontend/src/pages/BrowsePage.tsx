import React, { useState, useEffect } from 'react'
import { Download, Loader2, Search, X, Lock } from 'lucide-react'
import { searchApi, type SearchFilters } from '../api/search'
import { cx, fmtSize } from '../utils/helpers'
import logo from '../assets/logo.svg'

interface Paper {
  course_code:            string
  subject_name:           string
  semester:               string
  year:                   number
  total_questions:        number
  total_marks:            number
  questions_with_images:  number
  has_pdf:                boolean
  file_size_kb:           number
}

const cleanSem = (sem: string, year: number) =>
  sem
    .replace(/\bSEMESTER\b/gi, '')
    .replace(new RegExp(`\\b${year}\\b`, 'g'), '')
    .replace(/\s+/g, ' ')
    .trim()

const YEARS = Array.from({ length: 9 }, (_, i) => 2025 - i)
const SEMS  = ['January', 'May', 'August', 'September']

const accentColors = [
  'text-amber border-amber/30 bg-amber/5',
  'text-sky-400 border-sky-400/30 bg-sky-400/5',
  'text-emerald-400 border-emerald-400/30 bg-emerald-400/5',
  'text-violet-400 border-violet-400/30 bg-violet-400/5',
  'text-rose-400 border-rose-400/30 bg-rose-400/5',
]

const semOrder: Record<string, number> = { January: 0, May: 1, August: 2, September: 3 }

export default function BrowsePage() {
  const [papers,      setPapers]      = useState<Paper[]>([])
  const [loading,     setLoading]     = useState(false)
  const [filters,     setFilters]     = useState<SearchFilters>({})
  const [query,       setQuery]       = useState('')
  const [subjects,    setSubjects]    = useState<{ course_code: string; subject_name: string }[]>([])
  const [downloading, setDownloading] = useState<string | null>(null)
  const [dlError,     setDlError]     = useState<string | null>(null)

  useEffect(() => {
    searchApi.subjects()
      .then((d: { course_code: string; subject_name: string }[]) => setSubjects(d))
      .catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    searchApi.papers(filters)
      .then(setPapers)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [filters])

  const visible = query
    ? papers.filter(p =>
        p.course_code.toLowerCase().includes(query.toLowerCase()) ||
        (p.subject_name || '').toLowerCase().includes(query.toLowerCase()) ||
        p.semester.toLowerCase().includes(query.toLowerCase()) ||
        String(p.year).includes(query)
      )
    : papers

  const grouped = visible.reduce<Record<string, Paper[]>>((acc, p) => {
    acc[p.course_code] = acc[p.course_code] ?? []
    acc[p.course_code].push(p)
    return acc
  }, {})

  const subjectKeys = Object.keys(grouped).sort()
  const accentFor   = (code: string) =>
    accentColors[subjectKeys.indexOf(code) % accentColors.length]

  const handleDownload = async (p: Paper) => {
    const id = `${p.course_code}-${p.year}-${p.semester}`
    setDownloading(id)
    setDlError(null)
    try {
      const info = await searchApi.downloadPaper(p.course_code, p.year, p.semester)
      window.open(info.url, '_blank', 'noopener,noreferrer')
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Download failed'
      setDlError(detail)
    } finally {
      setDownloading(null)
    }
  }

  const hasFilters = query || Object.values(filters).some(Boolean)

  return (
    <div className="h-full flex flex-col overflow-hidden bg-base">
      {/* ── Header ── */}
      <div className="bg-surface border-b border-border px-6 py-4 shrink-0">
        <div className="flex items-center gap-3 mb-4">
          <span className="font-medium text-sm text-text">Past Year Papers</span>
          {!loading && (
            <span className="text-[11px] font-mono text-muted bg-border/40 px-2 py-0.5 rounded-full">
              {visible.length} papers
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted/50 pointer-events-none" />
            <input
              className="input-base text-xs py-1.5 pl-7 w-48"
              placeholder="Search subject or code…"
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
          </div>

          <select
            className="input-base text-xs py-1.5 w-44"
            value={filters.course_code ?? ''}
            onChange={e => setFilters(p => ({ ...p, course_code: e.target.value || undefined }))}
          >
            <option value="">All subjects</option>
            {subjects.map(s => (
              <option key={s.course_code} value={s.course_code}>
                {s.course_code}{s.subject_name && s.subject_name !== s.course_code ? ` — ${s.subject_name}` : ''}
              </option>
            ))}
          </select>

          <select
            className="input-base text-xs py-1.5 w-24"
            value={filters.year ?? ''}
            onChange={e => setFilters(p => ({ ...p, year: e.target.value ? +e.target.value : undefined }))}
          >
            <option value="">All years</option>
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>

          <select
            className="input-base text-xs py-1.5 w-32"
            value={filters.semester ?? ''}
            onChange={e => setFilters(p => ({ ...p, semester: e.target.value || undefined }))}
          >
            <option value="">All semesters</option>
            {SEMS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          {hasFilters && (
            <button
              onClick={() => { setFilters({}); setQuery('') }}
              className="flex items-center gap-1 text-[11px] text-muted/70 hover:text-text font-mono px-2 py-1.5 rounded-lg hover:bg-border/40 transition-colors"
            >
              <X size={11} /> Clear
            </button>
          )}
        </div>

        {dlError && (
          <div className="mt-3 flex items-center gap-2 text-red-400 text-xs bg-red-400/8 border border-red-400/20 rounded-lg px-3 py-2">
            <span>{dlError}</span>
            <button onClick={() => setDlError(null)} className="ml-auto hover:opacity-70"><X size={11} /></button>
          </div>
        )}
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {loading ? (
          <div className="flex items-center justify-center py-24 gap-2 text-muted">
            <Loader2 size={16} className="animate-spin" />
            <span className="text-sm">Loading papers…</span>
          </div>
        ) : visible.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-2">
            <img src={logo} alt="PaperSloth" className="w-14 h-14 rounded-lg object-contain" />
            <p className="text-muted text-sm">No papers match your filters</p>
            {hasFilters && (
              <button
                onClick={() => { setFilters({}); setQuery('') }}
                className="text-[11px] text-amber hover:underline mt-1"
              >
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-8 max-w-5xl">
            {Object.entries(grouped)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([code, list]) => {
                const name   = list[0]?.subject_name
                const accent = accentFor(code)
                const sorted = [...list].sort(
                  (a, b) => b.year - a.year || (semOrder[a.semester] ?? 9) - (semOrder[b.semester] ?? 9)
                )

                return (
                  <div key={code}>
                    <div className="flex items-center gap-3 mb-4">
                      <span className={cx('font-mono text-sm font-semibold px-2.5 py-1 rounded-lg border', accent)}>
                        {code}
                      </span>
                      {name && name !== code && (
                        <span className="text-sm text-text font-medium">{name}</span>
                      )}
                      <span className="text-[11px] text-muted/50 ml-auto font-mono">
                        {list.length} paper{list.length !== 1 ? 's' : ''}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                      {sorted.map(p => {
                        const id   = `${p.course_code}-${p.year}-${p.semester}`
                        const busy = downloading === id
                        const sem  = cleanSem(p.semester, p.year)

                        return (
                          <div
                            key={id}
                            className="flex flex-col bg-surface border border-border/60 rounded-2xl overflow-hidden hover:border-border transition-all duration-150 group"
                          >
                            <div className="flex-1 p-4">
                              <p className="font-mono text-2xl font-semibold text-text leading-none mb-2">
                                {p.year}
                              </p>
                              <p className="text-xs text-muted leading-snug">{sem}</p>
                            </div>

                            {p.has_pdf ? (
                              <button
                                onClick={() => handleDownload(p)}
                                disabled={busy}
                                className={cx(
                                  'flex items-center justify-center gap-2 py-2.5 text-[11px] font-medium border-t transition-all',
                                  'border-border/60 text-muted hover:text-amber hover:bg-amber/5 hover:border-amber/20',
                                  'disabled:opacity-50 active:scale-[0.98]'
                                )}
                              >
                                {busy
                                  ? <Loader2 size={11} className="animate-spin text-amber" />
                                  : <Download size={11} />}
                                {busy ? 'Getting link…' : 'Download PDF'}
                              </button>
                            ) : (
                              <div className="flex items-center justify-center gap-1.5 py-2.5 border-t border-border/40 text-[11px] text-muted/30 font-mono">
                                <Lock size={10} />
                                Not available
                              </div>
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
    </div>
  )
}