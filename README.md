# aprende-excel-instagram

Publicación programada en Instagram (@aprendeexceljugando) mediante la API oficial de Meta.

- `content/calendar.json`: qué se publica y cuándo (hora de Madrid).
- `content/media/`: imágenes y vídeos.
- `state/published.json`: lo ya publicado (lo escribe el flujo).
- `.github/workflows/publicar.yml`: se ejecuta cada hora.

Configuración: secreto `IG_ACCESS_TOKEN` (token del usuario del sistema
`publicador-instagram`) y variable `IG_USER_ID` en *Settings → Secrets and variables → Actions*.
Nunca guardar tokens en archivos del repositorio.
