import { useState, useCallback, useEffect } from 'react'
import { ChatMessage, ChatResponse, TranscriptMatch } from '@/types/chat'
import { toast } from 'sonner'
import api from '@/lib/api-client'

interface ApiError extends Error {
  response?: {
    status: number
    data?: any
  }
}

interface UseChatOptions {
  interviewId: string
  onError?: (error: ApiError) => void
}

export function useChat({ interviewId, onError }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [remainingTokens, setRemainingTokens] = useState<number | null>(null)
  const [transcriptMatches, setTranscriptMatches] = useState<TranscriptMatch[]>([])
  const [streamingMessage, setStreamingMessage] = useState<ChatMessage | null>(null)

  // Fetch message history
  const fetchMessages = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await api.get<ChatMessage[]>(`/api/chat/${interviewId}/messages`)
      setMessages(data)
    } catch (error) {
      const apiError = error as ApiError
      setError(apiError)
      onError?.(apiError)
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
    } catch (error) {
      const apiError = error as ApiError
      setError(apiError)
      onError?.(apiError)
      
      if (apiError.response?.status === 402) {
        toast.error('Not enough chat tokens remaining')
      } else {
        toast.error('Failed to send message')
      }
      
      throw error
    } finally {
      setIsLoading(false)
    }
  }, [interviewId, onError])

  // Stream a message
  const streamMessage = useCallback(async (content: string) => {
    try {
      setIsLoading(true)
      
      // Add user message immediately
      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      }
      
      // Add user message to the chat
      setMessages(prev => [...prev, userMessage])
      
      // Create placeholder for assistant message
      const assistantMessage: ChatMessage = {
        id: `stream-${Date.now().toString()}`,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      }
      
      // Set the streaming message
      setStreamingMessage(assistantMessage)
      
      // Open EventSource connection
      const url = `${api.getBaseUrl()}/api/chat/${interviewId}/chat/stream`
      const token = localStorage.getItem('token')
      
      const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      }
      
      // Create an AbortController to be able to cancel the fetch
      const controller = new AbortController()
      const { signal } = controller
      
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message: content }),
        signal,
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to stream message')
      }
      
      const reader = response.body?.getReader()
      if (!reader) throw new Error('Stream reader not available')
      
      const decoder = new TextDecoder()
      let completeContent = ''
      let receivedTokens = 0
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n\n')
        
        for (const line of lines) {
          if (!line.trim() || !line.startsWith('data:')) continue
          
          try {
            const eventData = JSON.parse(line.replace('data:', '').trim())
            
            if (eventData.type === 'token') {
              // Append token to the streaming message content
              completeContent += eventData.content
              // Use function form to prevent unnecessary re-renders
              setStreamingMessage(prev => 
                prev ? { ...prev, content: completeContent } : null
              )
            } else if (eventData.type === 'done') {
              // Store received tokens to use locally without dependency
              receivedTokens = eventData.remaining_tokens
              
              // Message is complete, create final message with all content
              const finalMessage = {
                ...assistantMessage,
                content: completeContent,
              }
              
              // Add the complete message to the messages array
              setMessages(prev => [...prev, finalMessage])
              
              // Clear streaming state since we now have the final message
              setStreamingMessage(null)
              
              // Update tokens
              setRemainingTokens(receivedTokens)
              
              // Return early since we've handled the message
              return { 
                user_message: userMessage, 
                assistant_message: finalMessage,
                remaining_tokens: receivedTokens
              }
            } else if (eventData.type === 'error') {
              throw new Error(eventData.content || 'Error in stream')
            }
          } catch (err) {
            console.error('Error parsing stream data:', err)
          }
        }
      }
      
      // This code should only run if we didn't get a 'done' event
      // Add the complete assistant message to the list as a fallback
      const finalMessage = {
        ...assistantMessage,
        content: completeContent,
      }
      
      setMessages(prev => [...prev, finalMessage])
      setStreamingMessage(null)
      
      // Don't reference remainingTokens state directly
      return { 
        user_message: userMessage, 
        assistant_message: finalMessage,
        remaining_tokens: receivedTokens || 0
      }
    } catch (error) {
      const apiError = error as ApiError
      setError(apiError)
      onError?.(apiError)
      
      if (apiError.response?.status === 402) {
        toast.error('Not enough chat tokens remaining')
      } else {
        toast.error(error instanceof Error ? error.message : 'Failed to stream message')
      }
      
      // Clear streaming message on error
      setStreamingMessage(null)
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
    streamingMessage,
    sendMessage,
    streamMessage,
    fetchMessages,
    searchTranscript
  }
}