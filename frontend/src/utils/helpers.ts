export const uid = () => Math.random().toString(36).slice(2)

export const cx = (...args: (string | false | null | undefined)[]) =>
  args.filter(Boolean).join(' ')

export const cleanSemester = (sem: string, year: number): string => {
  let s = sem
    .replace(/\bSEMESTER\b/gi, '')
    .replace(new RegExp(`\\b${year}\\b`, 'g'), '')
    .trim()
  s = s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()
  return `${s} ${year}`
}

export const fmtSize = (kb: number): string => {
  if (!kb) return ''
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}