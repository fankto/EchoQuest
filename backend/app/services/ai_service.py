import asyncio
import uuid
from typing import Dict, List, Optional, Any

import openai
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

from app.core.config import settings
from app.crud.crud_interview import interview_crud
from app.crud.crud_questionnaire import questionnaire_crud
from app.models.models import Interview, Questionnaire
from app.utils.exceptions import ExternalAPIError


@retry(
    stop=stop_after_attempt(settings.OPENAI_MAX_RETRIES),
    wait=wait_exponential(multiplier=settings.OPENAI_RETRY_DELAY, min=1, max=60),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
)
async def generate_answer_for_question(
        question: str,
        transcript: str,
        openai_api_key: str
) -> str:
    """
    Generate an answer for a single question based on the interview transcript.

    Args:
        question: The question to answer
        transcript: The interview transcript text
        openai_api_key: OpenAI API key

    Returns:
        Generated answer text
    """
    try:
        # Use GPT to generate the answer
        client = openai.AsyncOpenAI(api_key=openai_api_key)
        response = await client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI assistant that analyzes interview transcripts and answers questions based on the content. Provide concise and accurate answers."
                },
                {
                    "role": "user",
                    "content": f"Here is an interview transcript:\n\n{transcript}\n\nBased on this transcript, please answer the following question:\n{question}"
                }
            ],
            temperature=0.3,
            max_tokens=500,
        )

        answer = response.choices[0].message.content.strip()
        return answer

    except httpx.HTTPError as e:
        logger.error(f"HTTP error when calling OpenAI: {e}")
        raise ExternalAPIError(f"Error communicating with OpenAI: {str(e)}")
    except Exception as e:
        logger.error(f"Error generating answer: {e}")
        raise


async def generate_answers_from_transcript(
        interview_id: str,
        db: AsyncSession,
        questionnaire_id: Optional[str] = None
) -> None:
    """
    Generate answers for questionnaire questions using OpenAI's GPT model.
    This runs as a background task.

    Args:
        interview_id: Interview ID
        db: Database session
        questionnaire_id: Questionnaire ID (optional)
    """
    try:
        # Create a new session for background task
        async with db:
            # Get interview
            interview = await interview_crud.get(db, id=uuid.UUID(interview_id))

            if not interview or not interview.transcription:
                logger.error(f"Invalid interview state for answer generation: {interview_id}")
                return

            # Initialize the answers dict if it doesn't exist
            current_answers = interview.get_generated_answers()

            # Determine which questionnaires to process
            questionnaires_to_process = []

            if questionnaire_id:
                # Process only the specified questionnaire
                result = await db.execute(
                    f"SELECT * FROM questionnaires WHERE id = '{questionnaire_id}'"
                )
                questionnaire = result.fetchone()
                if questionnaire:
                    questionnaires_to_process.append(questionnaire)
            else:
                # Process all attached questionnaires through many-to-many relationship
                from sqlalchemy import text
                result = await db.execute(
                    text(f"""
                    SELECT q.* FROM questionnaires q
                    JOIN interview_questionnaire iq ON q.id = iq.questionnaire_id
                    WHERE iq.interview_id = '{interview_id}'
                    """)
                )
                questionnaires = result.fetchall()
                questionnaires_to_process.extend(questionnaires)

            if not questionnaires_to_process:
                logger.error(f"No questionnaires found for interview: {interview_id}")
                return

            # Process each questionnaire
            for questionnaire in questionnaires_to_process:
                if not questionnaire.questions:
                    logger.warning(f"No questions found in questionnaire: {questionnaire.id}")
                    continue

                # Initialize answers dict for this questionnaire
                questionnaire_answers = {}

                # Process each question
                for question in questionnaire.questions:
                    try:
                        # Generate answer for this question
                        answer = await generate_answer_for_question(
                            question,
                            interview.transcription,
                            settings.OPENAI_API_KEY
                        )

                        # Store answer
                        questionnaire_answers[question] = answer

                        # Add some delay to avoid rate limiting
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.error(f"Error generating answer for question: {e}")
                        questionnaire_answers[question] = f"Error generating answer: {str(e)}"

                # Update answers dict with the questionnaire's answers
                current_answers[str(questionnaire.id)] = questionnaire_answers

            # Update interview with generated answers
            interview.set_generated_answers(current_answers)
            await db.commit()

            logger.info(f"Successfully generated answers for interview {interview_id}")

    except Exception as e:
        logger.error(f"Error in generate_answers_from_transcript: {e}")
        logger.exception(e)