from .registry import registry
from .native_adapter import NativeAgentReadAdapter
from .langchain_adapter import LangchainAdapter
from .template_adapter import AgentTemplateAdapter

# Register native adapters by default
registry.register_adapter(NativeAgentReadAdapter())
registry.register_adapter(LangchainAdapter())
registry.register_adapter(AgentTemplateAdapter())
