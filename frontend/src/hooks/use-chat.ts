import { useState, useCallback, useEffect, useRef } from 'react'
import type { ChatMessage, ChatResponse, TranscriptMatch } from '@/types/chat'
import { toast } from 'sonner'
import api from '@/lib/api-client'

interface ApiError extends Error {
  response?: {
    status: number
    data?: unknown
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
  const contentRef = useRef<string>('')
  const hasFetchedRef = useRef(false)
  const isLoadingRef = useRef(false)
  const isMountedRef = useRef(true)
  const fetchRequested = useRef(false)
  const interviewIdRef = useRef<string>(interviewId)

  // Update the interview ID ref when it changes
  useEffect(() => {
    interviewIdRef.current = interviewId;
    
    // Reset fetch state when interview ID changes
    if (interviewId) {
      hasFetchedRef.current = false;
      fetchRequested.current = true;
    }
    
    return () => {
      // Component unmounting, reset state
      isMountedRef.current = false;
    };
  }, [interviewId]);
  
  // Reset the mounted ref on mount
  useEffect(() => {
    isMountedRef.current = true;
    
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Fetch message history
  const fetchMessages = useCallback(async () => {
    // Prevent multiple fetches and check loading state
    if (!isMountedRef.current || hasFetchedRef.current || isLoadingRef.current) return;
    
    // Prevent the function from being called again before it completes
    isLoadingRef.current = true;
    
    try {
      setIsLoading(true);
      
      // Clear the fetch requested flag
      fetchRequested.current = false;
      
      const data = await api.get<ChatMessage[]>(`/api/chat/${interviewIdRef.current}/messages`);
      
      // Only update state if component is still mounted and data is valid
      if (isMountedRef.current && Array.isArray(data)) {
        setMessages(data);
        hasFetchedRef.current = true;
      }
    } catch (error) {
      if (isMountedRef.current) {
        const apiError = error as ApiError;
        setError(apiError);
        onError?.(apiError);
        toast.error('Failed to load chat messages');
      }
    } finally {
      // Only update state if component is still mounted
      if (isMountedRef.current) {
        setIsLoading(false);
      }
      isLoadingRef.current = false;
    }
  }, [onError]);
  
  // Dedicated useEffect for handling the initial fetch and any refetches
  useEffect(() => {
    // Only fetch if requested and not already fetched/loading
    if (fetchRequested.current && !hasFetchedRef.current && !isLoadingRef.current) {
      fetchMessages();
    }
  }, [fetchMessages]);
  
  // When interviewId changes, trigger a fetch
  useEffect(() => {
    if (interviewId) {
      fetchRequested.current = true;
      // We need to reset fetch state when ID changes
      hasFetchedRef.current = false;
    }
  }, [interviewId]);

  // Send a message
  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoadingRef.current || !isMountedRef.current) return;
    
    try {
      isLoadingRef.current = true;
      setIsLoading(true);
      const response = await api.post<ChatResponse>(`/api/chat/${interviewIdRef.current}/chat`, {
        message: content
      });
      
      if (isMountedRef.current) {
        setMessages(prev => [...prev, response.user_message, response.assistant_message]);
        setRemainingTokens(response.remaining_tokens);
      }
      
      return response;
    } catch (error) {
      if (isMountedRef.current) {
        const apiError = error as ApiError;
        setError(apiError);
        onError?.(apiError);
        
        if (apiError.response?.status === 402) {
          toast.error('Not enough chat tokens remaining');
        } else {
          toast.error('Failed to send message');
        }
      }
      
      throw error;
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
      isLoadingRef.current = false;
    }
  }, [onError]);

  // Stream a message
  const streamMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoadingRef.current || !isMountedRef.current) return;
    
    try {
      isLoadingRef.current = true;
      setIsLoading(true);
      
      // Add user message immediately
      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      };
      
      // Add user message to the chat
      setMessages(prev => [...prev, userMessage]);
      
      // Create placeholder for assistant message
      const assistantMessage: ChatMessage = {
        id: `stream-${Date.now().toString()}`,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      };
      
      // Reset content reference before streaming
      contentRef.current = '';
      
      // Set the streaming message
      setStreamingMessage(assistantMessage);
      
      // Open EventSource connection
      const url = `${api.getBaseUrl()}/api/chat/${interviewIdRef.current}/chat/stream`
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
              
              // Only update if content has actually changed and component is mounted
              if (completeContent !== contentRef.current && isMountedRef.current) {
                contentRef.current = completeContent
                
                // Create a new message object to avoid reference issues
                const updatedMessage = {
                  ...assistantMessage,
                  content: completeContent
                }
                
                setStreamingMessage(updatedMessage)
              }
            } else if (eventData.type === 'done') {
              // Store received tokens to use locally without dependency
              receivedTokens = eventData.remaining_tokens
              
              // Message is complete, create final message with all content
              const finalMessage = {
                ...assistantMessage,
                content: completeContent,
              }
              
              // Only update state if component is still mounted
              if (isMountedRef.current) {
                // Add the complete message to the messages array
                setMessages(prev => [...prev, finalMessage])
                
                // Clear streaming state since we now have the final message
                setStreamingMessage(null)
                contentRef.current = ''
                
                // Update tokens
                setRemainingTokens(receivedTokens)
              }
              
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
      if (isMountedRef.current) {
        const finalMessage = {
          ...assistantMessage,
          content: completeContent,
        }
        
        setMessages(prev => [...prev, finalMessage])
        setStreamingMessage(null)
        contentRef.current = ''
      }
      
      // Don't reference remainingTokens state directly
      return { 
        user_message: userMessage, 
        assistant_message: {
          ...assistantMessage,
          content: completeContent,
        },
        remaining_tokens: receivedTokens || 0
      }
    } catch (error) {
      if (isMountedRef.current) {
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
        contentRef.current = ''
      }
      
      throw error
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false)
      }
      isLoadingRef.current = false
    }
  }, [onError]);

  // Search transcript
  const searchTranscript = useCallback(async (query: string, limit = 5) => {
    if (!isMountedRef.current) return [];
    
    try {
      const response = await api.post<{ matches: TranscriptMatch[] }>(`/api/chat/${interviewIdRef.current}/search`, {
        query,
        limit
      })
      
      if (isMountedRef.current) {
        setTranscriptMatches(response.matches)
      }
      return response.matches
    } catch (error) {
      console.error('Failed to search transcript:', error)
      return []
    }
  }, []);

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