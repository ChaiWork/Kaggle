# File: tripforge/utils/security.py
# Purpose: Core security module containing PII scrubbing, encryption, sanitization, and signature verification.
# Competition Concept: Security implementations

import os
import re
import uuid
import hmac
import json
import base64
import socket
import getpass
import hashlib
from typing import Dict, Any, Tuple
import click
from cryptography.fernet import Fernet

# Regex patterns for validation and PII scrubbing
EMAIL_REGEX = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
PHONE_REGEX = re.compile(r'\b(?:\+?\d{1,3}[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b')
CREDIT_CARD_REGEX = re.compile(r'\b(?:\d[ -]*?){13,19}\b')
# Broad passport regex (e.g., 9-digit alphanumeric patterns, sometimes mixed with prefix letters)
PASSPORT_REGEX = re.compile(r'\b[A-PR-WY0-9][1-9]\d\s?\d{4}[1-9]\b|\b[a-zA-Z0-9]{9}\b')

# Known cities list for sanitization
ALLOWED_CITIES = {"paris", "tokyo", "barcelona", "new york", "bali"}

def get_machine_key() -> bytes:
    """
    Derives a stable, machine-specific base64-encoded Fernet key.
    Does not write or store the key on disk.
    """
    try:
        node = uuid.getnode()
        username = getpass.getuser()
        hostname = socket.gethostname()
        # Combine parameters into a unique machine fingerprint
        fingerprint = f"{node}-{username}-{hostname}".encode("utf-8")
        key_hash = hashlib.sha256(fingerprint).digest()
        return base64.urlsafe_b64encode(key_hash)
    except Exception:
        # Fallback if host parameters fail
        fallback = b"tripforge-default-stable-secret-key-32b!"
        key_hash = hashlib.sha256(fallback).digest()
        return base64.urlsafe_b64encode(key_hash)

def validate_no_sensitive_pii(data: Dict[str, Any]) -> None:
    """
    Validates that a dictionary does not contain credit cards, passport numbers, or payment info.
    Raises ValueError if detected.
    """
    for key, value in data.items():
        val_str = str(value)
        # Check credit card
        if CREDIT_CARD_REGEX.search(val_str):
            raise ValueError(f"Security Block: Credit card or payment details detected in field '{key}'!")
        # Check passport (excluding cases that look like simple short integers)
        if len(val_str) >= 6 and PASSPORT_REGEX.search(val_str):
            # Narrow check to prevent false positives on simple zip codes or dates
            if not val_str.isdigit() or len(val_str) > 6:
                raise ValueError(f"Security Block: Passport number or sensitive ID detected in field '{key}'!")

def encrypt_profile(profile_dict: Dict[str, Any]) -> bytes:
    """
    Encrypts the profile dictionary using Fernet symmetric encryption.
    """
    validate_no_sensitive_pii(profile_dict)
    key = get_machine_key()
    fernet = Fernet(key)
    serialized = json.dumps(profile_dict).encode("utf-8")
    return fernet.encrypt(serialized)

def decrypt_profile_content(encrypted_data: bytes) -> Dict[str, Any]:
    """
    Decrypts encrypted profile content using the derived machine key.
    """
    key = get_machine_key()
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted_data)
    return json.loads(decrypted.decode("utf-8"))

def sanitize_destination(text: str) -> str:
    """
    Strips code injection attempts and validates the destination against the allowed city list.
    """
    # Detect shell or command injection characters
    if re.search(r'[;&|`$*<>\\%]', text):
        raise ValueError("Security block: Special characters or potential code injection detected.")
        
    # Strip HTML tags
    cleaned = re.sub(r'<[^>]*?>', '', text)
    cleaned = cleaned.strip()
    
    cleaned_lower = cleaned.lower()
    # Check if we match one of the allowed cities
    matched = None
    for city in ALLOWED_CITIES:
        if city in cleaned_lower:
            matched = city.title()
            break
            
    if not matched:
        # Allow other destinations but sanitize and format them
        return cleaned.title()
    return matched

def sanitize_budget(value: Any) -> float:
    """
    Validates that a budget value is numeric and within a reasonable range ($10 - $1,000,000).
    """
    try:
        num = float(value)
    except (ValueError, TypeError):
        raise ValueError("Budget must be a numeric value.")
        
    if num < 10.0 or num > 1000000.0:
        raise ValueError("Budget must be between $10 and $1,000,000.")
    return num

def scrub_pii(text: str) -> str:
    """
    Redacts email, phone number, credit card, and passport patterns from log text.
    """
    scrubbed = EMAIL_REGEX.sub("[REDACTED EMAIL]", text)
    scrubbed = PHONE_REGEX.sub("[REDACTED PHONE]", scrubbed)
    scrubbed = CREDIT_CARD_REGEX.sub("[REDACTED CARD]", scrubbed)
    scrubbed = PASSPORT_REGEX.sub("[REDACTED PASSPORT/ID]", scrubbed)
    return scrubbed

def sign_tool_call(tool_name: str, params: Dict[str, Any]) -> str:
    """
    Generates an HMAC-SHA256 signature for an MCP tool call based on parameters.
    """
    key = get_machine_key()
    serialized = json.dumps(params, sort_keys=True)
    msg = f"{tool_name}:{serialized}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

def verify_tool_call(tool_name: str, params: Dict[str, Any], signature: str) -> bool:
    """
    Verifies that the HMAC-SHA256 signature matches for the given tool call.
    """
    key = get_machine_key()
    serialized = json.dumps(params, sort_keys=True)
    msg = f"{tool_name}:{serialized}".encode("utf-8")
    expected = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def guard_external_call(service_name: str, location_details: str = None) -> bool:
    """
    Guard rails for external data sync. Warns before sending data and requires
    consent when in live mode. In mock mode, skips prompts.
    """
    mode = os.getenv("TRIPFORGE_MODE", "live").lower()
    if mode == "mock":
        return True
        
    click.secho(f"\n[SECURITY GUARD] Warning: System is about to query an external service ({service_name}).", fg="yellow", bold=True)
    if location_details:
        click.secho(f"[SECURITY GUARD] Data sent includes location/query details: '{location_details}'", fg="yellow")
        
    # Check if we are running in web mode
    is_web = os.getenv("TRIPFORGE_WEB_MODE", "false").lower() == "true"
    if is_web:
        if os.getenv("TRIPFORGE_BYPASS_GUARD", "false").lower() == "true":
            click.secho("[SECURITY GUARD] Consent pre-granted by web user.", fg="green")
            return True
        else:
            click.secho("[SECURITY GUARD] Consent denied/not granted by web user. Falling back to cached/mock data.", fg="red", bold=True)
            return False

    # CLI fallback (interactive terminal prompt)
    if os.getenv("TRIPFORGE_BYPASS_GUARD", "false").lower() == "true":
        click.secho("[SECURITY GUARD] Consent automatically granted via environment flag.", fg="green")
        return True
        
    consent = click.confirm("[SECURITY GUARD] Do you grant permission to query this external API?", default=True)
    if not consent:
        click.secho("[SECURITY GUARD] Action blocked by user. Falling back to cached/mock data.", fg="red", bold=True)
    return consent
