/** @type {import('tailwindcss').Config} */
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
        'fade-in':   'fadeIn 0.3s ease forwards',
        'slide-up':  'slideUp 0.3s ease forwards',
        'blink':     'blink 1s step-end infinite',
      },
      keyframes: {
        fadeIn:  { from: { opacity: '0' },              to: { opacity: '1' } },
        slideUp: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        blink:   { '0%,100%': { opacity: '1' }, '50%': { opacity: '0' } },
      },
    },
  },
  plugins: [],
}