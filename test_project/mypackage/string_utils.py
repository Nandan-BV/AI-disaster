"""String utilities module with intentional bugs fixed."""

def reverse_string(s: str) -> str:
    """Reverse a string."""
    return s[::-1]


def capitalize_words(s: str) -> str:
    """Capitalize each word in a string."""
    return ' '.join(word.capitalize() for word in s.split())


def count_vowels(s: str) -> int:
    """Count vowels in a string."""
    vowels = "aeiouAEIOU"
    return sum(1 for char in s if char in vowels)


def is_palindrome(s: str) -> bool:
    """Check if string is a palindrome."""
    cleaned = s.lower().replace(" ", "")
    return cleaned == cleaned[::-1]