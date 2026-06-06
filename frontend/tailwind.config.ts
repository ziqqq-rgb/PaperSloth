import typography from '@tailwindcss/typography'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        base:    '#0d1117',
        surface: '#161b22',
        border:  '#21262d',
        muted:   '#8b949e',
        text:    '#e6edf3',
        amber:   { DEFAULT: '#f59e0b', dim: '#92400e' },
      },
      fontFamily: {
        display: ['"Instrument Serif"', 'Georgia', 'serif'],
        sans:    ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono:    ['"IBM Plex Mono"', 'monospace'],
      },
      animation: {
        'fade-in':  'fadeIn 0.3s ease forwards',
        'slide-up': 'slideUp 0.3s ease forwards',
        'blink':    'blink 1s step-end infinite',
      },
      keyframes: {
        fadeIn:  { from: { opacity: '0' },              to: { opacity: '1' } },
        slideUp: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        blink:   { '0%,100%': { opacity: '1' }, '50%': { opacity: '0' } },
      },
      // ── Typography plugin customisation ──────────────────────────────────
      typography: {
        DEFAULT: {
          css: {
            '--tw-prose-body':        '#e6edf3',
            '--tw-prose-headings':    '#e6edf3',
            '--tw-prose-bold':        '#e6edf3',
            '--tw-prose-code':        '#f59e0b',
            '--tw-prose-bullets':     '#8b949e',
            '--tw-prose-counters':    '#8b949e',
            '--tw-prose-quotes':      '#8b949e',
            '--tw-prose-hr':          '#21262d',
            '--tw-prose-links':       '#f59e0b',
            maxWidth: 'none',
            h1: { fontSize: '1.2rem', fontWeight: '600', marginTop: '1.2rem', marginBottom: '0.5rem' },
            h2: { fontSize: '1.05rem', fontWeight: '600', marginTop: '1rem', marginBottom: '0.4rem' },
            h3: { fontSize: '0.95rem', fontWeight: '600', marginTop: '0.8rem', marginBottom: '0.3rem' },
            p:  { marginTop: '0.4rem', marginBottom: '0.4rem', lineHeight: '1.65' },
            ul: { marginTop: '0.4rem', marginBottom: '0.4rem', paddingLeft: '1.25rem' },
            ol: { marginTop: '0.4rem', marginBottom: '0.4rem', paddingLeft: '1.25rem' },
            li: { marginTop: '0.15rem', marginBottom: '0.15rem' },
            code: {
              backgroundColor: 'rgba(33,38,45,0.8)',
              padding: '0.15em 0.4em',
              borderRadius: '0.3rem',
              fontSize: '0.82em',
              fontWeight: '400',
            },
            'code::before': { content: '""' },
            'code::after':  { content: '""' },
            pre: {
              backgroundColor: '#161b22',
              border: '1px solid #21262d',
              borderRadius: '0.5rem',
              padding: '0.85rem 1rem',
            },
            blockquote: {
              borderLeftColor: '#f59e0b',
              borderLeftWidth: '3px',
              paddingLeft: '0.85rem',
              color: '#8b949e',
              fontStyle: 'normal',
            },
            strong: { color: '#e6edf3', fontWeight: '600' },
            a:      { color: '#f59e0b', textDecoration: 'none' },
            hr:     { borderColor: '#21262d' },
          },
        },
      },
    },
  },
  plugins: [
    typography,
  ],
}