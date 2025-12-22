"""
Text wrapping utilities for fiscal printer (CTS310II)

This module provides text wrapping functions that respect word boundaries
and handle the printer's line width constraints (48 characters per line).
"""


def wrap_text_to_lines(text, max_chars=48, max_lines=3):
    """
    Wrap text into lines respecting word boundaries.

    Args:
        text (str): Text to wrap
        max_chars (int): Maximum characters per line (default: 48 for CTS310II)
        max_lines (int): Maximum number of lines (default: 3)

    Returns:
        list[str]: List of wrapped lines (may be fewer than max_lines)

    Examples:
        >>> wrap_text_to_lines("Short text", 48, 3)
        ['Short text']

        >>> wrap_text_to_lines("A very long product description that needs wrapping", 48, 3)
        ['A very long product description that needs', 'wrapping']

        >>> wrap_text_to_lines("Exactly 48 characters in this line for testing!", 48, 3)
        ['Exactly 48 characters in this line for testing!']
    """
    # Handle empty or None input
    if not text or not text.strip():
        return []

    text = text.strip()
    lines = []

    while text and len(lines) < max_lines:
        # If text fits in one line, add and break
        if len(text) <= max_chars:
            lines.append(text)
            break

        # Find last space within max_chars
        split_pos = text.rfind(' ', 0, max_chars + 1)

        # If no space found (single long word), force split at max_chars
        if split_pos == -1 or split_pos == 0:
            split_pos = max_chars

        # Extract line and update remaining text
        lines.append(text[:split_pos].rstrip())
        text = text[split_pos:].lstrip()

    return lines


def distribute_text_bottom_up(text, num_lines=3, max_chars=48):
    """
    Distribute text from bottom line upward (line 3 → 2 → 1).

    This function ensures that line 3 (the bottom line) always has content,
    with additional lines filled upward as needed.

    Args:
        text (str): Text to distribute
        num_lines (int): Number of lines to fill (default: 3)
        max_chars (int): Characters per line (default: 48)

    Returns:
        list[str]: Lines in order [line1, line2, line3], with line3 guaranteed non-empty

    Examples:
        >>> distribute_text_bottom_up("Product Name", 3, 48)
        ['', '', 'Product Name']

        >>> distribute_text_bottom_up("Very Long Product Name That Spans Multiple Lines", 3, 48)
        ['', 'Very Long Product Name That Spans', 'Multiple Lines']

        >>> distribute_text_bottom_up("A B C D E F G H I J K L M N O P Q R S T U V W X Y Z " * 3, 3, 48)
        ['A B C D E F G H I J K L M N O P Q R S T U V W X', 'Y Z A B C D E F G H I J K L M N O P Q R S T U V', 'W X Y Z A B C D E F G H I J K L M N O P Q R S']
    """
    wrapped = wrap_text_to_lines(text, max_chars, num_lines)

    # Create result array with empty strings
    result = [''] * num_lines

    # Fill from bottom up (reverse index)
    for i, line in enumerate(reversed(wrapped)):
        result[num_lines - 1 - i] = line

    return result
