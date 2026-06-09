import React from 'react'
import { Sparkles } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { cx } from '../../utils/helpers'
import ExamImage from './ExamImage'
import type { Message } from '../../types'

interface MessageBubbleProps {
  message: Message
}

export default function MessageBubble({ message }: MessageBubbleProps) {
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