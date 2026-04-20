from slowapi import Limiter
from slowapi.util import get_remote_address

# Istanza condivisa del rate limiter — importata da main.py e dagli endpoint
limiter = Limiter(key_func=get_remote_address)
