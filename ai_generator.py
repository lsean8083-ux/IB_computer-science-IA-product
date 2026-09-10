"""Optional OpenAI contextual-passage integration; credentials are environment based."""
import math, os, re

def validate_passage(passage, target_words):
    found = [word for word in target_words if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", passage, re.I)]
    return found, len(found) >= math.ceil(len(target_words) * .80)

class ContextPassageGenerator:
    def generate(self, target_words, retries=1):
        if not 3 <= len(target_words) <= 8: raise ValueError("Select from 3 to 8 target words.")
        if not os.getenv("OPENAI_API_KEY"): raise RuntimeError("OPENAI_API_KEY is not configured; AI passage generation is unavailable.")
        try:
            from openai import OpenAI
            client = OpenAI()
            prompt = ("Write a professional, logically structured English passage. Use these vocabulary words naturally "
                      "and provide contextual clues to their meanings: " + ", ".join(target_words))
            for _ in range(retries + 1):
                response = client.responses.create(model="gpt-4.1-mini", input=prompt)
                passage = response.output_text.strip()
                found, valid = validate_passage(passage, target_words)
                if valid: return passage, found
            raise RuntimeError("The generated passage did not include at least 80% of the requested words.")
        except RuntimeError: raise
        except Exception as error: raise RuntimeError(f"AI passage generation failed: {error}") from error
