"""dogrula.py - Kartela için gerçek tarayıcı ölçümü (Chromium headless, sanal zaman).

Yerel bir sunucu siteyi sunar; bellek içi bir harness sayfayı iframe'de açar (masaüstü 1440x900 ve mobil 390x844), sayfanın kendi
ölçü kartlarını, kaynak isteklerini, taşmayı ve konsol hatalarını toplar. Sonuç olcu.json'a ve OLCU_RAPORU.md'nin 6. bölümüne yazılır.
Kullanım:  python -B dogrula.py        (Chromium yolu: SERGI_CHROME ortam değişkeni; yoksa PATH'teki chrome / chromium aranır)
"""
import sys, os, re, json, shutil, time, hashlib, threading, tempfile, subprocess, http.server, socketserver
from pathlib import Path

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
KOK = Path(__file__).resolve().parent
CHROME = os.environ.get("SERGI_CHROME") or shutil.which("chrome") or shutil.which("chromium") or shutil.which("google-chrome")
HARNESS = """<!doctype html><meta charset="utf-8"><body style="margin:0;background:#000">
<iframe id="f" src="/index.html__SORGU__" style="width:__W__px;height:__H__px;border:0;display:block"></iframe>
<script>
setTimeout(function () {
  var R = { hata: null };
  try {
    var w = document.getElementById('f').contentWindow, d = w.document, K = w.__KARTELA;
    R.olc = Object.keys(K.olc).map(function (k) { return [k, K.olc[k].d.textContent, K.olc[k].div.className]; });
    R.ms = K.durum.ms; R.gw = K.durum.gw; R.gh = K.durum.gh; R.hucre = K.durum.c; R.dik = K.durum.L.dik;
    R.kaynak = w.performance.getEntriesByType('resource').map(function (e) { return [e.name.replace(w.location.origin, ''), e.encodedBodySize]; });
    R.tasma = d.documentElement.scrollWidth - d.documentElement.clientWidth;
    R.bolum = d.querySelectorAll('.numune').length; R.kart = d.querySelectorAll('.kart').length; R.dort = d.querySelectorAll('#dort li').length;
    R.harici = Array.prototype.filter.call(d.querySelectorAll('a[href]'), function (a) { return /^https?:/.test(a.getAttribute('href')); }).length;
    R.eksikRel = Array.prototype.filter.call(d.querySelectorAll('a[target="_blank"]'), function (a) { return !/noopener/.test(a.rel); }).length;
    R.h1 = d.querySelector('h1') && d.querySelector('h1').textContent.slice(0, 60);
    R.kanvas = Array.prototype.map.call(d.querySelectorAll('.kat'), function (c) { return c.width + 'x' + c.height; });
  } catch (e) { R.hata = String(e); }
  console.log('SONUC:' + JSON.stringify(R));
}, __BEKLE__);
</script>"""


class Isleyici(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(KOK), **k)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/__hakem.html"):
            q = dict(p.split("=") for p in self.path.split("?", 1)[1].split("&")) if "?" in self.path else {}
            html = (HARNESS.replace("__W__", q.get("w", "1440")).replace("__H__", q.get("h", "900")).replace("__SORGU__", q.get("s", "").replace("%3F", "?").replace("%3D", "=")).replace("__BEKLE__", "5500"))
            b = html.encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        super().do_GET()


def calistir(url, genislik, yukseklik, png=None):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        args = [CHROME, "--headless=new", "--disable-extensions", "--no-first-run", "--hide-scrollbars", f"--window-size={genislik},{yukseklik}", "--enable-unsafe-swiftshader",
                "--use-angle=swiftshader", "--ignore-gpu-blocklist", f"--user-data-dir={d}", "--enable-logging=stderr", "--log-level=0", "--virtual-time-budget=9000"]
        if png:
            args.append(f"--screenshot={png}")
        args.append(url)
        p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        m = re.search(r'SONUC:(\{.*?\})", source', p.stderr)
        konsol = [l[-220:] for l in p.stderr.splitlines() if ("CONSOLE" in l or "Uncaught" in l or "Refused" in l) and "SONUC:" not in l and "GL Driver" not in l]
        return (json.loads(m.group(1)) if m else None), konsol


