"""Ensayo sin publicar: crea contenedores de un reel, un reel de demo y un carrusel
y comprueba que Meta los procesa. Nunca llama a media_publish.
También muestra qué páginas de Facebook y permisos ve el token (sin imprimir tokens)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import publish as P


def main():
    cal = json.load(open(P.CAL, encoding="utf-8"))
    picks = []
    for cond in (lambda p: p["type"] == "REEL" and p.get("cover"),
                 lambda p: p["type"] == "REEL" and p.get("cover_ms") is not None,
                 lambda p: p["type"] == "CAROUSEL"):
        picks.append(next(p for p in cal if cond(p)))
    if os.environ.get("ENSAYO_IDS"):
        want = os.environ["ENSAYO_IDS"].split(",")
        picks = [p for p in cal if p["id"] in want]
    ok = True
    for post in picks:
        print(f"→ ensayo {post['id']} ({post['type']}, {len(post['media'])} archivos, caption {len(post.get('caption',''))} car.)")
        try:
            cid = P.container(post)
            P.wait_ready(cid)
            print("   OK: Meta lo procesó (no se publica)")
        except Exception as e:
            ok = False
            print(f"   ERROR: {e}")
    try:
        lim = P.call("GET", f"{P.IG_USER}/content_publishing_limit", {"fields": "config,quota_usage"})
        print("Límite de publicación:", json.dumps(lim))
    except Exception as e:
        print("límite: no disponible:", e)
    try:
        perms = P.call("GET", "me/permissions", {})
        print("Permisos:", ", ".join(p["permission"] for p in perms.get("data", []) if p.get("status") == "granted"))
    except Exception as e:
        print("permisos: no disponible:", e)
    try:
        acc = P.call("GET", "me/accounts", {"fields": "id,name,tasks"})
        for a in acc.get("data", []):
            print("Página:", a.get("id"), a.get("name"), a.get("tasks"))
    except Exception as e:
        print("páginas: no disponible:", e)
    os.environ.setdefault("FB_PAGE_ID", "1391043200767851")
    P.FB_PAGE = os.environ["FB_PAGE_ID"]
    tok = P.fb_token()
    if tok:
        try:
            img = next(p for p in cal if p["type"] == "STORY")["media"][0]
            pid = P.fb_call("POST", f"{P.FB_PAGE}/photos", {"url": P.media_url(img), "published": "false"}, tok)["id"]
            P.fb_call("DELETE", pid, {}, tok)
            print("Facebook: OK (foto de prueba subida sin publicar y borrada)")
        except Exception as e:
            ok = False
            print("Facebook: ERROR", e)
    else:
        print("Facebook: sin acceso")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
