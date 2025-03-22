'use client'

import { useState, useEffect } from 'react'
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
import { Loader2, ChevronLeft, ArrowUp, ArrowDown } from 'lucide-react'
import { toast } from 'sonner'
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

export default function TransactionHistoryPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [filter, setFilter] = useState<string | null>(null)

  useEffect(() => {
    const fetchTransactions = async () => {
      try {
        setIsLoading(true)
        
        let url = `/api/credits/transactions?page=${page}&limit=10`
        if (filter) {
          url += `&type=${filter}`
        }
        
        const response = await api.get(url)
        setTransactions(response.items || [])
        setTotalPages(response.pages || 1)
      } catch (error) {
        console.error('Failed to fetch transactions:', error)
        toast.error('Failed to load transaction history')
      } finally {
        setIsLoading(false)
      }
    }

    fetchTransactions()
  }, [page, filter])

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
        
        <Card>
          <CardHeader className="space-y-0 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle>All Transactions</CardTitle>
              <Select 
                onValueChange={(value) => setFilter(value === 'all' ? null : value)}
                defaultValue="all"
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="All transactions" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All transactions</SelectItem>
                  <SelectItem value="interview_credit_purchase">Credit Purchases</SelectItem>
                  <SelectItem value="chat_token_purchase">Token Purchases</SelectItem>
                  <SelectItem value="interview_credit_usage">Credit Usage</SelectItem>
                  <SelectItem value="chat_token_usage">Token Usage</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <CardDescription>
              {filter ? `Showing ${formatTransactionType(filter).toLowerCase()}` : 'Showing all transaction types'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : transactions.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-muted-foreground">No transactions found</p>
              </div>
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Transaction Type</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead className="text-right">Price</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {transactions.map((transaction) => (
                      <TableRow key={transaction.id}>
                        <TableCell className="font-medium">
                          {formatTransactionType(transaction.transaction_type)}
                        </TableCell>
                        <TableCell>{formatDate(transaction.created_at)}</TableCell>
                        <TableCell>
                          <div className="flex items-center">
                            {isExpense(transaction.transaction_type) ? (
                              <ArrowDown className="mr-1 h-4 w-4 text-red-500" />
                            ) : (
                              <ArrowUp className="mr-1 h-4 w-4 text-green-500" />
                            )}
                            <span className={isExpense(transaction.transaction_type) ? 'text-red-500' : 'text-green-500'}>
                              {isExpense(transaction.transaction_type) ? '-' : '+'}{transaction.amount.toLocaleString()}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          {transaction.price 
                            ? `$${transaction.price.toFixed(2)}` 
                            : '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                
                {totalPages > 1 && (
                  <div className="mt-6">
                    <Pagination>
                      <PaginationContent>
                        <PaginationPrevious onClick={() => setPage(Math.max(1, page - 1))} />
                        {getPaginationItems()}
                        <PaginationNext onClick={() => setPage(Math.min(totalPages, page + 1))} />
                      </PaginationContent>
                    </Pagination>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}