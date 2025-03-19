'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { 
  Pagination, 
  PaginationContent, 
  PaginationItem, 
  PaginationLink, 
  PaginationNext, 
  PaginationPrevious 
} from '@/components/ui/pagination'
import { Loader2, ChevronLeft, ArrowUp, ArrowDown, ChevronsUpDown, HelpCircle } from 'lucide-react'
import { toast } from 'sonner'
import { formatDate } from '@/lib/format'
import api from '@/lib/api-client'

type Transaction = {
  id: string
  transaction_type: string
  amount: number
  price: number | null
  reference: string | null
  created_at: string
  interview_id: string | null
}

type TransactionType = 'all' | 'interview_credit_purchase' | 'chat_token_purchase' | 'interview_credit_usage' | 'chat_token_usage'

export default function TransactionHistoryPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(true)
  const [transactionType, setTransactionType] = useState<TransactionType>('all')
  const [dateRange, setDateRange] = useState<'all' | 'week' | 'month' | 'year'>('all')

  const fetchTransactions = useCallback(async (resetPage = false) => {
    if (resetPage) {
      setPage(1)
      setTransactions([])
    }
    
    if (!hasMore && !resetPage) return
    
    setLoading(true)
    setError(null)
    
    try {
      const response = await api.get<Transaction[]>('/api/credits/transactions', {
        params: {
          page,
          limit: 10,
          transaction_type: transactionType === 'all' ? undefined : transactionType,
          date_range: dateRange === 'all' ? undefined : dateRange,
        }
      })
      
      setTransactions(prev => resetPage ? response : [...prev, ...response])
      setHasMore(response.length === 10)
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load transaction history'
      setError(errorMessage)
      console.error('Failed to fetch transactions:', error)
    } finally {
      setLoading(false)
    }
  }, [page, transactionType, dateRange, hasMore])

  useEffect(() => {
    fetchTransactions(true)
  }, [fetchTransactions])

  const handleLoadMore = () => {
    setPage(prev => prev + 1)
  }

  const handleFilterChange = (type: TransactionType) => {
    setTransactionType(type)
    setHasMore(true)
  }

  const handleDateRangeChange = (range: 'all' | 'week' | 'month' | 'year') => {
    setDateRange(range)
    setHasMore(true)
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

  const isExpense = (type: string) => {
    return type.includes('usage')
  }

  const getPaginationItems = () => {
    const items = []
    const maxItems = 5
    
    let startPage = Math.max(1, page - Math.floor(maxItems / 2))
    const endPage = Math.min(totalPages, startPage + maxItems - 1)
    
    if (endPage - startPage + 1 < maxItems) {
      startPage = Math.max(1, endPage - maxItems + 1)
    }
    
    for (let i = startPage; i <= endPage; i++) {
      items.push(
        <PaginationItem key={i}>
          <PaginationLink
            isActive={page === i}
            onClick={() => setPage(i)}
          >
            {i}
          </PaginationLink>
        </PaginationItem>
      )
    }
    
    return items
  }

  function Pagination({ children }: { children: React.ReactNode }) {
    return <div className="flex items-center justify-center space-x-6 lg:space-x-8">{children}</div>;
  }

  function PaginationContent({ children }: { children: React.ReactNode }) {
    return <div className="flex items-center space-x-2">{children}</div>;
  }

  function PaginationItem({ children }: { children: React.ReactNode }) {
    return <div>{children}</div>;
  }

  function PaginationLink({ children, isActive, onClick }: { children: React.ReactNode, isActive?: boolean, onClick?: () => void }) {
    return (
      <button
        className={`h-9 w-9 rounded-md flex items-center justify-center text-sm ${
          isActive 
            ? "bg-primary text-primary-foreground"
            : "hover:bg-muted hover:text-foreground"
        }`}
        onClick={onClick}
      >
        {children}
      </button>
    );
  }

  function PaginationPrevious({ onClick }: { onClick?: () => void }) {
    return (
      <button
        className="h-9 px-2 rounded-md border border-input hover:bg-muted hover:text-foreground flex items-center gap-1 text-sm"
        onClick={onClick}
        disabled={page <= 1}
      >
        <ChevronLeft className="h-4 w-4" />
        Previous
      </button>
    );
  }

  function PaginationNext({ onClick }: { onClick?: () => void }) {
    return (
      <button
        className="h-9 px-2 rounded-md border border-input hover:bg-muted hover:text-foreground flex items-center gap-1 text-sm"
        onClick={onClick}
        disabled={page >= totalPages}
      >
        Next
        <ChevronLeft className="h-4 w-4 rotate-180" />
      </button>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader />
      
      <main className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between">
          <div>
            <Button variant="outline" size="sm" asChild className="mb-4">
              <Link href="/credits">
                <ChevronLeft className="mr-1 h-4 w-4" />
                Back to Credits
              </Link>
            </Button>
            <h2 className="text-3xl font-bold tracking-tight">Transaction History</h2>
            <p className="text-muted-foreground">
              Complete record of your credit and token transactions
            </p>
          </div>
        </div>
        
        <div className="flex gap-4">
          <Select value={transactionType} onValueChange={handleFilterChange}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Transaction Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Transactions</SelectItem>
              <SelectItem value="interview_credit_purchase">Credit Purchases</SelectItem>
              <SelectItem value="chat_token_purchase">Token Purchases</SelectItem>
              <SelectItem value="interview_credit_usage">Credit Usage</SelectItem>
              <SelectItem value="chat_token_usage">Token Usage</SelectItem>
            </SelectContent>
          </Select>

          <Select value={dateRange} onValueChange={handleDateRangeChange}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Date Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Time</SelectItem>
              <SelectItem value="week">Last Week</SelectItem>
              <SelectItem value="month">Last Month</SelectItem>
              <SelectItem value="year">Last Year</SelectItem>
            </SelectContent>
          </Select>

          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchTransactions(true)}
            disabled={loading}
          >
            {loading ? (
              <ChevronsUpDown className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <HelpCircle className="h-4 w-4 mr-2" />
            )}
            Refresh
          </Button>
        </div>

        {error ? (
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-destructive">{error}</p>
            </CardContent>
          </Card>
        ) : transactions.length > 0 ? (
          <Card>
            <CardContent className="p-4">
              <div className="space-y-4">
                {transactions.map((transaction) => (
                  <div key={transaction.id} className="flex items-center justify-between py-2 border-b last:border-0">
                    <div>
                      <p className="font-medium">
                        {transaction.transaction_type === 'interview_credit_purchase' ? 'Interview Credits Purchase' :
                         transaction.transaction_type === 'chat_token_purchase' ? 'Chat Tokens Purchase' :
                         transaction.transaction_type === 'interview_credit_usage' ? 'Interview Credits Usage' :
                         'Chat Tokens Usage'}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {new Date(transaction.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">
                        {transaction.transaction_type.includes('credit') ? 
                          `${transaction.amount} credits` : 
                          `${transaction.amount.toLocaleString()} tokens`}
                      </p>
                      {transaction.price && (
                        <p className="text-sm text-muted-foreground">
                          ${transaction.price.toFixed(2)}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {hasMore && (
                <div className="mt-4 text-center">
                  <Button
                    variant="outline"
                    onClick={handleLoadMore}
                    disabled={loading}
                  >
                    {loading ? (
                      <ChevronsUpDown className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      'Load More'
                    )}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">No transactions found</p>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  )
}