import asyncio
import time
import threading
from typing import Optional, List, Dict
import structlog
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions


logger = structlog.get_logger()

# Lock to serialize API key configuration and model usage
_api_key_lock = threading.Lock()


class ServiceUnavailableError(Exception):
    """raised when service is unavailable due to circuit breaker"""
    pass


class GeminiClient:
    """
    client for interacting with google gemini api
    includes circuit breaker pattern and error handling
    """
    
    def __init__(self):
        # circuit breaker state
        self._consecutive_failures = 0
        self._max_failures = 3
        self._circuit_open = False
        
        logger.info("gemini client initialized")
    
    async def generate(self, prompt: str, timeout: float, api_key: str) -> str:
        """
        generate response from gemini with timeout handling
        
        args:
            prompt: the user prompt to send to gemini
            timeout: timeout in seconds
            api_key: the gemini api key to use
            
        returns:
            generated text response
            
        raises:
            ServiceUnavailableError: if circuit breaker is open
            TimeoutError: if request times out
            google_exceptions.InvalidArgument: for bad api key
            google_exceptions.ResourceExhausted: for quota limits
        """
        # check circuit breaker
        if self._circuit_open:
            logger.error("circuit breaker is open, rejecting request")
            raise ServiceUnavailableError("service temporarily unavailable")
        
        start_time = time.time()
        
        try:
            def _generate_with_lock():
                """Execute generation with lock to prevent API key race conditions"""
                with _api_key_lock:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-flash-latest')
                    return model.generate_content(
                        prompt,
                        generation_config={'temperature': 0.7}
                    )
            
            # use asyncio.wait_for for timeout handling
            response = await asyncio.wait_for(
                asyncio.to_thread(_generate_with_lock),
                timeout=timeout
            )
            
            # reset circuit breaker on success
            self._consecutive_failures = 0
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info("gemini request successful", duration_ms=duration_ms)
            
            return response.text
            
        except asyncio.TimeoutError:
            self._handle_failure()
            duration_ms = (time.time() - start_time) * 1000
            logger.error("gemini request timeout", duration_ms=duration_ms)
            raise
            
        except google_exceptions.InvalidArgument as e:
            self._handle_failure()
            logger.error("invalid api key or bad request", error=str(e))
            raise
            
        except google_exceptions.ResourceExhausted as e:
            self._handle_failure()
            logger.error("gemini quota exhausted", error=str(e))
            raise
            
        except Exception as e:
            self._handle_failure()
            duration_ms = (time.time() - start_time) * 1000
            logger.error("gemini request failed", error=str(e), duration_ms=duration_ms)
            raise

    async def generate_chat(
        self,
        message: str,
        conversation_history: List[Dict[str, str]],
        model: str,
        timeout: float,
        api_key: str
    ) -> str:
        """
        generate chat response with conversation history
        
        args:
            message: the current user message
            conversation_history: list of previous messages with role and content
            model: the gemini model to use
            timeout: timeout in seconds
            api_key: the gemini api key to use
            
        returns:
            generated text response
        """
        # check circuit breaker
        if self._circuit_open:
            logger.error("circuit breaker is open, rejecting request")
            raise ServiceUnavailableError("service temporarily unavailable")
        
        start_time = time.time()
        
        try:
            def _generate_chat_with_lock():
                """Execute chat generation with conversation history"""
                with _api_key_lock:
                    genai.configure(api_key=api_key)
                    genai_model = genai.GenerativeModel(model)
                    
                    # build conversation history for gemini
                    # Map roles: 'user' stays 'user', 'assistant' becomes 'model'
                    history = []
                    for msg in conversation_history:
                        if msg["role"] == "user":
                            role = "user"
                        elif msg["role"] == "assistant":
                            role = "model"
                        else:
                            # Skip messages with invalid roles
                            logger.warning("skipping message with invalid role", role=msg["role"])
                            continue
                        history.append({
                            "role": role,
                            "parts": [msg["content"]]
                        })
                    
                    # start chat with history
                    chat = genai_model.start_chat(history=history)
                    
                    # send current message
                    response = chat.send_message(
                        message,
                        generation_config={'temperature': 0.7}
                    )
                    
                    return response
            
            # use asyncio.wait_for for timeout handling
            response = await asyncio.wait_for(
                asyncio.to_thread(_generate_chat_with_lock),
                timeout=timeout
            )
            
            # reset circuit breaker on success
            self._consecutive_failures = 0
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info("gemini chat request successful", duration_ms=duration_ms, model=model)
            
            return response.text
            
        except asyncio.TimeoutError:
            self._handle_failure()
            duration_ms = (time.time() - start_time) * 1000
            logger.error("gemini chat request timeout", duration_ms=duration_ms)
            raise
            
        except google_exceptions.InvalidArgument as e:
            self._handle_failure()
            logger.error("invalid api key or bad request", error=str(e))
            raise
            
        except google_exceptions.ResourceExhausted as e:
            self._handle_failure()
            logger.error("gemini quota exhausted", error=str(e))
            raise
            
        except Exception as e:
            self._handle_failure()
            duration_ms = (time.time() - start_time) * 1000
            logger.error("gemini chat request failed", error=str(e), duration_ms=duration_ms)
            raise
    
    def _handle_failure(self):
        """
        handle failure and update circuit breaker state
        """
        self._consecutive_failures += 1
        logger.warning(
            "gemini failure recorded",
            consecutive_failures=self._consecutive_failures,
            max_failures=self._max_failures
        )
        
        if self._consecutive_failures >= self._max_failures:
            self._circuit_open = True
            logger.error("circuit breaker opened after consecutive failures")
    
    def reset_circuit_breaker(self):
        """
        manually reset the circuit breaker
        """
        self._consecutive_failures = 0
        self._circuit_open = False
        logger.info("circuit breaker reset")
