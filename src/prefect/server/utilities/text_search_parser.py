"""Text search query parser

Parses text search queries according to the following syntax:

- Space-separated terms → OR logic (include)
- Prefix with `-` or `!` → Exclude term
- Prefix with `+` → Required term (AND logic, future)
- Quote phrases → Match exact phrase
- Backslash escapes → Allow quotes within phrases (\")
- Case-insensitive, substring matching
- 200 character limit
"""

from dataclasses import dataclass, field


@dataclass
class TextSearchQuery:
    """Parsed text search query structure"""

    include: list[str] = field(default_factory=list)  # OR terms
    exclude: list[str] = field(default_factory=list)  # NOT terms (-/!)
    required: list[str] = field(default_factory=list)  # AND terms (+)


def parse_text_search_query(query: str) -> TextSearchQuery:
    """Parse a text search query string into structured components

    Args:
        query: The query string to parse

    Returns:
        TextSearchQuery with parsed include/exclude/required terms
    """

    # Handle empty/whitespace-only queries
    if not query.strip():
        return TextSearchQuery()

    result = TextSearchQuery()
    i = 0

    while i < len(query):
        # Skip whitespace
        if query[i].isspace():
            i += 1
            continue

        # Check for prefix
        prefix = None
        if query[i] in "-!+":
            prefix_char = query[i]
            prefix_pos = i
            i += 1

            # Check if this is immediately followed by a non-whitespace character
            if i < len(query) and not query[i].isspace():
                # Valid prefix (no space between prefix and term)
                prefix = prefix_char
            else:
                # Prefix followed by space - ignore the prefix completely
                i = prefix_pos + 1  # Skip the prefix character
                prefix = None
                continue

        # Handle quoted phrases
        if i < len(query) and query[i] == '"':
            i += 1  # Skip opening quote
            phrase_start = i

            # Find closing quote, handling escaped quotes
            while i < len(query):
                if query[i] == "\\" and i + 1 < len(query):
                    # Skip escaped character
                    i += 2
                elif query[i] == '"':
                    # Found unescaped closing quote
                    break
                else:
                    i += 1

            # Extract phrase (even if quote is unclosed)
            phrase = query[phrase_start:i]

            if i < len(query):  # Found closing quote
                i += 1  # Skip closing quote

            # Unescape quotes and backslashes in the phrase
            phrase = _unescape_phrase(phrase)

            # Add to appropriate list based on prefix
            if phrase.strip():
                if prefix == "-" or prefix == "!":
                    result.exclude.append(phrase)
                elif prefix == "+":
                    result.required.append(phrase)
                else:
                    result.include.append(phrase)
            continue

        # Handle regular terms
        if i < len(query):
            term_start = i

            # Find end of term (next whitespace or quote)
            while i < len(query) and not query[i].isspace() and query[i] != '"':
                i += 1

            term = query[term_start:i]

            # Add to appropriate list based on prefix
            if term:
                if prefix == "-" or prefix == "!":
                    result.exclude.append(term)
                elif prefix == "+":
                    result.required.append(term)
                else:
                    result.include.append(term)

    return result


def _unescape_phrase(phrase: str) -> str:
    """Unescape quotes and backslashes in a quoted phrase"""
    # Process escapes in order: first backslashes, then quotes
    result = []
    i = 0
    while i < len(phrase):
        if phrase[i] == "\\" and i + 1 < len(phrase):
            next_char = phrase[i + 1]
            if next_char == '"':
                result.append('"')
                i += 2
            elif next_char == "\\":
                result.append("\\")
                i += 2
            else:
                # Not an escape sequence, keep the backslash
                result.append("\\")
                i += 1
        else:
            result.append(phrase[i])
            i += 1
    return "".join(result)
