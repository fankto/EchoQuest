"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface SliderProps {
  className?: string
  value?: number[]
  defaultValue?: number[]
  min?: number
  max?: number
  step?: number
  onValueChange?: (value: number[]) => void
  disabled?: boolean
}

const Slider = React.forwardRef<HTMLDivElement, SliderProps>(
  ({ 
    className, 
    value, 
    defaultValue = [0], 
    min = 0, 
    max = 100, 
    step = 1, 
    onValueChange, 
    disabled = false,
    ...props 
  }, ref) => {
    const [internalValue, setInternalValue] = React.useState<number[]>(value || defaultValue)
    const trackRef = React.useRef<HTMLDivElement>(null)
    const thumbRef = React.useRef<HTMLDivElement>(null)
    const isDragging = React.useRef(false)

    // Update internal value when external value changes
    React.useEffect(() => {
      if (value !== undefined) {
        setInternalValue(value)
      }
    }, [value])

    // Calculate percentage for styling
    const percentage = 
      internalValue[0] !== undefined 
        ? ((internalValue[0] - min) / (max - min)) * 100 
        : 0

    // Handle mouse and touch interactions
    const handleInteractionStart = React.useCallback(
      (clientX: number) => {
        if (disabled) return
        isDragging.current = true
        const trackRect = trackRef.current?.getBoundingClientRect()
        if (!trackRect) return

        const position = clientX - trackRect.left
        const percentage = Math.max(0, Math.min(1, position / trackRect.width))
        const newValue = Math.round((min + percentage * (max - min)) / step) * step
        
        const clampedValue = Math.max(min, Math.min(max, newValue))
        setInternalValue([clampedValue])
        onValueChange?.([clampedValue])
      },
      [min, max, step, onValueChange, disabled]
    )

    const handleMouseDown = React.useCallback(
      (e: React.MouseEvent) => {
        handleInteractionStart(e.clientX)
      },
      [handleInteractionStart]
    )

    const handleTouchStart = React.useCallback(
      (e: React.TouchEvent) => {
        e.preventDefault()
        handleInteractionStart(e.touches[0].clientX)
      },
      [handleInteractionStart]
    )

    const handleInteractionMove = React.useCallback(
      (clientX: number) => {
        if (!isDragging.current || disabled) return
        const trackRect = trackRef.current?.getBoundingClientRect()
        if (!trackRect) return

        const position = clientX - trackRect.left
        const percentage = Math.max(0, Math.min(1, position / trackRect.width))
        const newValue = Math.round((min + percentage * (max - min)) / step) * step
        
        const clampedValue = Math.max(min, Math.min(max, newValue))
        setInternalValue([clampedValue])
        onValueChange?.([clampedValue])
      },
      [min, max, step, onValueChange, disabled]
    )

    const handleMouseMove = React.useCallback(
      (e: MouseEvent) => {
        handleInteractionMove(e.clientX)
      },
      [handleInteractionMove]
    )

    const handleTouchMove = React.useCallback(
      (e: TouchEvent) => {
        handleInteractionMove(e.touches[0].clientX)
      },
      [handleInteractionMove]
    )

    const handleInteractionEnd = React.useCallback(() => {
      isDragging.current = false
    }, [])

    // Add and remove event listeners
    React.useEffect(() => {
      const handleMouseUp = () => handleInteractionEnd()
      const handleTouchEnd = () => handleInteractionEnd()

      document.addEventListener("mousemove", handleMouseMove)
      document.addEventListener("mouseup", handleMouseUp)
      document.addEventListener("touchmove", handleTouchMove, { passive: false })
      document.addEventListener("touchend", handleTouchEnd)

      return () => {
        document.removeEventListener("mousemove", handleMouseMove)
        document.removeEventListener("mouseup", handleMouseUp)
        document.removeEventListener("touchmove", handleTouchMove)
        document.removeEventListener("touchend", handleTouchEnd)
      }
    }, [handleMouseMove, handleTouchMove, handleInteractionEnd])

    return (
      <div
        ref={ref}
        className={cn(
          "relative flex w-full touch-none select-none items-center",
          disabled && "opacity-50 pointer-events-none",
          className
        )}
      >
        <div
          ref={trackRef}
          className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-secondary"
          onMouseDown={handleMouseDown}
          onTouchStart={handleTouchStart}
        >
          <div
            className="absolute h-full bg-primary"
            style={{ width: `${percentage}%` }}
          />
        </div>
        <div
          ref={thumbRef}
          className="absolute block h-4 w-4 rounded-full border border-primary/50 bg-background shadow transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          style={{ left: `calc(${percentage}% - 0.5rem)` }}
        />
      </div>
    )
  }
)

Slider.displayName = "Slider"

export { Slider } 