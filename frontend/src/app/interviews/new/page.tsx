'use client'

import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { InterviewForm } from '@/components/interview/interview-form'

export default function NewInterviewPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader />
      
      <main className="flex-1 space-y-4 p-8 pt-6">
        <h2 className="text-3xl font-bold tracking-tight">Create New Interview</h2>
        <p className="text-muted-foreground">
          Enter the details of the interview and upload audio files
        </p>
        
        <div className="mt-6">
          <InterviewForm />
        </div>
      </main>
    </div>
  )
}