'use client'

import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { InterviewForm } from '@/components/interview/interview-form'
import { ChevronLeft } from 'lucide-react'

export default function NewInterviewPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader />
      
      <main className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between">
          <div>
            <Button variant="outline" size="sm" asChild className="mb-4">
              <Link href="/interviews">
                <ChevronLeft className="mr-1 h-4 w-4" />
                Back to Interviews
              </Link>
            </Button>
            <h2 className="text-3xl font-bold tracking-tight">Create Interview</h2>
            <p className="text-muted-foreground">
              Create a new interview and upload audio for transcription
            </p>
          </div>
        </div>
        
        <InterviewForm />
      </main>
    </div>
  )
}