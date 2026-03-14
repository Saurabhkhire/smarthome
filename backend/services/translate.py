"""Language detection + DeepL translation with DB cache."""
import hashlib
import sys
import warnings
from pathlib import Path

import requests
from langdetect import detect, LangDetectException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from db.database import SessionLocal, init_db
from db.models import TranslationCache


def _cache_key(text: str, target_lang: str) -> str:
    return hashlib.sha256(f"{target_lang}:{text}".encode()).hexdigest()[:64]


def detect_language(text: str) -> str:
    if not text or not text.strip():
        return "en"
    try:
        return detect(text)
    except LangDetectException:
        return "en"


def _get_cached(db, source_text: str, target_lang: str) -> str | None:
    from sqlalchemy import select

    stmt = select(TranslationCache).where(
        TranslationCache.source_text == source_text,
        TranslationCache.target_lang == target_lang,
    )
    row = db.scalars(stmt).first()
    return row.translated_text if row else None


def _set_cached(db, source_text: str, target_lang: str, translated: str) -> None:
    from sqlalchemy import select
    existing = db.scalars(
        select(TranslationCache).where(
            TranslationCache.source_text == source_text,
            TranslationCache.target_lang == target_lang,
        )
    ).first()
    if existing:
        return
    db.add(
        TranslationCache(
            source_text=source_text,
            target_lang=target_lang,
            translated_text=translated,
        )
    )
    db.commit()


def _deepl(text: str, target_lang: str) -> str | None:
    if not config.DEEPL_API_KEY:
        warnings.warn("DEEPL_API_KEY not set; skipping DeepL translation.", UserWarning)
        return None
    # DeepL expects EN, ES, etc.
    tl = target_lang.upper()
    if tl == "EN":
        return text
    r = requests.post(
        "https://api-free.deepl.com/v2/translate",
        data={
            "auth_key": config.DEEPL_API_KEY,
            "text": text,
            "target_lang": tl,
        },
        timeout=30,
    )
    if not r.ok:
        warnings.warn(f"DeepL error: {r.status_code} {r.text}", UserWarning)
        return None
    data = r.json()
    if data.get("translations"):
        return data["translations"][0]["text"]
    return None


def _deepl_to_en(text: str) -> str | None:
    if not config.DEEPL_API_KEY:
        warnings.warn("DEEPL_API_KEY not set; skipping DeepL translation.", UserWarning)
        return None
    r = requests.post(
        "https://api-free.deepl.com/v2/translate",
        data={
            "auth_key": config.DEEPL_API_KEY,
            "text": text,
            "target_lang": "EN",
        },
        timeout=30,
    )
    if not r.ok:
        return None
    data = r.json()
    if data.get("translations"):
        return data["translations"][0]["text"]
    return None


def translate_to_english(text: str) -> tuple[str, str]:
    """Returns (translated_text, detected_lang_code)."""
    init_db()
    lang = detect_language(text)
    if lang == "en":
        return (text, "en")
    db = SessionLocal()
    try:
        cached = _get_cached(db, text, "EN")
        if cached:
            return (cached, lang)
        translated = _deepl_to_en(text)
        if translated:
            _set_cached(db, text, "EN", translated)
            return (translated, lang)
    finally:
        db.close()
    return (text, lang)


def translate_response(text: str, target_lang: str) -> str:
    if target_lang == "en" or not text:
        return text
    init_db()
    db = SessionLocal()
    try:
        cached = _get_cached(db, text, target_lang.upper())
        if cached:
            return cached
        out = _deepl(text, target_lang)
        if out:
            _set_cached(db, text, target_lang.upper(), out)
            return out
    finally:
        db.close()
    return text
