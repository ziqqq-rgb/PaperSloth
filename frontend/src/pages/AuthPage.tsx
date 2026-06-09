import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { authApi } from '../api/auth'
import logo from '../assets/logo.svg'
import mascotImg from '../assets/mascot.png'
import gearPattern from '../assets/2415.jpg'

export default function AuthPage() {
  const [mode,     setMode]     = useState<'login' | 'register'>('login')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [name,     setName]     = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })

  const { setAuth } = useAuthStore()
  const navigate    = useNavigate()

  const handleMouseMove = (e: React.MouseEvent) => {
    const x = (window.innerWidth / 2 - e.clientX) / 40
    const y = (window.innerHeight / 2 - e.clientY) / 40
    setMousePos({ x, y })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res =
        mode === 'login'
          ? await authApi.login(email, password)
          : await authApi.register(email, password, name)
      setAuth(res.access_token, res.user)
      navigate('/chat')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Something went wrong'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-base flex flex-col">
      {/* ── Full-width header ── */}
      <header className="w-full flex items-center -ml-3 px-7 py-1 border-b border-border bg-surface z-30 shrink-0">
        <img src={logo} alt="PaperSloth" className="w-14 h-14 object-contain" />
        <span className="font-display text-xl text-text tracking-tight -ml-2">PaperSloth</span>
      </header>

      {/* ── Two panels below the header ── */}
      <div className="flex flex-1">
        {/* Left branding panel */}
        <div
          className="hidden lg:flex lg:w-[52%] bg-surface border-r border-border flex-col relative overflow-hidden"
          onMouseMove={handleMouseMove}
        >
          <div className="min-h-full bg-[#12161a] px-16 pt-12 pb-12 flex flex-col justify-start">
            <div className="z-20 max-w-2xl mt-12">
              <p className="font-mono text-xs text-amber/60 uppercase tracking-[0.45em] mb-2">
                UTP Past Year Exam Assistant
              </p>
              <h1 className="font-display text-[3.5rem] tracking-tight font-semibold leading-[1.05] text-text">
                Study smarter,
                <br />
                <span className="text-amber">not harder.</span>
              </h1>
            </div>

            <div className="w-full flex justify-center items-center relative mt-8">
              <div className="absolute w-[30rem] h-[30rem] bg-amber/10 blur-[130px] rounded-full pointer-events-none -top-10" />
              <img
                src={mascotImg}
                alt="PaperSloth"
                className="relative z-10 w-[38rem] max-w-full animate-float transition-transform duration-200 ease-out drop-shadow-[0_25px_60px_rgba(0,0,0,0.45)] object-contain"
                style={{ transform: `translate(${mousePos.x}px, ${mousePos.y}px)` }}
              />
            </div>

            <div className="flex items-center gap-2 text-muted/40 z-20 mt-auto">
              <div className="w-1.5 h-1.5 rounded-full bg-amber/40" />
              <span className="text-xs font-mono">Powered by Gemini + Pinecone RAG</span>
            </div>
          </div>
        </div>

        {/* Right form panel */}
        <div className="flex-1 flex items-center justify-center p-8 bg-base relative overflow-hidden">
          <div
            className="absolute inset-0 z-0 opacity-[0.07] mix-blend-screen invert pointer-events-none"
            style={{
              backgroundImage: `url(${gearPattern})`,
              backgroundRepeat: 'repeat',
              backgroundSize: '250px 250px',
            }}
          />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-amber/5 blur-[150px] rounded-full pointer-events-none z-0" />

          <div className="w-full max-w-[420px] relative z-10 p-8 sm:p-10 rounded-[2.5rem] bg-white/[0.02] border border-white/[0.05] shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] backdrop-blur-2xl overflow-hidden">
            <div className="absolute inset-0 rounded-[2.5rem] border-t border-white/[0.08] pointer-events-none" />

            <div className="relative z-10">
              {/* Mobile logo */}
              <div className="lg:hidden flex justify-center items-center gap-3 mb-8">
                <img src={logo} alt="PaperSloth" className="w-12 h-12 rounded-xl object-contain drop-shadow-lg" />
                <span className="font-display text-2xl font-semibold text-text tracking-tight">PaperSloth</span>
              </div>

              {/* Header text */}
              <div className="text-center mb-10">
                <h2 className="font-display text-[2.25rem] font-bold text-text tracking-tight leading-tight mb-2">
                  {mode === 'login' ? 'Welcome back.' : 'Get started.'}
                </h2>
                <p className="text-muted/60 text-[15px]">
                  {mode === 'login'
                    ? 'Sign in to access your papers and notes.'
                    : 'Create your free account to continue.'}
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                {mode === 'register' && (
                  <div className="space-y-1.5 text-left">
                    <label className="block text-[13px] font-medium text-text/70 ml-1">Full name</label>
                    <input
                      className="w-full bg-white/[0.03] border border-white/[0.08] hover:border-white/[0.12] rounded-2xl px-5 py-4 text-[15px] text-text placeholder:text-muted/30 focus:outline-none focus:bg-white/[0.05] focus:border-amber/50 focus:ring-1 focus:ring-amber/50 transition-all duration-300 ease-out"
                      placeholder="Ahmad Razif"
                      value={name}
                      onChange={e => setName(e.target.value)}
                      required
                    />
                  </div>
                )}

                <div className="space-y-1.5 text-left">
                  <label className="block text-[13px] font-medium text-text/70 ml-1">Email address</label>
                  <input
                    className="w-full bg-white/[0.03] border border-white/[0.08] hover:border-white/[0.12] rounded-2xl px-5 py-4 text-[15px] text-text placeholder:text-muted/30 focus:outline-none focus:bg-white/[0.05] focus:border-amber/50 focus:ring-1 focus:ring-amber/50 transition-all duration-300 ease-out"
                    type="email"
                    placeholder="you@utp.edu.my"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    required
                  />
                </div>

                <div className="space-y-1.5 text-left">
                  <label className="block text-[13px] font-medium text-text/70 ml-1 flex justify-between items-center">
                    <span>Password</span>
                    {mode === 'login' && (
                      <button type="button" className="text-amber/80 hover:text-amber text-[12px] transition-colors">
                        Forgot?
                      </button>
                    )}
                  </label>
                  <input
                    className="w-full bg-white/[0.03] border border-white/[0.08] hover:border-white/[0.12] rounded-2xl px-5 py-4 text-[15px] text-text placeholder:text-muted/30 focus:outline-none focus:bg-white/[0.05] focus:border-amber/50 focus:ring-1 focus:ring-amber/50 transition-all duration-300 ease-out"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    required
                  />
                </div>

                {error && (
                  <div className="flex items-center gap-3 text-red-400 text-[13px] bg-red-400/10 border border-red-400/20 rounded-2xl px-5 py-3.5 mt-2 animate-in fade-in slide-in-from-top-2 duration-300">
                    <AlertCircle size={16} className="shrink-0" />
                    <span className="font-medium">{error}</span>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-amber text-[#12161a] font-bold text-[15px] rounded-2xl px-5 py-4 mt-6 flex items-center justify-center gap-2 transition-all duration-300 ease-out hover:bg-[#ffcf54] hover:shadow-[0_0_40px_-10px_rgba(251,191,36,0.3)] active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none"
                >
                  {loading ? (
                    <Loader2 size={18} className="animate-spin text-[#12161a]" />
                  ) : (
                    <CheckCircle2 size={18} className="text-[#12161a]" />
                  )}
                  {mode === 'login' ? 'Sign in to workspace' : 'Create your account'}
                </button>
              </form>

              <div className="mt-8 flex items-center justify-center gap-1.5 text-[14px]">
                <span className="text-muted/60">
                  {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}
                </span>
                <button
                  type="button"
                  className="text-amber font-semibold hover:text-amber/80 transition-colors"
                  onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
                >
                  {mode === 'login' ? 'Sign up' : 'Sign in'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}