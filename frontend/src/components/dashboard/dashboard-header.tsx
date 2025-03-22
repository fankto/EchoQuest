'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { useAuth } from '@/hooks/use-auth'

export function DashboardHeader() {
  const pathname = usePathname()
  const { user, logout } = useAuth()

  return (
    <header className="sticky top-0 z-40 border-b bg-background">
      <div className="container flex h-16 items-center justify-between py-4">
        <div className="flex items-center gap-2">
          <Link href="/" className="flex items-center gap-2">
            <Icons.logo className="h-6 w-6" />
            <span className="font-bold">EchoQuest</span>
          </Link>
          <nav className="hidden md:flex items-center gap-6 text-sm">
            <Link
              href="/"
              className={`transition-colors hover:text-foreground/80 ${
                pathname === '/' ? 'text-foreground font-medium' : 'text-foreground/60'
              }`}
            >
              Dashboard
            </Link>
            <Link
              href="/interviews"
              className={`transition-colors hover:text-foreground/80 ${
                pathname.startsWith('/interviews') ? 'text-foreground font-medium' : 'text-foreground/60'
              }`}
            >
              Interviews
            </Link>
            <Link
              href="/questionnaires"
              className={`transition-colors hover:text-foreground/80 ${
                pathname.startsWith('/questionnaires') ? 'text-foreground font-medium' : 'text-foreground/60'
              }`}
            >
              Questionnaires
            </Link>
            <Link
              href="/credits"
              className={`transition-colors hover:text-foreground/80 ${
                pathname.startsWith('/credits') ? 'text-foreground font-medium' : 'text-foreground/60'
              }`}
            >
              Credits
            </Link>
          </nav>
        </div>
        <div className="flex items-center gap-2">
          {user ? (
            <>
              <Link href="/profile">
                <Button variant="ghost" size="sm" className="hidden md:flex">
                  <Icons.user className="mr-2 h-4 w-4" />
                  {user.full_name || user.email}
                </Button>
              </Link>
              <Button variant="ghost" size="sm" onClick={logout}>
                <Icons.close className="h-4 w-4" />
                <span className="hidden md:inline ml-2">Logout</span>
              </Button>
            </>
          ) : (
            <Link href="/auth/login">
              <Button variant="default" size="sm">
                Login
              </Button>
            </Link>
          )}
        </div>
      </div>
    </header>
  )
}