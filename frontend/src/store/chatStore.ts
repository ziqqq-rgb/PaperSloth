import { create } from 'zustand'
import type { Message } from '../types'
import type { SearchFilters } from '../api/search'

interface ChatState {
  messages:      Message[]
  historyLoaded: boolean
  filters:       SearchFilters        
  showFilters:   boolean              
  setMessages:   (messages: Message[]) => void
  addMessage:    (message: Message) => void
  updateMessage: (id: string, update: Partial<Message>) => void
  clearMessages: () => void
  markLoaded:    () => void
  setFilters:    (filters: SearchFilters) => void     
  setShowFilters:(show: boolean) => void              
}

export const useChatStore = create<ChatState>((set) => ({
  messages:      [],
  historyLoaded: false,
  filters:       {},                  
  showFilters:   false,               
  setMessages:   (messages) => set({ messages }),
  addMessage:    (message)  => set(state => ({ messages: [...state.messages, message] })),
  updateMessage: (id, update) => set(state => ({
    messages: state.messages.map(m => m.id === id ? { ...m, ...update } : m)
  })),
  clearMessages: () => set({ messages: [], historyLoaded: false }),
  markLoaded:    () => set({ historyLoaded: true }),
  setFilters:    (filters) => set({ filters }),       
  setShowFilters:(show) => set({ showFilters: show }), 
}))