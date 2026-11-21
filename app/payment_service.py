import re

def cleanCardNumber(card_number: str) -> str:
    """Removes spaces and hyphens from the card number string."""
    if not isinstance(card_number, str):
        return ""
    return re.sub(r"[\s-]", "", card_number)

def validateCard(card_number: str) -> bool:
    """
    Validates a payment card number:
    1. Checks if it contains only digits after removing spaces/hyphens.
    2. Verifies length is between 13 and 19 digits (ISO/IEC 7812).
    3. Verifies the checksum using the Luhn algorithm.
    """
    cleaned = cleanCardNumber(card_number)
    
    # Check length and ensure only digits remain
    if not cleaned.isdigit() or not (13 <= len(cleaned) <= 19):
        return False
        
    # Luhn Algorithm implementation
    total_sum = 0
    reverse_digits = [int(d) for d in reversed(cleaned)]
    
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:  # Every second digit from the right
            doubled = digit * 2
            if doubled > 9:
                doubled -= 9
            total_sum += doubled
        else:
            total_sum += digit
            
    return total_sum % 10 == 0

def getCardType(card_number: str) -> str:
    """
    Identifies the card issuer based on IIN/BIN prefix and length:
    - Visa: Starts with '4' (lengths 13, 16, 19)
    - MasterCard: Starts with 51-55 or 2221-2720 (length 16)
    - American Express: Starts with 34 or 37 (length 15)
    - JCB: Starts with 3528-3589 (lengths 16-19)
    """
    cleaned = cleanCardNumber(card_number)
    
    if not cleaned.isdigit():
        return "Unknown"
        
    # American Express (Amex)
    if cleaned.startswith(("34", "37")) and len(cleaned) == 15:
        return "American Express"
        
    # MasterCard
    if len(cleaned) == 16:
        prefix_2 = int(cleaned[:2]) if cleaned[:2].isdigit() else 0
        prefix_4 = int(cleaned[:4]) if cleaned[:4].isdigit() else 0
        if (51 <= prefix_2 <= 55) or (2221 <= prefix_4 <= 2720):
            return "MasterCard"
            
    # Visa
    if cleaned.startswith("4") and len(cleaned) in (13, 16, 19):
        return "Visa"

    # JCB
    if 16 <= len(cleaned) <= 19:
        prefix_4 = int(cleaned[:4]) if cleaned[:4].isdigit() else 0
        if 3528 <= prefix_4 <= 3589:
            return "JCB"
            
    return "Unknown"