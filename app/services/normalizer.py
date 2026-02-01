import base64
import re
import unicodedata


class Normalizer:
    """
    text normalizer that standardizes input for security checking
    helps catch obfuscated malicious prompts
    """
    
    # leetspeak mapping
    LEETSPEAK_MAP = {
        '1': 'i',
        '3': 'e',
        '4': 'a',
        '0': 'o',
        '5': 's',
        '7': 't',
    }
    
    def __init__(self):
        # compile regex patterns for efficiency
        self.base64_pattern = re.compile(r'[A-Za-z0-9+/]{20,}={0,2}')
        self.multi_space_pattern = re.compile(r'\s+')
    
    def normalize(self, text: str) -> str:
        """
        normalize text through multiple transformations
        returns cleaned, standardized text for security analysis
        """
        if not text:
            return ""
        
        # step 1: decode any base64 strings
        text = self._decode_base64(text)
        
        # step 2: convert to lowercase
        text = text.lower()
        
        # step 3: convert leetspeak to normal characters
        text = self._convert_leetspeak(text)
        
        # step 4: normalize unicode homoglyphs to ascii
        text = self._normalize_unicode(text)
        
        # step 5: collapse multiple spaces
        text = self._collapse_spaces(text)
        
        return text.strip()
    
    def _decode_base64(self, text: str) -> str:
        """
        detect and decode base64 strings inline
        """
        def decode_match(match):
            try:
                encoded = match.group(0)
                # try to decode as base64
                decoded = base64.b64decode(encoded, validate=True).decode('utf-8', errors='ignore')
                # only return decoded if it looks like text (printable chars)
                if decoded and all(c.isprintable() or c.isspace() for c in decoded):
                    return decoded
            except Exception:
                pass
            return match.group(0)
        
        return self.base64_pattern.sub(decode_match, text)
    
    def _convert_leetspeak(self, text: str) -> str:
        """
        convert leetspeak characters to normal letters
        """
        result = []
        for char in text:
            result.append(self.LEETSPEAK_MAP.get(char, char))
        return ''.join(result)
    
    def _normalize_unicode(self, text: str) -> str:
        """
        normalize unicode homoglyphs to ascii equivalents
        uses NFKD normalization which decomposes characters
        """
        # NFKD normalization decomposes characters
        normalized = unicodedata.normalize('NFKD', text)
        # encode to ascii, ignoring non-ascii chars
        ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
        return ascii_text
    
    def _collapse_spaces(self, text: str) -> str:
        """
        collapse multiple whitespace characters into single spaces
        """
        return self.multi_space_pattern.sub(' ', text)
