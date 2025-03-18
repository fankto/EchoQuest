'use client'

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
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
import { formatDistanceToNow } from 'date-fns'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { ScrollArea } from '@/components/ui/scroll-area'
import { PlusIcon, MessageSquare, MoreVertical, Edit, Trash2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { ChatSession } from '@/types/chat'

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
  const [chatKey, setChatKey] = useState(Date.now())
  const [activeChatSession, setActiveChatSession] = useState<string | null>(null)
  const [renameSession, setRenameSession] = useState<{id: string, title: string} | null>(null)
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<string>('')
  const prevMessagesLengthRef = useRef<number>(0)
  const lastContentRef = useRef<string>('')
  const activeTabRef = useRef<boolean>(true)
  const router = useRouter()
  
  // Use a custom key to force remount when interviewId changes
  const chatKeyMemo = useMemo(() => `chat-${interviewId}`, [interviewId]);
  
  const { 
    messages, 
    streamingMessage, 
    isLoading, 
    remainingTokens, 
    streamMessage,
    chatSessions,
    fetchMessages,
    createChatSession,
    renameChatSession,
    deleteChatSession,
    loadChatSession
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

  // Track visibility in case the component is mounted but not visible (e.g., in a hidden tab)
  useEffect(() => {
    const handleVisibilityChange = () => {
      activeTabRef.current = document.visibilityState === 'visible';
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  // Function to scroll to bottom
  const scrollToBottom = useCallback(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [])

  // Create a new chat session
  const handleNewChat = useCallback(async () => {
    try {
      await createChatSession("New Chat")
      setActiveChatSession(null)
      setChatKey(Date.now()) // Reset the chat interface
    } catch (error) {
      console.error("Failed to create new chat:", error)
    }
  }, [createChatSession])

  // Handle session selection
  const handleSessionSelect = useCallback(async (sessionId: string) => {
    try {
      if (sessionId !== activeChatSession) {
        await loadChatSession(sessionId)
        setActiveChatSession(sessionId)
      }
    } catch (error) {
      console.error("Failed to load chat session:", error)
    }
  }, [activeChatSession, loadChatSession])

  // Handle session rename
  const handleRenameSubmit = async () => {
    if (renameSession) {
      try {
        await renameChatSession(renameSession.id, renameSession.title)
        setRenameSession(null)
      } catch (error) {
        console.error("Failed to rename chat session:", error)
      }
    }
  }

  // Handle session delete
  const handleDeleteSession = async () => {
    if (isDeleteConfirmOpen) {
      try {
        await deleteChatSession(isDeleteConfirmOpen)
        setIsDeleteConfirmOpen(null)
        if (isDeleteConfirmOpen === activeChatSession) {
          setActiveChatSession(null)
        }
      } catch (error) {
        console.error("Failed to delete chat session:", error)
      }
    }
  }

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
    // Skip if there's no streaming message
    if (!streamingMessage) {
      if (contentRef.current !== '') {
        contentRef.current = '';
      }
      return;
    }
    
    const currentContent = streamingMessage.content;
    
    // Only update if the content has actually changed to avoid loops
    if (currentContent !== lastContentRef.current) {
      lastContentRef.current = currentContent;
      contentRef.current = currentContent;
      scrollToBottom();
    }
  }, [streamingMessage, scrollToBottom]);

  // Clean up resources on unmount or when interviewId changes
  useEffect(() => {
    return () => {
      // Reset all refs when component unmounts or interviewId changes
      contentRef.current = '';
      prevMessagesLengthRef.current = 0;
      lastContentRef.current = '';
    };
  }, []); // No dependencies needed as we're just cleaning up on unmount

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!input.trim() || isLoading) return;
    
    setInput('')
    
    try {
      await streamMessage(input.trim(), activeChatSession)
    } catch (error) {
      // Error handling is done in the hook
      console.error('Error in chat submission:', error)
    }
  }

  const tokenPercentage = remainingTokens 
    ? (remainingTokens / 50000) * 100 // Assuming 50k is the default allocation
    : 100

  return (
    <div className="flex h-[600px] border rounded-md overflow-hidden" key={chatKey}>
      {/* Chat Sessions Sidebar */}
      <div className="w-56 border-r bg-muted/30 flex flex-col">
        <div className="p-3 flex justify-between items-center border-b">
          <h3 className="font-medium text-sm">Chat History</h3>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-7 w-7"
                  onClick={handleNewChat}
                >
                  <PlusIcon className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>New Chat</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        
        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {chatSessions.length === 0 ? (
              <div className="px-2 py-4 text-xs text-muted-foreground text-center">
                No chat sessions yet
              </div>
            ) : (
              chatSessions.map((session) => (
                <div 
                  key={session.id}
                  className={`group flex items-center justify-between rounded-md px-2 py-1.5 text-sm ${
                    session.id === activeChatSession
                      ? 'bg-accent text-accent-foreground'
                      : 'hover:bg-accent/50 cursor-pointer'
                  }`}
                  onClick={() => handleSessionSelect(session.id)}
                >
                  <div className="flex items-center gap-2 overflow-hidden">
                    <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{session.title}</span>
                  </div>
                  
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                      <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100">
                        <MoreVertical className="h-3.5 w-3.5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={(e) => {
                        e.stopPropagation()
                        setRenameSession({ id: session.id, title: session.title })
                      }}>
                        <Edit className="mr-2 h-4 w-4" /> Rename
                      </DropdownMenuItem>
                      <DropdownMenuItem 
                        className="text-destructive focus:text-destructive"
                        onClick={(e) => {
                          e.stopPropagation()
                          setIsDeleteConfirmOpen(session.id)
                        }}
                      >
                        <Trash2 className="mr-2 h-4 w-4" /> Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
        
        {/* Token usage display */}
        <div className="p-3 border-t">
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">
              Tokens remaining
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div 
                className="h-full bg-primary" 
                style={{ width: `${tokenPercentage}%` }}
              />
            </div>
            <div className="text-xs text-muted-foreground text-right">
              {remainingTokens !== null ? remainingTokens.toLocaleString() : "Loading..."}
            </div>
          </div>
        </div>
      </div>
      
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
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
      
      {/* Rename Dialog */}
      <Dialog open={!!renameSession} onOpenChange={(open) => !open && setRenameSession(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename Chat Session</DialogTitle>
          </DialogHeader>
          <Input 
            value={renameSession?.title || ''}
            onChange={(e) => setRenameSession(prev => prev ? {...prev, title: e.target.value} : null)}
            placeholder="Chat session name"
            className="mt-4"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameSession(null)}>Cancel</Button>
            <Button onClick={handleRenameSubmit}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* Delete Confirmation Dialog */}
      <Dialog open={!!isDeleteConfirmOpen} onOpenChange={(open) => !open && setIsDeleteConfirmOpen(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Chat Session</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this chat session? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteConfirmOpen(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDeleteSession}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}