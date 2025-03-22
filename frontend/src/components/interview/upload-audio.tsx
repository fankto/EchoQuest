'use client'

import { useState, useCallback } from 'react'
import { useDropzone, type FileRejection } from 'react-dropzone'
import { toast } from 'sonner'
import { Upload } from 'lucide-react'
import { X } from 'lucide-react'
import { Music } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const MAX_FILE_SIZE = 500 * 1024 * 1024 // 500MB
const ACCEPTED_FILE_TYPES = {
  'audio/mpeg': ['.mp3'],
  'audio/mp4': ['.mp4', '.m4a'],
  'audio/wav': ['.wav'],
  'audio/x-wav': ['.wav'],
  'audio/ogg': ['.ogg'],
  'audio/webm': ['.webm'],
  'audio/flac': ['.flac'],
}

interface UploadAudioProps {
  onFilesChange: (files: File[]) => void
  maxFiles?: number
}

export function UploadAudio({ onFilesChange, maxFiles = 10 }: UploadAudioProps) {
  const [files, setFiles] = useState<File[]>([])

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
    // Handle rejected files
    if (rejectedFiles.length > 0) {
      for (const file of rejectedFiles) {
        for (const error of file.errors) {
          if (error.code === 'file-too-large') {
            toast.error(`File ${file.file.name} is too large. Max size is 500MB.`)
          } else if (error.code === 'file-invalid-type') {
            toast.error(`File ${file.file.name} has an invalid file type.`)
          } else {
            toast.error(`Error with file ${file.file.name}: ${error.message}`)
          }
        }
      }
      return
    }

    // Add debugging for accepted files
    if (acceptedFiles.length > 0) {
      console.log('Accepted files:', acceptedFiles.map(f => ({ name: f.name, type: f.type, size: f.size })))
    }

    try {
      // Update files state and notify parent using functional updates
      setFiles((prev) => {
        // Check if adding these files would exceed the max
        if (prev.length + acceptedFiles.length > maxFiles) {
          toast.error(`You can only upload up to ${maxFiles} files.`)
          const newFiles = [...prev, ...acceptedFiles].slice(0, maxFiles)
          // Call onFilesChange outside of the render phase
          setTimeout(() => onFilesChange(newFiles), 0)
          return newFiles
        }

        const updated = [...prev, ...acceptedFiles]
        // Call onFilesChange outside of the render phase
        setTimeout(() => onFilesChange(updated), 0)
        return updated
      })
    } catch (error) {
      console.error('Error in file upload handler:', error)
      toast.error('An error occurred while handling the files. Please try again.')
    }
  }, [maxFiles, onFilesChange])

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => {
      const updated = prev.filter((_, i) => i !== index)
      // Call onFilesChange outside of the render phase
      setTimeout(() => onFilesChange(updated), 0)
      return updated
    })
  }, [onFilesChange])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    maxFiles: maxFiles,
  })

  function formatFileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} bytes`
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1048576).toFixed(1)} MB`
  }

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-md p-6 cursor-pointer text-center transition-colors",
          isDragActive
            ? "bg-primary/5 border-primary"
            : "border-muted-foreground/25 hover:border-primary/50"
        )}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center justify-center space-y-2">
          <Upload className="h-10 w-10 text-muted-foreground" />
          <p className="text-sm font-medium">
            Drag & drop audio files here, or click to select files
          </p>
          <p className="text-xs text-muted-foreground">
            Supported formats: MP3, WAV, FLAC, OGG, WebM, M4A (max. 500MB per file)
          </p>
        </div>
      </div>

      {files.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Uploaded Files ({files.length})</h3>
          <ul className="space-y-2">
            {files.map((file, index) => (
              <li
                key={`${file.name}-${index}`}
                className="flex items-center justify-between rounded-md border p-3"
              >
                <div className="flex items-center space-x-3">
                  <Music className="h-5 w-5 text-muted-foreground" />
                  <div className="space-y-1">
                    <p className="text-sm font-medium">{file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removeFile(index)}
                  className="h-8 w-8"
                >
                  <X className="h-4 w-4" />
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}