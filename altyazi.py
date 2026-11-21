#!/usr/bin/env python3
"""Live Turkish subtitles for a game: read the English subtitle band of the PS Remote Play
window, translate it, and show it on a big-text page any device on the home network can open.

  python3 altyazi.py                     # watches "PS Remote Play"
  python3 altyazi.py --window Chrome     # any window whose app name or title contains this
  python3 altyazi.py --band 0.2 0.82 0.8 0.935

Open http://<this Mac's IP>:8765 on a phone or tablet (see README.md for the setup).
The Gemini key comes from GEMINI_API_KEY or a .env file next to this script (copy .env.public)
and is never printed.
"""
import argparse
import difflib
import json
import os
import queue
import re
import socket
import subprocess
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = "gemini-flash-lite-latest"
# Gemini's response time varies per request (0.6-10 s, sometimes 503), so a slow request is
# raced against a second lite model. Only one backup, and on a different model (its own quota):
# racing a repeat of the same model as well ran into 429 rate limits in the 2026-11-21 test.
# gemini-flash-latest was dropped: it answered only 503/429 or timed out that day.
BACKUPS = ["gemini-3.1-flash-lite-preview"]
HEDGE = 1.5  # seconds before the backup is asked as well
PROMPT = """Bir video oyunundaki İngilizce diyalog altyazısını Türkçeye çevir.
Konuşma dili kullan, kısa tut. Deyimleri birebir değil anlamıyla çevir (ör. "keep your head down" = "göze batma").
Küfrü yumuşatma ama cümlenin anlamını bozma: küfür hangi kelimeyi vurguluyorsa Türkçede de onu vurgulasın
(ör. "get in the fucking car" = "bin şu lanet arabaya").
Başta "İSİM:" gibi bir konuşmacı adı varsa aynen bırak. Okuma hatası gibi duran kelimeleri bağlamdan düzelt.
Yalnız çeviriyi yaz.

Önceki satırlar (bağlam için, çevirme): {context}

Çevrilecek: {text}"""


def gemini_key():
    """GEMINI_API_KEY from the environment, else from .env next to this script."""
    key = os.environ.get("GEMINI_API_KEY", "")
    env = HERE / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "GEMINI_API_KEY":
                key = value.strip().strip('"\'')
    if not key or key == "buraya-kendi-anahtarini-yaz":
        raise SystemExit("Gemini anahtarı yok: .env.public dosyasını .env adıyla kopyalayıp "
                         "GEMINI_API_KEY satırına kendi anahtarını yaz (README.md, adım 3).")
    return key


class Translator:
    def __init__(self):
        self.key = gemini_key()
        self.cache, self.history = {}, []
        self.pool = ThreadPoolExecutor(max_workers=8)

    def _ask(self, model, body):
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=json.dumps(body).encode(),
            headers={"x-goog-api-key": self.key, "Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=8))
        return "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"]).strip()

    def __call__(self, text):
        """Translation, or None if every model failed (the caller keeps the previous line)."""
        if text in self.cache:
            return self.cache[text]
        body = {"contents": [{"parts": [{"text": PROMPT.format(
                    context=" / ".join(self.history[-3:]) or "-", text=text)}]}],
                "generationConfig": {"temperature": 0.2}}
        futs = [self.pool.submit(self._ask, MODEL, body)]
        done, _ = wait(futs, timeout=HEDGE)
        if not done or futs[0].exception():
            futs += [self.pool.submit(self._ask, m, body) for m in BACKUPS]
        for f in as_completed(futs):
            if f.exception() is None:
                out = f.result()
                self.cache[text] = out
                self.history.append(text)
                return out
            print(f"  çeviri hatası: {getattr(f.exception(), 'code', type(f.exception()).__name__)}", flush=True)
        return None


class Hub:
    """Latest subtitle plus a queue per open page (server-sent events)."""
    def __init__(self):
        self.latest, self.clients, self.lock = {"tr": "", "en": ""}, [], threading.Lock()

    def publish(self, msg):
        with self.lock:
            self.latest = msg
            for q in self.clients:
                q.put(msg)

    def subscribe(self):
        q = queue.Queue()
        with self.lock:
            self.clients.append(q)
            q.put(self.latest)
        return q

    def unsubscribe(self, q):
        with self.lock:
            self.clients.remove(q)


