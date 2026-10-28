"""ARPG yerel sunucu: auth + bulut kayit + auction house + dogrulama
   http://127.0.0.1:8787"""
import json, hashlib, os, threading, time, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "accounts.json")
SAVES = os.path.join(BASE, "saves")
AH = os.path.join(BASE, "auction.json")
PEND = os.path.join(BASE, "pending.json")
os.makedirs(SAVES, exist_ok=True)
lock = threading.Lock()

def load(p, d):
    if os.path.exists(p):
        try: return json.load(open(p, "r", encoding="utf-8"))
        except Exception: return d
    return d

def save(p, o):
    json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def h(u, p):
    return hashlib.sha256(("arpg:" + u.lower() + ":" + p + ":s7f2").encode("utf-8")).hexdigest()

def auth(user, pw):
    db = load(DB, {})
    k = (user or "").lower()
    if k not in db: return None
    if db[k]["hash"] != h(user, pw): return None
    return db[k]["user"]

# ---------------- ITEM DOGRULAMA ----------------
def valid_item(it):
    if not isinstance(it, dict): return False
    try:
        plus = int(it.get("plus", 0))
        if plus < 0 or plus > 10: return False
        mods = it.get("appliedMods") or []
        if not isinstance(mods, list) or len(mods) > 6: return False
        for f in ("damage","armor","life","crit","resist","area","mana",
                  "incDamage","incArmor","incLife","incMana","incSpeed","critMulti","attackSpeed"):
            v = int(it.get(f, 0) or 0)
            if v < 0 or v > 100000: return False
        cnt = int(it.get("count", 1) or 1)
        if cnt < 1 or cnt > 5000: return False
        return True
    except Exception:
        return False

def valid_save(s):
    if not isinstance(s, dict): return False
    try:
        lv = int(s.get("level", 1))
        if lv < 1 or lv > 100: return False
        if int(s.get("gold", 0)) < 0 or int(s.get("gold", 0)) > 10**9: return False
        bag = s.get("bag") or []
        if len(bag) > 60: return False
        for it in bag:
            if not valid_item(it): return False
        return True
    except Exception:
        return False

