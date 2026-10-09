"""Tests for string_utils module."""

import pytest
from mypackage.string_utils import reverse_string, capitalize_words, count_vowels, is_palindrome


def test_reverse_string():
    assert reverse_string("hello") == "olleh"
    assert reverse_string("Python") == "nohtyP"
    assert reverse_string("") == ""
    assert reverse_string("a") == "a"


def test_capitalize_words():
    assert capitalize_words("hello world") == "Hello World"
    assert capitalize_words("python programming") == "Python Programming"
    assert capitalize_words("") == ""
    assert capitalize_words("single") == "Single"


def test_count_vowels():
    assert count_vowels("hello") == 2
    assert count_vowels("PYTHON") == 0
    assert count_vowels("aeiou") == 5
    assert count_vowels("") == 0


def test_is_palindrome():
    assert is_palindrome("racecar") is True
    assert is_palindrome("A man a plan a canal Panama") is True
    assert is_palindrome("hello") is False
    assert is_palindrome("") is True