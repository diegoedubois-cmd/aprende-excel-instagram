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
        req = urllib.request.Request(url, data=data, method="POST")
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
        return call("POST", f"{IG_USER}/media", p)["id"]
    if kind == "STORY":
        m = media[0]
        p = {"media_type": "STORIES"}
        p["video_url" if is_video(m) else "image_url"] = media_url(m)
        return call("POST", f"{IG_USER}/media", p)["id"]
    if kind == "IMAGE":
        return call("POST", f"{IG_USER}/media", {"image_url": media_url(media[0]), "caption": caption})["id"]
    raise ValueError(f"tipo desconocido: {kind}")


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
        except Exception as e:  # sigue con el resto y deja constancia
            errors += 1
            prev = state.get(post["id"], {})
            print(f"   ERROR: {e}", file=sys.stderr)
            if prev.get("tries", 0) >= 2:
                state[post["id"]] = {"status": "error", "error": str(e)[:500], "at": now.isoformat()}
            else:
                state.setdefault("_retries", {})[post["id"]] = prev.get("tries", 0) + 1
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
