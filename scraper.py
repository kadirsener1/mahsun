import requests

# 1. GITHUB'DAKİ ORİJİNAL PLAYLIST URL'Sİ
REMOTE_PLAYLIST_URL = "https://raw.githubusercontent.com/kadirsener1/avva/refs/heads/main/playlist.m3u"


def main():
    # ----------------- KANAL BULMA / TARAMA KISMI -----------------
    # Kendi kodunuzda kanalları bulup link ürettiğiniz kısım burasıdır.
    # Burada amaç; kanal adını KEY, yeni linki VALUE olarak bir dict içinde toplamak.
    # Örnek (Kendi kodunuza göre burayı güncelleyin):
    yeni_kanallar = {
        "Kanal D": "http://yeni-link-kanald.m3u8",
        "Star TV": "http://yeni-link-startv.m3u8",
        "TRT 1": "http://yeni-link-trt1.m3u8",
        # Kendi tarama algoritmanızdan gelen verileri buraya doldurun.
    }
    # --------------------------------------------------------------

    print("GitHub'daki orijinal playlist indiriliyor...")
    try:
        response = requests.get(REMOTE_PLAYLIST_URL)
        response.raise_for_status()
        # Satır sonu karakterlerine göre listeye bölüyoruz
        playlist_lines = response.text.splitlines()
    except Exception as e:
        print(f"Hata: GitHub listesi indirilemedi! {e}")
        return

    guncellenmis_satirlar = []
    i = 0
    toplam_satir = len(playlist_lines)

    print("Playlist güncelleniyor (Sıralama ve düzen korunuyor)...")

    while i < toplam_satir:
        satir = playlist_lines[i]

        # Eğer satır #EXTINF ile başlıyorsa kanal bilgisini içeriyordur
        if satir.startswith("#EXTINF"):
            guncellenmis_satirlar.append(satir)  # Meta veri satırını aynen koru

            # Kanal adını virgülden sonraki kısımdan çekiyoruz (Örn: ...,Kanal D)
            kanal_adi = ""
            if "," in satir:
                kanal_adi = satir.split(",")[-1].strip()

            # Bir sonraki satırın varlığını kontrol et (Bu satır kanalın URL'sidir)
            if i + 1 < toplam_satir:
                sonraki_satir = playlist_lines[i + 1]

                # Eğer sonraki satır bir URL ise (yorum satırı veya boşluk değilse)
                if not sonraki_satir.startswith("#") and sonraki_satir.strip():
                    # Kanal ismi bizim yeni listemizde var mı? (Birebir uyum kontrolü)
                    if kanal_adi in yeni_kanallar:
                        # Eşleşme bulundu! Eski link yerine yenisini ekle
                        yeni_link = yeni_kanallar[kanal_adi]
                        guncellenmis_satirlar.append(yeni_link)
                        print(f"Güncellendi: {kanal_adi}")
                    else:
                        # Eşleşme yoksa eski linki aynen koru
                        guncellenmis_satirlar.append(sonraki_satir)

                    i += 2  # Hem EXTINF hem URL satırını işlediğimiz için 2 adım atla
                    continue

        # #EXTINF dışındaki satırları (#EXTM3U başlığı, boş satırlar vb.) aynen koru
        guncellenmis_satirlar.append(satir)
        i += 1

    # 2. TEK BİR playlist.m3u DOSYASI OLARAK KAYDETME
    dosya_adi = "playlist.m3u"
    try:
        with open(dosya_adi, "w", encoding="utf-8") as f:
            f.write("\n".join(guncellenmis_satirlar))
        print(f"İşlem tamamlandı! '{dosya_adi}' başarıyla oluşturuldu.")
    except Exception as e:
        print(f"Dosya yazılırken hata oluştu: {e}")


if __name__ == "__main__":
    main()
