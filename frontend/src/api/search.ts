import api from './client'
import { useAuthStore } from '../store/authStore'

export interface SearchFilters {
  course_code?:   string
  year?:          number
  semester?:      string
  question_type?: string
  min_marks?:     number
}

export interface Source {
  parent_id:       string
  question_number: string
  full_text?:      string
  total_marks:     number
  image_urls:      Record<string, string>
  course_code:     string
  semester:        string
  year:            number
}

export interface SearchResult {
  answer:  string
  sources: Source[]
  cached:  boolean
}

export interface DownloadInfo {
  url:          string
  filename:     string
  subject_name: string
  file_size_kb: number
  expires_in:   number
}

// Standard search — returns full JSON
export const searchApi = {
  search: (query: string, filters: SearchFilters = {}): Promise<SearchResult> =>
    api.post('/api/search', { query, ...filters }).then(r => r.data),

  subjects: () =>
    api.get('/api/subjects').then(r => r.data),

  papers: (filters: SearchFilters = {}) =>
    api.get('/api/papers', { params: filters }).then(r => r.data),

  getPaper: (courseCode: string, year: number, semester: string) =>
    api.get(`/api/papers/${courseCode}/${year}/${encodeURIComponent(semester)}`).then(r => r.data),

  downloadPaper: (courseCode: string, year: number, semester: string): Promise<DownloadInfo> =>
    api
      .get(`/api/papers/${courseCode}/${year}/${encodeURIComponent(semester)}/download`)
      .then(r => r.data),
}

// Streaming search — returns SSE
export type StreamEvent =
  | { type: 'intent';      intent: string; slots: Record<string, unknown> }
  | { type: 'tutor_start'; question_number: string; course_code: string; year: number; semester: string; sub_parts: string[]; full_text: string }
  | { type: 'sources';     sources: Source[] }
  | { type: 'token';       token: string }
  | { type: 'done' }
  | { type: 'error';       message: string }

export async function* streamSearch(
  query:   string,
  filters: SearchFilters = {}
): AsyncGenerator<StreamEvent> {
  const token = useAuthStore.getState().token

  const res = await fetch('/api/search/agent', {
    method:  'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ query, ...filters }),
  })

  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`)

  const reader  = res.body!.getReader()
  const decoder = new TextDecoder()
  let   buffer  = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          yield JSON.parse(line.slice(6)) as StreamEvent
        } catch {
          // malformed line — skip
        }
      }
    }
  }
}

export const historyApi = {
  get: (limit = 50): Promise<{ messages: { role: string; content: string; created_at: string }[] }> =>
    api.get('/api/history', { params: { limit } }).then(r => r.data),

  save: (role: string, content: string, intent?: string) =>
    api.post('/api/history', { role, content, intent }).catch(() => {}), // silent fail

  clear: () =>
    api.delete('/api/history'),
}