import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "publisher"))
import publish as p


class MensajesPrivadosTests(unittest.TestCase):
    def test_solicitud_privada_usa_comentario(self):
        with patch.multiple(p, IG_USER="ig", FB_PAGE="fb"), patch.object(p, "fb_call", return_value={"message_id": "ok"}) as send:
            p.private_reply("c1", "instagram", "token")
            method, path, params, _ = send.call_args.args
            self.assertEqual((method, path), ("POST", "fb/messages"))
            self.assertEqual(json.loads(params["recipient"]), {"comment_id": "c1"})
            self.assertIn("https://aprendeexceljugando.com/", json.loads(params["message"])["text"])
            p.private_reply("c2", "facebook", "token")
            self.assertEqual(send.call_args.args[1], "fb/messages")

    def test_reenvio_no_se_omite_por_antigua_respuesta_publica(self):
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        def call(method, path, params):
            if path == "ig": return {"username": "marca"}
            if path == "ig/media": return {"data": [{"id": "m", "timestamp": now}]}
            if path == "m/comments": return {"data": [{"id": "c1", "username": "visitante", "text": "MISIÓN", "timestamp": now}]}
            self.fail("No debería enviarse otra respuesta pública")
        with patch.multiple(p, IG_USER="ig", FB_PAGE="fb", DRY=False), patch.object(p, "call", side_effect=call), patch.object(p, "fb_token", return_value="token"), patch.object(p, "fb_call", return_value={"data": []}), patch.object(p, "private_reply") as send:
            state = {"_respondidos": ["c1"]}
            p.answer_comments(state)
            p.answer_comments(state)
            send.assert_called_once_with("c1", "instagram", "token")
            self.assertEqual(state["_privados"], ["c1"])

    def test_fallo_privado_no_promete_envio(self):
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        def call(method, path, params):
            if path == "ig": return {"username": "marca"}
            if path == "ig/media": return {"data": [{"id": "m", "timestamp": now}]}
            if path == "m/comments": return {"data": [{"id": "c1", "username": "visitante", "text": "mision", "timestamp": now}]}
            self.fail("Una respuesta pública no debe anunciar un envío fallido")
        with patch.multiple(p, IG_USER="ig", FB_PAGE="fb", DRY=False), patch.object(p, "call", side_effect=call), patch.object(p, "fb_token", return_value="token"), patch.object(p, "fb_call", return_value={"data": []}), patch.object(p, "private_reply", side_effect=RuntimeError("denegado")):
            state = {}
            with self.assertRaises(RuntimeError): p.answer_comments(state)
            self.assertEqual(state["_privados"], [])
            self.assertEqual(state["_respondidos"], [])


if __name__ == "__main__": unittest.main()
