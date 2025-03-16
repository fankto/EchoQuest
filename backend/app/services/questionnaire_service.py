from typing import List, Optional

import openai
from fastapi import UploadFile
from loguru import logger

from app.core.config import settings


class QuestionnaireService:
    """Service for managing questionnaires and extracting questions"""
    
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
    
    async def extract_questions(self, content: str) -> List[str]:
        """
        Extract questions from questionnaire content
        
        Args:
            content: Questionnaire content
            
        Returns:
            List of extracted questions
        """
        try:
            # Use OpenAI to extract questions
            response = await openai.chat.completions.create(
                model=settings.OPENAI_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "Extract all questions from the following text. Return just a list of questions, one per line. Don't add any explanations."},
                    {"role": "user", "content": content}
                ],
                temperature=0.3,
            )
            
            # Parse response
            questions_text = response.choices[0].message.content.strip()
            
            # Split by new lines and clean up
            questions = [q.strip() for q in questions_text.split('\n') if q.strip()]
            
            # Filter out non-questions
            questions = [q for q in questions if q.endswith('?')]
            
            logger.info(f"Extracted {len(questions)} questions")
            return questions
        
        except Exception as e:
            logger.error(f"Error extracting questions: {e}")
            # Return some basic questions as fallback
            return ["What is your background?", "What are your main responsibilities?", "What challenges do you face?"]
    
    async def extract_content_from_file(self, file: UploadFile) -> str:
        """
        Extract content from uploaded file
        
        Args:
            file: Uploaded file
            
        Returns:
            Extracted content
        """
        try:
            content = b""
            # Read file in chunks
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                content += chunk
            
            # Convert to string
            text_content = content.decode("utf-8")
            
            # For more complex files (docx, pdf), you would need additional libraries
            # This is a simple implementation for text files
            
            return text_content
        
        except Exception as e:
            logger.error(f"Error extracting content from file: {e}")
            return ""


# Create singleton instance
questionnaire_service = QuestionnaireService()