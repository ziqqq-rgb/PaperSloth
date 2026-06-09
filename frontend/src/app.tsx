import React from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import AppShell from './components/layout/AppShell'
import AuthPage from './pages/AuthPage'
import ChatPage from './pages/ChatPage'
import BrowsePage from './pages/BrowsePage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthed } = useAuthStore()
  return isAuthed() ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  const { isAuthed } = useAuthStore()

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={isAuthed() ? <Navigate to="/chat" replace /> : <AuthPage />}
        />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <AppShell>
                <Routes>
                  <Route path="/chat"   element={<ChatPage />} />
                  <Route path="/browse" element={<BrowsePage />} />
                  <Route path="*"       element={<Navigate to="/chat" replace />} />
                </Routes>
              </AppShell>
            </RequireAuth>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}