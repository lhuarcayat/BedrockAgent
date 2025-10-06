def clean_text_for_json(text):
    """
    Clean text to remove unusual line terminators and other problematic characters
    that can break JSON parsing and file handling.
    """
    if not isinstance(text, str):
        return text
    
    import unicodedata
    
    # Remove unusual line terminators
    text = text.replace('\u2028', ' ')  # Line Separator (LS)
    text = text.replace('\u2029', ' ')  # Paragraph Separator (PS)
    text = text.replace('\u000B', ' ')  # Vertical Tab
    text = text.replace('\u000C', ' ')  # Form Feed
    text = text.replace('\u0085', ' ')  # Next Line (NEL)
    
    # Remove other control characters that can cause issues
    text = ''.join(char for char in text if unicodedata.category(char) not in ['Cc', 'Cf'] or char in ['\n', '\r', '\t'])
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text