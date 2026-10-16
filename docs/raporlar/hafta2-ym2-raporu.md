# HAFTA 2 İLERLEME RAPORU (15 – 21 Ekim 2026)
**Ders:** Akıllı Şebekeler Dersi Projesi  
**Rol:** YM-2 (Yazılım Üyesi 2 - Şarj İstasyonu Modeli)  
**Rapor Teslim Tarihi:** 22 Ekim 2026 (Perşembe Dersi)  
**Aşama:** Tasarım: Şema, Boyutlar ve Modül Arayüzleri  

---

## 📌 1. Bu Hafta Yapılanlar (Kısa Maddeler)
- **Araç Talep Modeli Tasarlandı:** Gerçekçi olasılık dağılımları kullanılarak 24 saatlik EV geliş/gidiş trafiği, varış saatleri ($T_{\text{arr}}$), parklanma süreleri ($T_{\text{stay}}$), geliş SOC ($SOC_{\text{arr}}$) ve hedef SOC ($SOC_{\text{target}}$) matematiksel modelleri oluşturuldu.
- **ChargingStation ve Vehicle Sınıf Tasarımı Tamamlandı:** Nesne yönelimli programlama (OOP) yapısında `ElectricVehicle`, `ChargingUnit` ve `ChargingStation` sınıfları tasarlanarak UML Sınıf Diyagramı hazırlandı.
- **Parametre Tablosu ve Modül Arayüz Dokümanı Repoya Eklendi:** YM-3 (EMS), YM-4 (pandapower/Dashboard) ve EM-1 (Tek Hat Şeması) ile fonksiyon imzaları, birimler (kW, kWh, saat, SOC) ve parametre değerleri sabitlendi.
- **Tasarımın Çalışır Prototipi ve Testi Hazırlandı:** Tasarlanan sınıfların doğrulanması için otomatik test betiği koşturuldu ve tasarımın hatasız çalıştığı kanıtlandı.

---

## 🎲 2. Araç Talep Modeli Tasarımı ve Olasılık Dağılımları

Elektrikli araçların rastgele gelişlerini ve oluşturdukları yükü simüle etmek için aşağıdaki istatistiksel modeller kurulmuştur:

```
                            ┌──────────────────────────────────────────────┐
                            │      24 Saatlik EV Talep Modeli Dağılımı     │
                            └──────────────────────┬───────────────────────┘
                                                   │
          ┌───────────────────────────┬────────────┴──────────────┬───────────────────────────┐
          ▼                           ▼                           ▼                           ▼
1. Varış Saati (T_arr)       2. Kalış Süresi (T_stay)     3. Geliş SOC (SOC_arr)      4. Hedef SOC (SOC_target)
• Akşam Piki: N(18.0, 1.6)h  • AC Araçlar: U(2.5, 9.0)h   • Dağılım: U(0.18, 0.45)    • Dağılım: U(0.85, 1.00)
• Gündüz: N(11.5, 2.5)h      • DC Araçlar: U(0.5, 2.0)h   • Ortalama: %31.5           • Kullanıcı memnuniyeti hedefi
```

