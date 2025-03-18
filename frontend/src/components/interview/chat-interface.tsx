'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import TextareaAutosize from 'react-textarea-autosize'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/components/ui/icons'
import { formatTokens } from '@/lib/format'
import api from '@/lib/api-client'
import { toast } from 'sonner'
import { useChat } from '@/hooks/use-chat'

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at?: string
}

type ChatResponse = {
  user_message: Message
  assistant_message: Message
  remaining_tokens: number
}

type ChatInterfaceProps = {
  interviewId: string
  interviewTitle: string
  transcriptHighlights?: {
    highlightedText?: string[]
    onHighlightClick?: (index: number) => void
  }
}

export function ChatInterface({ 
  interviewId, 
  interviewTitle,
  transcriptHighlights
}: ChatInterfaceProps) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<string>('')
  const prevMessagesLengthRef = useRef<number>(0)
  const router = useRouter()
  
  const { 
    messages, 
    streamingMessage, 
    isLoading, 
    remainingTokens, 
    streamMessage 
  } = useChat({ 
    interviewId,
    onError: (error) => {
      // Check if the error has a response property with status code
      const apiError = error as { response?: { status: number } }
      if (apiError.response?.status === 402) {
        toast.error('You\'ve used all your chat tokens for this interview.', {
          action: (
            <Button variant="outline" size="sm" onClick={() => router.push('/credits')}>
              Buy Tokens
            </Button>
          )
        })
      }
    }
  })

  // Function to scroll to bottom
  const scrollToBottom = useCallback(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [])

  // Scroll when messages change but only if the length increases
  useEffect(() => {
    // Only scroll if messages are added (not on initial load with 0 messages)
    if (messages.length > 0 && messages.length !== prevMessagesLengthRef.current) {
      prevMessagesLengthRef.current = messages.length
      scrollToBottom()
    }
  }, [messages.length, scrollToBottom])
  
  // Handle streaming message updates efficiently
  useEffect(() => {
    if (streamingMessage && streamingMessage.content !== contentRef.current) {
      contentRef.current = streamingMessage.content
      scrollToBottom()
    } else if (!streamingMessage) {
      // Reset content ref when streaming is done
      contentRef.current = ''
    }
  }, [streamingMessage, scrollToBottom])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!input.trim()) return
    
    setInput('')
    
    try {
      await streamMessage(input.trim())
    } catch (error) {
      // Error handling is done in the hook
      console.error('Error in chat submission:', error)
    }
  }

  const tokenPercentage = remainingTokens 
    ? (remainingTokens / 50000) * 100 // Assuming 50k is the default allocation
    : 100

  return (
    <div className="flex flex-col h-[600px] border rounded-md">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(message => (
          <div
            key={message.id}
            className={`flex ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted'
              }`}
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
          </div>
        ))}
        
        {/* Streaming message */}
        {streamingMessage && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-4 py-2 bg-muted">
              <p className="whitespace-pre-wrap">{streamingMessage.content}</p>
              <span className="inline-block w-1 h-4 bg-primary animate-pulse ml-1" />
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      <Separator />
      
      <form onSubmit={handleSubmit} className="p-4">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <TextareaAutosize
              placeholder="Ask a question about this interview..."
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 min-h-[40px] max-h-[120px]"
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={isLoading}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit(e)
                }
              }}
            />
          </div>
          <Button type="submit" disabled={isLoading || !input.trim()}>
            {isLoading ? (
              <Icons.spinner className="h-4 w-4 animate-spin" />
            ) : (
              <Icons.arrowRight className="h-4 w-4" />
            )}
            <span className="sr-only">Send</span>
          </Button>
        </div>
      </form>
    </div>
  )
}