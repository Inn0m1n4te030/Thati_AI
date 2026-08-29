"""Safe provider errors. Details stay server-side; API clients get a code only."""


class ProviderError(Exception):
    """Gemini or other provider call failed."""


class ProviderUnavailableError(Exception):
    """Live mode is selected but the provider cannot be used."""
