# Project State: LLM Guardrail Proxy

## 🔄 Last Updated
- **Date:** 2026-01-31
- **Task Completed:** Task 4 - Frontend Dashboard
- **Status:** ✅ Core Implementation Complete

## ✅ What We Just Built
- [x] Project skeleton and folder structure
- [x] Configuration management with Pydantic Settings
- [x] FastAPI app initialization
- [x] Health check endpoint
- [x] Text normalizer for security analysis
- [x] Two-tier guardrail system
  - [x] Tier 1: Fast regex checks (<50ms)
  - [x] Tier 2: Semantic analysis with Gemini Judge LLM
- [x] Gemini client with circuit breaker
- [x] Main prompt processing endpoint
- [x] Rate limiting and exception handling
- [x] Frontend dashboard with modern UI
- [x] Complete documentation (README.md)

## 📁 Current File Structure
```
llm-guardrail-proxy/
├── app/
│   ├── __init__.py
│   ├── config.py              # Pydantic settings
│   ├── main.py                # FastAPI app with routers, exception handlers, root route
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py          # Health check endpoint
│   │   └── prompt.py          # Main prompt processing endpoint (POST /api/v1/prompt)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── normalizer.py      # Text normalization (base64, leetspeak, unicode)
│   │   ├── guardrail.py       # Two-tier security guardrail
│   │   └── gemini_client.py   # Gemini API client with circuit breaker
│   └── static/
│       └── index.html         # Frontend dashboard (single-page app)
├── requirements.txt           # Python dependencies
├── .env.example              # Example environment variables
├── project_state.md          # This file
└── README.md                 # Complete documentation
```

## 🔐 Guardrail Features

### Normalizer
- Base64 detection and decoding
- Leetspeak conversion (1→i, 3→e, 4→a, 0→o, 5→s, 7→t)
- Unicode homoglyph normalization
- Multiple space collapsing

### Tier 1 Checks (Regex, <50ms)
- Prompt injection attempts ("ignore instructions")
- Jailbreak attempts ("you are now DAN")
- System prompt leakage ("reveal your instructions")
- PII detection (SSN, credit cards, emails)

### Tier 2 Check (Semantic)
- Gemini-based semantic analysis
- Detects subtle attacks missed by regex
- JSON-based safe/unsafe classification

## 🚀 API Endpoints

### GET /
Serves the frontend dashboard (index.html)

### GET /health
Returns health status and version

### POST /api/v1/prompt
Main endpoint for processing prompts through guardrails and Gemini.

**Flow:**
1. Validate prompt length
2. Run guardrail check with timeout
3. If guardrail fails → return 400 with failure reason
4. If guardrail passes → call Gemini and return response
5. On any exception → fail closed, return 500

**Features:**
- Rate limiting (configurable via settings)
- Circuit breaker (3 consecutive failures)
- Comprehensive error handling
- Timeout handling for both guardrail and Gemini
- Full guardrail metadata in responses

## 🔧 Gemini Client Features
- Async/await with timeout handling (asyncio.wait_for)
- Circuit breaker pattern (opens after 3 consecutive failures)
- Exception handling for:
  - InvalidArgument (bad API key)
  - ResourceExhausted (quota limits)
  - Timeout errors
- Request duration logging (never logs prompt content)

## 🎨 Frontend Dashboard Features

### UI Components
- Clean, modern design with gradient background
- Responsive layout
- Real-time character counter (0-10,000)
- Submit button with loading state
- Animated loading spinner
- Result display area with color-coded status

### Security Features
- Content Security Policy (CSP) meta tag
- XSS prevention (uses textContent, not innerHTML)
- All user input properly escaped
- Network error handling

### User Experience
- Visual feedback for success/failure
- Detailed guardrail analysis display:
  - Status (Safe/Blocked)
  - Reason for decision
  - Tier level
  - Pattern matched (if any)
  - Latency measurement
- Formatted Gemini response display
- Enter key to submit (Shift+Enter for newline)

## 📖 Documentation

### README.md Includes:
- Project overview and architecture
- Quick start guide
- Environment setup instructions
- Configuration reference
- Complete API documentation
- Railway deployment guide
- Testing examples
- Security considerations
- Project structure
- Contributing guidelines

## 🎯 Next Task
**Task 5: Chaos Testing**

Implement comprehensive testing including:
- Load testing
- Failure scenario testing
- Circuit breaker validation
- Rate limiting verification
- Security bypass attempts
