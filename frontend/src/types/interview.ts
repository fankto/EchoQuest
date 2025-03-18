export enum InterviewStatus {
    CREATED = 'created',
    UPLOADED = 'uploaded',
    PROCESSING = 'processing',
    PROCESSED = 'processed',
    TRANSCRIBING = 'transcribing',
    TRANSCRIBED = 'transcribed',
    ERROR = 'error',
  }
  
  export type Transcript = {
    text: string
    start_time: number
    end_time: number
    speaker: string
  }
  
  export type QuestionnaireInfo = {
    id: string
    title: string
    questions: string[]
  }
  
  export type GeneratedAnswer = {
    question: string
    answer: string
  }
  
  export type Interview = {
    id: string
    title: string
    interviewee_name: string
    date: string
    location?: string
    status: InterviewStatus
    duration?: number
    error_message?: string
    original_filenames?: string[]
    processed_filenames?: string[]
    transcription?: string
    transcript_segments?: Transcript[]
    generated_answers?: Record<string, Record<string, string>>
    questionnaire_id?: string
    questionnaire?: QuestionnaireInfo
    questionnaires?: QuestionnaireInfo[]
    remaining_chat_tokens?: number
    created_at: string
    updated_at?: string
  }
  
  export type InterviewCreate = {
    title: string
    interviewee_name: string
    date: string
    location?: string
    notes?: string
    questionnaire_id?: string
  }
  
  export type InterviewPatch = {
    title?: string
    interviewee_name?: string
    date?: string
    location?: string
    notes?: string
    questionnaire_id?: string
  }
  
  export type TaskResponse = {
    status: string
    message: string
  }