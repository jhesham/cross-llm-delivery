from cld.executors.base import Executor
from cld.providers_api import get_provider, load_providers, all_providers


def get_executor(name: str, **kwargs) -> Executor:
    """Factory to get an executor by name, resolved via the provider registry."""
    load_providers()
    return get_provider(name.strip().lower()).make_executor(**kwargs)
