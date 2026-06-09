import React, { useEffect, useState } from 'react'
import {
  AlertCircle,
  ChevronDown,
  Download,
  Hash,
  ImageIcon,
  Loader2,
  Star,
  X,
} from 'lucide-react'
import { searchApi } from '../../api/search'
import { cx, cleanSemester, fmtSize } from '../../utils/helpers'
import ExamImage from '../ui/ExamImage'
import type { Paper, Question } from '../../types'

interface PaperDetailModalProps {
  paper:   Paper
  onClose: () => void
}

export default function PaperDetailModal({ paper, onClose }: PaperDetailModalProps) {
  const [questions,   setQuestions]   = useState<Question[]>([])
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState('')
  const [expanded,    setExpanded]    = useState<Set<string>>(new Set())
  const [downloading, setDownloading] = useState(false)
  const [dlError,     setDlError]     = useState('')

  useEffect(() => {
    searchApi
      .getPaper(paper.course_code, paper.year, paper.semester)
      .then((data: { questions: Question[] }) => setQuestions(data.questions ?? []))
      .catch(() => setError('Failed to load questions'))
      .finally(() => setLoading(false))
  }, [paper])

  const toggle = (id: string) =>
    setExpanded(prev => {
      const n = new Set(prev)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setDownloading(true)
    setDlError('')
    try {
      const info = await searchApi.downloadPaper(paper.course_code, paper.year, paper.semester)
      window.open(info.url, '_blank', 'noopener,noreferrer')
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Download failed'
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
      onClick={e => e.target === e.currentTarget && onClose()}
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
                {cleanSemester(paper.semester, paper.year)}
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

          {!loading && !error && questions.map(q => {
            const open      = expanded.has(q.parent_id)
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
                    <p className={cx('text-sm text-text leading-snug', !open && 'line-clamp-2')}>
                      {q.full_text}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 mt-0.5">
                    {hasImages && <ImageIcon size={11} className="text-muted/50" />}
                    <span className="text-[11px] text-muted font-mono">{q.total_marks}m</span>
                    <ChevronDown
                      size={13}
                      className={cx('text-muted/50 transition-transform', open && 'rotate-180')}
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