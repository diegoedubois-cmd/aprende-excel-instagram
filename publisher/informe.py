"""Informe semanal: métricas de cada publicación de Instagram de los últimos 7 días.
Escribe informes/AAAA-MM-DD.md y añade filas a informes/metricas.csv. No publica nada."""
import csv, json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import publish as P

OUT = os.path.join(P.ROOT, "informes")
METRICS = {"REELS": "reach,views,likes,comments,saved,shares,total_interactions,ig_reels_avg_watch_time",
           "CAROUSEL_ALBUM": "reach,views,likes,comments,saved,shares,total_interactions",
           "IMAGE": "reach,views,likes,comments,saved,shares,total_interactions"}


def ins(mid, metrics):
    try:
        data = P.call("GET", f"{mid}/insights", {"metric": metrics}).get("data", [])
        return {d["name"]: (d.get("values") or [{}])[0].get("value", d.get("total_value", {}).get("value")) for d in data}
    except Exception as e:
        return {"error": str(e)[:120]}


def main():
    now = dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=7)
    acc = P.call("GET", P.IG_USER, {"fields": "username,followers_count,media_count"})
    media = P.call("GET", f"{P.IG_USER}/media", {"fields": "id,caption,media_product_type,media_type,timestamp,permalink", "limit": "60"}).get("data", [])
    rows = []
    for m in media:
        ts = dt.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
        if ts < since:
            continue
        kind = "REELS" if m.get("media_product_type") == "REELS" else m.get("media_type", "IMAGE")
        r = ins(m["id"], METRICS.get(kind, METRICS["IMAGE"]))
        reach = r.get("reach") or 0
        r.update(fecha=ts.astimezone(P.TZ).strftime("%Y-%m-%d %H:%M"), tipo=kind,
                 titulo=(m.get("caption") or "").split("\n")[0][:70], enlace=m.get("permalink", ""),
                 envios_por_alcance=round((r.get("shares") or 0) / reach * 100, 2) if reach else 0,
                 guardados_por_alcance=round((r.get("saved") or 0) / reach * 100, 2) if reach else 0)
        rows.append(r)
    rows.sort(key=lambda r: (r.get("envios_por_alcance", 0), r.get("reach") or 0), reverse=True)
    os.makedirs(OUT, exist_ok=True)
    day = now.astimezone(P.TZ).strftime("%Y-%m-%d")
    lines = [f"# Informe semanal · {day}", "",
             f"Seguidores: **{acc.get('followers_count')}** · Publicaciones: {acc.get('media_count')}", "",
             "Ordenado por envíos por alcance (la señal que más pesa para llegar a gente nueva).", "",
             "| Fecha | Tipo | Título | Alcance | Envíos | Guardados | Envíos/alcance % | Guardados/alcance % |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['fecha']} | {r['tipo']} | [{r['titulo']}]({r['enlace']}) | {r.get('reach','')} | {r.get('shares','')} | "
                     f"{r.get('saved','')} | {r['envios_por_alcance']} | {r['guardados_por_alcance']} |")
    if rows:
        top = rows[0]
        lines += ["", f"Mejor de la semana: **{top['titulo']}**. Repite su formato y su gancho."]
    open(os.path.join(OUT, f"{day}.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    path = os.path.join(OUT, "metricas.csv")
    cols = ["fecha", "tipo", "titulo", "reach", "views", "likes", "comments", "saved", "shares",
            "total_interactions", "ig_reels_avg_watch_time", "envios_por_alcance", "guardados_por_alcance", "enlace"]
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
