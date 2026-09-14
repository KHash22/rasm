
class BatteryObj:
    def __init__(self, 
                max_capacity:float, 
                cpx_inv:float, 
                cpx_batt:float, 
                opx_batt_init:float, 
                soc_max: float, 
                charge_rate_max:float,
                discharge_rate_max:float,
                batt_max_cyc:float,
                eta_batt:float,
                rt_eff:float):
        self.max_capcity = max_capacity
        self.cpx_inv = cpx_inv
        self.cpx_batt = cpx_batt
        self.opx_batt_init = opx_batt_init
        self.soc_max = soc_max 
        self.charge_rate_max = charge_rate_max
        self.discharge_rate_max = discharge_rate_max
        self.batt_max_cyc = batt_max_cyc
        self.eta_batt = eta_batt
        self.rt_eff = rt_eff
        return
