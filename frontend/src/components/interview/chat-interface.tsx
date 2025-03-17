'use client'

import React, { useState, useRef, useEffect } from 'react'
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
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hello! I can help answer questions about this interview. What would you like to know?'
    }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [remainingTokens, setRemainingTokens] = useState<number | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const router = useRouter()

  const fetchMessages = async () => {
    try {
      const data = await api.get<Message[]>(`/api/chat/${interviewId}/messages`)
      setMessages(data)
    } catch (error) {
      toast.error('Failed to load chat messages')
    }
  }

  useEffect(() => {
    fetchMessages()
  }, [interviewId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!input.trim()) return
    
    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input
    }
    
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)
    
    try {
      const response = await api.post<ChatResponse>(`/api/chat/${interviewId}/chat`, {
        message: input
      })
      
      setMessages(prev => [
        ...prev, 
        response.user_message, 
        response.assistant_message
      ])
      
      setRemainingTokens(response.remaining_tokens)
    } catch (error: any) {
      if (error.response?.status === 402) {
        toast.error('You\'ve used all your chat tokens for this interview.', {
          action: (
            <Button variant="outline" size="sm" onClick={() => router.push('/credits')}>
              Buy Tokens
            </Button>
          )
        })
      } else {
        toast.error(error.message || 'Failed to send message')
      }
    } finally {
      setIsLoading(false)
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