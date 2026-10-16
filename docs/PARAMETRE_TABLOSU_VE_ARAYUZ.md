# PARAMETRE TABLOSU VE MODÜL ARAYÜZ DOKÜMANI
**Proje:** Mikro-Şebeke Modellenmesi ve Analizi (EV Şarj İstasyonu İçeren Sistem)  
**Rol:** YM-2 (Şarj İstasyonu Modeli)  
**Tarih:** 21 Ekim 2026 (Hafta 2 Çıktısı)  
**İlgili Paydaşlar:** EM-1 (Tek Hat Şeması), YM-3 (EMS & Optimizasyon), YM-4 (Entegrasyon & Dashboard)

---

## 📋 1. İstasyon ve Bileşen Parametre Tablosu

| Parametre Adı | Değer | Birim | Kaynak / Açıklama | İlgili Rol |
| :--- | :--- | :--- | :--- | :--- |
| **İstasyon Konsepti** | Karma Ticari / AVM Otoparkı | - | EM-1 ve YM-2 ortak kararı | EM-1, YM-2 |
| **AC Şarj Soketi Sayısı** | 8 | Adet | Tip-2 Mennekes standardı | EM-1, YM-2 |
| **AC Soket Nominal Gücü** | 22.0 | kW | 3 Faz, 400V, 32A | EM-1, YM-2 |
| **DC Şarj Soketi Sayısı** | 2 | Adet | CCS2 Combo standardı | EM-1, YM-2 |
| **DC Soket Nominal Gücü** | 50.0 | kW | Hızlı şarj doğrultucu ünitesi | EM-1, YM-2 |
| **İstasyon Toplam Kurulu Güç** | **276.0** | **kW** | $(8 \times 22) + (2 \times 50)$ kW teorik tavan | EM-1, YM-4 |
| **Trafo / Bağlantı Kapasitesi** | **180.0** | **kW** | Şebeke bağlantı sınırı (EMS bu sınırı korumalıdır) | EM-1, YM-3 |
| **Aşırı Yük Payı (Over-subscription)** | %153 | - | Kurulu Güç / Trafo Sınırı $(276 / 180)$ | EM-2, YM-2 |
| **Şarj Verimliliği ($\eta$)** | 0.95 | Oran | Dönüştürücü ve batarya iç kayıpları | YM-2, YM-3 |
| **CC-CV Kırılma Eşiği** | 0.80 (%80) | Oran | Sabit akımdan sabit gerilime geçiş noktası | YM-2, EM-1 |
| **Zaman Adımı ($\Delta t$)** | 0.25 | Saat | 15 dakikalık simülasyon adımı (günde 96 adım) | YM-1..4 |

---

## 🚗 2. Araç Filosu Parametre Havuzu

| Model | Batarya (kWh) | Max AC (kW) | Max DC (kW) | V2G Desteği | Dağılımdaki Ağırlık |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Renault Zoe E-Tech** | 52.0 | 22.0 | 50.0 | Hayır | %25 |
| **Tesla Model 3 SR+** | 60.0 | 11.0 | 170.0 | Evet | %30 |
| **Togg T10X Uzun Menzil** | 88.5 | 22.0 | 150.0 | Hayır | %25 |
| **Hyundai Ioniq 5** | 77.4 | 11.0 | 220.0 | Evet | %10 |
| **Peugeot e-208** | 50.0 | 11.0 | 100.0 | Hayır | %10 |

---

## 🔌 3. Modül Arayüz Sözleşmesi (Interface Contract)

Proje akışında modüllerin birbirine sorunsuz entegre olabilmesi için YM-2 modülünün girdi ve çıktı fonksiyon imzaları sabitlenmiştir:

### A. YM-2 $\rightarrow$ YM-3 (Enerji Yönetim Sistemi Girişi)
Her simülasyon zaman adımında EMS'in (YM-3) karar üretebilmesi için çağıracağı metot:
```python
def bagli_araclar(current_time_hours: float) -> List[dict]:
    """
    O anda şarj istasyonundaki soketlere bağlı tüm araçların durumunu döner.
    
    Dönüş Formatı:
    [
        {
            "unit_id": "AC-01",                # str: Ünite kimliği
            "unit_type": "AC",                 # str: "AC" veya "DC"
            "unit_max_power_kw": 22.0,         # float: Ünitenin fiziksel tavan gücü
            "vehicle_id": "EV-003",            # str: Araç kimliği
            "model_name": "Togg T10X",         # str: Araç modeli
            "battery_capacity_kwh": 88.5,      # float: Batarya anma kapasitesi
            "current_soc": 0.42,               # float: Anlık şarj seviyesi (0.0 - 1.0)
            "target_soc": 0.90,                # float: İstenen hedef seviye (0.0 - 1.0)
            "energy_needed_kwh": 42.48,        # float: Hedefe kalan net enerji ihtiyacı
            "max_deliverable_power_kw": 22.0,  # float: CC-CV ve ünite limitindeki tavan güç
            "arrival_time": 17.5,              # float: Varış saati (ör. 17:30)
            "departure_time": 21.5,            # float: Ayrılış saati (ör. 21:30)
            "remaining_time_hours": 4.0,       # float: Kalan parklanma süresi (saat)
            "v2g_capable": False               # bool: Şebekeye enerji verebilir mi?
        },
        ...
    ]
    """
```

### B. YM-3 $\rightarrow$ YM-2 (EMS Güç Atama Komutu)
EMS algoritması (kural tabanlı veya MILP optimizasyonu) her üniteye vereceği gücü hesaplayıp bu metoda iletir:
```python
def apply_power_allocations(allocations: Dict[str, float]) -> None:
    """
    Parametre:
    allocations = {
        "AC-01": 22.0,   # float: kW (+: Şebekeden araca şarj)
        "AC-02": 11.0,   # float: kW (kısılmış şarj gücü)
        "DC-01": 50.0,   # float: kW (tam güç DC)
        "DC-02": -10.0,  # float: kW (-: Araçtan şebekeye V2G deşarjı)
    }
    """
```

### C. YM-2 $\rightarrow$ YM-4 (pandapower Yük Akışı ve Streamlit Dashboard Girişi)
YM-4'ün şebeke yük akışı analizi ve dashboard çizimleri için kullanacağı metotlar:
```python
def get_total_power_kw() -> float:
    """
    İstasyonun mikro-şebekeden çektiği net toplam gücü döner (kW).
    pandapower'da istasyon barasına aktif yük (P_load) olarak bağlanır.
    """

def get_dashboard_state() -> dict:
    """
    Streamlit arayüzünde canlı istasyon soketleri, dolu/boş durumları,
    araç SOC yüzdeleri ve anlık kW güçlerini göstermek için durum sözlüğü döner.
    """
```

### D. YM-2 $\rightarrow$ EM-1 / EM-2 (Simulink Dinamik Model Girişi)
Simulink ekibine 24 saatlik döngü sonucunda tespit edilen **en kritik tepe anı (ör. 18:30)** şu parametrelerle iletilir:
- Anlık toplam istasyon gücü ($P_{\text{load, critical}}$) [kW]
- Bağlı araç sayısı ve aktif şarj olan soket tipleri (AC/DC adedi)
- Ortalama araç batarya SOC değeri (Simulink batarya başlangıç durumu için)
