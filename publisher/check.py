"""Comprueba el token sin publicar nada: lee el nombre de la cuenta y cuántos posts tiene."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import publish as p
if not p.TOKEN or not p.IG_USER:
    sys.exit("Falta IG_ACCESS_TOKEN o IG_USER_ID")
info = p.call("GET", p.IG_USER, {"fields": "username,media_count"})
print(f"Conexión OK con @{info.get('username')} · publicaciones: {info.get('media_count')}")
lim = p.call("GET", f"{p.IG_USER}/content_publishing_limit", {"fields": "config,quota_usage"})
print("Límite de publicación:", lim.get("data"))
