import React from 'react'
import { X } from 'lucide-react'

interface FilterChipProps {
  label:    string
  onRemove: () => void
}

export default function FilterChip({ label, onRemove }: FilterChipProps) {
  return (
    <span className="inline-flex items-center gap-1 bg-amber/8 border border-amber/20 text-amber text-[11px] font-mono px-2 py-0.5 rounded-full">
      {label}
      <button onClick={onRemove} className="hover:opacity-70 transition-opacity">
        <X size={10} />
      </button>
    </span>
  )
}