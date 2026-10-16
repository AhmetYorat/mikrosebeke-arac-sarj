"""
YM-2 Şarj İstasyonu Birim Testleri.
Hafta 2 Sınıf Tasarımı ve Araç Talep Modeli Doğrulaması.
Hem pytest hem unittest ile çalışacak şekilde yapılandırılmıştır.
"""
import unittest
from microgrid.station import (
    ElectricVehicle,
    ChargingUnit,
    UnitStatus,
    ChargingStation,
    DemandModel,
)


class TestChargingStation(unittest.TestCase):

    def test_vehicle_cc_cv_logic(self):
        """Li-ion CC-CV şarj eğrisi doğrulaması."""
        ev = ElectricVehicle(
            vehicle_id="EV-001",
            model_name="Togg T10X",
            battery_capacity_kwh=88.5,
            initial_soc=0.20,
            target_soc=0.95,
            max_ac_power_kw=22.0
        )
        # SOC < %80 iken nominal güç
        p_cc = ev.get_max_charging_power("AC", 22.0)
        self.assertEqual(p_cc, 22.0)

        # SOC >= %80 iken kademeli güç düşüşü (CV fazı)
        ev.current_soc = 0.88
        p_cv = ev.get_max_charging_power("AC", 22.0)
        self.assertLess(p_cv, 22.0)
        self.assertGreater(p_cv, 0.0)

    def test_charging_unit_flow(self):
        """Şarj soketine araç bağlama ve durum değişimi testi."""
        unit = ChargingUnit(unit_id="AC-01", unit_type="AC", max_power_kw=22.0)
        ev = ElectricVehicle(
            vehicle_id="EV-002",
            model_name="Renault Zoe",
            battery_capacity_kwh=52.0,
            initial_soc=0.30,
            target_soc=0.90,
            max_ac_power_kw=22.0
        )
        self.assertFalse(unit.is_occupied)
        self.assertEqual(unit.status, UnitStatus.AVAILABLE)

        success = unit.connect_vehicle(ev)
        self.assertTrue(success)
        self.assertTrue(unit.is_occupied)
        self.assertEqual(unit.status, UnitStatus.OCCUPIED_IDLE)

        # Güç ataması
        applied = unit.set_power(22.0)
        self.assertEqual(applied, 22.0)
        self.assertEqual(unit.status, UnitStatus.OCCUPIED_CHARGING)

        # 1 saat işlet
        unit.step(dt_hours=1.0)
        self.assertGreater(ev.current_soc, 0.30)

    def test_station_aggregate_power_and_overload(self):
        """İstasyonun toplam güç hesabı ve trafo aşım kontrolü."""
        station = ChargingStation(
            station_id="STATION-01",
            transformer_limit_kw=180.0,
            num_ac_units=8,
            num_dc_units=2
        )
        self.assertEqual(station.get_total_power_kw(), 0.0)
        self.assertFalse(station.is_transformer_overloaded())

        # 10 araç bağlayıp tam güç isteyelim
        model = DemandModel(random_seed=42)
        fleet = model.generate_fleet(total_vehicles=10)
        for ev in fleet:
            station.plug_in_vehicle(ev)

        demands = station.bagli_araclar(current_time_hours=18.0)
        self.assertEqual(len(demands), 10)

        # Kontrolsüz şarj: her araca izin verilen tam güç
        allocations = {d["unit_id"]: d["max_deliverable_power_kw"] for d in demands}
        station.apply_power_allocations(allocations)

        total_p = station.get_total_power_kw()
        self.assertGreater(total_p, 0.0)
        # Akşam piki trafo sınırını (180 kW) aşmalıdır
        self.assertTrue(station.is_transformer_overloaded())


if __name__ == "__main__":
    unittest.main()
