import api from './client'

export const authApi = {
  register: (email: string, password: string, name: string) =>
    api.post('/api/auth/register', { email, password, name }).then(r => r.data),

  login: (email: string, password: string) =>
    // Notice the added /api prefix here!
    api.post('/api/auth/login', { email, password }).then(r => r.data),

  getMe: () =>
    api.get('/api/auth/me').then(r => r.data),
}