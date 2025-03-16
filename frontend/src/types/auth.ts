export enum UserRole {
    ADMIN = 'admin',
    USER = 'user',
  }
  
  export type User = {
    id: string
    email: string
    full_name?: string
    role: UserRole
    is_active: boolean
    available_interview_credits: number
    available_chat_tokens: number
    created_at: string
  }
  
  export type AuthResponse = {
    access_token: string
    refresh_token: string
    token_type: string
  }
  
  export type ResetPasswordRequest = {
    token: string
    password: string
  }