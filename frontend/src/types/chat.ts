export type ChatMessage = {
    id: string
    role: 'user' | 'assistant'
    content: string
    created_at: string
    tokens_used?: number
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
    text: string
    start_time: number
    end_time: number
    speaker: string
    score: number
  }