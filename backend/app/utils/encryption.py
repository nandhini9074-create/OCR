import os
from pathlib import Path
from cryptography.fernet import Fernet

class TokenEncryption:
    def __init__(self):
        # Determine encryption key
        key = os.getenv("ENCRYPTION_KEY") or os.environ.get("ENCRYPTION_KEY")
        
        if not key:
            # Fallback to local cached file inside workspace
            cache_dir = Path(__file__).resolve().parents[2] / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            key_file = cache_dir / "encryption.key"
            
            if key_file.exists():
                key = key_file.read_text(encoding="utf-8").strip()
            else:
                key = Fernet.generate_key().decode("utf-8")
                key_file.write_text(key, encoding="utf-8")
        
        self.fernet = Fernet(key.encode("utf-8"))

    def encrypt(self, text: str) -> str:
        """Encrypt plain text data into a secure encrypted string."""
        if not text:
            return ""
        return self.fernet.encrypt(text.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt encrypted text data back into plain text."""
        if not encrypted_text:
            return ""
        return self.fernet.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")

# Singleton helper
_encryption_instance = None

def get_encryptor() -> TokenEncryption:
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = TokenEncryption()
    return _encryption_instance
