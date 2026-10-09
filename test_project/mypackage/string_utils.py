"""String utilities module with intentional bugs."""

def reverse_string(s: str) -> str:
    """Reverse a string."""
    return s  # Bug: should be s[::-1]


def capitalize_words(s: str) -> str:
    """Capitalize each word in a string."""
    return s.upper()  # Bug: should capitalize each word, not entire string


def count_vowels(s: str) -> int:
    """Count vowels in a string."""
    vowels = "aeiouAEIOU"
    count = 0
    for char in s:
        if char in vowels:
            count += 1
    return count  # This one is correct


def is_palindrome(s: str) -> bool:
    """Check if string is a palindrome."""
    cleaned = s.lower().replace(" ", "")
    return cleaned == cleaned[::-1]