def sanitize_session_name(name: str) -> str:
    """Prevents Path Traversal attacks by sanitizing filenames."""
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip())
    # Collapse consecutive underscores into a single underscore
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized
