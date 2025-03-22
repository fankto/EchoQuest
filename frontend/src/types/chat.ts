import { UUID } from './common';

export type ChatMessage = {
    id: string
    interview_id: string
    role: 'user' | 'assistant'
    content: string
    created_at: string
    tokens_used?: number
    chat_session_id?: string
  }
  
  export type ChatRequest = {
    message: string
  }
  
  export type ChatResponse = {
    user_message: ChatMessage
    assistant_message: ChatMessage
    remaining_tokens: number
  }
  
  export type TranscriptMatch = {
    speaker: string
    text: string
    start_time: number
    end_time: number
    score: number
  }

  export type ChatSession = {
    id: string
    interview_id: string
    title: string
    created_at: string
    updated_at?: string
    message_count?: number
    last_message?: ChatMessage
  }