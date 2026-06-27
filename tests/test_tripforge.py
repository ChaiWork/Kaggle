# File: tests/test_tripforge.py
# Purpose: Comprehensive unit tests to verify TripForge utilities and security features.
# Competition Concept: Verification Plan

import pytest
import os
import json
from tripforge.utils.security import (
    sanitize_destination,
    sanitize_budget,
    scrub_pii,
    get_machine_key,
    encrypt_profile,
    decrypt_profile_content,
    sign_tool_call,
    verify_tool_call
)

def test_sanitize_destination():
    # Valid cities
    assert sanitize_destination("Paris") == "Paris"
    assert sanitize_destination("tokyo ") == "Tokyo"
    assert sanitize_destination("I want to visit New York!") == "New York"
    
    # Invalid cities
    with pytest.raises(ValueError):
        sanitize_destination("London")
        
    # Code injection attempt
    with pytest.raises(ValueError):
        sanitize_destination("Paris; cat /etc/passwd")

def test_sanitize_budget():
    # Valid range
    assert sanitize_budget(1500.0) == 1500.0
    assert sanitize_budget("3000") == 3000.0
    
    # Invalid values or out of range
    with pytest.raises(ValueError):
        sanitize_budget(5.0)  # Too low
    with pytest.raises(ValueError):
        sanitize_budget(2000000.0)  # Too high
    with pytest.raises(ValueError):
        sanitize_budget("free")  # Not numeric

def test_scrub_pii():
    log_text = "User email is test@domain.com and passport is AB1234567. Phone number +1-555-123-4567."
    scrubbed = scrub_pii(log_text)
    
    assert "test@domain.com" not in scrubbed
    assert "+1-555-123-4567" not in scrubbed
    assert "[REDACTED EMAIL]" in scrubbed
    assert "[REDACTED PHONE]" in scrubbed

def test_profile_encryption_decryption():
    profile = {
        "name": "Jane Doe",
        "travelers": 3,
        "accessibility_needs": "wheelchair",
        "dietary_restrictions": "vegan",
        "interests": ["art", "gardens"]
    }
    
    # Test valid encryption and decryption
    encrypted = encrypt_profile(profile)
    assert isinstance(encrypted, bytes)
    
    decrypted = decrypt_profile_content(encrypted)
    assert decrypted["name"] == "Jane Doe"
    assert decrypted["travelers"] == 3
    assert decrypted["dietary_restrictions"] == "vegan"
    
    # Test rejection of sensitive payment PII
    profile_with_card = profile.copy()
    profile_with_card["payment_note"] = "My card is 4111 1111 1111 1111"
    
    with pytest.raises(ValueError):
        encrypt_profile(profile_with_card)

def test_tool_call_signing():
    tool_name = "get_weather"
    params = {"city": "Paris", "date": "2025-08-15"}
    
    sig = sign_tool_call(tool_name, params)
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA-256 hex digest length
    
    # Valid signature check
    assert verify_tool_call(tool_name, params, sig) is True
    
    # Tampered params check
    tampered_params = params.copy()
    tampered_params["date"] = "2025-08-16"
    assert verify_tool_call(tool_name, tampered_params, sig) is False
