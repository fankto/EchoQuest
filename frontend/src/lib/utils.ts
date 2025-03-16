import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function truncate(str: string, length: number) {
  if (!str) return ""
  return str.length > length ? `${str.substring(0, length)}...` : str
}

export function formatBytes(bytes: number, decimals = 2) {
  if (bytes === 0) return "0 Bytes"
  
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
  
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i]
}

export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
) {
  let timeoutId: ReturnType<typeof setTimeout> | null = null
  
  return function(this: ThisParameterType<T>, ...args: Parameters<T>) {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    
    timeoutId = setTimeout(() => {
      fn.apply(this, args)
    }, delay)
  }
}

export function getInitials(name: string) {
  if (!name) return "U"
  
  const parts = name.split(" ")
  if (parts.length === 1) return name.substring(0, 2).toUpperCase()
  
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export function generateColorFromString(str: string) {
  if (!str) return "hsl(0, 0%, 75%)"
  
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  
  const h = hash % 360
  return `hsl(${h}, 70%, 75%)`
}

export function isValidDate(dateString: string) {
  const date = new Date(dateString)
  return !isNaN(date.getTime())
}

export function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return String(error)
}