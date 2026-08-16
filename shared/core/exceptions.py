class NasoBaseException(Exception):
    """Base class for every NASO exception."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthenticationError(NasoBaseException):
    """Raised when authentication fails."""

    pass


class AuthorizationError(NasoBaseException):
    """Raised on a permission violation or a multi-tenant isolation breach."""

    pass


class ResourceNotFoundError(NasoBaseException):
    """Raised when a resource (Tenant, Leak, Keyword) does not exist."""

    pass


class ProcessingError(NasoBaseException):
    """Error during YARA analysis or AI reasoning."""

    pass


class InfrastructureError(NasoBaseException):
    """Connection error against the database, Elasticsearch, MinIO or Tor."""

    pass


class CrawlerError(NasoBaseException):
    """Error specific to the scraping/ingestion workers."""

    pass
