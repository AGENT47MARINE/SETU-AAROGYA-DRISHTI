try:
    from indicnlp.normalize.indic_normalize import IndicNormalizerFactory
    HAS_INDIC_NLP = True
except ImportError:
    HAS_INDIC_NLP = False

class ScriptNormalizer:
    """
    Normalizes Unicode representations of Indic scripts.
    Handles Devanagari (hi), Tamil (ta), Telugu (te), and Kannada (kn).
    """
    def __init__(self):
        self.normalizers = {}
        if HAS_INDIC_NLP:
            self.factory = IndicNormalizerFactory()
            # Pre-initialize normalizers for supported languages
            self.normalizers = {
                'hi': self.factory.get_normalizer('hi'),
                'ta': self.factory.get_normalizer('ta'),
                'te': self.factory.get_normalizer('te'),
                'kn': self.factory.get_normalizer('kn')
            }

    def normalize(self, text: str, lang: str) -> str:
        if HAS_INDIC_NLP and lang in self.normalizers:
            return self.normalizers[lang].normalize(text)
        return text

if __name__ == "__main__":
    normalizer = ScriptNormalizer()
    test_hi = "नमस्ते"
    print(f"Original: {test_hi} | Normalized: {normalizer.normalize(test_hi, 'hi')}")
