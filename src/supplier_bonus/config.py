"""Конфигурация приложения. Читается из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_list(name: str, default: str) -> list[str]:
    return [s.strip() for s in os.getenv(name, default).split(",") if s.strip()]


@dataclass(frozen=True)
class Settings:
    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")
    llm_model: str = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
    llm_vision_model: str | None = os.getenv("LLM_VISION_MODEL") or None

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL") or None
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None

    # OCR
    ocr_primary: str = os.getenv("OCR_PRIMARY", "tesseract")
    ocr_fallback: str = os.getenv("OCR_FALLBACK", "paddleocr")
    ocr_confidence_threshold: float = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.75"))
    ocr_languages: list[str] = field(default_factory=lambda: _env_list("OCR_LANGUAGES", "ru,en"))
    ocr_device: str = os.getenv("OCR_DEVICE", "cpu")

    # Сверка
    amount_tolerance: float = float(os.getenv("AMOUNT_TOLERANCE", "1.0"))
    fuzzy_threshold: int = int(os.getenv("FUZZY_THRESHOLD", "90"))

    # Review queue
    review_documents_dir: str | None = os.getenv("REVIEW_DOCUMENTS_DIR") or "./data/review"

    # Данные
    test_data_path: Path = Path(os.getenv("TEST_DATA_PATH", "./data/examples"))


def get_settings() -> Settings:
    return Settings()
