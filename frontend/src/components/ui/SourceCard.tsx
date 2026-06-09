import React, { useState } from 'react'
import { ChevronDown, ImageIcon } from 'lucide-react'
import { cx, cleanSemester } from '../../utils/helpers'
import type { Source } from '../../types'

interface SourceCardProps {
  source: Source
  index:  number
}

export default function SourceCard({ source, index }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false)
  const imageEntries = Object.entries(source.image_urls ?? {})
  const hasImages    = imageEntries.length > 0

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
          {hasImages && <ImageIcon size={11} className="text-muted/60" />}
          <ChevronDown
            size={13}
            className={cx('text-muted/60 transition-transform', expanded && 'rotate-180')}
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
            <p className="text-[14px] text-muted/50 italic">Full text not available</p>
          )}
        </div>
      )}
    </div>
  )
}