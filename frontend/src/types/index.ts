import type { Source } from '../api/search'

export type { Source }

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  isStreaming?: boolean
  timestamp: Date
}

export interface Paper {
  course_code: string
  subject_name: string
  semester: string
  year: number
  total_questions: number
  total_marks: number
  questions_with_images: number
  has_pdf: boolean
  file_size_kb: number
}

export interface Question {
  parent_id: string
  question_number: string
  full_text: string
  total_marks: number
  children: unknown
  image_urls: Record<string, string>
}