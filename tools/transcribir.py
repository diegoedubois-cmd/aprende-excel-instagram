import json, sys, glob, os
from faster_whisper import WhisperModel
m = WhisperModel("small", device="cpu", compute_type="int8")
out = {}
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.mp4"))):
    segs, _ = m.transcribe(f, language="es", word_timestamps=True)
    words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in s.words]
    out[os.path.basename(f)] = {"text": " ".join(x["w"] for x in words), "words": words}
    print(os.path.basename(f), "→", out[os.path.basename(f)]["text"])
json.dump(out, open(os.path.join(sys.argv[1], "transcripcion.json"), "w"), ensure_ascii=False, indent=1)
