"""uret.py - Kartela veri hattı. kaynak/*.json (ham OSM + bağlı site ölçümü) -> veri.json, veri.js, OLCU_RAPORU.md

Ağ gerekmez; aynı kaynak her zaman aynı baytları üretir (zaman damgası kaynak dosyalardan gelir).
Kullanım:  python -B uret.py
"""
import json, math, hashlib, time, sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
KOK = Path(__file__).resolve().parent
KAYNAK = KOK / "kaynak"

# ------------------------------------------------------------------ renk bilimi (JS'teki kartela.js ile aynı formüller)
def srgb_lab(hexs):
    r, g, b = [int(hexs[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    R, G, B = lin(r), lin(g), lin(b)
    X = 0.4124564 * R + 0.3575761 * G + 0.1804375 * B
    Y = 0.2126729 * R + 0.7151522 * G + 0.0721750 * B
    Z = 0.0193339 * R + 0.1191920 * G + 0.9503041 * B
    f = lambda t: t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116  # noqa: E731
    fx, fy, fz = f(X / 0.95047), f(Y), f(Z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def de2000(l1, l2):
    L1, a1, b1 = l1
    L2, a2, b2 = l2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if (a1p or b1) else 0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if (a2p or b2) else 0
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dhp = 0
    else:
        dhp = h2p - h1p
        if dhp > 180:
            dhp -= 360
        elif dhp < -180:
            dhp += 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))
    Lpm, Cpm = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hpm = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hpm = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hpm = (h1p + h2p + 360) / 2
    else:
        hpm = (h1p + h2p - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hpm - 30)) + 0.24 * math.cos(math.radians(2 * hpm))
         + 0.32 * math.cos(math.radians(3 * hpm + 6)) - 0.20 * math.cos(math.radians(4 * hpm - 63)))
    dth = 30 * math.exp(-(((hpm - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cpm ** 7 / (Cpm ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / math.sqrt(20 + (Lpm - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cpm, 1 + 0.015 * Cpm * T
    Rt = -math.sin(math.radians(2 * dth)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def lum(hexs):
    r, g, b = [int(hexs[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def kontrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ------------------------------------------------------------------ yer ölçüleri
R_DUNYA = 6371008.8


def haversine(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_DUNYA * math.asin(math.sqrt(a))


def yon(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    dl = math.radians(lo2 - lo1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


RUZGAR = ["K", "KKD", "KD", "DKD", "D", "DGD", "GD", "GGD", "G", "GGB", "GB", "BGB", "B", "BKB", "KB", "KKB"]


def yon_adi(d):
    return RUZGAR[int((d + 11.25) // 22.5) % 16]


def m_derece(lat):  # enlem derecesi başına metre (WGS84 serisi), boylam derecesi başına metre
    p = math.radians(lat)
    return 111132.92 - 559.82 * math.cos(2 * p) + 1.175 * math.cos(4 * p), 111412.84 * math.cos(p) - 93.5 * math.cos(3 * p)


def merkez_alan(halka, lat_ref):
    """halka: [[lon,lat],...] -> (alan m², merkez [lat, lon]) yerel düzlemde ağırlık merkezi."""
    ky, kx = m_derece(lat_ref)
    pts = [(lo * kx, la * ky) for lo, la in halka]
    a = cx = cy = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        c = x1 * y2 - x2 * y1
        a += c
        cx += (x1 + x2) * c
        cy += (y1 + y2) * c
    a /= 2
    if abs(a) < 1e-9:
        return 0.0, [sum(la for _, la in halka) / len(halka), sum(lo for lo, _ in halka) / len(halka)]
    return abs(a), [cy / (6 * a) / ky, cx / (6 * a) / kx]


def ayrik(halka, lat0, lon0):
    """Halkayı (lon0, lat0) etrafında 1e-6 derece tamsayı ofsetlerine çevirir (ağ gerekmez, kayıpsız ~0,1 m)."""
    return [[round((lo - lon0) * 1e6), round((la - lat0) * 1e6)] for lo, la in halka]


def s6(x):
    return f"{x:.6f}"


# ------------------------------------------------------------------ girdiler
arama = json.loads((KAYNAK / "osm_arama.json").read_text(encoding="utf-8"))
cevre = json.loads((KAYNAK / "osm_cevre.json").read_text(encoding="utf-8"))
siteler = json.loads((KAYNAK / "site_olc.json").read_text(encoding="utf-8"))
N = arama["nesneler"]


def nesne(ad):
    return N[ad]["sonuc"][0]


def halka_of(ad):
    g = nesne(ad)["geojson"]
    return g["coordinates"][0] if g["type"] == "Polygon" else max((p[0] for p in g["coordinates"]), key=len)


parsel_halka = halka_of("modern_parsel")
_, parsel_merkez = merkez_alan(parsel_halka, 40.9884)
lat0, lon0 = parsel_merkez

# ------------------------------------------------------------------ üç blok (gerçek OSM ayak izi)
HEDEF_ESLEME = {"A": "watergarden", "B": "ifm", "C": "maltepe_miting"}
bloklar = []
for kod, ad in (("A", "blok_a"), ("B", "blok_b"), ("C", "blok_c")):
    o = nesne(ad)
    h = halka_of(ad)
    alan, mrk = merkez_alan(h, lat0)
    bloklar.append({"kod": kod, "ad": o["display_name"].split(",")[0], "osm": f"way/{o['osm_id']}", "yukseklik_m": int(float((o.get("extratags") or {}).get("height", 0))),
                    "alan_m2": round(alan), "merkez": [s6(mrk[0]), s6(mrk[1])], "halka": ayrik(h, lat0, lon0), "hedef": HEDEF_ESLEME[kod]})

# ------------------------------------------------------------------ hedefler
HEDEF_AD = {"watergarden": ("Watergarden AVM", "Alışveriş · sanat · buluşma", "https://watergarden.com.tr/iletisim", "watergarden-resmi"),
            "ifm": ("İstanbul Finans Merkezi", "İş · fikir · fırsat", "https://ifm.gov.tr/b/2/iletisim", "ifm-resmi"),
            "maltepe_miting": ("Maltepe Miting Alanı", "Sahil · açık hava · konser", "", "")}
hedefler = []
for kod, (ad, konu, resmi, olc_ad) in HEDEF_AD.items():
    o = nesne(kod)
    h = halka_of(kod)
    alan, mrk = merkez_alan(h, 40.99 if kod != "maltepe_miting" else 40.92)
    blok = next(b for b in bloklar if b["hedef"] == kod)
    bla, blo = float(blok["merkez"][0]), float(blok["merkez"][1])
    d_m, yn = haversine(bla, blo, mrk[0], mrk[1]), yon(bla, blo, mrk[0], mrk[1])
    hedefler.append({"kod": kod, "ad": ad, "konu": konu, "blok": blok["kod"], "osm": f"{o['osm_type']}/{o['osm_id']}", "merkez": [s6(mrk[0]), s6(mrk[1])], "alan_m2": round(alan),
                     "halka": ayrik(h, mrk[0], mrk[1]), "mesafe_m": round(d_m), "yon_onda": round(yn * 10), "yon_ad": yon_adi(yn), "resmi_url": resmi,
                     "resmi_durum": (siteler["olcumler"].get(olc_ad) or {}).get("durum") if olc_ad else None})

# ------------------------------------------------------------------ çevre binaları (parsel dışı da dahil; 3 blok ayrıca işaretli)
blok_idler = {b["osm"] for b in bloklar}
cevre_bina = []
for e in cevre["oge"]:
    if f"way/{e['id']}" in blok_idler:
        continue
    cevre_bina.append({"o": e["id"], "k": int(e["etiket"].get("building:levels", 0) or 0) if str(e["etiket"].get("building:levels", "")).isdigit() else 0, "h": ayrik(e["geom"], lat0, lon0)})
toplam_alan = 0.0
for e in cevre["oge"]:
    toplam_alan += merkez_alan(e["geom"], lat0)[0]

# ------------------------------------------------------------------ mürekkep (plaka) ölçüleri
MUREKKEP = [
    {"kod": "Z0", "anahtar": "zemin", "ad": "Çivit", "hex": "#1B2B4B", "kaynak": "çivit (Indigofera tinctoria)", "rol": "Zemin · dimi 3/1 kumaş"},
    {"kod": "P1", "anahtar": "yazi", "ad": "Ekru", "hex": "#F1EADB", "kaynak": "boyasız pamuk", "rol": "Yazı"},
    {"kod": "P2", "anahtar": "cevre", "ad": "Ceviz", "hex": "#8A6B4E", "kaynak": "ceviz kabuğu (Juglans regia)", "rol": "Çevre binaları · parsel"},
    {"kod": "P3", "anahtar": "yapi", "ad": "Safran", "hex": "#F0B429", "kaynak": "safran (Crocus sativus)", "rol": "Üç blok"},
    {"kod": "P4", "anahtar": "rota", "ad": "Kökboya", "hex": "#D63C54", "kaynak": "kökboya (Rubia tinctorum)", "rol": "Uçuş ipliği"},
    {"kod": "P5", "anahtar": "hedef", "ad": "Yeşil", "hex": "#34A98A", "kaynak": "çivit üstüne sarı (iki banyo)", "rol": "Hedef halkası"},
]
for m in MUREKKEP:
    m["pantone"] = None  # eşleşme yalnız fiziksel numune ölçülürse yazılır; ölçülmedi
labs = {m["anahtar"]: srgb_lab(m["hex"]) for m in MUREKKEP}
de = {}
for i, a in enumerate(MUREKKEP):
    for b in MUREKKEP[i + 1:]:
        de[f"{a['anahtar']}|{b['anahtar']}"] = round(de2000(labs[a["anahtar"]], labs[b["anahtar"]]) * 10)  # ondalık hatası olmasın: ΔE00 × 10 tamsayı
min_de = min(de.values())
kontr = {m["anahtar"]: round(kontrast(m["hex"], "#1B2B4B") * 100) for m in MUREKKEP if m["anahtar"] != "zemin"}  # kontrast × 100 tamsayı

veri = {
    "sema": "biy.kartela.veri.v1",
    "yapi": "Başka İstanbul Yok · Kartela",
    "uretim_utc": cevre["alinma_utc"],
    "merkez": {"ad": "Ataşehir Modern", "osm": f"way/{nesne('modern_parsel')['osm_id']}", "merkez": [s6(lat0), s6(lon0)],
               "adres": "Atatürk Mahallesi, Gülnihal Sokak, Ataşehir Modern Sitesi, Ataşehir / İstanbul", "adres_kaynak": "https://atasehirmodern.com/iletisim",
               "parsel": ayrik(parsel_halka, lat0, lon0)},
    "bloklar": bloklar,
    "hedefler": hedefler,
    "cevre": {"bina_adedi": len(cevre_bina), "yaricap_m": 450, "toplam_taban_m2": round(toplam_alan), "bina": cevre_bina},
    "murekkep": MUREKKEP,
    "ayriklik": {"yontem": "CIEDE2000 (kL=kC=kH=1), sRGB D65; değerler onda bir birim tamsayı (×10)", "esik_de00": 20, "en_kucuk_de00_onda": min_de, "cift_onda": de, "zemin_kontrast_yuzde": kontr},
    "surec": {"suzulme_orani": "2.5", "suzulme_notu": "Varsayım: kanat elbisesiyle yaklaşık 2,5:1 yatay/düşey süzülme; yalnız büyüklük mertebesi için. Ölçülmüş bir uçuş verisi değildir."},
    "kumas": {"lif": "pamuk", "dokuma": "dimi 3/1", "cozgu": "çivit", "atki": "ekru", "selvaj": "ekru + kökboya çizgi", "metre_hucre": 8},
    "siteler": siteler["olcumler"],
    "siteler_yontem": siteler["yontem"],
    "kaynaklar": {"osm_cevre": {"alinma_utc": cevre["alinma_utc"], "kaynak": cevre["kaynak"], "lisans": cevre["lisans"]},
                  "osm_arama": {"alinma_utc": arama["alinma_utc"], "kaynak": arama["kaynak"], "lisans": arama["lisans"],
                                "url": {k: v["url"] for k, v in N.items()}}},
}
assert min_de >= 200, "plakalar yeterince ayrık değil: en küçük ΔE00×10 = %s; en yakın çiftler: %s" % (min_de, sorted(de.items(), key=lambda kv: kv[1])[:4])

metin = json.dumps(veri, ensure_ascii=False, separators=(",", ":"))
(KOK / "veri.json").write_text(metin, encoding="utf-8", newline="\n")
sha = hashlib.sha256(metin.encode("utf-8")).hexdigest()
(KOK / "veri.js").write_text("window.BIY=" + metin + ";window.BIY_SHA256=\"" + sha + "\";\n", encoding="utf-8", newline="\n")

# ------------------------------------------------------------------ OLCU_RAPORU.md
S = []
S.append("# Başka İstanbul Yok · Kartela — ÖLÇÜ RAPORU\n")
S.append("İlke: ölçülmeyen iddia edilmez. Bu raporda her sayı kaynağı, yöntemi ve zamanıyla yazılır; sayfa aynı sayıları tarayıcıda yeniden hesaplar (Numune 05).\n")
S.append("## 1. Kaynak ve lisans\n")
S.append(f"- Konum ve bina ayak izi: OpenStreetMap (ODbL 1.0, © OpenStreetMap katkıcıları). Alınma: {cevre['alinma_utc']} (çevre binaları, Overpass), {arama['alinma_utc']} (nesne aramaları, Nominatim lookup).")
S.append("- Harita döşemesi, uydu, sokak panoraması, Google/Mapbox/MapLibre **kullanılmadı**. Yalnız nokta koordinatı ve bina çokgeni alındı; çizim bu sayfanın kendi dokuma motorudur.")
S.append(f"- Resmî adres (proje sitesi): {veri['merkez']['adres']} — kaynak {veri['merkez']['adres_kaynak']}\n")
S.append("## 2. Üç blok (OSM ayak izi)\n")
for b in bloklar:
    S.append(f"- {b['ad']} · {b['osm']} · yükseklik {b['yukseklik_m']} m (OSM etiketi) · taban {b['alan_m2']} m² · merkez {b['merkez'][0]}, {b['merkez'][1]} · hedef: {b['hedef']}")
S.append(f"\nÇevre: {len(cevre_bina)} bina (≤ 450 m), toplam taban ≈ {round(toplam_alan)} m².\n")
S.append("## 3. Hedefler ve ölçüler (blok ağırlık merkezi → hedef çokgen ağırlık merkezi; haversine R=6371008,8 m; ilk yön)\n")
for h in hedefler:
    S.append(f"- Blok {h['blok']} → {h['ad']} ({h['osm']}): {h['mesafe_m']} m · yön {h['yon_onda'] / 10:.1f}° ({h['yon_ad']}) · merkez {h['merkez'][0]}, {h['merkez'][1]}" + (f" · resmî sayfa HTTP {h['resmi_durum']}" if h["resmi_durum"] else ""))
S.append("\nSüzülme (varsayım, ölçülmüş değil): kanat elbisesi ≈ 2,5:1 → çatı yüksekliği × 2,5 yatay menzil.\n")
for b in bloklar:
    h = next(x for x in hedefler if x["kod"] == b["hedef"])
    S.append(f"- Blok {b['kod']}: {b['yukseklik_m']} m × 2,5 = {round(b['yukseklik_m'] * 2.5)} m menzil; hedef {h['mesafe_m']} m uzakta → {h['mesafe_m'] / (b['yukseklik_m'] * 2.5):.1f} kat. Uçuş bu yüzden bir **anlatım**; ulaşım iddiası değildir.")
S.append("\n## 4. Plakalar (mürekkep) — ayrıklık ölçüsü\n")
S.append(f"Yöntem: {veri['ayriklik']['yontem']}. Eşik: ΔE00 ≥ {veri['ayriklik']['esik_de00']} (ayrık sayılır). En küçük çift: ΔE00 = {min_de / 10:.1f}.\n")
for m in MUREKKEP:
    S.append(f"- {m['kod']} {m['ad']} {m['hex']} · {m['rol']} · bitki/lif: {m['kaynak']} · Pantone eşleşmesi: ölçülmedi" + (f" · zemin kontrastı {kontr[m['anahtar']] / 100:.2f}:1" if m["anahtar"] in kontr else ""))
S.append("\nÇiftler (ΔE00): " + "; ".join(f"{k.replace('|', '–')} {v / 10:.1f}" for k, v in de.items()) + "\n")
S.append("## 5. Bağlı sitelerin ölçümü\n")
S.append(f"Yöntem: {siteler['yontem']}\n")
for ad, s in siteler["olcumler"].items():
    S.append(f"- {ad}: HTTP {s.get('durum')} · {s.get('ms', '-')} ms · {s.get('baslik') or s.get('hata', '')} · {s.get('zaman_utc')}")
S.append("\n## 6. Tarayıcı ölçümü\n")
S.append("(dogrula.py bu bölümü gerçek tarayıcı koşusuyla doldurur.)\n")
S.append("## 7. Bu sayfada ne yok\n")
S.append("- Canlı müsaitlik, gerçek randevu, ödeme, kullanıcı hesabı, çerez, izleyici yok. Terzi/danışman takvimi bağlı değil (kaynak: afair.live Yaşam Masası, ölçüm tarihi yukarıda).")
S.append("- Gerçek uçuş/ulaşım yok: mesafeler kuş uçuşu çizgidir, rota değildir; süzülme oranı varsayımdır.")
S.append("- Pantone eşleşmesi yok: renkler ekran sRGB değerleridir; fiziksel numune ölçülmeden Pantone iddia edilmez.")
S.append("- baskaistanbulyok.com alan adına bağlantı iddiası yok (DNS/yayın ayrıca doğrulanır).\n")
S.append("## 8. Yeniden üretim\n")
S.append("`python -B uret.py` (ağ gerekmez) → veri.json, veri.js, bu rapor. `python -B dogrula.py` → gerçek tarayıcıda ölçüm. veri.json SHA-256: " + sha + "\n")
(KOK / "OLCU_RAPORU.md").write_text("\n".join(S), encoding="utf-8", newline="\n")

print("veri.json", len(metin), "bayt, sha256", sha[:16])
print("bloklar:", [(b["kod"], b["yukseklik_m"], b["alan_m2"]) for b in bloklar])
for h in hedefler:
    print("hedef", h["kod"], h["mesafe_m"], "m", h["yon_onda"] / 10, h["yon_ad"], h["alan_m2"], "m2")
print("cevre bina", len(cevre_bina), "| en kucuk dE00", min_de / 10)
print("dE00:", de)
print("kontrast (zemine):", kontr)
