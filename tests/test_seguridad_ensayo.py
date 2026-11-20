import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "publisher"))
import publish
import validar


class EnsayoTests(unittest.TestCase):
    def test_ensayo_no_modifica_el_estado(self):
        with tempfile.TemporaryDirectory() as folder:
            calendar = Path(folder) / "calendar.json"
            state = Path(folder) / "published.json"
            original = '{"anterior":{"status":"publicado"}}'
            state.write_text(original, encoding="utf-8")
            old = (dt.datetime.now(publish.TZ) - dt.timedelta(days=3)).replace(tzinfo=None)
            calendar.write_text(json.dumps([{"id": "atrasado", "at": old.isoformat(), "type": "REEL"}]), encoding="utf-8")
            def mutate_state(value):
                value["_respondidos"] = ["simulado"]
            with patch.multiple(publish, CAL=str(calendar), STATE=str(state), DRY=True), patch.object(publish, "answer_comments", side_effect=mutate_state), patch.object(publish, "container") as container:
                publish.main()
                container.assert_not_called()
            self.assertEqual(state.read_text(encoding="utf-8"), original)

    def test_publicacion_real_sigue_guardando_atrasos(self):
        with tempfile.TemporaryDirectory() as folder:
            calendar = Path(folder) / "calendar.json"
            state = Path(folder) / "published.json"
            old = (dt.datetime.now(publish.TZ) - dt.timedelta(days=3)).replace(tzinfo=None)
            calendar.write_text(json.dumps([{"id": "atrasado", "at": old.isoformat(), "type": "REEL"}]), encoding="utf-8")
            with patch.multiple(publish, CAL=str(calendar), STATE=str(state), DRY=False), patch.object(publish, "answer_comments"):
                publish.main()
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["atrasado"]["status"], "omitido_por_atraso")

    def test_seleccion_explicita_y_desconocida(self):
        cal = [{"id": "uno", "type": "STORY"}]
        self.assertEqual(validar.select_posts(cal, " uno "), cal)
        with self.assertRaises(ValueError):
            validar.select_posts(cal, "uno, inexistente")
        with self.assertRaises(ValueError):
            validar.select_posts(cal, " , ")


if __name__ == "__main__":
    unittest.main()
