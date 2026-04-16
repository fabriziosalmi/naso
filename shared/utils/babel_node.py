import re
import unicodedata
import logging

logger = logging.getLogger("naso-babel")

class BabelNode:
    """
    NASO NLP & Data Extraction Node.
    Filters by cybercrime-relevant languages and extracts Named Entities (NER) via robust heuristics.
    """
    
    # regex pattern robusti (non-exhaustive in locale, ma Enterprise-shaped)
    REGEX_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    REGEX_IPV4 = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")
    REGEX_BTC_ADDRESS = re.compile(r"\b(?:1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,39}\b")
    REGEX_XMR_ADDRESS = re.compile(r"\b(?:4|8)[0-9a-zA-Z]{94}\b")
    
    # Rilevamento esoterico multilingua (Block Ranges)
    LANG_BLOCKS = {
        "Cyrillic (Russian/Ukrainian)":     (0x0400, 0x04FF),
        "CJK (Chinese)":                    (0x4E00, 0x9FFF),
        "Devanagari (Hindi)":               (0x0900, 0x097F),
        "Arabic (Arabic/Farsi)":            (0x0600, 0x06FF),
        "Hebrew (Israeli)":                 (0x0590, 0x05FF)
    }

    @classmethod
    def detect_languages(cls, text: str) -> list[str]:
        """Scansiona i blocchi Unicode per capire in quale lingua "criptica" è scritto il leak."""
        detected = set()
        
        # O(N) pass, we sample max 1000 chars per speed in workers
        sample_text = text[:1000]
        
        for char in sample_text:
            code = ord(char)
            for lang, (start, end) in cls.LANG_BLOCKS.items():
                if start <= code <= end:
                    detected.add(lang)
                    break
                    
        # Check latini specifici (Romanian: ș, ț, ă / Spanish: ñ, ¿, ¡)
        if "ș" in sample_text or "ț" in sample_text or "ă" in sample_text:
            detected.add("Latin (Romanian)")
        if "ñ" in sample_text or "¿" in sample_text:
            detected.add("Latin (Spanish)")
            
        # Fallback se ci sono solo ascii
        if not detected and sample_text.strip():
            detected.add("Latin (English/Generic)")
            
        return list(detected)

    @classmethod
    def extract_entities(cls, text: str) -> dict:
        """Estrae gli asset infrastrutturali/economici dal testo."""
        return {
            "emails": list(set(cls.REGEX_EMAIL.findall(text))),
            "ips": list(set(cls.REGEX_IPV4.findall(text))),
            "btc_wallets": list(set(cls.REGEX_BTC_ADDRESS.findall(text))),
            "xmr_wallets": list(set(cls.REGEX_XMR_ADDRESS.findall(text)))
        }
        
    @classmethod
    def process_leak(cls, raw_content: str) -> dict:
        """EntryPoint per il NLP pre-Triage."""
        try:
            langs = cls.detect_languages(raw_content)
            entities = cls.extract_entities(raw_content)
            
            logger.info(f"[BABEL NODE] Detected languages: {langs} | Entities found: {len(entities['emails'])} emails, {len(entities['btc_wallets'])} BTC")
            
            return {
                "detected_languages": langs,
                "extracted_entities": entities,
                "needs_translation": any(lang for lang in langs if "Latin" not in lang) # Flag per future translation pipeline
            }
        except Exception as e:
            logger.error(f"[BABEL NODE] Processing failed: {e}")
            return {"detected_languages": [], "extracted_entities": {}}

babel_node = BabelNode()
