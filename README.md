# Başka İstanbul Yok · Kartela (MASA)

Harita değil, kartela: Ataşehir Modern'in üç bloğu ve çevresindeki 169 binanın **gerçek ayak izi** (OpenStreetMap, ODbL) dimi dokuma bir kumaş olarak
dokunur; her renk ayrı bir **plaka**dır ve kaydırıcıyla birbirinden ayrılır. Üç çatıdan üç hedefe uçuş ipliği, ölçüleriyle birlikte gösterilir.
Sayfadaki her sayı kaynağı ve ölçüm tarihiyle yazılır; sayfa aynı sayıları tarayıcıda yeniden hesaplar (Numune 05).

Sade sürüm (Dila'nın 8 maddesi): az metin, bölüm başına tek eylem, ayrıntı "Künye / Kaynak / Ölçüm" açılırlarının arkasında. Hareket gerçek ve yönetilebilir:
saçak rüzgârda sönümlü, sürülen bir salınıcı olarak hesaplanır (yay + sönüm + rüzgâr; kaydırıcı ve imleç yönetir), plakalar kaydırıcıyla ayrılır,
uçuş iğnesini kullanıcı çatıdan başlatır. Hareket azaltma tercihi açıksa hiçbir şey kendiliğinden oynamaz; kullanıcı kaydırırsa ya da tıklarsa oynar.

- Harici betik, yazı tipi, görsel, harita döşemesi, uydu, sokak panoraması, Google/Mapbox/MapLibre, çerez, izleyici: **yok**.
- Canlı müsaitlik ve gerçek randevu: **yok**. Terzi/danışman talebi, çalışan "Yaşam Masası" sayfasına bağlanır; kaynak sayfanın kendi cümlesi ölçüm tarihiyle gösterilir.
- Pantone eşleşmesi: **ölçülmedi** (renkler ekran sRGB değerleridir).
- Uçuş: gerçek ulaşım iddiası değil, anlatımdır; süzülme oranı (2,5:1) bir varsayımdır.

## Dosyalar
`index.html` · `kartela.css` · `kartela.js` (dokuma motoru) · `veri.js` / `veri.json` (aynı veri; SHA-256 sayfada sınanır) · `OLCU_RAPORU.md` (ölçü raporu)
· `kaynak/` (ham OSM ve bağlı site ölçümleri) · `uret.py` (veri hattı, ağ gerekmez) · `dogrula.py` (gerçek tarayıcı ölçümü) · `olcu.json`

## Yeniden üretim
```
python -B uret.py          # kaynak/*.json -> veri.json, veri.js, OLCU_RAPORU.md
set SERGI_CHROME=<chromium yolu>
python -B dogrula.py       # masaüstü, mobil ve ayrık görünüm; olcu.json ve rapor 6. bölüm
python -m http.server 8771 # yerel önizleme
```

Konum ve bina geometrisi © OpenStreetMap katkıcıları (ODbL 1.0). Deneysel sürüm; baskaistanbulyok.com alan adına bağlantı iddiası yoktur.
