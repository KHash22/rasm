import pyomo.environ as pyo
from pyomo.core         import *
from pyomo.environ      import *

def constraint(fn):
    """Marks a method as a selectable constraint."""
    fn._is_constraint = True
    return fn

class BESSConstraints:
    REQUIRES = ("T", 
                "SOC", 
                "SOH", 
                "DC_CHARGE", 
                "DC_DISCHARGE", 
                "I_c", 
                "I_d", 
                "max_capacity", 
                "max_soc", 
                "max_rate_charge",
                "max_rate_discharge", 
                "max_rate_inverter", 
                "max_cycle_battery",
                "capex_inverter",
                "capex_battery",
                "opex_battery",
                "eff_batt",
                "eff_charge",
                "eff_discharge",
                "eff_retention")

    @constraint
    def rule_soc(self, _blk, t): #TODO ask about degredation param
        prev = _blk.init_soc if t == value(_blk.t0) else _blk.SOC[t-1]
        return _blk.SOC[t] == (1-_blk.eff_retention)*prev + (_blk.eff_charge*_blk.DC_CHARGE[t] - _blk.DC_DISCHARGE[t]/_blk.eff_discharge)/_blk.max_capacity
    
    @constraint
    def rule_soh(self, _blk, t):
    # health only fades with throughput (eta_batt per full-capacity discharge), it does not self-discharge
        prev = _blk.init_soh if t == value(_blk.t0) else _blk.SOH[t-1]
        return _blk.SOH[t] == prev - _blk.eff_batt*_blk.DC_DISCHARGE[t]/_blk.max_capacity

    @constraint
    def bound_soc(self, _blk, t):
        return 0 >= (_blk.SOC[t]-_blk.SOH[t]) #SOH should be larger than SOC, ie less than 0.

    @constraint
    def bound_charging(self, _blk, t):
        return 0 >= (_blk.DC_CHARGE[t] - _blk.I_c[t]*_blk.max_rate_charge)

    @constraint
    def bound_discharging(self, _blk, t):
        return 0 >= (_blk.DC_DISCHARGE[t] - _blk.I_d[t]*_blk.max_rate_discharge)

    @constraint
    def rule_charge_decision(self, _blk, t):
        return _blk.I_c[t]+_blk.I_d[t] <= 1 

    @constraint
    def bound_charge_decision(self, _blk, t):
        net_charge = _blk.DC_CHARGE[t]-_blk.DC_DISCHARGE[t]
        return inequality(_blk.max_rate_inverter*(-1), net_charge, _blk.max_rate_inverter)

    @constraint
    def rule_degredation(self, _blk, d):
        hrs = _blk.day_hours[d]
        total_discharge = (1/(1-_blk.eff_batt))*sum(_blk.DC_DISCHARGE[h] for h in hrs)
        soh_start = _blk.init_soh if hrs.first() == value(_blk.t0) else _blk.SOH[hrs.first()-1]
        discharge_limit = (len(hrs)/24)*_blk.max_rate_discharge*soh_start
        return total_discharge <= discharge_limit