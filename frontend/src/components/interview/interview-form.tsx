'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { format } from 'date-fns'

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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { toast } from 'sonner'
import { Icons } from '@/components/ui/icons'
import { UploadAudio } from './upload-audio'
import api from '@/lib/api-client'
import { useAuth } from '@/hooks/use-auth'

// Define questionnaire type
interface Questionnaire {
  id: string;
  title: string;
}

// Define the form schema
const formSchema = z.object({
  title: z.string().min(1, { message: 'Title is required' }),
  interviewee_name: z.string().min(1, { message: 'Interviewee name is required' }),
  date: z.string().min(1, { message: 'Date is required' }),
  location: z.string().optional(),
  questionnaire_id: z.string().optional(),
  notes: z.string().optional(),
})

export function InterviewForm() {
  const [isLoading, setIsLoading] = useState(false)
  const [questionnaires, setQuestionnaires] = useState<Questionnaire[]>([])
  const [audioFiles, setAudioFiles] = useState<File[]>([])
  const router = useRouter()
  const { isAuthenticated, user } = useAuth()

  // Check authentication when component loads
  useEffect(() => {
    if (!isAuthenticated && !user) {
      toast.error('You must be logged in to create an interview')
      router.push('/auth/login')
    }
  }, [isAuthenticated, user, router])

  // Initialize form
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: '',
      interviewee_name: '',
      date: format(new Date(), 'yyyy-MM-dd\'T\'HH:mm'),
      location: '',
      questionnaire_id: '',
      notes: '',
    },
  })

  // Fetch questionnaires
  useEffect(() => {
    const fetchQuestionnaires = async () => {
      try {
        const data = await api.get<Questionnaire[]>('/questionnaires')
        setQuestionnaires(data)
      } catch (error) {
        console.error('Failed to load questionnaires:', error)
        toast.error('Failed to load questionnaires')
      }
    }

    fetchQuestionnaires()
  }, [])

  // This function is called from the UploadAudio component
  // We need to use useCallback to prevent unnecessary re-renders
  const handleFilesChange = useCallback((files: File[]) => {
    console.log('Files changed in InterviewForm:', files.length)
    try {
      setAudioFiles(files)
    } catch (error) {
      console.error('Error handling files in InterviewForm:', error)
      toast.error('There was an error handling the selected files')
    }
  }, [])

  // Form submission handler
  const onSubmit = async (values: z.infer<typeof formSchema>) => {
    if (audioFiles.length === 0) {
      toast.error('Please upload at least one audio file')
      return
    }

    // Check authentication
    const token = localStorage.getItem('token')
    if (!token || !isAuthenticated || !user) {
      console.log('Authentication missing or invalid, redirecting to login')
      toast.error('You must be logged in to create an interview')
      router.push('/auth/login')
      return
    }

    setIsLoading(true)

    try {
      // Ensure date is in ISO format
      const formattedValues: {
        title: string;
        interviewee_name: string;
        date: string;
        location?: string;
        notes?: string;
        questionnaire_id?: string;
      } = {
        title: values.title,
        interviewee_name: values.interviewee_name,
        date: new Date(values.date).toISOString(),
      }

      // Only add optional fields if they have values
      if (values.location) {
        formattedValues.location = values.location
      }
      
      if (values.notes) {
        formattedValues.notes = values.notes
      }

      // Add questionnaire_id if selected
      if (values.questionnaire_id && values.questionnaire_id.trim() !== '') {
        formattedValues.questionnaire_id = values.questionnaire_id
      }

      console.log('Creating interview with values:', formattedValues)
      console.log(`Using authentication token: ${token.substring(0, 10)}...`)

      // First create the interview
      const interviewResponse = await api.post<{ id: string }>('/interviews', formattedValues)
      console.log('Interview created:', interviewResponse)
      
      try {
        // Then upload audio files
        console.log('Preparing to upload', audioFiles.length, 'files for interview', interviewResponse.id)
        const formData = new FormData()
        for (const file of audioFiles) {
          formData.append('files', file)
        }

        await api.upload(`/interviews/${interviewResponse.id}/upload`, formData)

        toast.success('Interview created successfully')
        router.push(`/interviews/${interviewResponse.id}`)
      } catch (uploadError) {
        console.error('Failed to upload audio files:', uploadError)
        toast.error(`Interview created but failed to upload audio files: ${uploadError instanceof Error ? uploadError.message : 'Unknown error'}`)
        router.push(`/interviews/${interviewResponse.id}`)
      }
    } catch (error) {
      console.error('Failed to create interview:', error)
      let errorMessage = 'Failed to create interview'
      
      if (error instanceof Error) {
        // Check for specific error messages
        if (error.message.includes("credits")) {
          errorMessage = "You don't have enough interview credits available"
        } else if (error.message.includes("[object Object]")) {
          errorMessage = "Server validation error. Please check your form inputs."
        } else if (error.message.includes("No response from server")) {
          errorMessage = "Server connection error. This could be due to CORS or authentication issues."
          console.error("Detailed error info:", {
            message: error.message,
            stack: error.stack,
            token: !!localStorage.getItem('token')
          })
          // Don't automatically log out - might be a temporary CORS issue
        } else {
          // Use the actual error message
          errorMessage = `Error: ${error.message}`
        }
      }
      
      toast.error(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card className="w-full max-w-4xl mx-auto">
      <CardHeader>
        <CardTitle>Create New Interview</CardTitle>
        <CardDescription>
          Enter interview details and upload audio files
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Interview Title</FormLabel>
                    <FormControl>
                      <Input placeholder="Interview with John Doe" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="interviewee_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Interviewee Name</FormLabel>
                    <FormControl>
                      <Input placeholder="John Doe" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Interview Date</FormLabel>
                    <FormControl>
                      <Input type="datetime-local" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="location"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Location (Optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="Zoom Meeting" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="questionnaire_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Questionnaire</FormLabel>
                    <Select 
                      value={field.value} 
                      onValueChange={field.onChange}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a questionnaire" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {questionnaires.map((questionnaire) => (
                          <SelectItem key={questionnaire.id} value={questionnaire.id}>
                            {questionnaire.title}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Notes (Optional)</FormLabel>
                  <FormControl>
                    <textarea 
                      className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 min-h-[100px]"
                      placeholder="Additional notes about the interview..." 
                      {...field} 
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div>
              <FormLabel>Upload Audio Files</FormLabel>
              <UploadAudio onFilesChange={handleFilesChange} />
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading && <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />}
              Create Interview
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}