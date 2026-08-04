from .client import YasinCoreClient
from yasin_core.config import (
    ConfigurationManager,
    ConfigurationValidationError,
    Settings,
)
from yasin_core.agents.base import BaseAgent
from yasin_core.agents.task import Task
from yasin_core.agents.runtime import IAgentRuntime, AgentRuntime
from yasin_core.context.manager import active_context, get_current_context
from yasin_core.context.engine import RuntimeContext, ContextEngine
from yasin_core.plugins.bridge import PluginExecutionBridge
from yasin_core.agents.tool import (
    BaseTool,
    FunctionTool,
    tool,
    ToolRegistry,
    ToolManager,
)
from yasin_core.events import Event, EventBus
from yasin_core.di import (
    DIContainer,
    IDIContainer,
    ServiceLifetime,
    DIError,
    DependencyResolutionError,
    CircularDependencyError,
)
from yasin_core.storage import (
    BaseStorage,
    JSONFileStorage,
    InMemoryStorage,
    StorageError,
    StorageConnectionError,
    StorageNotFoundError,
    StorageValidationError,
    get_storage,
    register_backend,
)
from yasin_core.core.orchestrator import RuntimeOrchestrator, RuntimeState, OrchestratorError
from yasin_core.observability import (
    MetricsRegistry,
    Metric,
    Counter,
    Gauge,
    Histogram,
    MetricType,
    BaseMetricProvider,
    InMemoryMetricProvider,
    ErrorTracker,
    ErrorRecord,
    PerformanceTimer,
    JSONFormatter,
    StructuredLogger,
    get_structured_logger,
    ObservabilityService,
)
from yasin_core.execution import Job, ExecutionTask, JobStatus, JobPriority, TaskExecutionEngine, Scheduler, ScheduledJob
from yasin_core.execution.distributed import (
    WorkerState,
    WorkerNode,
    BaseDistributedWorker,
    DistributedWorkerManager,
)

# Import AI Provider Layer
from yasin_core.providers import (
    AIProvider,
    AIChatMessage,
    AIRequest,
    AIResponse,
    AIResponseChunk,
    AIProviderError,
    AIProviderConnectionError,
    AIProviderAuthError,
    AIProviderRateLimitError,
    ProviderRegistry,
    ProviderManager,
    MockProvider,
    LocalProvider,
    OpenAICompatibleProvider,
)

# Import API Gateway components
from yasin_core.api import (
    APIRequest,
    APIResponse,
    APIError,
    APIErrorCode,
    BaseAuthenticator,
    APIKeyAuthenticator,
    APIGateway,
)

# Import Security components
from yasin_core.security import (
    SecurityError,
    AccessDeniedError,
    AuthenticationError,
    PermissionValidationError,
    Permission,
    Role,
    Subject,
    BasePolicy,
    DefaultRBACPolicy,
    PolicyEngine,
    ConfigurationSecurityValidator,
    SensitiveDataProtector,
    BaseCredentialStore,
    InMemoryCredentialStore,
    AuditLogger,
    SECURITY_EVENT_AUDIT,
    SECURITY_ACCESS_GRANTED,
    SECURITY_ACCESS_DENIED,
    SecurityManager,
    require_permission,
)

# Import SDK v2 Components
from .errors import (
    SDKError,
    SDKValidationError,
    SDKAuthenticationError,
    SDKConnectionError,
    SDKExecutionError,
    SDKDeprecationWarning,
    translate_core_errors,
)
from .models import SDKRequest, SDKResponse
from .interfaces import ISDKClient, ISDKAuthenticator
from .compat import SDKVersionChecker, deprecated, SDKMigrationHelper
from .async_client import AsyncYasinCoreClient

# Import Compatibility Framework components
from yasin_core.compatibility import (
    Version,
    is_compatible,
    VersionNegotiator,
    APICompatibilityChecker,
    DeprecationManager,
    LegacyAPIAdapter,
    SchemaMigrator,
    ConfigurationMigrator,
    DataMigrator,
    AgentCompatibilityValidator,
    HubCompatibilityValidator,
    RelayCompatibilityValidator,
    CLICompatibilityValidator,
    RuntimeCompatibilityChecker,
    CompatibilityManager,
    CompatibilityError,
    VersionMismatchError,
    APICompatibilityError,
    MigrationError,
    EcosystemValidationError,
)

# Event Name Constants
AGENT_REGISTERED = "agent_registered"
AGENT_REMOVED = "agent_removed"
AGENT_STARTED = "agent_started"
AGENT_STOPPED = "agent_stopped"
TASK_STARTED = "task_started"
TASK_COMPLETED = "task_completed"
TASK_FAILED = "task_failed"

