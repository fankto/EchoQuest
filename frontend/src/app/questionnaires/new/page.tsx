'use client'

import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { QuestionnaireForm } from '@/components/questionnaire/questionnaire-form'
import { ChevronLeft } from 'lucide-react'

export default function NewQuestionnairePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader />
      
      <main className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between">
          <div>
            <Button variant="outline" size="sm" asChild className="mb-4">
              <Link href="/questionnaires">
                <ChevronLeft className="mr-1 h-4 w-4" />
                Back to Questionnaires
              </Link>
            </Button>
            <h2 className="text-3xl font-bold tracking-tight">Create Questionnaire</h2>
            <p className="text-muted-foreground">
              Create a new interview questionnaire template
            </p>
          </div>
        </div>
        
        <div className="mx-auto max-w-3xl">
          <QuestionnaireForm />
        </div>
      </main>
    </div>
  )
}