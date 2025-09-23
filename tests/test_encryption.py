from sdk_reforge.encryption import Encryption


class TestEncryption:
    def test_encryption(self):
        secret = Encryption.generate_new_hex_key()

        enc = Encryption(secret)

        clear_text = "hello world"
        encrypted = enc.encrypt(clear_text)
        assert enc.decrypt(encrypted) == clear_text
