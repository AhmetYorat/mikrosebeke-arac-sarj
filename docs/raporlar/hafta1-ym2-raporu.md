# HAFTA 1 İLERLEME RAPORU (9 – 14 Ekim 2026)
**Ders:** Akıllı Şebekeler Dersi Projesi  
**Rol:** YM-2 (Yazılım Üyesi 2 - Şarj İstasyonu Modeli)  
**Rapor Teslim Tarihi:** 15 Ekim 2026 (Perşembe Dersi)  
**Aşama:** Başlangıç ve Kapsam: Konuyu ve Referans Örneği Tanıma  

---

## 📌 1. Bu Hafta Yapılanlar (Kısa Maddeler)
- **Şarj Standartları Araştırıldı:** AC Seviye-2 (Tip-2, 22 kW üç faz), DC Hızlı Şarj (CCS2 / Combo-2, 50 kW ve 150 kW) ve Li-ion bataryalar için Sabit Akım - Sabit Gerilim (CC-CV) şarj eğrisi mekanizması incelendi.
- **İstasyon Parametre Listesi Taslağı Hazırlandı:** İstasyon tipi, ünite sayıları, nominal güç limitleri, trafo sınırı ve incelenecek araç batarya havuzu EM-1 ile koordine edilmek üzere taslak olarak çıkarıldı.
- **MathWorks Referans Örneği İncelendi:** Simscape Electrical dokümantasyonundaki `MicrogridEVToGridExample` (Microgrid with Electric Vehicles V2G Support) örneği incelendi. Örnekteki araçların sadece 2 sabit batarya grubu olarak modellendiği, bizim katkımızın ise araçların tek tek gelip bağlandığı, CC-CV eğrisine sahip ve ünite bazlı yönetilen gerçekçi bir istasyon olacağı belirlendi.
- **Ekip İçi Kapsam Kararına Katkı Sağlandı:** EM-1 ve YM ekibiyle birlikte istasyon tipinin "Karma AVM / Ofis & Ticari Otopark" olması ve Python tarafında 1 temsili günün (24 saat, 15 dakikalık adımlarla) modellenmesi yönünde ortak karar taslağı oluşturuldu.

---

## 🔍 2. Şarj Standartları Araştırma Notları

### A. AC Şarj Standardı (Tip-2 Mennekes / IEC 62196-2)
- **Nominal Güç:** 22 kW (400V AC, 32A, Üç Faz).
- **Özellik:** Şebekeden gelen alternatif akım doğrudan araca iletilir. Doğrultma işlemi aracın yerleşik şarj cihazı (On-Board Charger - OBC) tarafından yapılır.
- **Darboğaz Kısıtı:** Birçok ticari binek EV'nin dahili OBC kapasitesi 11 kW ile sınırlıdır (Örn: Tesla Model 3 standart, Peugeot e-208). İstasyon 22 kW sunsa dahi araç en fazla 11 kW çekebilir. Bu kısıt modelimizde araç ve ünite gücünün minimumu (`min(P_arac, P_unite)`) şeklinde dikkate alınacaktır.
- **Kullanım Senaryosu:** 3 saat ve üzeri uzun süreli kalışlar (Ofis, AVM, gece parklanma).

### B. DC Hızlı Şarj Standardı (CCS2 / Combined Charging System)
- **Nominal Güç:** 50 kW (veya 150 kW Ultra Hızlı Şarj).
- **Özellik:** Güç elektroniği ve AC/DC doğrultucu istasyon kabini içerisindedir. Doğrudan batarya paketine doğru akım basılır; OBC limiti devre dışıdır.
- **Kullanım Senaryosu:** 20 – 60 dakika arası kısa süreli ve acil şarj ihtiyaçları.

