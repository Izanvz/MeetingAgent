import os
import pytest
from unittest.mock import patch

def test_openai_provider():
    with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"}):
        from src.providers.llm import get_llm
        llm = get_llm()
        assert llm.__class__.__name__ == "ChatOpenAI"

def test_claude_provider():
    with patch.dict(os.environ, {"LLM_PROVIDER": "claude", "ANTHROPIC_API_KEY": "sk-ant-test"}):
        from importlib import reload
        import src.providers.llm as llm_module
        reload(llm_module)
        llm = llm_module.get_llm()
        assert llm.__class__.__name__ == "ChatAnthropic"

def test_ollama_provider():
    with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}):
        from importlib import reload
        import src.providers.llm as llm_module
        reload(llm_module)
        llm = llm_module.get_llm()
        assert llm.__class__.__name__ == "ChatOllama"

def test_unknown_provider_raises():
    with patch.dict(os.environ, {"LLM_PROVIDER": "unknown"}):
        from importlib import reload
        import src.providers.llm as llm_module
        reload(llm_module)
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            llm_module.get_llm()