def main():
    if not CHROME:
        print("Chromium bulunamadı"); return 2
    class Sunucu(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

        def handle_error(self, *a):  # tarayıcı boşta bağlantıları keser; gürültü yapma
            pass

    sunucu = Sunucu(("127.0.0.1", 0), Isleyici)
    port = sunucu.server_address[1]
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    out = {"sema": "biy.kartela.dogrulama.v1", "zaman_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tarayici": os.path.basename(os.path.dirname(os.path.dirname(CHROME))) if CHROME else None, "kosular": {}}
    sorunlar = []
    for ad, (w, h, s) in {"masaustu": (1440, 900, ""), "mobil": (390, 844, ""), "ayrik": (1440, 900, "%3Fayir%3D100")}.items():
        t0 = time.time()
        r, konsol = calistir(f"http://127.0.0.1:{port}/__hakem.html?w={w}&h={h}&s={s}", 1500, 1000)
        k = {"genislik": w, "yukseklik": h, "ms": round((time.time() - t0) * 1000), "konsol_hata": konsol, "sonuc": r}
        out["kosular"][ad] = k
        if not r or r.get("hata"):
            sorunlar.append(f"{ad}: sonuç alınamadı {r and r.get('hata')}")
            continue
        kotu = [o for o in r["olc"] if o[2] != "o"]
        if kotu: sorunlar.append(f"{ad}: ölçü kartı tutmuyor {kotu}")
        if konsol: sorunlar.append(f"{ad}: konsol {konsol[:2]}")
        if r["tasma"] > 0: sorunlar.append(f"{ad}: yatay taşma {r['tasma']} px")
        if r["eksikRel"]: sorunlar.append(f"{ad}: noopener eksik {r['eksikRel']}")
        dis = [x for x in r["kaynak"] if not x[0].startswith("/")]
        if dis: sorunlar.append(f"{ad}: dış kaynak {dis}")
    ana = [KOK / n for n in ("index.html", "kartela.css", "kartela.js", "veri.js", "veri.json", "OLCU_RAPORU.md")]
    out["dosyalar"] = {p.name: {"bayt": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()} for p in ana if p.exists() and p.name != "OLCU_RAPORU.md"}
    out["sorun"] = sorunlar
    (KOK / "olcu.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    # rapor 6. bölüm
    mas, mob = out["kosular"]["masaustu"]["sonuc"], out["kosular"]["mobil"]["sonuc"]
    if mas and mob:
        toplam = sum(x[1] for x in mas["kaynak"])
        satir = [f"Tarayıcı: {out['tarayici']} (headless, sanal zaman 9 sn) · ölçüm {out['zaman_utc']}.",
                 f"- Masaüstü 1440×900: dokuma {mas['ms']} ms, {mas['gw']}×{mas['gh']} tel, hücre {mas['hucre']} px; yatay taşma {mas['tasma']} px; bölüm {mas['bolum']}, ihtiyaç kartı {mas['kart']}, site kartı {mas['dort']}; konsol hatası {len(out['kosular']['masaustu']['konsol_hata'])}.",
                 f"- Mobil 390×844: dikey kompozisyon ({mob['gw']}×{mob['gh']} tel), dokuma {mob['ms']} ms; yatay taşma {mob['tasma']} px; konsol hatası {len(out['kosular']['mobil']['konsol_hata'])}.",
                 f"- Kaynak istekleri (aynı köken): {len(mas['kaynak'])} dosya, toplam {toplam} bayt; dış istek {len([x for x in mas['kaynak'] if not x[0].startswith('/')])}.",
                 "- Sayfanın kendi ölçü kartları (masaüstü): " + "; ".join(f"{o[0]} = {o[1]}" + ("" if o[2] == "o" else f" [{o[2]}]") for o in mas["olc"]) + ".",
                 f"- Plaka ayrık görünümü (?ayir=100) {'hatasız açıldı' if not out['kosular']['ayrik']['konsol_hata'] and out['kosular']['ayrik']['sonuc'] else 'SORUNLU'}.",
                 f"- Sorun listesi: {'yok' if not sorunlar else '; '.join(sorunlar)}.", ""]
        rp = (KOK / "OLCU_RAPORU.md").read_text(encoding="utf-8")
        yeni = re.sub(r"(## 6\. Tarayıcı ölçümü\n\n).*?(## 7\.)", lambda m: m.group(1) + "\n".join(satir) + "\n" + m.group(2), rp, flags=re.S)
        (KOK / "OLCU_RAPORU.md").write_text(yeni, encoding="utf-8", newline="\n")
    sunucu.shutdown()
    print(json.dumps({"sorun": sorunlar, "masaustu_ms": out["kosular"]["masaustu"]["ms"], "dosyalar": {k: v["bayt"] for k, v in out["dosyalar"].items()}}, ensure_ascii=False))
    return 1 if sorunlar else 0


if __name__ == "__main__":
    sys.exit(main())
