'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { toast } from 'sonner'
import api from '@/lib/api-client'
import { useAuth } from '@/hooks/use-auth'
import type { AuthResponse } from '@/types/auth'

export default function Auth0CallbackPage() {
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()
  const searchParams = useSearchParams()
  const { login } = useAuth()
  
  useEffect(() => {
    const handleAuth0Callback = async () => {
      try {
        const code = searchParams.get('code')
        
        if (!code) {
          setError('Authorization code not found')
          setIsLoading(false)
          return
        }
        
        // Exchange code for tokens
        const response = await api.post<AuthResponse>('/api/auth/auth0/token', { code })
        
        // Store tokens
        const { access_token, refresh_token } = response
        localStorage.setItem('token', access_token)
        localStorage.setItem('refreshToken', refresh_token)
        
        // Update auth context
        await login()
        
        // Redirect to dashboard
        router.push('/')
        toast.success('Login successful!')
      } catch (error) {
        console.error('Auth0 callback error:', error)
        setError('Authentication failed. Please try again.')
        setIsLoading(false)
      }
    }
    
    handleAuth0Callback()
  }, [searchParams, router, login])
  
  if (error) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Authentication Error</h1>
          <p className="mt-2 text-muted-foreground">{error}</p>
          <button
            className="mt-4 rounded-md bg-primary px-4 py-2 text-primary-foreground"
            onClick={() => router.push('/auth/login')}
          >
            Back to Login
          </button>
        </div>
      </div>
    )
  }
  
  return (
    <div className="flex h-screen w-full flex-col items-center justify-center">
      <div className="text-center">
        <h1 className="text-2xl font-bold">Authenticating...</h1>
        <p className="mt-2 text-muted-foreground">Please wait while we complete your login.</p>
        <div className="mt-4 h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
      </div>
    </div>
  )
} 