# Job Event Name Constants
JOB_QUEUED = "job_queued"
JOB_STARTED = "job_started"
JOB_COMPLETED = "job_completed"
JOB_FAILED = "job_failed"
JOB_CANCELLED = "job_cancelled"
JOB_RETRYING = "job_retrying"

__all__ = [
    "YasinCoreClient",
    "AIProvider",
    "AIChatMessage",
    "AIRequest",
    "AIResponse",
    "AIResponseChunk",
    "AIProviderError",
    "AIProviderConnectionError",
    "AIProviderAuthError",
    "AIProviderRateLimitError",
    "ProviderRegistry",
    "ProviderManager",
    "MockProvider",
    "LocalProvider",
    "OpenAICompatibleProvider",
    "MetricsRegistry",
    "Metric",
    "Counter",
    "Gauge",
    "Histogram",
    "MetricType",
    "BaseMetricProvider",
    "InMemoryMetricProvider",
    "ErrorTracker",
    "ErrorRecord",
    "PerformanceTimer",
    "JSONFormatter",
    "StructuredLogger",
    "get_structured_logger",
    "ObservabilityService",
    "ConfigurationManager",
    "RuntimeOrchestrator",
    "RuntimeState",
    "OrchestratorError",
    "ConfigurationValidationError",
    "Settings",
    "BaseAgent",
    "Task",
    "IAgentRuntime",
    "AgentRuntime",
    "active_context",
    "get_current_context",
    "RuntimeContext",
    "ContextEngine",
    "Event",
    "EventBus",
    "AGENT_REGISTERED",
    "AGENT_REMOVED",
    "AGENT_STARTED",
    "AGENT_STOPPED",
    "TASK_STARTED",
    "TASK_COMPLETED",
    "TASK_FAILED",
    "JOB_QUEUED",
    "JOB_STARTED",
    "JOB_COMPLETED",
    "JOB_FAILED",
    "JOB_CANCELLED",
    "JOB_RETRYING",
    "PluginExecutionBridge",
    "BaseTool",
    "FunctionTool",
    "tool",
    "ToolRegistry",
    "ToolManager",
    "DIContainer",
    "IDIContainer",
    "ServiceLifetime",
    "DIError",
    "DependencyResolutionError",
    "CircularDependencyError",
    "BaseStorage",
    "JSONFileStorage",
    "InMemoryStorage",
    "StorageError",
    "StorageConnectionError",
    "StorageNotFoundError",
    "StorageValidationError",
    "get_storage",
    "register_backend",
    "Job",
    "ExecutionTask",
    "JobStatus",
    "JobPriority",
    "TaskExecutionEngine",
    "Scheduler",
    "ScheduledJob",
    "WorkerState",
    "WorkerNode",
    "BaseDistributedWorker",
    "DistributedWorkerManager",
    # Security components
    "SecurityError",
    "AccessDeniedError",
    "AuthenticationError",
    "PermissionValidationError",
    "Permission",
    "Role",
    "Subject",
    "BasePolicy",
    "DefaultRBACPolicy",
    "PolicyEngine",
    "ConfigurationSecurityValidator",
    "SensitiveDataProtector",
    "BaseCredentialStore",
    "InMemoryCredentialStore",
    "AuditLogger",
    "SECURITY_EVENT_AUDIT",
    "SECURITY_ACCESS_GRANTED",
    "SECURITY_ACCESS_DENIED",
    "SecurityManager",
    "require_permission",
    # SDK v2 Stabilization Components
    "SDKError",
    "SDKValidationError",
    "SDKAuthenticationError",
    "SDKConnectionError",
    "SDKExecutionError",
    "SDKDeprecationWarning",
    "translate_core_errors",
    "SDKRequest",
    "SDKResponse",
    "ISDKClient",
    "ISDKAuthenticator",
    "SDKVersionChecker",
    "deprecated",
    "SDKMigrationHelper",
    "AsyncYasinCoreClient",
    # Compatibility Framework exports
    "Version",
    "is_compatible",
    "VersionNegotiator",
    "APICompatibilityChecker",
    "DeprecationManager",
    "LegacyAPIAdapter",
    "SchemaMigrator",
    "ConfigurationMigrator",
    "DataMigrator",
    "AgentCompatibilityValidator",
    "HubCompatibilityValidator",
    "RelayCompatibilityValidator",
    "CLICompatibilityValidator",
    "RuntimeCompatibilityChecker",
    "CompatibilityManager",
    "CompatibilityError",
    "VersionMismatchError",
    "APICompatibilityError",
    "MigrationError",
    "EcosystemValidationError",
]