### C. CC-CV (Sabit Akım - Sabit Gerilim) Şarj Karakteristiği
Li-ion bataryaların güvenli şarjı ve hücre aşırı gerilimini önlemek için şarj süreci iki fazdan oluşur:
1. **Sabit Akım (Constant Current - CC) Aşaması:** $\text{SOC} < 0.80$ iken batarya anma gücünde ($P_{\text{nom}}$) şarj edilir.
2. **Sabit Gerilim (Constant Voltage - CV) Aşaması:** $\text{SOC} \ge 0.80$ olduğunda hücre gerilimi tepe noktaya ulaştığı için akım ve güç kademeli olarak azaltılır:
   $$P(SOC) = P_{\text{nom}} \times \max\left(0.15, \, \frac{1.0 - \text{SOC}}{0.20}\right) \quad (\text{SOC} \ge 0.80)$$
   *Bu sayede SOC %80'den %100'e yaklaşırken çekilen güç nominalin %15'ine kadar iner; tepe yük simülasyonunda gerçekçi bir davranış sergiler.*

---

## 📊 3. İstasyon Parametre Listesi Taslağı

| Parametre | Taslak Değer | Gerekçe / Açıklama |
| :--- | :--- | :--- |
| **İstasyon Konsepti** | Karma Ticari / AVM Otoparkı | Hem uzun süreli (AC) hem hızlı (DC) şarj dinamiklerini incelemek için en uygun yapı |
| **AC Şarj Soketi Sayısı** | 8 Adet | Her biri 22 kW Tip-2 (Toplam teorik AC güç: 176 kW) |
| **DC Şarj Soketi Sayısı** | 2 Adet | Her biri 50 kW CCS2 (Toplam teorik DC güç: 100 kW) |
| **İstasyon Toplam Kurulu Güç** | **276 kW** | Tüm soketlerin tam güç çektiğindeki teorik tavan |
| **Trafo / Şebeke Bağlantı Limiti** | **180 kW – 200 kW** | Kontrolsüz şarjda aşımı (peak overload) gözlemlemek ve EMS'in tepe tıraşlama (peak-shaving) başarısını kanıtlamak için soket gücünden düşük seçilmiştir |
| **Zaman Çözünürlüğü** | 15 Dakika ($\Delta t = 0.25$ saat) | 24 saatte 96 zaman adımı (Hassas yük eğrisi) |
| **Araç Batarya Boyutları** | 50 – 88.5 kWh | Renault Zoe (52 kWh), Tesla Model 3 (60 kWh), Togg T10X (88.5 kWh) |

---

## ❓ 4. Karşılaşılan Sorunlar ve 15 Ekim Dersinde Hocaya Sorulacak Sorular

1. **Referans Örnek:** Derste önerilen MathWorks modeli `MicrogridEVToGridExample` mıdır? Bu modeldeki iki batarya grubunu soket bazlı dinamik istasyon haline getirmemiz bizim özgün katkımız olarak yeterli midir?
2. **Simülasyon Kapsamı:** Python tarafında 1 temsili günün (24 saat, 15 dk çözünürlük) modellenmesi proje isterleri için yeterli midir, yoksa mevsimsel 1 yıllık analiz mi beklenmektedir? *(Ekip olarak önerimiz: 1 temsili günün ayrıntılı ve yüksek çözünürlüklü incelenmesi).*
3. **Trafo Kapasitesi Sınırı:** İstasyonun mikro-şebekeye bağlantı noktasına (PCC) trafo gücü olarak 180 kW veya 200 kW gibi sert bir sınır koyup, EMS'in bu sınırı aşmamasını (peak shaving) temel başarı metriği almamız uygun mudur?

---

## 🗓️ 5. Gelecek Hafta (Hafta 2) Planı
- **Araç Talep Modelinin Tasarımı:** Varış saatleri (akşam 18:00 piki Normal dağılımı), otoparkta kalış süreleri, geliş ve hedef SOC dağılımlarının matematiksel tanımlanması.
- **Sınıf Mimarisi ve UML Diyagramı:** `ElectricVehicle`, `ChargingUnit` ve `ChargingStation` sınıflarının nesne yönelimli tasarımı ve sınıf diyagramının çizilmesi.
- **Parametre Tablosu ve Modül Arayüz Sözleşmesi:** YM-3 (EMS) ve YM-4 (pandapower/Dashboard) ile veri formatlarının (kW, kWh, saat) sabitlenmesi.
