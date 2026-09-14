import pandas as pd
import numpy as np
from argparse import ArgumentParser
from pyomo.core import *
from pyomo.environ import *

### Model Definition

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
                rt_eff:float,
                ret_eta:float):
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
        self.ret_eta = ret_eta
        return

    def set_time(self, t0, tf):
        self.t0 = t0
        self.tf = tf
        return

battery = BatteryObj(50000,21.7391,434.782,0.8695,1,50000,50000,1,0.00005475,0.85,0.01)

### Model Parameters

t0 = 0
tf = 8736 
hour = np.arange(t0,tf)

## Model Definition
model = ConcreteModel()
model.T = Set(initialize=hour)
model.battery = Block()

## Battery - Variables
model.battery.SOC = Var(hour, bounds=(0,battery.soc_max), doc='[%]')
model.battery.SOH = Var(hour, bounds=(0,battery.soc_max), doc='[%]')
model.battery.DC_CHARGE = Var(hour, bounds=(0,None), doc='[MW]', within=NonNegativeReals)
model.battery.DC_DISCHARGE = Var(hour, bounds=(0,None), doc='[MW]', within=NonNegativeReals)
model.battery.I_c = Var(hour, bounds=(0,1), within=NonNegativeIntegers)
model.battery.I_d = Var(hour, bounds=(0,1), within=NonNegativeIntegers)

## Battery - Parameters

## Battery - Constraints
def rule_soc(_blk, t): #TODO ask about degredation param
    if t == 0: return Constraint.Skip
    else: return _blk.SOC[t] == (1-battery.ret_eta)*_blk.SOC[t-1]+(1-battery.eta_batt)*_blk.battery.DC_CHARGE-(1/(1-battery.eta_batt))*_blk.battery.DC_DISCHARGE
model.battery.r_soc = Constraint(hour, rule=rule_soc)

def rule_soh(_blk, t):
    if t == 0: return Constraint.Skip
    else: return _blk.SOH[t] == (1-battery.ret_eta)*_blk.SOH[t-1]-battery.eta_batt*_blk.battery.DC_DISCHARGE
model.battery.r_soh = Constraint(hour, rule=rule_soh)

def bound_soc(_blk, t):
    return inequality(0, _blk.SOC[t], _blk.SOH[t])
model.battery.b_soc = Constraint(hour, rule=bound_soc)

def bound_charging(_blk, t):
    return inequality(0, _blk.DC_CHARGE[t], _blk.I_c[t]*battery.charge_rate_max)
model.battery.b_charge