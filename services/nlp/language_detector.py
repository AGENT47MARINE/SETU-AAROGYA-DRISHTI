import os

try:
    import fasttext
    HAS_FASTTEXT = True
except ImportError:
    HAS_FASTTEXT = False
    try:
        from langdetect import detect as ld_detect
        HAS_LANGDETECT = True
    except ImportError:
        HAS_LANGDETECT = False

class LanguageDetector:
    """
    Language detection service.
    Primary: FastText (high speed)
    Fallback: langdetect (pure python)
    """
    def __init__(self, model_path=None):
        self.model = None
        if HAS_FASTTEXT:
            if model_path is None:
                model_path = os.path.join(os.path.dirname(__file__), "models", "lid.176.bin")
            
            if os.path.exists(model_path):
                self.model = fasttext.load_model(model_path)
            else:
                print(f"FastText model not found at {model_path}. Using fallback.")

    def detect(self, text: str) -> str:
        if not text.strip():
            return "unknown"
            
        if HAS_FASTTEXT and self.model:
            text_clean = text.replace('\n', ' ').strip()
            predictions = self.model.predict(text_clean, k=1)
            return predictions[0][0].replace('__label__', '')
        
        if HAS_LANGDETECT:
            try:
                return ld_detect(text)
            except:
                return "unknown"
                
        return "unknown"

if __name__ == "__main__":
    detector = LanguageDetector()
    sample = "Paracetamol lene ke baad chakkar aa raha hai"
    print(f"Detected: {detector.detect(sample)}")
