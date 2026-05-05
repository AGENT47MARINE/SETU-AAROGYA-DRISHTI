import re

class PrivacyFilter:
    """
    Strips PII (Personal Identifiable Information) from text.
    Handles Phone numbers, Email addresses, and generic patterns.
    Note: Phase 2 will integrate Indic-aware NER for name stripping.
    """
    def __init__(self):
        self.phone_regex = re.compile(r'(\+91[\-\s]?)?[0-9]{10}')
        self.email_regex = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

    def strip_pii(self, text: str) -> str:
        """
        Replaces PII with [REDACTED].
        """
        text = self.phone_regex.sub("[PHONE_REDACTED]", text)
        text = self.email_regex.sub("[EMAIL_REDACTED]", text)
        return text

if __name__ == "__main__":
    p = PrivacyFilter()
    sample = "Mera number 9876543210 hai aur email test@gmail.com hai."
    print(p.strip_pii(sample))
