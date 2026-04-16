class NasoBaseException(Exception):
    """Classe base per tutte le eccezioni del sistema Naso."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class AuthenticationError(NasoBaseException):
    """Sollevata quando l'autenticazione fallisce."""
    pass

class AuthorizationError(NasoBaseException):
    """Sollevata per violazioni di permessi o isolamento multi-tenant."""
    pass

class ResourceNotFoundError(NasoBaseException):
    """Sollevata quando una risorsa (Tenant, Leak, Keyword) non esiste."""
    pass

class ProcessingError(NasoBaseException):
    """Errore durante l'analisi YARA o il Thinking dell'AI."""
    pass

class InfrastructureError(NasoBaseException):
    """Errore di connessione a DB, Elasticsearch, MinIO o Tor."""
    pass

class CrawlerError(NasoBaseException):
    """Errore specifico dei worker di scraping/ingestion."""
    pass
