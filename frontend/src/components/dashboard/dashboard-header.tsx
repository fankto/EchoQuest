'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { useTheme } from 'next-themes'
import { useAuth } from '@/hooks/use-auth'
import { Icons } from '@/components/ui/icons'
import { getInitials, generateColorFromString } from '@/lib/utils'

const navigationItems = [
  {
    title: 'Dashboard',
    href: '/',
    icon: <Icons.chart className="mr-2 h-4 w-4" />,
  },
  {
    title: 'Interviews',
    href: '/interviews',
    icon: <Icons.fileAudio className="mr-2 h-4 w-4" />,
  },
  {
    title: 'Questionnaires',
    href: '/questionnaires',
    icon: <Icons.fileText className="mr-2 h-4 w-4" />,
  },
  {
    title: 'Credits',
    href: '/credits',
    icon: <Icons.zap className="mr-2 h-4 w-4" />,
  },
]

export function DashboardHeader() {
  const [isMounted, setIsMounted] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const { user, logout } = useAuth()
  const { setTheme, theme } = useTheme()
  const pathname = usePathname()

  // Fix hydration issues with theme provider
  useEffect(() => {
    setIsMounted(true)
  }, [])

  if (!isMounted) {
    return (
      <header className="sticky top-0 z-40 w-full border-b bg-background">
        <div className="container flex h-16 items-center justify-between py-4">
          <div className="flex items-center gap-2">
            <Icons.logo className="h-6 w-6" />
            <span className="text-xl font-bold">EchoQuest</span>
          </div>
        </div>
      </header>
    )
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background">
      <div className="container flex h-16 items-center justify-between py-4">
        <div className="flex items-center gap-6">
          <Link 
            href="/" 
            className="flex items-center gap-2 font-semibold"
          >
            <Icons.logo className="h-6 w-6" />
            <span className="hidden md:inline-block text-xl font-bold">EchoQuest</span>
          </Link>
          
          <nav className="hidden md:flex items-center gap-6">
            {navigationItems.map((item, index) => (
              <Link
                key={index}
                href={item.href}
                className={`text-sm font-medium flex items-center transition-colors hover:text-primary ${
                  pathname === item.href ? 'text-primary' : 'text-muted-foreground'
                }`}
              >
                {item.icon}
                {item.title}
              </Link>
            ))}
          </nav>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Mobile Navigation */}
          <Sheet open={isOpen} onOpenChange={setIsOpen}>
            <SheetTrigger asChild>
              <Button 
                variant="ghost" 
                size="icon"
                className="md:hidden"
              >
                <Icons.menu className="h-6 w-6" />
                <span className="sr-only">Toggle Menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="pr-0">
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2">
                  <Icons.logo className="h-5 w-5" />
                  EchoQuest
                </SheetTitle>
              </SheetHeader>
              <nav className="flex flex-col gap-4 mt-8">
                {navigationItems.map((item, index) => (
                  <Link
                    key={index}
                    href={item.href}
                    className={`text-sm font-medium p-2 flex items-center rounded-md transition-colors hover:bg-muted ${
                      pathname === item.href ? 'bg-muted' : ''
                    }`}
                    onClick={() => setIsOpen(false)}
                  >
                    {item.icon}
                    {item.title}
                  </Link>
                ))}
              </nav>
            </SheetContent>
          </Sheet>
          
          {/* Theme Toggle */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                {theme === 'light' ? (
                  <Icons.sun className="h-5 w-5" />
                ) : theme === 'dark' ? (
                  <Icons.moon className="h-5 w-5" />
                ) : (
                  <Icons.laptop className="h-5 w-5" />
                )}
                <span className="sr-only">Toggle theme</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setTheme('light')}>
                <Icons.sun className="mr-2 h-4 w-4" />
                <span>Light</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('dark')}>
                <Icons.moon className="mr-2 h-4 w-4" />
                <span>Dark</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('system')}>
                <Icons.laptop className="mr-2 h-4 w-4" />
                <span>System</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          
          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="relative h-8 w-8 rounded-full">
                <Avatar className="h-8 w-8">
                  <AvatarImage src="" alt="User Avatar" />
                  <AvatarFallback 
                    style={{ backgroundColor: generateColorFromString(user?.full_name || user?.email || '') }}
                  >
                    {getInitials(user?.full_name || user?.email || 'U')}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="end" forceMount>
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium leading-none">{user?.full_name || 'User'}</p>
                  <p className="text-xs leading-none text-muted-foreground">
                    {user?.email || ''}
                  </p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link href="/profile">
                  <Icons.user className="mr-2 h-4 w-4" />
                  <span>Profile</span>
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href="/credits">
                  <Icons.zap className="mr-2 h-4 w-4" />
                  <span>Credits</span>
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href="/profile/settings">
                  <Icons.settings className="mr-2 h-4 w-4" />
                  <span>Settings</span>
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={logout}>
                <Icons.logout className="mr-2 h-4 w-4" />
                <span>Log out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}

function Sheet({
  children,
  open,
  onOpenChange,
}: {
  children: React.ReactNode,
  open?: boolean,
  onOpenChange?: (open: boolean) => void,
}) {
  return (
    <div>
      {children}
    </div>
  );
}

function SheetTrigger({ asChild, children }: { asChild?: boolean, children: React.ReactNode }) {
  return <>{children}</>;
}

function SheetContent({ side, children, className }: { side: string, children: React.ReactNode, className?: string }) {
  return <div className={`fixed inset-y-0 left-0 z-50 w-64 border-r bg-background p-6 ${className}`}>{children}</div>;
}

function SheetHeader({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>;
}

function SheetTitle({ className, children }: { className?: string, children: React.ReactNode }) {
  return <h2 className={`text-lg font-semibold ${className}`}>{children}</h2>;
}