def make_handler(hub):
    page = (HERE / "index.html").read_bytes()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                q = hub.subscribe()
                try:
                    while True:
                        try:
                            msg = q.get(timeout=15)
                            self.wfile.write(f"data: {json.dumps(msg, ensure_ascii=False)}\n\n".encode())
                        except queue.Empty:
                            self.wfile.write(b": ping\n\n")  # keeps phones from dropping the stream
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    hub.unsubscribe(q)
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(page)
    return H


def looks_like_subtitle(text):
    """Drops OCR crumbs ("N", "eB", "own"): a subtitle has two words or ends like a sentence."""
    words = [w for w in text.split() if any(c.isalpha() for c in w)]
    return len(words) >= 2 or (len(words) == 1 and text.rstrip()[-1:] in ".!?")


CODE = re.compile(r"[A-Z0-9-]*\d[A-Z0-9-]*$")  # "J26", "487": number plates and HUD numbers


def strip_codes(text):
    """Drops plate/HUD codes the band catches at either end of a line ("J26 487 No, why?")."""
    words = text.split()
    while words and CODE.match(words[0]):
        words.pop(0)
    while words and CODE.match(words[-1]):
        words.pop()
    return " ".join(words)


def same_line(a, b):
    """True when two OCR reads are the same subtitle: a misread ("okay," / "okay."), the
    same line read again after it flickered out, or a line that grew a second row."""
    a, b = (" ".join("".join(c for c in t.lower() if c.isalnum() or c == " ").split()) for t in (a, b))
    if a and b and (a.startswith(b) or b.startswith(a)):
        return True
    return difflib.SequenceMatcher(None, a.split(), b.split()).ratio() >= 0.75


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="PS Remote Play")
    ap.add_argument("--band", nargs=4, type=float, default=[0.2, 0.82, 0.8, 0.935],
                    metavar=("X0", "Y0", "X1", "Y1"), help="subtitle area as fractions of the window")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--interval", type=float, default=0.08, help="seconds between screen reads")
    ap.add_argument("--clear-after", type=float, default=5.0,
                    help="seconds without any subtitle before the page is cleared")
    args = ap.parse_args()

    hub, tr = Hub(), Translator()
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(hub))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"Sayfa: http://{lan_ip()}:{args.port}  (pencere: {args.window!r})", flush=True)

    ocr = subprocess.Popen([str(HERE / "subocr"), args.window, *map(str, args.band), str(args.interval)],
                           stdout=subprocess.PIPE, text=True)
    # Every line is translated at once, in parallel, so a slow request neither delays the next
    # line nor makes a short line vanish untranslated. `seq` lets the page keep the order when
    # a later line's translation lands first.
    jobs = ThreadPoolExecutor(max_workers=4)

    def translate(seq, en):
        t0 = time.time()
        tr_text = tr(en)
        print(f"[{time.time() - t0:.1f}s] {en}  →  {tr_text}", flush=True)
        if tr_text is not None and newest_read[seq] == en:  # an older read must not overwrite a newer one
            hub.publish({"tr": tr_text, "en": en, "seq": seq})

    # A translation stays until the next different line replaces it; the line it replaces moves
    # up as the grey one. A re-read of the same line takes the same seq, so it updates in place.
    # When nobody has spoken for --clear-after seconds, the page is emptied.
    seq, last_en, newest_read, timer = 0, "", {}, None
    for line in ocr.stdout:
        msg = json.loads(line)
        if "error" in msg:
            print(msg["error"], flush=True)
            continue
        en = msg["text"]
        if timer:
            timer.cancel()
        if not en:
            timer = threading.Timer(args.clear_after, hub.publish, [{"tr": "", "en": ""}])
            timer.start()
            continue
        en = strip_codes(en)
        if not looks_like_subtitle(en):
            continue
        if not same_line(en, last_en):
            seq += 1
        elif len(en) <= len(last_en) + 3:
            continue  # a misread of the line already shown: not worth another request
        last_en = newest_read[seq] = en
        jobs.submit(translate, seq, en)


if __name__ == "__main__":
    main()
