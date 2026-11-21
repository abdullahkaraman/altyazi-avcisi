# altyazi-avcisi

PS5'te oynadığın oyunun İngilizce altyazısını canlı olarak Türkçeye çevirip telefonda, tablette
ya da TV'nin köşesinde gösterir. GTA 6 ile denendi. Ekranda İngilizce altyazı gösteren her oyunda
çalışması gerekir.

```
PS5 ──HDMI──► TV (oyunu burada oynarsın)
 │
 └──ağ──► Mac'te PS Remote Play penceresi
            → altyazı bandı okunur (macOS Vision)
            → Gemini Türkçeye çevirir (~1 sn)
            → yerel ağda bir sayfa: http://<Mac'in IP'si>:8765
                 → telefon / tablet / TV köşesi
```

Kendi yönteminle de yapabilirsin. Buradaki kod, bir yapay zekâ asistanıyla (Claude) birlikte bir
akşamda yazıldı. Yönergeyi bir yapay zekâya verip kendi kurulumuna göre uyarlatabilirsin.

## Gerekenler

- **Mac** (macOS 14 veya üstü). Altyazıyı macOS'un kendi yazı tanıması (Vision) okuyor, bu yüzden
  şimdilik yalnız Mac'te çalışıyor.
- **PS5** ve [PS Remote Play](https://remoteplay.dl.playstation.net/remoteplay/) uygulaması.
- **İkinci bir PlayStation hesabı.** Remote Play'e, konsolda oynadığın hesaptan farklı bir hesapla
  bağlan. Aynı hesap iki yerde açık olunca bağlantı kopabiliyor.
- **Gemini API anahtarı:** [Google AI Studio](https://aistudio.google.com/apikey)'dan ücretsiz
  alınıyor. Herkes kendi anahtarını kullanır, depoda anahtar yok.
- Python 3 ve Xcode komut satırı araçları (`xcode-select --install`).
- Çeviriyi göstereceğin bir telefon ya da tablet (aynı Wi-Fi'da).

## Kurulum

1. **Kodu indir:**
   ```sh
   git clone https://github.com/abdullahkaraman/altyazi-avcisi.git && cd altyazi-avcisi
   ```
2. **Ekran okuyucuyu derle:**
   ```sh
   swiftc -O subocr.swift -o subocr
   ```
3. **Anahtarını ekle:**
   ```sh
   cp .env.public .env
   ```
   `.env` dosyasını aç, `GEMINI_API_KEY=` satırına kendi anahtarını yaz. `.env` git'e girmez.
4. **Ekran kaydı izni ver:** Sistem Ayarları → Gizlilik ve Güvenlik → Ekran ve Sistem Sesi Kaydı →
   programı çalıştıracağın terminal uygulamasını aç (Terminal, iTerm…). İzin, terminal yeniden
   açılınca geçerli olur.
5. **PS5'te Remote Play'i aç:** Ayarlar → Sistem → Remote Play → Etkinleştir. Mac'te Remote Play'i
   açıp ikinci hesapla PS5'e bağlan.

## Çalıştırma

```sh
python3 altyazi.py
```

Ekrana `Sayfa: http://192.168.x.x:8765` yazar. Bu adresi telefonda ya da tablette aç. Ekrana bir
kez dokununca sayfa tam ekrana geçer. Oyunda biri konuştukça Türkçesi orada belirir.

- Yeni cümle büyük ve beyaz yazılır, bir önceki üstte gri durur. Hızlı geçen satırı kaçırmazsın.
- 5 saniye kimse konuşmazsa ekran temizlenir.
- Sağ alttaki nokta yeşilse sayfa bağlı demektir.

### Çeviriyi nerede göreceksin?

- **Telefon/tablet TV'nin yanında:** En temizi bu. TV yalnız oyunu gösterir, görüntü kalitesi bozulmaz.
- **Android TV / Google TV:** Bazı uygulamalar oyunun üstünde küçük, yüzen bir pencere açabiliyor.
  Sayfayı o pencerede açarsan çeviri TV'nin köşesinde durur.
- **Samsung (Tizen):** Uygulamalar HDMI görüntüsünün üstüne çıkamıyor. Tek yol **Multi View**:
  telefonu ya da tableti TV'ye yansıtıp PiP olarak köşeye alırsın. Ama Multi View açıkken TV Oyun
  Modu'nu ve HDR'ı kapatıyor, görüntü kalitesi belirgin düşüyor. Bunu dert etmiyorsan çalışıyor.

## Bilmen gerekenler

- **Remote Play penceresi tamamen kapanmasın.** macOS, üstü tamamen başka bir pencereyle kapanan
  pencereyi çizmeyi bırakıyor. O zaman görüntü donar, çeviri durur. Pencerenin küçük bir kenarı
  görünse yeter. Mac'in kapağını da kapatma.
- **Başka oyunlarda altyazı yeri farklı olabilir.** Okunan alan pencerenin yüzdesi olarak verilir
  (varsayılan GTA 6 için: alt orta). Kendi oyununda ekran görüntüsü alıp dene:
  ```sh
  ./subocr file:ekran.png 0.2 0.82 0.8 0.935     # bu alanda ne okunuyor?
  python3 altyazi.py --band 0.2 0.82 0.8 0.935   # bulduğun alanla çalıştır
  ```
  Alanı fazla geniş tutarsan haritadaki, plakalardaki ya da tabelalardaki yazılar da çevrilir.
- **Gemini'nin hızı değişkendir.** Genelde bir satır 1 saniyenin altında çevriliyor. Google'ın
  sunucuları yoğunken 3-5 saniyeye çıkabiliyor. Ücretsiz katmanın dakikalık istek sınırı da var,
  aşılırsa birkaç satır çevrilmeden geçer.
- **Çeviri birebir değil.** Konuşma dili ve argo anlamıyla çevrilir, küfürler yumuşatılmaz.

## Hesap bilgilerini kimseye verme

Bu tür bir çözümü hazır sunan uygulamalar PlayStation hesabınla giriş yapmanı isteyebilir. O
zaman hesap bilgilerin onların sunucularına gider. Buradaki kurulumda PlayStation girişi yalnız
Sony'nin kendi Remote Play uygulamasında yapılır. Çeviri için Google'a yalnız altyazı metni
gider, ekran görüntüsü de hesap bilgisi de gitmez.

## Lisans

MIT
