// Re-export all types for easier imports
export * from './auth'
export * from './interview'
export * from './chat'

// Common application types
export type PaginatedResponse<T> = {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export type ApiError = {
  status: number
  message: string
  code?: string
}

export type ToastMessage = {
  title: string
  description?: string
  type: 'success' | 'error' | 'info' | 'warning'
}

export type SortDirection = 'asc' | 'desc'

export type SortOption = {
  field: string
  direction: SortDirection
}

export enum OrganizationRole {
  OWNER = 'owner',
  ADMIN = 'admin',
  MEMBER = 'member'
}

export type Organization = {
  id: string
  name: string
  description?: string
  member_count: number
  available_interview_credits: number
  available_chat_tokens: number
  created_at: string
  updated_at?: string
}

export type CreditSummary = {
  available_interview_credits: number
  available_chat_tokens: number
  interview_credits_used: number
  chat_tokens_used: number
}