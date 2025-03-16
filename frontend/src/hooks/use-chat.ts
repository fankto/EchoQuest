import { useState, useCallback, useEffect } from 'react'
import { ChatMessage, ChatResponse, TranscriptMatch } from '@/types/chat'
import { toast } from 'sonner'
import api from '@/lib/api-client'

interface UseChatOptions {
  interviewId: string
  onError?: (error: Error) => void
}

export function useChat({ interviewId, onError }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [remainingTokens, setRemainingTokens] = useState<number | null>(null)
  const [transcriptMatches, setTranscriptMatches] = useState<TranscriptMatch[]>([])

  // Fetch message history
  const fetchMessages = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await api.get<ChatMessage[]>(`/api/chat/${interviewId}/messages`)
      setMessages(data)
    } catch (error: any) {
      setError(error)
      onError?.(error)
      toast.error('Failed to load chat messages')
    } finally {
      setIsLoading(false)
    }
  }, [interviewId, onError])

  // Send a message
  const sendMessage = useCallback(async (content: string) => {
    try {
      setIsLoading(true)
      const response = await api.post<ChatResponse>(`/api/chat/${interviewId}/chat`, {
        message: content
      })
      
      setMessages(prev => [...prev, response.user_message, response.assistant_message])
      setRemainingTokens(response.remaining_tokens)
      
      return response
    } catch (error: any) {
      setError(error)
      onError?.(error)
      
      if (error.response?.status === 402) {
        toast.error('Not enough chat tokens remaining')
      } else {
        toast.error('Failed to send message')
      }
      
      throw error
    } finally {
      setIsLoading(false)
    }
  }, [interviewId, onError])

  // Search transcript
  const searchTranscript = useCallback(async (query: string, limit: number = 5) => {
    try {
      const response = await api.post<{ matches: TranscriptMatch[] }>(`/api/chat/${interviewId}/search`, {
        query,
        limit
      })
      
      setTranscriptMatches(response.matches)
      return response.matches
    } catch (error: any) {
      console.error('Failed to search transcript:', error)
      return []
    }
  }, [interviewId])

  // Load messages on mount
  useEffect(() => {
    fetchMessages()
  }, [fetchMessages])

  return {
    messages,
    isLoading,
    error,
    remainingTokens,
    transcriptMatches,
    sendMessage,
    fetchMessages,
    searchTranscript
  }
}