import os
import httpx
try:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    HAS_LOCAL_TRANSLATION_DEPS = True
except Exception:
    torch = None
    AutoModelForSeq2SeqLM = None
    AutoTokenizer = None
    HAS_LOCAL_TRANSLATION_DEPS = False

class Translator:
    """
    Translator service for Indic -> English conversion.
    Supports local IndicTrans2 model with HuggingFace API fallback.
    """
    def __init__(self, model_name="ai4bharat/indictrans2-indic-en-dist-200M", use_local=True):
        self.use_local = use_local
        self.model_name = model_name
        self.hf_token = os.getenv("HF_TOKEN")
        self.api_url = f"https://api-inference.huggingface.co/models/{model_name}"
        
        if use_local and HAS_LOCAL_TRANSLATION_DEPS:
            try:
                print(f"Loading local translation model: {model_name}...")
                self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(
                    model_name, 
                    trust_remote_code=True,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
                )
                if torch.cuda.is_available():
                    self.model = self.model.to("cuda")
                print("Local translation model loaded successfully.")
            except Exception as e:
                print(f"Failed to load local model: {e}. Falling back to API mode.")
                self.use_local = False
        elif use_local and not HAS_LOCAL_TRANSLATION_DEPS:
            print("Local translation dependencies not installed. Falling back to API mode.")
            self.use_local = False

    async def translate(self, text: str, src_lang: str) -> str:
        """
        Translates text from src_lang to English.
        """
        if not text.strip():
            return ""
            
        if self.use_local:
            return self._translate_local(text, src_lang)
        else:
            return await self._translate_api(text, src_lang)

    def _translate_local(self, text: str, src_lang: str) -> str:
        # Simplified inference for local model
        # Note: IndicTrans2 requires specific prefix/formatting which the tokenizer usually handles
        inputs = self.tokenizer(text, return_tensors="pt")
        if torch and torch.cuda.is_available():
            inputs = inputs.to("cuda")
            
        with torch.no_grad():
            generated_tokens = self.model.generate(**inputs)
            
        result = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
        # Clean up CUDA cache after translation to save VRAM on 8GB cards
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
        return result

    async def _translate_api(self, text: str, src_lang: str) -> str:
        if not self.hf_token:
            return f"[UNTRANSLATED: {text}]"
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.hf_token}"},
                    json={"inputs": text},
                    timeout=30.0
                )
                if response.status_code == 200:
                    return response.json()[0].get("generated_text", text)
                else:
                    print(f"API Error: {response.status_code} - {response.text}")
                    return text
            except Exception as e:
                print(f"Translation API request failed: {e}")
                return text

if __name__ == "__main__":
    import asyncio
    async def test():
        t = Translator(use_local=False) # Use API for quick test
        res = await t.translate("नमस्ते", "hi")
        print(f"Translated: {res}")
    asyncio.run(test())
