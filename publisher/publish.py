"""Publica en Instagram lo que toca según content/calendar.json.

Se ejecuta cada hora desde GitHub Actions. Solo usa la API oficial de Meta.
Variables: IG_ACCESS_TOKEN (secreto), IG_USER_ID, RAW_BASE, DRY_RUN.
"""
import json, os, sys, time, datetime as dt, urllib.request, urllib.parse
from zoneinfo import ZoneInfo

API = "https://graph.facebook.com/v24.0"
TZ = ZoneInfo("Europe/Madrid")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAL = os.path.join(ROOT, "content", "calendar.json")
STATE = os.path.join(ROOT, "state", "published.json")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
IG_USER = os.environ.get("IG_USER_ID", "")
RAW_BASE = os.environ.get("RAW_BASE", "").rstrip("/")
DRY = os.environ.get("DRY_RUN", "false").lower() == "true"
MAX_LATE = dt.timedelta(hours=36)  # no publicar posts muy atrasados


def call(method, path, params):
    params = dict(params, access_token=TOKEN)
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} -> {e.code}: {body}") from None


def media_url(p):
    return p if p.startswith("http") else f"{RAW_BASE}/{p.lstrip('/')}"


def is_video(p):
    return p.lower().endswith((".mp4", ".mov"))


def wait_ready(cid, tries=40):
    for _ in range(tries):
        st = call("GET", cid, {"fields": "status_code,status"})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"contenedor {cid}: {st}")
        time.sleep(15)
    raise RuntimeError(f"contenedor {cid} no terminó de procesarse")


def container(post):
    kind, media, caption = post["type"], post["media"], post.get("caption", "")
    if kind == "CAROUSEL":
        children = []
        for m in media:
            p = {"is_carousel_item": "true"}
            if is_video(m):
                p.update(media_type="VIDEO", video_url=media_url(m))
            else:
                p["image_url"] = media_url(m)
            c = call("POST", f"{IG_USER}/media", p)["id"]
            if is_video(m):
                wait_ready(c)
            children.append(c)
        return call("POST", f"{IG_USER}/media", {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption})["id"]
    if kind == "REEL":
        p = {"media_type": "REELS", "video_url": media_url(media[0]), "caption": caption, "share_to_feed": "true"}
        if post.get("cover"):
            p["cover_url"] = media_url(post["cover"])
        elif post.get("cover_ms") is not None:
            p["thumb_offset"] = str(post["cover_ms"])
        return call("POST", f"{IG_USER}/media", p)["id"]
    if kind == "STORY":
        m = media[0]
        p = {"media_type": "STORIES"}
        p["video_url" if is_video(m) else "image_url"] = media_url(m)
        return call("POST", f"{IG_USER}/media", p)["id"]
    if kind == "IMAGE":
        return call("POST", f"{IG_USER}/media", {"image_url": media_url(media[0]), "caption": caption})["id"]
    raise ValueError(f"tipo desconocido: {kind}")


FB_PAGE = os.environ.get("FB_PAGE_ID", "")
_fb_token = None


def fb_token():
    """Token de la página si el token del sistema tiene pages_manage_posts; si no, None."""
    global _fb_token
    if _fb_token is not None:
        return _fb_token or None
    _fb_token = ""
    if not FB_PAGE:
        return None
    try:
        perms = call("GET", "me/permissions", {})
        granted = {p["permission"] for p in perms.get("data", []) if p.get("status") == "granted"}
        if "pages_manage_posts" not in granted:
            print("Facebook: falta el permiso pages_manage_posts, solo se publica en Instagram")
            return None
        _fb_token = call("GET", FB_PAGE, {"fields": "access_token"}).get("access_token", "")
    except Exception as e:
        print(f"Facebook: no disponible ({e})")
    return _fb_token or None


def fb_call(method, path, params, tok):
    global TOKEN
    old, TOKEN = TOKEN, tok
    try:
        return call(method, path, params)
    finally:
        TOKEN = old


FB_LINK = "https://aprendeexceljugando.com/?utm_source=facebook&utm_medium=social&utm_campaign=organico"


def fb_caption(text):
    """En Facebook los enlaces son clicables: cambia «link en la bio» por la web."""
    import re
    text = text.replace(" (también en el link de la bio)", "")
    return re.sub(r"\s*(?:→|:|\.)?\s*[Ll]ink en la bio", f": {FB_LINK}", text)


