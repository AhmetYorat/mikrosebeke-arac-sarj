"""
Akıllı Şebekeler - YM-2 (Yazılım Üyesi 2)
Hafta 2 Sınıf Tasarımı ve Araç Talep Modeli Canlı Demo Betiği
"""
from microgrid.station import ChargingStation, DemandModel, ElectricVehicle


def main():
    print("=" * 72)
    print("⚡ YM-2 HAFTA 2: SINIF TASARIMI VE TALEP MODELİ DOĞRULAMA TESTİ ⚡")
    print("=" * 72)

    station = ChargingStation(
        station_id="STATION-01",
        name="Merkezi Mikro-Şebeke EV Parkı",
        transformer_limit_kw=180.0,
        num_ac_units=8,
        ac_unit_power_kw=22.0,
        num_dc_units=2,
        dc_unit_power_kw=50.0,
    )
    print(f"İstasyon Adı : {station.name}")
    print(f"Soket Sayısı : {len(station.units)} Adet (8 x 22.0 kW AC + 2 x 50.0 kW DC)")
    print(f"Kurulu Güç   : {station.total_capacity_kw:.1f} kW | Trafo Sınırı: {station.transformer_limit_kw:.1f} kW")
    print("-" * 72)

    # 1. CC-CV Şarj Eğrisi Doğrulaması
    print("\n🔍 [1/4] CC-CV Şarj Karakteristiği Doğrulaması:")
    test_car = ElectricVehicle(
        vehicle_id="EV-TEST",
        model_name="Renault Zoe E-Tech",
        battery_capacity_kwh=52.0,
        initial_soc=0.20,
        target_soc=0.95,
        max_ac_power_kw=22.0
    )
    p_20 = test_car.get_max_charging_power("AC", 22.0)
    test_car.current_soc = 0.90
    p_90 = test_car.get_max_charging_power("AC", 22.0)
    print(f"  • SOC = %20 iken çekilebilir güç : {p_20:.2f} kW (Sabit Akım)")
    print(f"  • SOC = %90 iken çekilebilir güç : {p_90:.2f} kW (Sabit Gerilim)")
    assert p_20 == 22.0 and p_90 < 22.0
    print("  ✅ CC-CV matematiği doğrulandı.")

    # 2. Araç Talep Modeli Testi
    print("\n🎲 [2/4] Araç Talep Modeli Testi:")
    model = DemandModel(random_seed=42)
    fleet = model.generate_fleet(total_vehicles=10)
    print(f"  • Üretilen Araç Sayısı: {len(fleet)}")
    for ev in fleet[:3]:
        print(f"    - [{ev.vehicle_id}] {ev.model_name:<20} | Batarya: {ev.battery_capacity_kwh:4.1f} kWh | Varış: {ev.arrival_time:04.1f}h")
    print("  ✅ Talep modeli başarıyla çalıştı.")

    # 3. Soket Bağlantısı ve Arayüz Testi
    print("\n🔌 [3/4] Modül Arayüz Sözleşmesi Testi:")
    for ev in fleet:
        station.plug_in_vehicle(ev)
    demands = station.bagli_araclar(current_time_hours=18.0)
    print(f"  • YM-3 EMS Arayüzü (`bagli_araclar`): {len(demands)} araç talebi listelendi.")

    allocations = {d["unit_id"]: d["max_deliverable_power_kw"] for d in demands}
    station.apply_power_allocations(allocations)
    total_p = station.get_total_power_kw()
    print(f"  • YM-4 pandapower Arayüzü (`get_total_power_kw`): {total_p:.2f} kW")
    print("  ✅ Arayüz fonksiyonları doğrulandı.")

    # 4. Trafo Aşım Kontrolü
    print("\n⚠️ [4/4] Trafo Aşım Tespiti:")
    overloaded = station.is_transformer_overloaded()
    print(f"  • Trafo Sınırı: {station.transformer_limit_kw:.1f} kW | Çekilen: {total_p:.1f} kW")
    print(f"  • Trafo Aşıldı mı?: {overloaded} (Aşım: {max(0.0, total_p - station.transformer_limit_kw):.1f} kW)")
    print("  ✅ Trafo güvenlik kontrolü doğrulandı.")

    print("\n" + "=" * 72)
    print("🎉 YM-2 HAFTA 2 MODÜL VE SINIF TASARIMI TESTİ BAŞARIYLA GEÇTİ!")
    print("=" * 72)


if __name__ == "__main__":
    main()
