import secrets

# Generate a 32-byte (256-bit) random key and convert it to a hex string
secret_key = secrets.token_hex(32)
print("\nHere's your secure secret key for production:")
print("-" * 70)
print(secret_key)
print("-" * 70)
print("\nAdd this to your .env file as:")
print("SECRET_KEY=" + secret_key)
print()
