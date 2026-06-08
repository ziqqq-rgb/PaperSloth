import React from 'react';

export default function PaperSlothMascot() {
  return (
    <svg 
      xmlns="http://www.w3.org/2000/svg" 
      viewBox="0 0 400 400" 
      className="w-full h-full drop-shadow-2xl"
    >
      <defs>
        <linearGradient id="paperGlow" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f59e0b" />
          <stop offset="100%" stopColor="#d97706" />
        </linearGradient>

        <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="10" stdDeviation="15" floodColor="#f59e0b" floodOpacity="0.3"/>
        </filter>
      </defs>

      {/* Optional subtle ring */}
      <circle cx="200" cy="200" r="180" fill="none" stroke="#21262d" strokeWidth="2" strokeDasharray="10 10" />

      {/* Sloth Body */}
      <path d="M 100 280 C 100 120, 300 120, 300 280" fill="#21262d" />
      
      {/* Sloth Face Mask */}
      <path d="M 125 280 C 125 160, 275 160, 275 280" fill="#8b949e" />

      {/* Sloth Eyes */}
      <rect x="150" y="200" width="35" height="6" rx="3" fill="#0d1117" className="animate-pulse" />
      <rect x="215" y="200" width="35" height="6" rx="3" fill="#0d1117" className="animate-pulse" />

      {/* Sloth Nose */}
      <path d="M 190 230 Q 200 240 210 230 Z" fill="#0d1117" stroke="#0d1117" strokeWidth="4" strokeLinejoin="round" />

      {/* Sloth Smile */}
      <path d="M 185 250 Q 200 260 215 250" fill="none" stroke="#0d1117" strokeWidth="3" strokeLinecap="round" />

      {/* Floating Orange Tablet */}
      <rect 
        x="70" y="270" width="260" height="90" rx="12" 
        fill="url(#paperGlow)" filter="url(#glow)"
        transform="rotate(-5 200 270)" 
      />

      {/* Tablet UI Lines */}
      <rect x="100" y="300" width="80" height="6" rx="3" fill="#ffffff" opacity="0.8" transform="rotate(-5 200 270)" />
      <rect x="100" y="320" width="140" height="6" rx="3" fill="#ffffff" opacity="0.8" transform="rotate(-5 200 270)" />
      <rect x="100" y="340" width="100" height="6" rx="3" fill="#ffffff" opacity="0.4" transform="rotate(-5 200 270)" />
    </svg>
  );
}