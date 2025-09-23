import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_LENGTH = 12
SEPARATOR = "--"


class DecryptionException(Exception):
    def __init__(self, message):
        super().__init__(message)


class Encryption:
    def __init__(self, secret):
        self.secret = bytes.fromhex(secret)
        self.input_secret = secret

    @staticmethod
    def generate_new_hex_key():
        return secrets.token_bytes(32).hex()

    def encrypt(self, clear_text):
        aesgcm = AESGCM(self.secret)
        nonce = secrets.token_bytes(NONCE_LENGTH)
        enc_and_tag = aesgcm.encrypt(nonce, bytes(clear_text, "utf-8"), None).hex()
        encrypted = enc_and_tag[:-32]
        tag = enc_and_tag[-32:]

        return SEPARATOR.join([encrypted, nonce.hex(), tag])

    def decrypt(self, encrypted_string):
        aesgcm = AESGCM(self.secret)
        encrypted, nonce, tag = [
            bytes.fromhex(x) for x in encrypted_string.split(SEPARATOR)
        ]
        return aesgcm.decrypt(nonce, encrypted + tag, None).decode("utf-8")
