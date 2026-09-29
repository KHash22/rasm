"""
Core describes the general parameters.
It should know nothing about the constraints

"""
import pyomo.environ as pyo
import numpy as np
from pyomo.core         import *
from pyomo.environ      import *

def build_bess(t0:int, tf:int, params:dict, price_DA):
    # Definition
    model = pyo.ConcreteModel()
    hour = np.arange(t0, tf)
    model.T = Set(initialize=hour)
    day_hours = {}
    for h in hour:
        # Verbose Explanation: we create a dict doing 
        day_hours.setdefault(int(h // 24), []).append(int(h))

    model.battery = Block()
    model.battery.D =           Set(initialize=sorted(day_hours))                          # day indices
    model.battery.day_hours =   Set(model.battery.D, initialize=day_hours, ordered=True)  # hours in each day
    model.battery.t0 =          Param(default=t0)   # on the battery block, not the model (see below)
    # Variables
    model.battery.SOC =             Var(hour, bounds=(0,params["soc_max"]), doc='[%]')
    model.battery.SOH =             Var(hour, bounds=(0,params["init_soh"]), doc='[%]')
    model.battery.DC_CHARGE =       Var(hour, bounds=(0,None), doc='[MW]', within=NonNegativeReals)
    model.battery.DC_DISCHARGE =    Var(hour, bounds=(0,None), doc='[MW]', within=NonNegativeReals)
    model.battery.I_c =             Var(hour, bounds=(0,1), within=NonNegativeIntegers)
    model.battery.I_d =             Var(hour, bounds=(0,1), within=NonNegativeIntegers)
    # Parameters
    model.battery.init_soc =            Param(default=params["init_soc"])
    model.battery.init_soh =            Param(default=params["init_soh"])
    model.battery.max_capacity =        Param(default=params["max_capacity"])
    model.battery.max_soc =             Param(default=params["soc_max"])
    model.battery.max_rate_charge =     Param(default=params["max_rate_charge"])
    model.battery.max_rate_discharge =  Param(default=params["max_rate_discharge"])
    model.battery.max_rate_inverter =   Param(default=params["max_rate_inverter"], mutable = True)
    model.battery.max_cycle_battery =   Param(default=params["max_cycle_battery"])
    model.battery.capex_inverter =      Param(default=params["capex_inverter"])
    model.battery.capex_battery =       Param(default=params["capex_battery"])
    model.battery.opex_battery =        Param(default=params["opex_battery"])
    model.battery.eff_batt =            Param(default=params["eff_batt"])
    model.battery.eff_retention =       Param(default=params["eff_retention"], mutable = True)
    model.battery.eff_charge =          Param(default=np.sqrt(params["eff_rt"]), mutable = True)
    model.battery.eff_discharge =       Param(default=np.sqrt(params["eff_rt"]), mutable = True)

    def obj_rule(optmodel):
    # revenue: sell (discharge) at price, pay price to buy (charge). price is per MWh, power in kW -> /1000
        return sum(price_DA[n]*(optmodel.battery.DC_DISCHARGE[n]-optmodel.battery.DC_CHARGE[n]) for n in hour) / 1000
    model.obj = Objective(rule=obj_rule,sense=maximize)
