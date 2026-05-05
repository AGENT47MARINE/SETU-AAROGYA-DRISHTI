try:
    import torch
    from transformers import pipeline
    HAS_TRANSFORMERS = True
except Exception:
    torch = None
    pipeline = None
    HAS_TRANSFORMERS = False

class EntityExtractor:
    """
    Extracts medical entities. 
    Includes a lightweight keyword-based fallback for demo/low-bandwidth environments.
    """
    def __init__(self, model_name="d4data/biomedical-ner-all"):
        self.ner_pipeline = None
        self.keywords = {
            "fever": "SYMPTOM",
            "cough": "SYMPTOM",
            "dizziness": "SYMPTOM",
            "chakkar": "SYMPTOM",
            "stomach pain": "SYMPTOM",
            "vomiting": "SYMPTOM",
            "paracetamol": "DRUG",
            "coldrif": "DRUG",
            "dolo 650": "DRUG"
        }
        
        print(f"Attempting to load Medical NER model: {model_name}...")
        if HAS_TRANSFORMERS:
            try:
                self.ner_pipeline = pipeline(
                    "ner", 
                    model=model_name, 
                    aggregation_strategy="simple",
                    device=0 if (torch and torch.cuda.is_available()) else -1,
                )
                print("Medical NER model loaded.")
            except Exception as e:
                print(f"NER Model load failed or skipped: {e}. Using Keyword Mock Mode.")
        else:
            print("Transformers not installed. Using Keyword Mock Mode.")

    def extract(self, text: str):
        if not text.strip():
            return []
            
        # Try pipeline if available
        if self.ner_pipeline:
            try:
                results = self.ner_pipeline(text)
                return [{"text": res["word"], "label": res["entity_group"], "confidence": float(res["score"])} for res in results]
            except Exception as e:
                print(f"Pipeline extraction failed: {e}. Falling back to keywords.")
        
        # Keyword Mock Fallback
        entities = []
        lower_text = text.lower()
        for kw, label in self.keywords.items():
            if kw in lower_text:
                entities.append({
                    "text": kw,
                    "label": label,
                    "confidence": 0.95
                })
        return entities
