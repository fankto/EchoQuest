import { useEffect, useState, useCallback, createContext, useContext } from 'react'
import { useRouter } from 'next/navigation'
import api from '@/lib/api-client'
import { User } from '@/types/auth'

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: () => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  login: async () => {},
  logout: () => {},
  refreshUser: async () => {},
})

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const router = useRouter()

  const fetchUser = useCallback(async () => {
    try {
      setIsLoading(true)
      const userData = await api.get<User>('/api/auth/me')
      setUser(userData)
      return userData
    } catch (error) {
      setUser(null)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [])

  const login = useCallback(async () => {
    await fetchUser()
  }, [fetchUser])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    setUser(null)
    router.push('/auth/login')
  }, [router])

  const refreshUser = useCallback(async () => {
    return await fetchUser()
  }, [fetchUser])

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      fetchUser()
    } else {
      setIsLoading(false)
    }
  }, [fetchUser])

  const value = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    logout,
    refreshUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}