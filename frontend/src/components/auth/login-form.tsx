'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'
import { Icons } from '@/components/ui/icons'
import api from '@/lib/api-client'
import { useAuth } from '@/hooks/use-auth'
import { Separator } from '@/components/ui/separator'
import type { AuthResponse } from '@/types/auth'

const formSchema = z.object({
  email: z
    .string()
    .min(1, { message: 'Email is required' })
    .email({ message: 'Must be a valid email' }),
  password: z
    .string()
    .min(1, { message: 'Password is required' }),
})

export function LoginForm() {
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()
  const { login } = useAuth()
  
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })

  async function onSubmit(values: z.infer<typeof formSchema>) {
    setIsLoading(true)
    
    try {
      const formData = new FormData()
      formData.append('username', values.email)
      formData.append('password', values.password)
      
      const response = await api.post<AuthResponse>('/api/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
      
      // Store tokens
      const { access_token, refresh_token } = response
      localStorage.setItem('token', access_token)
      localStorage.setItem('refreshToken', refresh_token)
      
      // Update auth context
      await login()
      
      // Redirect to dashboard
      router.push('/')
      toast.success('Login successful!')
    } catch (error: unknown) {
      console.error(error)
      const errorMessage = error instanceof Error ? error.message : 'Login failed. Please try again.'
      toast.error(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  const handleAuth0Login = () => {
    const auth0Domain = process.env.NEXT_PUBLIC_AUTH0_DOMAIN
    const auth0ClientId = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID
    const redirectUri = process.env.NEXT_PUBLIC_AUTH0_CALLBACK_URL
    const audience = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE
    
    if (!auth0Domain || !auth0ClientId || !redirectUri) {
      toast.error('Auth0 configuration is missing')
      return
    }
    
    const auth0Url = 'https://' + auth0Domain + '/authorize?' +
      'response_type=code&' +
      'client_id=' + auth0ClientId + '&' +
      'redirect_uri=' + redirectUri + '&' +
      'scope=openid profile email&' +
      (audience ? 'audience=' + audience : '')
    
    window.location.href = auth0Url
  }

  return (
    <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[350px]">
      <div className="flex flex-col space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Welcome back</h1>
        <p className="text-sm text-muted-foreground">
          Enter your credentials to sign in to your account
        </p>
      </div>
      
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input 
                    placeholder="name@example.com" 
                    type="email" 
                    disabled={isLoading} 
                    {...field} 
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Password</FormLabel>
                <FormControl>
                  <Input 
                    placeholder="••••••••" 
                    type="password" 
                    disabled={isLoading} 
                    {...field} 
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading && <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />}
            Sign In
          </Button>
        </form>
      </Form>
      
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <Separator className="w-full" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">
            Or continue with
          </span>
        </div>
      </div>
      
      <Button 
        variant="outline" 
        type="button" 
        className="w-full"
        onClick={handleAuth0Login}
        disabled={isLoading}
      >
        <svg className="mr-2 h-4 w-4" aria-hidden="true" focusable="false" data-prefix="fab" data-icon="google" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 488 512">
          <path fill="currentColor" d="M488 261.8C488 403.3 391.1 504 248 504 110.8 504 0 393.2 0 256S110.8 8 248 8c66.8 0 123 24.5 166.3 64.9l-67.5 64.9C258.5 52.6 94.3 116.6 94.3 256c0 86.5 69.1 156.6 153.7 156.6 98.2 0 135-70.4 140.8-106.9H248v-85.3h236.1c2.3 12.7 3.9 24.9 3.9 41.4z"></path>
        </svg>
        Google
      </Button>
      
      <div className="text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{" "}
        <Link
          href="/auth/register"
          className="underline underline-offset-4 hover:text-primary"
        >
          Sign up
        </Link>
      </div>
    </div>
  )
}