1. **Varış Saati Dağılımı ($T_{\text{arr}}$):**
   - **Akşam Piki (%65):** $T_{\text{arr}} \sim \mathcal{N}(\mu = 18.0, \, \sigma = 1.6)$ saat. *(Proje föyü Madde 5'teki Normal(18:00, 1.5h) dağılımı referans alınmıştır).*
   - **Gündüz Varışları (%35):** $T_{\text{arr}} \sim \mathcal{N}(\mu = 11.5, \, \sigma = 2.5)$ saat.
2. **Kalış Süresi Dağılımı ($T_{\text{stay}}$):**
   - AC soketler (Tip-2 22 kW): $\text{Uniform}(2.5, \, 9.0)$ saat (Ofis/AVM ve gece parklanma).
   - DC hızlı şarj soketleri (CCS2 50 kW): $\text{Uniform}(0.5, \, 2.0)$ saat (Kısa süreli dolum).
3. **Başlangıç ve Hedef Şarj Seviyesi:**
   - Geliş Şarjı: $SOC_{\text{arr}} \sim \text{Uniform}(0.18, \, 0.45)$ (İstasyona düşük şarjla varış).
   - Hedef Şarj: $SOC_{\text{target}} \sim \text{Uniform}(0.85, \, 1.00)$ (Tam veya tama yakın dolum talebi).

---

## 🏛️ 3. Sınıf Mimarisi ve UML Sınıf Diyagramı

Sistemimizin nesne yönelimli mimarisi `docs/SINIF_DIYAGRAMI.md` dosyasında detaylandırılmış olup özet yapı aşağıdadır:

- **`ElectricVehicle`:** Aracın batarya kapasitesi (kWh), anlık/hedef SOC takibi, CC-CV şarj düşüm formülü ve V2G güvenlik limitleri.
- **`ChargingUnit`:** Soket bazlı yönetim (AC/DC tip, nominal güç, anlık güç, dolu/boş/şarjda durumu).
- **`ChargingStation`:** İstasyonun tamamı, toplam çekilen kW gücü, trafo sınırı koruması, EMS arayüzü (`bagli_araclar`) ve pandapower yük entegrasyonu.

---

## 🔌 4. Parametre Tablosu ve Modül Arayüz Özeti

Hafta 2 Çarşamba çıktısı olan resmi sözleşme `docs/PARAMETRE_TABLOSU_VE_ARAYUZ.md` dosyasında sunulmuştur. Ana başlıklar:
- **İstasyon Parametreleri:** 8 × 22 kW AC + 2 × 50 kW DC = **276 kW Toplam Güç**, **180 kW Trafo Sınırı**.
- **YM-3 (EMS) Arayüzü:** `ev_talebi = station.bagli_araclar(saat)` $\rightarrow$ EMS'e bağlı her aracın SOC, aciliyet ve enerji ihtiyacını liste olarak verir. EMS'in güç kararı `station.apply_power_allocations(karar)` ile soketlere aktarılır.
- **YM-4 (pandapower/Dashboard) Arayüzü:** `station.get_total_power_kw()` ile mikro-şebeke barasına gidecek anlık kW yükü üretilir.

---

## 📈 5. Kanıt: Sınıf Tasarımı ve Talep Modeli Doğrulama Çıktısı

Tasarlanan `ChargingStation`, `ElectricVehicle` ve `DemandModel` sınıfları `test_hafta2_tasarim.py` betiği üzerinden test edilmiş ve doğrulanmıştır:

```
======================================================================
⚡ YM-2 HAFTA 2: SINIF TASARIMI VE TALEP MODELİ DOĞRULAMA TESTİ ⚡
======================================================================
İstasyon: Merkezi Mikro-Şebeke EV Parkı
Soket Sayısı: 10 Adet (8 x 22.0 kW AC + 2 x 50.0 kW DC)
Kurulu Güç  : 276.0 kW | Trafo Sınırı: 180.0 kW
----------------------------------------------------------------------
Talep Modeli ile Üretilen Örnek Araçlar:
  • [EV-001] Tesla Model 3 SR+   | Batarya:  60.0 kWh | Varış: 10.4h | Hedef SOC: %94
  • [EV-005] Togg T10X Uzun     | Batarya:  88.5 kWh | Varış: 17.8h | Hedef SOC: %99
  • [EV-008] Renault Zoe E-Tech  | Batarya:  52.0 kWh | Varış: 18.2h | Hedef SOC: %91
----------------------------------------------------------------------
✅ CC-CV Karakteristiği Testi:
   - SOC %20 iken çekilebilir tavan güç : 22.00 kW (Sabit Akım)
   - SOC %90 iken çekilebilir tavan güç : 11.00 kW (Sabit Gerilim Düşümü)
✅ Arayüz Testi: bagli_araclar() çağrıldı -> 10 aktif talep başarıyla listelendi.
✅ Toplam İstasyon Gücü: 198.00 kW hesaplandı (pandapower girdisi hazır).
✅ Trafo Aşım Tespiti: True (Trafo sınırı olan 180 kW aşıldı, EMS akıllı şarjı gereklidir).
======================================================================
```

---

## ❓ 6. Karşılaşılan Sorunlar ve Çözümleri
1. **Problem:** Araçların dahili yerleşik şarj cihazı (On-Board Charger - OBC) AC soketin 22 kW olmasına rağmen 11 kW çekebiliyordu.  
   **Çözüm:** `ElectricVehicle.get_max_charging_power()` fonksiyonunda araç OBC kapasitesi ile soket kapasitesinin minimumu alınarak (`min(max_ac, unit_max)`) donanımsal darboğaz hesaba katıldı.
2. **Problem:** Akşam saatlerinde kontrolsüz şarjda trafo sınırının aşılması şebeke çökmesine yol açıyordu.  
   **Çözüm:** Hafta 2 arayüz sözleşmesine EMS'in müdahale edebileceği `apply_power_allocations()` fonksiyonu eklenerek güç kısma altyapısı hazırlandı.

---

## 🗓️ 7. Gelecek Hafta (Hafta 3) Planı
- **ChargingStation v1 Geliştirmesi:** Araçların geliş sırasına göre soketlere dinamik atanması, kalış süresi sonunda otomatik ayrılması.
- **Birim Testleri (Unit Tests):** `pytest` / `unittest` ile batarya dolumu, CC-CV eğrisi ve trafo aşım kontrollerinin otomatik testlerinin yazılması.
- **YM-4 ile İlk Veri Entegrasyonu:** Mock (sahte) veriler yerine gerçek istasyon yük profilinin simülasyon döngüsüne verilmesi.
