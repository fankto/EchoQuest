import { useState, useCallback, useEffect } from 'react'
import { toast } from 'sonner'
import { useAuth } from './use-auth'
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

type PurchaseResponse = {
  success: boolean
  message: string
  credits_added: number
  total_credits: number
  transaction_id: string
}

export function useCredits() {
  const [interviewCredits, setInterviewCredits] = useState<CreditPackage[]>([])
  const [tokenPackages, setTokenPackages] = useState<TokenPackage[]>([])
  const [isLoadingPackages, setIsLoadingPackages] = useState(false)
  const [isProcessingPayment, setIsProcessingPayment] = useState(false)
  const { refreshUser } = useAuth()

  // Fetch available packages
  const fetchCreditPackages = useCallback(async () => {
    try {
      setIsLoadingPackages(true)
      const data = await api.get<CreditPackage[]>('/api/credits/interview-packages')
      setInterviewCredits(data)
      return data
    } catch (error) {
      console.error('Failed to fetch credit packages:', error)
      toast.error('Failed to load credit packages')
      return []
    } finally {
      setIsLoadingPackages(false)
    }
  }, [])

  const fetchTokenPackages = useCallback(async () => {
    try {
      setIsLoadingPackages(true)
      const data = await api.get<TokenPackage[]>('/api/credits/token-packages')
      setTokenPackages(data)
      return data
    } catch (error) {
      console.error('Failed to fetch token packages:', error)
      toast.error('Failed to load token packages')
      return []
    } finally {
      setIsLoadingPackages(false)
    }
  }, [])

  // Purchase credits
  const purchaseCredits = useCallback(async (packageId: string) => {
    try {
      setIsProcessingPayment(true)
      const response = await api.post<PurchaseResponse>('/api/credits/purchase-credits', {
        package_id: packageId,
      })
      
      // Refresh user data to get updated credit balance
      await refreshUser()
      
      toast.success(response.message || 'Credits purchased successfully')
      return response
    } catch (error: any) {
      toast.error(error.message || 'Failed to purchase credits')
      throw error
    } finally {
      setIsProcessingPayment(false)
    }
  }, [refreshUser])

  // Purchase tokens
  const purchaseTokens = useCallback(async (packageId: string) => {
    try {
      setIsProcessingPayment(true)
      const response = await api.post<PurchaseResponse>('/api/credits/purchase-tokens', {
        package_id: packageId,
      })
      
      // Refresh user data to get updated token balance
      await refreshUser()
      
      toast.success(response.message || 'Tokens purchased successfully')
      return response
    } catch (error: any) {
      toast.error(error.message || 'Failed to purchase tokens')
      throw error
    } finally {
      setIsProcessingPayment(false)
    }
  }, [refreshUser])

  // Fetch transaction history
  const fetchTransactionHistory = useCallback(async () => {
    try {
      const data = await api.get('/api/credits/transactions')
      return data
    } catch (error) {
      console.error('Failed to fetch transaction history:', error)
      toast.error('Failed to load transaction history')
      return []
    }
  }, [])

  // Fetch credit usage
  const fetchCreditUsage = useCallback(async () => {
    try {
      const data = await api.get('/api/credits/usage')
      return data
    } catch (error) {
      console.error('Failed to fetch credit usage:', error)
      toast.error('Failed to load credit usage data')
      return null
    }
  }, [])

  // Load packages on init
  useEffect(() => {
    fetchCreditPackages()
    fetchTokenPackages()
  }, [fetchCreditPackages, fetchTokenPackages])

  return {
    interviewCredits,
    tokenPackages,
    isLoadingPackages,
    isProcessingPayment,
    fetchCreditPackages,
    fetchTokenPackages,
    purchaseCredits,
    purchaseTokens,
    fetchTransactionHistory,
    fetchCreditUsage
  }
}