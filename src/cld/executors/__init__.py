from cld.executors.base import Executor

KNOWN_EXECUTORS = ("gemini", "composer")

def get_executor(name: str, **kwargs) -> Executor:
    """Factory to get an executor by name."""
    clean_name = name.strip().lower()

    if clean_name == "gemini":
        from cld.executors.gemini import GeminiExecutor
        return GeminiExecutor(**kwargs)
    elif clean_name == "composer":
        from cld.executors.composer import ComposerExecutor
        return ComposerExecutor(**kwargs)
    else:
        raise ValueError(
            f"Unknown executor: '{name}'. Known executors are: {', '.join(KNOWN_EXECUTORS)}"
        )
