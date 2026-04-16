rule private_key {
    meta:
        description = "Rileva chiavi private RSA/EC/Generic"
    strings:
        $rsa = "-----BEGIN RSA PRIVATE KEY-----"
        $generic = "-----BEGIN PRIVATE KEY-----"
        $ec = "-----BEGIN EC PRIVATE KEY-----"
    condition:
        any of them
}

rule generic_api_key {
    meta:
        description = "Rileva potenziali API Key generiche"
    strings:
        $api_key = /api[_-]key[ ]*[:=][ ]*['"][A-Za-z0-9]{20,60}['"]/ i
        $auth_token = /auth[_-]token[ ]*[:=][ ]*['"][A-Za-z0-9]{20,60}['"]/ i
    condition:
        any of them
}

rule google_api_key {
    meta:
        description = "Rileva Google API Keys"
    strings:
        $key = /AIza[0-9A-Za-z\\-_]{35}/
    condition:
        $key
}
