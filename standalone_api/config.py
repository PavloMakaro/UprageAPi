import os

# Core LLM API Config (allows switching to OpenAI, Anthropic via proxy, etc)
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# Extra API Keys configured via Environment Variables
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OCR_API_KEY = os.getenv("OCR_API_KEY", "")
LANGSEARCH_API_KEY = os.getenv("LANGSEARCH_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

ALLOWED_USERS = []
