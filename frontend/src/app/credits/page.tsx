'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from 'sonner'
import { Check, ChevronsUpDown, HelpCircle, Sparkles, Zap, History } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api-client'

type CreditPackage = {
  id: string
  name: string
  description: string
  credits: number
  price: number
  validity_days: number
}

type TokenPackage = {
  id: string
  name: string
  description: string
  tokens: number
  price: number
}

type CreditPurchaseResponse = {
  success: boolean
  message: string
  credits_added: number
  total_credits: number
  transaction_id: string
}

type Transaction = {
  id: string
  transaction_type: string
  amount: number
  price: number | null
  reference: string | null
  created_at: string
  interview_id: string | null
}

export default function CreditsPage() {
  const [loading, setLoading] = useState<string | null>(null)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [transactionsLoading, setTransactionsLoading] = useState(false)
  const [transactionsError, setTransactionsError] = useState<string | null>(null)
  const [interviewCredits, setInterviewCredits] = useState<CreditPackage[]>([
    {
      id: 'starter',
      name: 'Starter Pack',
      description: '10 interview credits (~$4.90/interview)',
      credits: 10,
      price: 49.00,
      validity_days: 365,
    },
    {
      id: 'professional',
      name: 'Professional Bundle',
      description: '40 interview credits (~$3.73/interview)',
      credits: 40,
      price: 149.00,
      validity_days: 365,
    },
    {
      id: 'team',
      name: 'Team Bundle',
      description: '100 interview credits (~$3.49/interview)',
      credits: 100,
      price: 349.00,
      validity_days: 547,
    },
  ])
  
  const [tokenPackages, setTokenPackages] = useState<TokenPackage[]>([
    {
      id: 'small',
      name: 'Small Token Package',
      description: '100K chat tokens',
      tokens: 100000,
      price: 5.0,
    },
    {
      id: 'medium',
      name: 'Medium Token Package',
      description: '500K chat tokens',
      tokens: 500000,
      price: 20.0,
    },
    {
      id: 'large',
      name: 'Large Token Package',
      description: '1M chat tokens',
      tokens: 1000000,
      price: 35.0,
    },
  ])

  const handleBuyCredits = async (packageId: string) => {
    setLoading(packageId)
    try {
      const response = await api.post<CreditPurchaseResponse>('/api/credits/purchase-credits', {
        package_id: packageId,
      })
      
      toast.success(`Successfully purchased credits! ${response.credits_added} credits added.`)
      
      // In a real app, you would update the user's credit balance here
      
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to purchase credits'
      toast.error(errorMessage)
    } finally {
      setLoading(null)
    }
  }
  
  const handleBuyTokens = async (packageId: string) => {
    setLoading(packageId)
    try {
      const response = await api.post<CreditPurchaseResponse>('/api/credits/purchase-tokens', {
        package_id: packageId,
      })
      
      toast.success(`Successfully purchased tokens! ${response.credits_added.toLocaleString()} tokens added.`)
      
      // In a real app, you would update the user's token balance here
      
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to purchase tokens'
      toast.error(errorMessage)
    } finally {
      setLoading(null)
    }
  }

  const fetchTransactions = useCallback(async () => {
    setTransactionsLoading(true)
    setTransactionsError(null)
    try {
      const response = await api.get<Transaction[]>('/api/credits/transactions', {
        params: {
          page: 1,
          limit: 10
        }
      })
      setTransactions(response)
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load transaction history'
      setTransactionsError(errorMessage)
      console.error('Failed to fetch transactions:', error)
    } finally {
      setTransactionsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTransactions()
  }, [fetchTransactions])

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader />
      
      <main className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between space-y-2">
          <h2 className="text-3xl font-bold tracking-tight">Credits & Tokens</h2>
          <Link href="/credits/history">
            <Button variant="outline" size="sm">
              <History className="h-4 w-4 mr-2" />
              View History
            </Button>
          </Link>
        </div>
        
        <Tabs defaultValue="credits" className="space-y-4">
          <TabsList>
            <TabsTrigger value="credits">Interview Credits</TabsTrigger>
            <TabsTrigger value="tokens">Chat Tokens</TabsTrigger>
          </TabsList>
          
          <TabsContent value="credits">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {interviewCredits.map((pkg) => (
                <Card key={pkg.id} className={cn(
                  "flex flex-col",
                  pkg.id === 'professional' && "border-primary"
                )}>
                  <CardHeader>
                    <CardTitle>{pkg.name}</CardTitle>
                    <CardDescription>{pkg.description}</CardDescription>
                    {pkg.id === 'professional' && (
                      <div className="absolute top-6 right-6">
                        <Badge variant="default" className="bg-gradient-to-r from-green-400 to-blue-500">
                          Most Popular
                        </Badge>
                      </div>
                    )}
                  </CardHeader>
                  <CardContent className="flex-1">
                    <div className="text-4xl font-bold mb-6">
                      ${pkg.price.toFixed(2)}
                    </div>
                    <ul className="space-y-2">
                      <li className="flex items-start gap-2">
                        <Check className="h-5 w-5 text-green-500 mt-0.5" />
                        <span>{pkg.credits} interview credits</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="h-5 w-5 text-green-500 mt-0.5" />
                        <span>Valid for {pkg.validity_days} days</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="h-5 w-5 text-green-500 mt-0.5" />
                        <span>Full audio processing & enhancement</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="h-5 w-5 text-green-500 mt-0.5" />
                        <span>High-quality transcription</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="h-5 w-5 text-green-500 mt-0.5" />
                        <span>50K chat tokens per interview</span>
                      </li>
                    </ul>
                  </CardContent>
                  <CardFooter>
                    <Button 
                      className="w-full" 
                      onClick={() => handleBuyCredits(pkg.id)}
                      disabled={loading !== null}
                      variant={pkg.id === 'professional' ? "default" : "outline"}
                    >
                      {loading === pkg.id ? (
                        <ChevronsUpDown className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Zap className="h-4 w-4 mr-2" />
                      )}
                      Buy Now
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
            
            <div className="mt-8">
              <h3 className="text-lg font-semibold mb-2">About Interview Credits</h3>
              <div className="grid md:grid-cols-3 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">What are interview credits?</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Each interview credit allows you to process one interview, including audio enhancement, 
                      transcription, and AI-powered analysis.
                    </p>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">How long do credits last?</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Credits are valid for the duration specified in your package (typically 12-18 months) 
                      and don't expire until that time.
                    </p>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">What's included?</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Each credit includes full audio processing, transcription, and a base allocation of 
                      50K chat tokens for interactive analysis.
                    </p>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="tokens">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {tokenPackages.map((pkg) => (
                <Card key={pkg.id}>
                  <CardHeader>
                    <CardTitle>{pkg.name}</CardTitle>
                    <CardDescription>{pkg.description}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex-1">
                    <div className="text-4xl font-bold mb-6">
                      ${pkg.price.toFixed(2)}
                    </div>
                    <ul className="space-y-2">
                      <li className="flex items-start gap-2">
                        <Check className="h-5 w-5 text-green-500 mt-0.5" />
                        <span>{(pkg.tokens/1000).toFixed(0)}K chat tokens</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="h-5 w-5 text-green-500 mt-0.5" />
                        <span>No expiration</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="h-5 w-5 text-green-500 mt-0.5" />
                        <span>Use across all your interviews</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <Check className="h-5 w-5 text-green-500 mt-0.5" />
                        <span>${(pkg.price/(pkg.tokens/1000)).toFixed(2)} per 1K tokens</span>
                      </li>
                    </ul>
                  </CardContent>
                  <CardFooter>
                    <Button 
                      className="w-full" 
                      onClick={() => handleBuyTokens(pkg.id)}
                      disabled={loading !== null}
                      variant={pkg.id === 'medium' ? "default" : "outline"}
                    >
                      {loading === pkg.id ? (
                        <ChevronsUpDown className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Sparkles className="h-4 w-4 mr-2" />
                      )}
                      Buy Tokens
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
            
            <div className="mt-8">
              <h3 className="text-lg font-semibold mb-2">About Chat Tokens</h3>
              <div className="grid md:grid-cols-3 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">What are chat tokens?</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Chat tokens let you interact with your interview transcripts. They're consumed 
                      when you ask questions or request analysis about your interviews.
                    </p>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">How many do I need?</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      Each interview includes 50K tokens by default. A typical conversation uses 
                      about 1-2K tokens per message exchange.
                    </p>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">When should I buy more?</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      If you need to have extended conversations with your interviews or analyze 
                      multiple aspects of a single interview in depth.
                    </p>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline"
  className?: string
}

function Badge({ variant = "default", className = "", ...props }: BadgeProps): JSX.Element {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        variant === "default" &&
          "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        variant === "secondary" &&
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        variant === "destructive" &&
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        variant === "outline" && "text-foreground",
        className
      )}
      {...props}
    />
  )
}