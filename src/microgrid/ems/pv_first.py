"""EMS v0 (YM-3, Hafta 4): önce PV'yi kullan, eksik kalanı şebekeden al.

İlk uçtan uca sürümün enerji yönetimi bilerek basit tutuldu (kural yok, tarife yok):

  - Araçlar: kontrolsüz şarj. Her araç bağlandığı an ünitesinin izin verdiği tam güçle şarj olur
    (hedef SOC'ye ulaşınca durur). Sorunun görüldüğü senaryo budur (Senaryo 2).
  - Güç sırası: PV → (varsa batarya) → şebeke. PV doğrudan tüketilir; fazlası bataryaya gider;
    eksik kalan önce bataryadan, o da yetmezse şebekeden karşılanır. Şebeke gücünü EMS hesaplamaz,
    döngü güç dengesinden bulur (docs/arayuz-sozlesmesi.md); "eksik kalanı şebekeden al" bu yüzden ayrı
    bir kod gerektirmez: EMS PV ve bataryayı kullanır, kalan zaten şebekeden akar.

`use_bess=False` (varsayılan) bataryayı hiç kullanmaz: Senaryo 2'nin tanımı budur. `use_bess=True`
aynı kontrolsüz şarjı bataryayla destekler (tarifeye bakmadan, yalnızca PV fazlası ve açık).

Sınırlar (istasyon 150 kW, site 180 kW) bilerek uygulanmaz: kontrolsüz şarjın aşımı göstermesi gerekir.
Sınırlara uyan EMS `RuleBasedEMS`'tir (rule_based.py).
"""
from __future__ import annotations

from microgrid.interfaces import Decision, EmsInputs


class PvFirstEMS:
    def __init__(self, bess_power_kw: float = 0.0):
        """bess_power_kw: bataryanın inverter gücü. 0 ise batarya kullanılmaz (Senaryo 2).

        Güç değeri yalnızca istenen güce üst sınır koymak içindir; SOC sınırlarını `BESS.apply` uygular.
        """
        self.bess_power_kw = bess_power_kw

    @classmethod
    def from_config(cls, cfg: dict, use_bess: bool = False) -> "PvFirstEMS":
        return cls(bess_power_kw=cfg["bess"]["power_kw"] if use_bess else 0.0)

    def prepare(self, forecast) -> None:
        pass

    def decide(self, inp: EmsInputs) -> Decision:
        dt = inp.ctx.dt_h
        ev = {v.charger_id: min(v.max_charge_kw, v.energy_needed_kwh / dt) for v in inp.vehicles}
        if self.bess_power_kw <= 0:
            return Decision(ev_kw=ev)
        # PV'den sonra kalan: > 0 şebekeden çekilecek olan açık, < 0 PV fazlası
        net = inp.base_load_kw + sum(ev.values()) - inp.pv_kw
        bess = max(-self.bess_power_kw, min(self.bess_power_kw, -net))   # fazla -> şarj (+), açık -> deşarj (-)
        return Decision(ev_kw=ev, bess_kw=bess)
