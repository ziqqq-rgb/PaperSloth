import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  MessageSquare,
  BookOpen,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { cx } from '../../utils/helpers'
import logo from '../../assets/logo.svg'

export default function Sidebar() {
  const { user, logout } = useAuthStore()
  const location         = useLocation()
  const navigate         = useNavigate()
  const [collapsed, setCollapsed] = useState(false)

  const nav = [
    { path: '/chat',   icon: MessageSquare, label: 'Ask AI' },
    { path: '/browse', icon: BookOpen,      label: 'Browse Papers' },
  ]

  return (
    <aside
      className={cx(
        'h-screen bg-surface border-r border-border flex flex-col shrink-0 transition-all duration-200 ease-in-out',
        collapsed ? 'w-[56px]' : 'w-[220px]'
      )}
    >
      {/* Logo */}
      <div
        className={cx(
          'flex items-center h-[52px] border-b border-border px-2 shrink-0',
          collapsed ? 'justify-center' : ''
        )}
      >
        <img src={logo} alt="PaperSloth" className="w-14 h-14 rounded-lg object-contain" />
        {!collapsed && (
          <span className="font-display text-[1.1rem] text-text leading-none -ml-2">
            PaperSloth
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 p-2 space-y-0.5">
        {nav.map(({ path, icon: Icon, label }) => {
          const active = location.pathname === path
          return (
            <Link
              key={path}
              to={path}
              title={collapsed ? label : undefined}
              className={cx(
                'flex items-center rounded-lg text-sm transition-all duration-100',
                collapsed ? 'justify-center h-9 w-9 mx-auto' : 'gap-2.5 px-3 py-2',
                active
                  ? 'bg-amber/10 text-amber'
                  : 'text-muted hover:text-text hover:bg-border/60'
              )}
            >
              <Icon size={15} className="shrink-0" />
              {!collapsed && <span className="font-medium">{label}</span>}
            </Link>
          )
        })}
      </nav>

      {/* Bottom */}
      <div className="p-2 border-t border-border space-y-0.5">
        {!collapsed && user && (
          <div className="px-3 py-2 mb-1">
            <p className="text-xs font-medium text-text truncate">
              {user.name || user.email}
            </p>
            <p className="text-[11px] text-muted truncate font-mono">{user.email}</p>
          </div>
        )}

        <button
          onClick={() => setCollapsed(!collapsed)}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={cx(
            'flex items-center rounded-lg text-muted hover:text-text hover:bg-border/60 text-sm transition-all duration-100',
            collapsed ? 'justify-center h-9 w-9 mx-auto' : 'gap-2.5 px-3 py-2 w-full'
          )}
        >
          {collapsed ? (
            <PanelLeftOpen size={15} />
          ) : (
            <>
              <PanelLeftClose size={15} className="shrink-0" />
              <span>Collapse</span>
            </>
          )}
        </button>

        <button
          onClick={() => { logout(); navigate('/login') }}
          title="Sign out"
          className={cx(
            'flex items-center rounded-lg text-muted hover:text-red-400 hover:bg-red-400/8 text-sm transition-all duration-100',
            collapsed ? 'justify-center h-9 w-9 mx-auto' : 'gap-2.5 px-3 py-2 w-full'
          )}
        >
          <LogOut size={15} className="shrink-0" />
          {!collapsed && <span>Sign out</span>}
        </button>
      </div>
    </aside>
  )
}