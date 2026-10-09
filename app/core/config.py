"""app/core/config.py — .env dosyasindan ayar okur (bagimliliksiz)."""
import os

_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), ".env")


def _load_env_file():
    if not os.path.exists(_ENV_PATH):
        return
    with open(_ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:   # gercek env degiskeni oncelikli
                os.environ[k] = v


_load_env_file()


class Settings:
    llm_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    llm_model: str = os.environ.get("LLM_MODEL", "claude-sonnet-4-5")
    llm_max_retries: int = 2
    llm_max_segment_chars: int = 12000
    whisper_model_size: str = os.environ.get("WHISPER_MODEL", "large-v3")
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    audio_retention_hours: int = 24


settings = Settings()
