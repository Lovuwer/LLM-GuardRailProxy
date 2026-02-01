import asyncio
from typing import Optional, Dict, Any, List
import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.services.guardrail import GuardrailService
from app.services.gemini_client import GeminiClient, ServiceUnavailableError


logger = structlog.get_logger()

# initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# initialize services
guardrail_service = GuardrailService()
gemini_client = GeminiClient()

router = APIRouter(prefix="/api/v1", tags=["prompt"])


# valid model options
VALID_MODELS = [
    # Gemini 3 models (preview)
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    # Gemini 2.5 models
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    # Gemini 2 models
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    # Legacy aliases
    "gemini-flash-latest",
    "gemini-pro-latest"
]


from enum import Enum


class MessageRole(str, Enum):
    """valid roles for conversation messages"""
    user = "user"
    assistant = "assistant"


class ConversationMessage(BaseModel):
    """a single message in the conversation"""
    role: MessageRole = Field(..., description="role of the message sender (user/assistant)")
    content: str = Field(..., description="content of the message")


class PromptRequest(BaseModel):
    """request model for prompt endpoint"""
    prompt: str = Field(
        ..., 
        max_length=settings.MAX_PROMPT_LENGTH, 
        description="user prompt to process"
    )
    api_key: SecretStr = Field(
        ...,
        description="gemini api key provided by user"
    )


class ChatRequest(BaseModel):
    """request model for chat endpoint with conversation history"""
    message: str = Field(
        ..., 
        max_length=settings.MAX_PROMPT_LENGTH, 
        description="user message to process"
    )
    api_key: SecretStr = Field(
        ...,
        description="gemini api key provided by user"
    )
    model: str = Field(
        default="gemini-2.0-flash",
        description="gemini model to use"
    )
    conversation_history: List[ConversationMessage] = Field(
        default=[],
        description="previous conversation messages for context"
    )


class PromptResponse(BaseModel):
    """response model for prompt endpoint"""
    success: bool = Field(..., description="whether the request was successful")
    response: Optional[str] = Field(None, description="generated response from gemini")
    guardrail: Dict[str, Any] = Field(..., description="guardrail check results")
    error: Optional[str] = Field(None, description="error message if failed")


@router.post("/prompt", response_model=PromptResponse)
@limiter.limit(settings.RATE_LIMIT)
async def process_prompt(request: Request, prompt_request: PromptRequest):
    """
    main endpoint for processing prompts through guardrails and gemini
    
    flow:
    1. validate prompt length
    2. run guardrail check with timeout
    3. if guardrail fails -> return 400 with failure reason
    4. if guardrail passes -> call gemini and return response
    5. on any exception -> fail closed, return 500
    """
    prompt = prompt_request.prompt
    
    try:
        # validate prompt length
        if len(prompt) > settings.MAX_PROMPT_LENGTH:
            logger.warning("prompt too long", length=len(prompt))
            return PromptResponse(
                success=False,
                guardrail={"safe": False, "reason": "prompt exceeds maximum length"},
                error="prompt too long"
            )
        
        # run guardrail check with timeout
        try:
            guardrail_result = await asyncio.wait_for(
                guardrail_service.check_prompt(prompt, api_key=prompt_request.api_key.get_secret_value()),
                timeout=settings.GUARDRAIL_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.error("guardrail check timeout")
            return PromptResponse(
                success=False,
                guardrail={"safe": False, "reason": "guardrail check timeout"},
                error="security check timed out"
            )
        
        # if guardrail fails, return 400
        if not guardrail_result['safe']:
            logger.warning("guardrail blocked prompt", reason=guardrail_result['reason'])
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "guardrail": guardrail_result,
                    "error": "prompt blocked by security guardrails"
                }
            )
        
        # guardrail passed, call gemini
        try:
            response_text = await gemini_client.generate(
                prompt,
                timeout=settings.GEMINI_TIMEOUT_SECONDS,
                api_key=prompt_request.api_key.get_secret_value()
            )
            
            logger.info("prompt processed successfully")
            return PromptResponse(
                success=True,
                response=response_text,
                guardrail=guardrail_result
            )
            
        except ServiceUnavailableError:
            logger.error("gemini service unavailable")
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "guardrail": guardrail_result,
                    "error": "gemini service temporarily unavailable"
                }
            )
        
        except asyncio.TimeoutError:
            logger.error("gemini request timeout")
            raise HTTPException(
                status_code=504,
                detail={
                    "success": False,
                    "guardrail": guardrail_result,
                    "error": "gemini request timed out"
                }
            )
        
        except Exception as e:
            logger.error("gemini request failed", error=str(e))
            # fail closed - return error
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "guardrail": guardrail_result,
                    "error": f"failed to generate response: {str(e)}"
                }
            )
    
    except HTTPException:
        # re-raise http exceptions
        raise
    
    except Exception as e:
        # catch any unexpected errors and fail closed
        logger.error("unexpected error processing prompt", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "guardrail": {"safe": False, "reason": "unexpected error"},
                "error": f"internal error: {str(e)}"
            }
        )


