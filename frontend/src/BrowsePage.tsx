import React, { useState, useEffect } from 'react'
import {
  BookOpen, Download, Loader2, Search,
  HelpCircle, Award, Image, Lock, X,
} from 'lucide-react'
import { searchApi, type SearchFilters } from './search'

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

const cx = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(' ')

const fmtSize = (kb: number) => {
  if (!kb) return ''
  return kb < 1024 ? `${kb} KB` : `${(kb / 1024).toFixed(1)} MB`
}

const cleanSem = (sem: string, year: number) =>
  sem
    .replace(/\bSEMESTER\b/gi, '')
    .replace(new RegExp(`\\b${year}\\b`, 'g'), '')
    .trim()

export default function BrowsePage() {
  const [papers, setPapers]         = useState<Paper[]>([])
  const [loading, setLoading]       = useState(false)
  const [filters, setFilters]       = useState<SearchFilters>({})
  const [query, setQuery]           = useState('')
  const [subjects, setSubjects]     = useState<{ course_code: string; subject_name: string }[]>([])
  const [downloading, setDownloading] = useState<string | null>(null)
  const [dlError, setDlError]       = useState<string | null>(null)

  const YEARS = Array.from({ length: 9 }, (_, i) => 2025 - i)
  const SEMS  = ['January', 'May', 'August', 'September']

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

  const semOrder: Record<string, number> = { January: 0, May: 1, August: 2, September: 3 }

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
          <BookOpen size={15} className="text-amber" />
          <span className="font-medium text-sm text-text">Past Year Papers</span>
          {!loading && (
            <>
              <span className="text-[11px] font-mono text-muted bg-border/40 px-2 py-0.5 rounded-full">
                {visible.length} papers
              </span>
              <span className="text-[11px] font-mono text-muted bg-border/40 px-2 py-0.5 rounded-full">
                {visible.reduce((s, p) => s + p.total_questions, 0)} questions
              </span>
            </>
          )}
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          {/* Text search */}
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted/50 pointer-events-none" />
            <input
              className="input-base text-xs py-1.5 pl-7 w-48"
              placeholder="Search subject or code…"
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
          </div>

          {/* Subject */}
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

          {/* Year */}
          <select
            className="input-base text-xs py-1.5 w-24"
            value={filters.year ?? ''}
            onChange={e => setFilters(p => ({ ...p, year: e.target.value ? +e.target.value : undefined }))}
          >
            <option value="">All years</option>
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>

          {/* Semester */}
          <select
            className="input-base text-xs py-1.5 w-32"
            value={filters.semester ?? ''}
            onChange={e => setFilters(p => ({ ...p, semester: e.target.value || undefined }))}
          >
            <option value="">All semesters</option>
            {SEMS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          {/* Clear */}
          {hasFilters && (
            <button
              onClick={() => { setFilters({}); setQuery('') }}
              className="flex items-center gap-1 text-[11px] text-muted/70 hover:text-text font-mono px-2 py-1.5 rounded-lg hover:bg-border/40 transition-colors"
            >
              <X size={11} /> Clear
            </button>
          )}
        </div>

        {/* Download error */}
        {dlError && (
          <div className="mt-3 flex items-center gap-2 text-red-400 text-xs bg-red-400/8 border border-red-400/20 rounded-lg px-3 py-2">
            <span>{dlError}</span>
            <button onClick={() => setDlError(null)} className="ml-auto hover:opacity-70">
              <X size={11} />
            </button>
          </div>
        )}
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {loading ? (
          <div className="flex items-center justify-center py-24 gap-2 text-muted">
            <Loader2 size={16} className="animate-spin" />
            <span className="text-sm">Loading papers…</span>
          </div>
        ) : visible.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center gap-2">
            <BookOpen size={28} className="text-border" />
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
          <div className="space-y-7 max-w-4xl">
            {Object.entries(grouped)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([code, list]) => {
                const name = list[0]?.subject_name
                const sorted = [...list].sort(
                  (a, b) => b.year - a.year || (semOrder[a.semester] ?? 9) - (semOrder[b.semester] ?? 9)
                )
                return (
                  <div key={code}>
                    {/* Subject header */}
                    <div className="flex items-baseline gap-3 mb-2.5 pb-2.5 border-b border-border/60">
                      <span className="font-mono text-sm font-medium text-amber">{code}</span>
                      {name && name !== code && (
                        <span className="text-xs text-muted truncate">{name}</span>
                      )}
                      <span className="text-[11px] text-muted/50 ml-auto font-mono">
                        {list.length} paper{list.length !== 1 ? 's' : ''}
                      </span>
                    </div>

                    {/* Paper rows */}
                    <div className="flex flex-col gap-1.5">
                      {sorted.map(p => {
                        const id  = `${p.course_code}-${p.year}-${p.semester}`
                        const busy = downloading === id
                        const sem = cleanSem(p.semester, p.year)

                        return (
                          <div
                            key={id}
                            className="flex items-center gap-4 bg-surface border border-border/60 rounded-xl px-4 py-3 hover:border-border transition-colors"
                          >
                            {/* Year badge */}
                            <span className="font-mono text-xs text-muted/70 w-8 shrink-0">
                              {p.year}
                            </span>

                            {/* Semester */}
                            <span className="text-sm text-text font-medium min-w-[140px]">
                              {sem}
                            </span>

                            {/* Meta */}
                            <div className="flex items-center gap-4 flex-1">
                              <span className="flex items-center gap-1 text-[11px] text-muted/60 font-mono">
                                <HelpCircle size={11} />
                                {p.total_questions}Q
                              </span>
                              <span className="flex items-center gap-1 text-[11px] text-muted/60 font-mono">
                                <Award size={11} />
                                {p.total_marks}m
                              </span>
                              {p.questions_with_images > 0 && (
                                <span className="flex items-center gap-1 text-[11px] text-muted/60 font-mono">
                                  <Image size={11} />
                                  {p.questions_with_images}
                                </span>
                              )}
                            </div>

                            {/* Download / unavailable */}
                            {p.has_pdf ? (
                              <button
                                onClick={() => handleDownload(p)}
                                disabled={busy}
                                className={cx(
                                  'flex items-center gap-1.5 text-[11px] font-medium px-3 py-1.5 rounded-lg border transition-all shrink-0',
                                  'bg-amber/8 border-amber/25 text-amber hover:bg-amber/15 active:scale-95 disabled:opacity-50'
                                )}
                              >
                                {busy
                                  ? <Loader2 size={11} className="animate-spin" />
                                  : <Download size={11} />}
                                {busy ? 'Getting link…' : 'Download PDF'}
                                {p.file_size_kb > 0 && !busy && (
                                  <span className="text-amber/50 font-mono">{fmtSize(p.file_size_kb)}</span>
                                )}
                              </button>
                            ) : (
                              <span className="flex items-center gap-1 text-[11px] text-muted/40 font-mono shrink-0">
                                <Lock size={10} />
                                Not available
                              </span>
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