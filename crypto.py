import json
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from hashlib import sha256

class AESGCMCrypto:
    @staticmethod
    def get_secret_key() -> str:
        return '3a374c6f0e20f5656bb4b745ac8c0cb15056a339bc7a7bf836632b7b5143c7dd'

    @staticmethod
    def encrypt(plain_text: str, secret_key: str) -> str:
        # Derive AES-256 key from SHA-256 hash of secret key
        key = sha256(secret_key.encode()).digest()  # 32 bytes

        # Generate 12-byte IV
        iv = os.urandom(12)

        # Encrypt
        aesgcm = AESGCM(key)
        cipher_text = aesgcm.encrypt(iv, plain_text.encode('utf-8'), None)  # tag appended automatically

        # Combine IV + cipher_text
        combined = iv + cipher_text

        # Encode as Base64
        return base64.b64encode(combined).decode('utf-8')

    @staticmethod
    def decrypt(encrypted_b64: str, secret_key: str) -> str:
        try:
            # Decode Base64
            combined = base64.b64decode(encrypted_b64)

            # Extract IV (12 bytes) and ciphertext+tag
            iv = combined[:12]
            ciphertext = combined[12:]

            # Derive AES-256 key
            key = sha256(secret_key.encode()).digest()

            # Decrypt
            aesgcm = AESGCM(key)
            decrypted = aesgcm.decrypt(iv, ciphertext, None)

            return decrypted.decode('utf-8')
        except Exception as e:
            print("Decryption failed:", e)
            return None