@router.post("/chat", response_model=PromptResponse)
@limiter.limit(settings.RATE_LIMIT)
async def process_chat(request: Request, chat_request: ChatRequest):
    """
    chat endpoint for processing messages with conversation history
    
    flow:
    1. validate message length and model
    2. run guardrail check on the current message
    3. if guardrail fails -> return 400 with failure reason
    4. if guardrail passes -> call gemini with conversation context
    5. on any exception -> fail closed, return 500
    """
    message = chat_request.message
    model = chat_request.model
    
    # validate model
    if model not in VALID_MODELS:
        model = "gemini-2.0-flash"
    
    try:
        # validate message length
        if len(message) > settings.MAX_PROMPT_LENGTH:
            logger.warning("message too long", length=len(message))
            return PromptResponse(
                success=False,
                guardrail={"safe": False, "reason": "message exceeds maximum length"},
                error="message too long"
            )
        
        # run guardrail check with timeout on the current message
        try:
            guardrail_result = await asyncio.wait_for(
                guardrail_service.check_prompt(message, api_key=chat_request.api_key.get_secret_value()),
                timeout=settings.GUARDRAIL_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.error("guardrail check timeout")
            return PromptResponse(
                success=False,
                guardrail={"safe": False, "reason": "guardrail check timeout"},
                error="security check timed out"
            )
        
        # if guardrail fails, return 400
        if not guardrail_result['safe']:
            logger.warning("guardrail blocked message", reason=guardrail_result['reason'])
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "guardrail": guardrail_result,
                    "error": "message blocked by security guardrails"
                }
            )
        
        # guardrail passed, call gemini with conversation history
        try:
            response_text = await gemini_client.generate_chat(
                message=message,
                conversation_history=[
                    {"role": msg.role, "content": msg.content}
                    for msg in chat_request.conversation_history
                ],
                model=model,
                timeout=settings.GEMINI_TIMEOUT_SECONDS,
                api_key=chat_request.api_key.get_secret_value()
            )
            
            logger.info("chat message processed successfully", model=model)
            return PromptResponse(
                success=True,
                response=response_text,
                guardrail=guardrail_result
            )
            
        except ServiceUnavailableError:
            logger.error("gemini service unavailable")
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "guardrail": guardrail_result,
                    "error": "gemini service temporarily unavailable"
                }
            )
        
        except asyncio.TimeoutError:
            logger.error("gemini request timeout")
            raise HTTPException(
                status_code=504,
                detail={
                    "success": False,
                    "guardrail": guardrail_result,
                    "error": "gemini request timed out"
                }
            )
        
        except Exception as e:
            logger.error("gemini request failed", error=str(e))
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "guardrail": guardrail_result,
                    "error": f"failed to generate response: {str(e)}"
                }
            )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error("unexpected error processing chat", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "guardrail": {"safe": False, "reason": "unexpected error"},
                "error": f"internal error: {str(e)}"
            }
        )
