from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared rate limiter instance — imported by main.py and by the endpoints
limiter = Limiter(key_func=get_remote_address)
