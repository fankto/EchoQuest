'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
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
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Icons } from '@/components/ui/icons'
import { toast } from 'sonner'
import api from '@/lib/api-client'

const formSchema = z.object({
  title: z.string().min(1, { message: 'Title is required' }),
  description: z.string().optional(),
  content: z.string().min(1, { message: 'Content is required' }),
})

type QuestionnaireFormProps = {
  initialData?: {
    id?: string
    title?: string
    description?: string
    content?: string
    questions?: string[]
  }
}

export function QuestionnaireForm({ initialData }: QuestionnaireFormProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [questions, setQuestions] = useState<string[]>(initialData?.questions || [])
  const [isExtracting, setIsExtracting] = useState(false)
  const router = useRouter()
  
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: initialData?.title || '',
      description: initialData?.description || '',
      content: initialData?.content || '',
    },
  })
  
  const watchContent = form.watch('content')
  
  // Extract questions when content changes
  useEffect(() => {
    const extractQuestions = async () => {
      if (!watchContent || watchContent.length < 50) return
      
      try {
        setIsExtracting(true)
        const response = await api.post('/api/questionnaires/extract-questions', {
          content: watchContent
        })
        
        if (response.questions) {
          setQuestions(response.questions)
        }
      } catch (error) {
        // Silent fail - don't notify user of extraction failures
        console.error('Failed to extract questions:', error)
      } finally {
        setIsExtracting(false)
      }
    }
    
    const debounce = setTimeout(() => {
      extractQuestions()
    }, 1000)
    
    return () => clearTimeout(debounce)
  }, [watchContent])
  
  async function onSubmit(values: z.infer<typeof formSchema>) {
    setIsLoading(true)
    
    try {
      const formData = new FormData()
      formData.append('title', values.title)
      formData.append('content', values.content)
      
      if (values.description) {
        formData.append('description', values.description)
      }
      
      if (questions.length > 0) {
        questions.forEach(q => formData.append('questions', q))
      }
      
      if (initialData?.id) {
        // Update existing
        await api.upload(`/api/questionnaires/${initialData.id}`, formData)
        toast.success('Questionnaire updated successfully')
      } else {
        // Create new
        const response = await api.upload('/api/questionnaires', formData)
        toast.success('Questionnaire created successfully')
        router.push(`/questionnaires/${response.id}`)
      }
    } catch (error: any) {
      toast.error(error.message || 'Failed to save questionnaire')
    } finally {
      setIsLoading(false)
    }
  }
  
  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>{initialData?.id ? 'Edit' : 'Create'} Questionnaire</CardTitle>
        <CardDescription>
          Create a questionnaire template for your interviews
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Title</FormLabel>
                  <FormControl>
                    <Input placeholder="Customer Interview Template" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description (Optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="Template for customer satisfaction interviews" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="content"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Questionnaire Content</FormLabel>
                  <FormControl>
                    <textarea 
                      className="flex min-h-[200px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      placeholder="Enter your questionnaire content here. Include all questions that will be asked during the interview."
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <div>
              <h3 className="text-sm font-medium mb-2 flex items-center">
                Extracted Questions
                {isExtracting && <Icons.spinner className="ml-2 h-4 w-4 animate-spin" />}
              </h3>
              {questions.length > 0 ? (
                <ul className="space-y-1 text-sm">
                  {questions.map((question, index) => (
                    <li key={index} className="p-2 rounded bg-muted flex items-start">
                      <span className="mr-2 text-muted-foreground">{index + 1}.</span>
                      <span>{question}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No questions extracted yet. Add more content to your questionnaire.
                </p>
              )}
            </div>
            
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading && <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />}
              {initialData?.id ? 'Update' : 'Create'} Questionnaire
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}