class H(BaseHTTPRequestHandler):
    def _j(self, obj, code=200):
        b = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a): pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self):
        p = self.path.rstrip("/")
        if p == "" or p == "/":
            acc = len(load(DB, {}))
            lst = len(load(AH, []))
            html = """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>Path of ARPG - Sunucu</title>
<style>
body{margin:0;background:#0d0b09;color:#d8c9a3;font-family:Segoe UI,Arial,sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{max-width:620px;padding:40px;border:1px solid #6b5a33;border-radius:12px;
background:linear-gradient(#1c1712,#12100d);text-align:center}
h1{margin:0 0 6px;color:#d6b26c;font-size:30px;letter-spacing:2px}
.sub{color:#8d7f66;font-size:13px;margin-bottom:26px}
.ok{color:#8fdc7a;font-size:15px;margin:10px 0 22px}
.stat{display:flex;gap:24px;justify-content:center;margin:18px 0}
.stat div{background:#191510;border:1px solid #3a2f1e;border-radius:8px;padding:10px 18px}
.stat b{display:block;color:#d6b26c;font-size:22px}
.stat span{font-size:11px;color:#7d7059}
.note{margin-top:24px;font-size:12px;color:#6e6350;line-height:1.6}
</style></head><body><div class="card">
<h1>PATH OF ARPG</h1>
<div class="sub">OYUN SUNUCUSU</div>
<div class="ok">&#9679; Sunucu calisiyor</div>
<div class="stat">
<div><b>__ACC__</b><span>KAYITLI HESAP</span></div>
<div><b>__LST__</b><span>AH ILANI</span></div>
</div>
<div class="note">Bu adres oyunun sunucusudur. Oyuna girmek icin
PathOfArpg.exe dosyasini calistir ve giris ekranindaki
<b>Sunucu</b> kutusuna bu sayfanin adresini yaz.</div>
</div></body></html>"""
            body = html.replace("__ACC__", str(acc)).replace("__LST__", str(lst)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p == "/health":
            return self._j({"ok": True, "server": "arpg-local",
                            "accounts": len(load(DB, {})),
                            "listings": len(load(AH, []))})
        if p == "/ah":
            with lock:
                return self._j({"ok": True, "listings": load(AH, [])})
        self._j({"ok": False, "error": "yok"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            d = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return self._j({"ok": False, "error": "gecersiz istek"}, 400)

        path = self.path.rstrip("/")
        user = (d.get("user") or "").strip()
        pw = d.get("pass") or ""

        # ---- KAYIT / GIRIS ----
        if path == "/register":
            if len(user) < 3: return self._j({"ok": False, "error": "Kullanici adi en az 3 karakter"})
            if len(pw) < 4: return self._j({"ok": False, "error": "Sifre en az 4 karakter"})
            with lock:
                db = load(DB, {})
                k = user.lower()
                if k in db: return self._j({"ok": False, "error": "Bu kullanici zaten var"})
                db[k] = {"user": user, "hash": h(user, pw), "created": int(time.time())}
                save(DB, db)
            return self._j({"ok": True, "user": user})

        if path == "/login":
            u = auth(user, pw)
            if not u: return self._j({"ok": False, "error": "Kullanici veya sifre yanlis"})
            return self._j({"ok": True, "user": u})

        # ---- BULUT KAYIT ----
        if path == "/save":
            u = auth(user, pw)
            if not u: return self._j({"ok": False, "error": "Yetkisiz"})
            data = d.get("data")
            if not valid_save(data): return self._j({"ok": False, "error": "Gecersiz kayit verisi"})
            with lock:
                save(os.path.join(SAVES, u.lower() + ".json"), data)
            return self._j({"ok": True})

        if path == "/load":
            u = auth(user, pw)
            if not u: return self._j({"ok": False, "error": "Yetkisiz"})
            data = load(os.path.join(SAVES, u.lower() + ".json"), None)
            return self._j({"ok": True, "data": data})

        # ---- AUCTION HOUSE ----
        if path == "/ah/sell":
            u = auth(user, pw)
            if not u: return self._j({"ok": False, "error": "Yetkisiz"})
            it = d.get("item")
            if not valid_item(it): return self._j({"ok": False, "error": "Gecersiz esya"})
            try: price = int(d.get("price", 0))
            except Exception: price = 0
            if price < 1 or price > 10**7: return self._j({"ok": False, "error": "Gecersiz fiyat"})
            with lock:
                lst = load(AH, [])
                lst.append({"id": str(uuid.uuid4())[:8], "seller": u,
                            "item": it, "price": price, "ts": int(time.time())})
                save(AH, lst)
            return self._j({"ok": True})

        if path == "/ah/buy":
            u = auth(user, pw)
            if not u: return self._j({"ok": False, "error": "Yetkisiz"})
            lid = d.get("id")
            with lock:
                lst = load(AH, [])
                for i, l in enumerate(lst):
                    if l.get("id") == lid:
                        if l.get("seller", "").lower() == u.lower():
                            return self._j({"ok": False, "error": "Kendi ilanini alamazsin"})
                        lst.pop(i)
                        save(AH, lst)

                        # saticiya altin biriktir
                        pend = load(PEND, {})
                        sk = l.get("seller", "").lower()
                        pend[sk] = int(pend.get(sk, 0)) + int(l["price"])
                        save(PEND, pend)

                        return self._j({"ok": True, "item": l["item"], "price": l["price"]})
            return self._j({"ok": False, "error": "Ilan bulunamadi"})

        if path == "/ah/pending":
            u = auth(user, pw)
            if not u: return self._j({"ok": False, "error": "Yetkisiz"})
            with lock:
                pend = load(PEND, {})
                k = u.lower()
                amt = int(pend.get(k, 0))
                if amt > 0:
                    pend[k] = 0
                    save(PEND, pend)
            return self._j({"ok": True, "gold": amt})

        if path == "/ah/mine":
            u = auth(user, pw)
            if not u: return self._j({"ok": False, "error": "Yetkisiz"})
            lst = [l for l in load(AH, []) if l.get("seller", "").lower() == u.lower()]
            return self._j({"ok": True, "listings": lst})

        self._j({"ok": False, "error": "bilinmeyen istek"}, 404)

if __name__ == "__main__":
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"

    port = int(os.environ.get("PORT", "8787"))
    srv = HTTPServer(("0.0.0.0", port), H)
    print("ARPG server hazir")
    print("  bu bilgisayar   : http://127.0.0.1:8787")
    print("  ag (arkadasin)  : http://" + ip + ":8787")
    srv.serve_forever()





