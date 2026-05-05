import asyncio
from .language_detector import LanguageDetector
from .normalizer import ScriptNormalizer
from .translator import Translator
from .entity_extractor import EntityExtractor
from .entity_mapper import EntityMapper
from .privacy_filter import PrivacyFilter

class NLPController:
    """
    Orchestrates the full NLP pipeline:
    De-identification -> Detection -> Normalization -> Translation -> NER -> Ontology Mapping
    """
    def __init__(self):
        self.privacy = PrivacyFilter()
        self.detector = LanguageDetector()
        self.normalizer = ScriptNormalizer()
        self.translator = Translator(use_local=False) # Default to API for now
        self.extractor = EntityExtractor()
        self.mapper = EntityMapper()

    async def process_text(self, text: str):
        # 1. Strip PII (De-identification)
        clean_text = self.privacy.strip_pii(text)
        
        # 2. Detect Language
        lang = self.detector.detect(clean_text)
        
        # 3. Normalize (if Indic)
        normalized_text = self.normalizer.normalize(clean_text, lang)
        
        # 4. Translate to English (if not already English)
        if lang != 'en':
            english_text = await self.translator.translate(normalized_text, lang)
        else:
            english_text = normalized_text
            
        # 4. Extract Entities
        entities = self.extractor.extract(english_text)
        
        # 5. Map to Ontology
        mapped_entities = []
        for ent in entities:
            mapping = self.mapper.map_to_ontology(ent["text"])
            mapped_entities.append({
                **ent,
                "ontology_code": mapping["code"],
                "ontology_system": mapping["system"]
            })
            
        return {
            "original_text": text,
            "detected_lang": lang,
            "translated_text": english_text,
            "entities": mapped_entities
        }

if __name__ == "__main__":
    async def test():
        ctrl = NLPController()
        sample = "Paracetamol lene ke baad chakkar aa raha hai"
        result = await ctrl.process_text(sample)
        import json
        print(json.dumps(result, indent=2))
    
    asyncio.run(test())