def fb_publish(post):
    """Publica el mismo contenido en la página de Facebook (reels, carruseles, imágenes e historias de imagen)."""
    tok = fb_token()
    if not tok:
        return None
    kind, media, caption = post["type"], post["media"], fb_caption(post.get("caption", ""))
    if kind == "STORY":
        if is_video(media[0]):
            return None
        pid = fb_call("POST", f"{FB_PAGE}/photos", {"url": media_url(media[0]), "published": "false"}, tok)["id"]
        return fb_call("POST", f"{FB_PAGE}/photo_stories", {"photo_id": pid}, tok).get("post_id", pid)
    if kind == "REEL":
        vid = fb_call("POST", f"{FB_PAGE}/video_reels", {"upload_phase": "start"}, tok)["video_id"]
        req = urllib.request.Request(
            f"https://rupload.facebook.com/video-upload/v24.0/{vid}", method="POST",
            headers={"Authorization": f"OAuth {tok}", "file_url": media_url(media[0])})
        with urllib.request.urlopen(req, timeout=120) as r:
            json.load(r)
        fb_call("POST", f"{FB_PAGE}/video_reels", {"upload_phase": "finish", "video_id": vid,
                                                    "video_state": "PUBLISHED", "description": caption}, tok)
        return vid
    imgs = [m for m in media if not is_video(m)]
    if not imgs:
        return None
    ids = [fb_call("POST", f"{FB_PAGE}/photos", {"url": media_url(m), "published": "false"}, tok)["id"] for m in imgs]
    params = {"message": caption}
    for i, pid in enumerate(ids):
        params[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
    return fb_call("POST", f"{FB_PAGE}/feed", params, tok)["id"]


import random, unicodedata

REPLIES = [
    "@{u} ¡Aquí la tienes! Entra en aprendeexceljugando.com (también en el link de la bio) y practícala gratis en el Distrito 1 🎮",
    "@{u} ¡Hecho! La misión te espera gratis en aprendeexceljugando.com 👉 link en la bio",
    "@{u} ¡Vamos! Crea tu cuenta gratis en aprendeexceljugando.com y empieza por el Distrito 1 💪",
]


def _norm(t):
    return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower()


PRIVATE_MESSAGE = "¡Aquí tienes tu acceso! Practica Excel gratis en el Distrito 1: https://aprendeexceljugando.com/ 🎮"


def private_reply(comment_id, platform, page_token):
    """Envía una respuesta privada asociada al comentario, no al usuario."""
    if platform not in ("instagram", "facebook"):
        raise ValueError("Plataforma no compatible")
    result = fb_call("POST", f"{FB_PAGE}/messages", {
        "recipient": json.dumps({"comment_id": comment_id}),
        "message": json.dumps({"text": PRIVATE_MESSAGE}),
    }, page_token)
    if not result.get("message_id"):
        raise RuntimeError("Meta no confirmó el envío del mensaje privado")
    return result


def comment_is_recent(value):
    if not value:
        return False
    try:
        when = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return when.tzinfo is not None and dt.timedelta(0) <= dt.datetime.now(dt.timezone.utc) - when <= dt.timedelta(days=7)
    except (ValueError, TypeError):
        return False


def failure_label(label, error):
    # Solo códigos numéricos: no volcar datos personales ni credenciales.
    import re
    code = re.search(r'"code"\s*:\s*(\d+)', str(error))
    subcode = re.search(r'"error_subcode"\s*:\s*(\d+)', str(error))
    return label + (f" (Meta {code.group(1)}" + (f"/{subcode.group(1)}" if subcode else "") + ")" if code else " (sin código de Meta)")


def answer_comments(state):
    """Envía un enlace privado por comentario y mantiene separado el registro público."""
    done = state.setdefault("_respondidos", [])
    private_done = state.setdefault("_privados", [])
    failures = []
    me = call("GET", IG_USER, {"fields": "username"}).get("username", "")
    media = call("GET", f"{IG_USER}/media", {"fields": "id,timestamp", "limit": "40"}).get("data", [])
    limit = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    n = 0
    tok = fb_token()
    if not tok:
        raise RuntimeError("No se ha podido obtener el token de la página para mensajes privados")
    for m in media:
        if dt.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")) < limit:
            continue
        comments = call("GET", f"{m['id']}/comments",
                        {"fields": "id,text,username,timestamp,replies{username}", "limit": "50"}).get("data", [])
        for c in comments:
            if c.get("username") == me or "mision" not in _norm(c.get("text", "")) or not comment_is_recent(c.get("timestamp")):
                continue
            if DRY:
                print("   DRY_RUN: enviaría un mensaje privado en Instagram")
                continue
            if c["id"] not in private_done:
                try:
                    private_reply(c["id"], "instagram", tok)
                    private_done.append(c["id"]); n += 1
                except Exception as error:
                    failures.append(failure_label("mensaje privado de Instagram", error))
                    continue
            if c["id"] not in done:
                if any(r.get("username") == me for r in c.get("replies", {}).get("data", [])):
                    done.append(c["id"]); continue
                try:
                    call("POST", f"{c['id']}/replies", {"message": "¡Listo! Te enviamos el enlace por mensaje privado ✨"})
                    done.append(c["id"])
                except Exception as error:
                    failures.append(failure_label("respuesta pública de Instagram", error))
    if tok:
        posts = fb_call("GET", f"{FB_PAGE}/posts", {"fields": "id,created_time", "limit": "40"}, tok).get("data", [])
        for p in posts:
            for c in fb_call("GET", f"{p['id']}/comments", {"fields": "id,message,from,created_time,comments{from}", "limit": "50"}, tok).get("data", []):
                who = (c.get("from") or {}).get("id")
                if who == FB_PAGE or "mision" not in _norm(c.get("message", "")) or not comment_is_recent(c.get("created_time")):
                    continue
                if DRY:
                    print("   DRY_RUN: enviaría un mensaje privado en Facebook"); continue
                if c["id"] not in private_done:
                    try:
                        private_reply(c["id"], "facebook", tok)
                        private_done.append(c["id"]); n += 1
                    except Exception as error:
                        failures.append(failure_label("mensaje privado de Facebook", error))
                        continue
                if c["id"] not in done:
                    if any((r.get("from") or {}).get("id") == FB_PAGE for r in c.get("comments", {}).get("data", [])):
                        done.append(c["id"]); continue
                    try:
                        fb_call("POST", f"{c['id']}/comments", {"message": "¡Listo! Te enviamos el enlace por mensaje privado ✨"}, tok)
                        done.append(c["id"])
                    except Exception as error:
                        failures.append(failure_label("respuesta pública de Facebook", error))
    state["_respondidos"] = done[-2000:]
    state["_privados"] = private_done[-2000:]
    if n:
        print(f"Mensajes privados enviados: {n}")
    if failures:
        raise RuntimeError("Errores al procesar comentarios: " + ", ".join(failures))


def main():
    cal = json.load(open(CAL, encoding="utf-8"))
    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    now = dt.datetime.now(TZ)
    due = []
    for post in cal:
        if post["id"] in state or post.get("skip"):
            continue
        when = dt.datetime.fromisoformat(post["at"]).replace(tzinfo=TZ)
        if when <= now:
            if now - when > MAX_LATE:
                state[post["id"]] = {"status": "omitido_por_atraso", "at": now.isoformat()}
            else:
                due.append(post)
    errors = 0
    for post in sorted(due, key=lambda p: p["at"]):
        print(f"→ {post['id']} ({post['type']})")
        if DRY:
            print("   DRY_RUN: no se publica")
            continue
        try:
            cid = container(post)
            if post["type"] in ("REEL", "STORY", "CAROUSEL"):
                wait_ready(cid)
            mid = call("POST", f"{IG_USER}/media_publish", {"creation_id": cid})["id"]
            state[post["id"]] = {"status": "publicado", "media_id": mid, "at": dt.datetime.now(TZ).isoformat()}
            print(f"   publicado: {mid}")
            try:
                fid = fb_publish(post)
                if fid:
                    state[post["id"]]["facebook_id"] = fid
                    print(f"   también en Facebook: {fid}")
            except Exception as e:  # Facebook no debe frenar Instagram
                print(f"   Facebook falló: {e}", file=sys.stderr)
        except Exception as e:  # sigue con el resto y deja constancia
            errors += 1
            print(f"   ERROR: {e}", file=sys.stderr)
            retries = state.setdefault("_retries", {})
            retries[post["id"]] = retries.get(post["id"], 0) + 1
            if retries[post["id"]] >= 3:
                state[post["id"]] = {"status": "error", "error": str(e)[:500], "at": now.isoformat()}
    # Las respuestas a comentarios las gestiona Manychat. Mantenerlas fuera
    # del publicador evita mensajes duplicados y reglas que compitan entre sí.
    if not DRY:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as state_file:
            json.dump(state, state_file, ensure_ascii=False, indent=1)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
