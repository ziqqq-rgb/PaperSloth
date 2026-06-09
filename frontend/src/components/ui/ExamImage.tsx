import React, { useState } from 'react'
import { Loader2, ImageIcon } from 'lucide-react'
import { cx } from '../../utils/helpers'

interface ExamImageProps {
  url:   string
  label: string
}

export default function ExamImage({ url, label }: ExamImageProps) {
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading')

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
  )
}