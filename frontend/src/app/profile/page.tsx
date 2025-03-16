'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'
import { UserRole } from '@/types/auth'
import { useAuth } from '@/hooks/use-auth'
import { getInitials, generateColorFromString } from '@/lib/utils'
import { formatDate } from '@/lib/format'
import api from '@/lib/api-client'

type Transaction = {
  id: string
  transaction_type: string
  amount: number
  price?: number
  reference?: string
  created_at: string
}

export default function ProfilePage() {
  const { user } = useAuth()
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchTransactions = async () => {
      try {
        setIsLoading(true)
        const data = await api.get<Transaction[]>('/api/credits/transactions?limit=5')
        setTransactions(data)
      } catch (error) {
        console.error('Failed to fetch transactions:', error)
        toast.error('Failed to load recent transactions')
      } finally {
        setIsLoading(false)
      }
    }

    fetchTransactions()
  }, [])

  if (!user) {
    return (
      <div className="flex min-h-screen flex-col">
        <DashboardHeader />
        <main className="flex-1 space-y-4 p-8 pt-6">
          <div className="flex justify-center p-8">
            <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full"></div>
          </div>
        </main>
      </div>
    )
  }

  const formatTransactionType = (type: string) => {
    switch (type) {
      case 'interview_credit_purchase': return 'Interview Credit Purchase'
      case 'chat_token_purchase': return 'Chat Token Purchase'
      case 'interview_credit_usage': return 'Interview Credit Usage'
      case 'chat_token_usage': return 'Chat Token Usage'
      default: return type
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader />
      
      <main className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between">
          <h2 className="text-3xl font-bold tracking-tight">Your Profile</h2>
          <Button asChild variant="outline">
            <Link href="/profile/settings">
              Edit Profile
            </Link>
          </Button>
        </div>
        
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="transactions">Transactions</TabsTrigger>
          </TabsList>
          
          <TabsContent value="overview" className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <Card className="col-span-2">
                <CardHeader>
                  <CardTitle>Profile Information</CardTitle>
                  <CardDescription>
                    Your account details and preferences
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <Avatar className="h-16 w-16">
                      <AvatarImage src="" alt={user.full_name || user.email} />
                      <AvatarFallback 
                        style={{ backgroundColor: generateColorFromString(user.full_name || user.email) }}
                        className="text-lg"
                      >
                        {getInitials(user.full_name || user.email)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="space-y-1">
                      <h3 className="text-xl font-semibold">{user.full_name || 'User'}</h3>
                      <p className="text-sm text-muted-foreground">{user.email}</p>
                    </div>
                  </div>
                  
                  <Separator />
                  
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <Label className="text-muted-foreground">Account Type</Label>
                      <p className="font-medium">{user.role === UserRole.ADMIN ? 'Administrator' : 'Standard User'}</p>
                    </div>
                    <div>
                      <Label className="text-muted-foreground">Member Since</Label>
                      <p className="font-medium">{formatDate(user.created_at)}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              <Card>
                <CardHeader>
                  <CardTitle>Credit Balance</CardTitle>
                  <CardDescription>
                    Your current credits and tokens
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label className="text-muted-foreground">Interview Credits</Label>
                    <p className="text-2xl font-bold">{user.available_interview_credits}</p>
                  </div>
                  
                  <Separator />
                  
                  <div>
                    <Label className="text-muted-foreground">Chat Tokens</Label>
                    <p className="text-2xl font-bold">{user.available_chat_tokens.toLocaleString()}</p>
                  </div>
                  
                  <Button asChild className="w-full mt-4">
                    <Link href="/credits">
                      Purchase Credits
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
          
          <TabsContent value="transactions">
            <Card>
              <CardHeader>
                <CardTitle>Recent Transactions</CardTitle>
                <CardDescription>
                  Your recent credit and token activity
                </CardDescription>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="flex justify-center py-8">
                    <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full"></div>
                  </div>
                ) : transactions.length === 0 ? (
                  <div className="text-center py-8">
                    <p className="text-muted-foreground">No transactions found</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {transactions.map((transaction) => (
                      <div key={transaction.id} className="flex items-center justify-between border-b pb-4">
                        <div>
                          <p className="font-medium">{formatTransactionType(transaction.transaction_type)}</p>
                          <p className="text-sm text-muted-foreground">{formatDate(transaction.created_at)}</p>
                        </div>
                        <div className="text-right">
                          <p className={`font-medium ${transaction.transaction_type.includes('usage') ? 'text-red-500' : 'text-green-500'}`}>
                            {transaction.transaction_type.includes('usage') ? '-' : '+'}{transaction.amount.toLocaleString()}
                          </p>
                          {transaction.price && (
                            <p className="text-sm text-muted-foreground">${transaction.price.toFixed(2)}</p>
                          )}
                        </div>
                      </div>
                    ))}
                    
                    <div className="text-center pt-4">
                      <Button asChild variant="outline">
                        <Link href="/credits/history">
                          View All Transactions
                        </Link>
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}