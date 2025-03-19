export type Questionnaire = {
  id: string
  title: string
  description?: string
  content: string
  questions: string[]
  creator_id: string
  organization_id?: string
  created_at: string
  updated_at?: string
  interview_count: number
} 