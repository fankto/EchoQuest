'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { Pencil, Trash, GripVertical, Plus, Save, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface QuestionListProps {
  questions: string[]
  readOnly?: boolean
  onQuestionsChange?: (questions: string[]) => void
}

export function QuestionList({
  questions,
  readOnly = false,
  onQuestionsChange,
}: QuestionListProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editValue, setEditValue] = useState('')
  const [localQuestions, setLocalQuestions] = useState<string[]>(questions)
  const [isDragging, setIsDragging] = useState(false)
  const [draggedItem, setDraggedItem] = useState<number | null>(null)

  // Update local state when props change
  if (JSON.stringify(questions) !== JSON.stringify(localQuestions)) {
    setLocalQuestions(questions)
  }

  const handleEdit = (index: number) => {
    setEditingIndex(index)
    setEditValue(localQuestions[index])
  }

  const handleSaveEdit = () => {
    if (editingIndex !== null) {
      const newQuestions = [...localQuestions]
      newQuestions[editingIndex] = editValue
      setLocalQuestions(newQuestions)
      onQuestionsChange?.(newQuestions)
      setEditingIndex(null)
    }
  }

  const handleCancelEdit = () => {
    setEditingIndex(null)
  }

  const handleDelete = (index: number) => {
    const newQuestions = localQuestions.filter((_, i) => i !== index)
    setLocalQuestions(newQuestions)
    onQuestionsChange?.(newQuestions)
  }

  const handleAddQuestion = () => {
    const newQuestions = [...localQuestions, 'New question?']
    setLocalQuestions(newQuestions)
    onQuestionsChange?.(newQuestions)
    handleEdit(newQuestions.length - 1)
  }

  const handleDragStart = (index: number) => {
    setIsDragging(true)
    setDraggedItem(index)
  }

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    if (draggedItem === null || draggedItem === index) return

    const newQuestions = [...localQuestions]
    const draggedItemValue = newQuestions[draggedItem]
    newQuestions.splice(draggedItem, 1)
    newQuestions.splice(index, 0, draggedItemValue)

    setLocalQuestions(newQuestions)
    setDraggedItem(index)
  }

  const handleDragEnd = () => {
    setIsDragging(false)
    setDraggedItem(null)
    onQuestionsChange?.(localQuestions)
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-md">Questions</CardTitle>
        {!readOnly && (
          <Button size="sm" variant="ghost" onClick={handleAddQuestion}>
            <Plus className="h-4 w-4 mr-1" />
            Add Question
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {localQuestions.length === 0 ? (
          <div className="text-center py-4 text-muted-foreground">
            No questions available
          </div>
        ) : (
          <ul className="space-y-2">
            {localQuestions.map((question, index) => (
              <li
                key={index}
                draggable={!readOnly}
                onDragStart={() => handleDragStart(index)}
                onDragOver={(e) => handleDragOver(e, index)}
                onDragEnd={handleDragEnd}
                className={cn(
                  "flex items-start gap-2 p-2 rounded-md",
                  isDragging && draggedItem === index ? "opacity-50" : "",
                  !readOnly && "border cursor-move"
                )}
              >
                {!readOnly && (
                  <div className="text-muted-foreground mt-0.5">
                    <GripVertical className="h-5 w-5" />
                  </div>
                )}
                
                {editingIndex === index ? (
                  <div className="flex-1 flex gap-2">
                    <Input
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="flex-1"
                      autoFocus
                    />
                    <Button 
                      size="icon" 
                      variant="ghost" 
                      onClick={handleSaveEdit}
                    >
                      <Save className="h-4 w-4" />
                    </Button>
                    <Button 
                      size="icon" 
                      variant="ghost" 
                      onClick={handleCancelEdit}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="flex-1">
                      <span className="mr-2 text-muted-foreground">{index + 1}.</span>
                      {question}
                    </div>
                    
                    {!readOnly && (
                      <div className="flex items-center gap-1">
                        <Button 
                          size="icon" 
                          variant="ghost" 
                          onClick={() => handleEdit(index)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button 
                          size="icon" 
                          variant="ghost" 
                          onClick={() => handleDelete(index)}
                        >
                          <Trash className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}