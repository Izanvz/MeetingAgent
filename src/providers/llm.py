import os
from langchain_core.language_models import BaseChatModel


def get_llm() -> BaseChatModel:
    provider = os.getenv("LLM_PROVIDER", "openai")
    match provider:
        case "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini")
        case "claude":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model="claude-3-5-haiku-latest")
        case "ollama":
            from langchain_ollama import ChatOllama
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            return ChatOllama(model="mistral:7b", base_url=base_url)
        case _:
            raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Use 'openai', 'claude', or 'ollama'.")
