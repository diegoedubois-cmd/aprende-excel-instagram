"""Diagnóstico de solo lectura: no publica ni envía mensajes."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.facebook.com/v24.0"
TOKEN = os.environ["IG_ACCESS_TOKEN"]
IG_USER = os.environ["IG_USER_ID"]
PAGE = os.environ["FB_PAGE_ID"]


def get(path, params, token=TOKEN):
    query = urllib.parse.urlencode(dict(params, access_token=token))
    try:
        with urllib.request.urlopen(f"{API}/{path}?{query}", timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            detail = json.load(error).get("error", {})
            return {"error": {"code": detail.get("code"), "subcode": detail.get("error_subcode")}}
        except (ValueError, OSError):
            return {"error": {"http": error.code}}


def main():
    info = get("debug_token", {"input_token": TOKEN})
    info = info.get("data", {})
    print("Credencial: app=", info.get("app_id", "no disponible"), "válida=", info.get("is_valid", "no disponible"))
    permissions = get("me/permissions", {})
    if "error" in permissions:
        print("Permisos: error", permissions["error"])
        return
    granted = sorted(p["permission"] for p in permissions.get("data", []) if p.get("status") == "granted")
    print("Permisos autorizados:", ", ".join(granted))
    target = None
    media = get(f"{IG_USER}/media", {"fields": "id,permalink,comments_count", "limit": 100})
    if "error" in media:
        print("Instagram: error al leer publicaciones", media["error"])
    else:
        checked = matched = errors = 0
        for item in media.get("data", []):
            comments = get(f"{item['id']}/comments", {"fields": "id,text", "limit": 50})
            if "error" in comments:
                errors += 1
                continue
            checked += len(comments.get("data", []))
            matched += sum("mision" in c.get("text", "").lower() or "misión" in c.get("text", "").lower() for c in comments.get("data", []))
        print(f"Instagram: publicaciones={len(media.get('data', []))}, comentarios={checked}, coincidencias={matched}, errores={errors}")
        target = next((m for m in media.get("data", []) if "DgAy6i2FdhO" in m.get("permalink", "")), None)
        print("Publicación indicada localizada:", bool(target))
        if target:
            print("Comentarios registrados en publicación indicada:", target.get("comments_count", "no disponible"))
            detail = get(f"{target['id']}/comments", {"fields": "id,text,username,timestamp", "limit": 100})
            print("Comentarios accesibles con token de usuario:", len(detail.get("data", [])), "error:", detail.get("error", "ninguno"))
    page = get(PAGE, {"fields": "access_token"})
    if "error" in page or not page.get("access_token"):
        print("Facebook: no se pudo obtener acceso de página", page.get("error", {}))
        return
    if target:
        detail = get(f"{target['id']}/comments", {"fields": "id,text,username,timestamp", "limit": 100}, page["access_token"])
        print("Comentarios accesibles con token de página:", len(detail.get("data", [])), "error:", detail.get("error", "ninguno"))
    posts = get(f"{PAGE}/posts", {"fields": "id", "limit": 10}, page["access_token"])
    if "error" in posts:
        print("Facebook: error al leer publicaciones", posts["error"])
        return
    checked = matched = errors = 0
    for item in posts.get("data", []):
        comments = get(f"{item['id']}/comments", {"fields": "id,message", "limit": 50}, page["access_token"])
        if "error" in comments:
            errors += 1
            continue
        checked += len(comments.get("data", []))
        matched += sum("mision" in c.get("message", "").lower() or "misión" in c.get("message", "").lower() for c in comments.get("data", []))
    print(f"Facebook: publicaciones={len(posts.get('data', []))}, comentarios={checked}, coincidencias={matched}, errores={errors}")


if __name__ == "__main__":
    main()
