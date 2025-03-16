import React, { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/router'
import TextareaAutosize from 'react-textarea-autosize'
import { useToast } from '@/components/ui/use-toast'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { SendIcon, Search, ZapIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatTokens } from '@/lib/format'
import api from '@/lib/api-client'

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
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
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [remainingTokens, setRemainingTokens] = useState<number | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const { toast } = useToast()

  const fetchMessages = async () => {
    try {
      const data = await api.get<Message[]>(`/api/chat/${interviewId}/messages`)
      setMessages(data)
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load chat messages",
        variant: "destructive",
      })
    }
  }

  useEffect(() => {
    fetchMessages()
  }, [interviewId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const message = inputValue.trim()
    
    if (!message) return
    
    setInputValue('')
    setIsLoading(true)
    
    try {
      const response = await api.post(`/api/chat/${interviewId}/chat`, {
        message
      })
      
      setMessages(prev => [
        ...prev, 
        response.user_message, 
        response.assistant_message
      ])
      
      setRemainingTokens(response.remaining_tokens)
    } catch (error: any) {
      if (error.response?.status === 402) {
        toast({
          title: "Insufficient Credits",
          description: "You've used all your chat tokens for this interview.",
          variant: "destructive",
          action: (
            <Button variant="outline" size="sm" onClick={() => router.push('/credits')}>
              Buy Tokens
            </Button>
          )
        })
      } else {
        toast({
          title: "Error",
          description: error.message || "Failed to send message",
          variant: "destructive",
        })
      }
    } finally {
      setIsLoading(false)
    }
  }

  const tokenPercentage = remainingTokens 
    ? (remainingTokens / 50000) * 100 // Assuming 50k is the default allocation
    : 100

  return (
    <div className="flex flex-col h-full">
      <Card className="flex flex-col h-full">
        <CardHeader className="px-4 py-3 flex flex-row items-center space-y-0 justify-between border-b">
          <CardTitle className="text-lg">Chat with {interviewTitle}</CardTitle>
          {remainingTokens !== null && (
            <div className="flex flex-col gap-1 items-end">
              <div className="text-xs text-muted-foreground">
                {formatTokens(remainingTokens)} tokens remaining
              </div>
              <Progress className="h-1 w-24" value={tokenPercentage} />
            </div>
          )}
        </CardHeader>
        
        <CardContent className="p-4 flex-1 overflow-auto flex flex-col gap-4">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center">
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-muted">
                <Search className="h-10 w-10 text-muted-foreground" />
              </div>
              <h3 className="mt-4 text-lg font-semibold">
                Ask questions about your interview
              </h3>
              <p className="mt-2 text-center text-sm text-muted-foreground max-w-sm">
                Start a conversation to explore insights, find quotes, or analyze themes from your interview transcript.
              </p>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                key={message.id || index}
                className={cn(
                  "flex items-start gap-4 w-full",
                  message.role === "assistant" && "flex-row-reverse"
                )}
              >
                <div className={cn(
                  "flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-md border text-sm font-semibold",
                  message.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                )}>
                  {message.role === "user" ? "U" : "AI"}
                </div>
                <div className={cn(
                  "flex flex-col gap-1 max-w-4xl",
                  message.role === "assistant" ? "items-end mr-[calc(5%)]" : "items-start ml-[calc(5%)]"
                )}>
                  <div className={cn(
                    "rounded-lg px-4 py-2 text-sm",
                    message.role === "user" ? "bg-muted" : "bg-primary text-primary-foreground"
                  )}>
                    {message.content}
                  </div>
                  <span className="text-xs text-muted-foreground px-1">
                    {new Date(message.created_at).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </CardContent>
        
        <CardFooter className="p-4 pt-2 border-t">
          {transcriptHighlights?.highlightedText && transcriptHighlights.highlightedText.length > 0 && (
            <div className="mb-3 w-full">
              <p className="text-xs text-muted-foreground mb-2">Relevant sections:</p>
              <div className="flex flex-wrap gap-2">
                {transcriptHighlights.highlightedText.map((text, index) => (
                  <Badge 
                    key={index} 
                    variant="outline" 
                    className="cursor-pointer hover:bg-muted truncate max-w-[250px]"
                    onClick={() => transcriptHighlights.onHighlightClick?.(index)}
                  >
                    {text}
                  </Badge>
                ))}
              </div>
              <Separator className="my-3" />
            </div>
          )}
          
          <form onSubmit={handleSubmit} className="flex w-full items-end gap-2">
            <div className="relative flex-1">
              <TextareaAutosize
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Ask a question about the interview..."
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 min-h-[80px] max-h-[240px]"
                minRows={3}
                maxRows={10}
                disabled={isLoading}
              />
            </div>
            <Button type="submit" size="icon" disabled={isLoading || !inputValue.trim()}>
              {isLoading ? <ZapIcon className="h-4 w-4 animate-pulse" /> : <SendIcon className="h-4 w-4" />}
            </Button>
          </form>
        </CardFooter>
      </Card>
    </div>
  )
}