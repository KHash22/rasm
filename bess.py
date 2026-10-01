import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import os
from argparse           import ArgumentParser
from dotenv             import load_dotenv
from pyomo.core         import *
from pyomo.environ      import *
from util.market_parser import MarketParser
from util.plotter       import ts_plotter

parser = ArgumentParser()
parser.add_argument('iteration', type=int)
args = parser.parse_args()

### Model Definition

### architecture thinking:
# first get A model working 
# then separate the model constraints to a separate file
# on pricing: set start date, get everything up to tf then include it in the final used rpice dat a

### PRICE DATA

load_dotenv()

re = pd.read_csv('data/DEU_CentralAll15Min_Prices.csv')
column_date = os.getenv('COL_Date')
column_da   = os.getenv('COL_DA')
price_df = MarketParser().da_hour_mean(db=re, col_date=column_date, col_da=column_da)
print(price_df.head())

dates_DA = price_df[column_date].to_numpy()
price_DA = price_df[column_da].to_numpy()


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
                ret_eta:float,
                inverter_max:float):
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
        self.inverter_max = inverter_max
        return

    def set_time(self, t0, tf):
        self.t0 = t0
        self.tf = tf
        return

battery = BatteryObj(50000,21.7391,434.782,0.8695,1,20000,20000,1,0.00005475,0.85,0.01,50000)

### Model Parameters

t0 = 0
tf = 8760
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
soc_init = 0    # battery starts empty, so the solver can't sell energy it never bought
soh_init = 1    # battery starts at full health
eta_c = np.sqrt(battery.rt_eff)  # one-way charge efficiency
eta_d = np.sqrt(battery.rt_eff)  # one-way discharge efficiency

## Battery - Constraints
# SOC/SOH are fractions of max capacity, power is in kW over 1h steps, so energy flows are divided by capacity
def rule_soc(_blk, t): #TODO ask about degredation param
    prev = soc_init if t == 0 else _blk.SOC[t-1]
    return _blk.SOC[t] == (1-battery.ret_eta)*prev + (eta_c*_blk.DC_CHARGE[t] - _blk.DC_DISCHARGE[t]/eta_d)/battery.max_capcity
model.battery.r_soc = Constraint(hour, rule=rule_soc)

def rule_soh(_blk, t):
    # health only fades with throughput (eta_batt per full-capacity discharge), it does not self-discharge
    prev = soh_init if t == 0 else _blk.SOH[t-1]
    return _blk.SOH[t] == prev - battery.eta_batt*_blk.DC_DISCHARGE[t]/battery.max_capcity
model.battery.r_soh = Constraint(hour, rule=rule_soh)
"""
def bound_soc1(_blk, t):
    return 0 <= _blk.SOC[t]
model.battery.b_soc1 = Constraint(hour, rule=bound_soc1)
"""
def bound_soc2(_blk, t):
    return 0 >= (_blk.SOC[t]-_blk.SOH[t]) #SOH should be larger than SOC, ie less than 0.
model.battery.b_soc2 = Constraint(hour, rule=bound_soc2)
"""
def bound_charging1(_blk, t):
    return 0 <= _blk.DC_CHARGE[t]
model.battery.b_charge1 = Constraint(hour, rule=bound_charging1)
"""
def bound_charging2(_blk, t):
    return 0 >= (_blk.DC_CHARGE[t] - _blk.I_c[t]*battery.charge_rate_max)
model.battery.b_charge2 = Constraint(hour, rule=bound_charging2)
"""
def bound_charging3(_blk, t):
    return 0 <= _blk.DC_DISCHARGE[t]
model.battery.b_discharge3 = Constraint(hour, rule=bound_charging3)
"""
def bound_charging4(_blk, t):
    return 0 >= (_blk.DC_DISCHARGE[t] - _blk.I_d[t]*battery.discharge_rate_max)
model.battery.b_discharge4 = Constraint(hour, rule=bound_charging4)

def rule_charge_decision(_blk, t):
    return _blk.I_c[t]+_blk.I_d[t] <= 1 
model.battery.r_charge_decision = Constraint(hour, rule=rule_charge_decision)

def bound_charge_decision(_blk, t):
    net_charge = _blk.DC_CHARGE[t]-_blk.DC_DISCHARGE[t]
    return inequality(battery.inverter_max*(-1), net_charge, battery.inverter_max)
model.battery.b_charge_decision = Constraint(hour, rule=bound_charge_decision)

def bound_soh_discharge(_blk, t):
    return _blk.I_c[t]+_blk.I_d[t] <= 1
model.battery.b_soh_decision = Constraint(hour, rule=bound_soh_discharge)

day_hours = {}
for h in hour:
    day_hours.setdefault(int(h // 24), []).append(int(h))

def rule_degredation(_blk, d):
    hrs = day_hours[d]
    total_discharge = (1/(1-battery.eta_batt))*sum(_blk.DC_DISCHARGE[h] for h in hrs)
    soh_start = soh_init if hrs[0] == t0 else _blk.SOH[hrs[0]-1]
    discharge_limit = (len(hrs)/24)*battery.charge_rate_max*soh_start
    return total_discharge <= discharge_limit
model.battery.r_degredation = Constraint(list(day_hours), rule=rule_degredation)
'''
def rule_degredation(_blk, t):
    total_discharge = (1/(1-battery.eta_batt))*_blk.DC_DISCHARGE[t]
    charge_limit = (1/24)*battery.charge_rate_max*_blk.SOH[t]
    return total_discharge <= charge_limit
model.battery.r_degredation = Constraint(hour, rule=rule_degredation)
'''
def obj_rule(optmodel):
    # revenue: sell (discharge) at price, pay price to buy (charge). price is per MWh, power in kW -> /1000
    return sum(price_DA[n]*(optmodel.battery.DC_DISCHARGE[n]-optmodel.battery.DC_CHARGE[n]) for n in hour) / 1000
model.obj = Objective(rule=obj_rule,sense=maximize)

solver = SolverFactory('gurobi', solver_io='direct')
#solver.options['NonConvex'] = -1
results = solver.solve(model, tee=True)
print(f'solver status: {results.solver.status}, termination: {results.solver.termination_condition}')
print(f'objective (revenue): {value(model.obj):,.2f}')

##### POST PROCESSING #####
import cloudpickle

if args.iteration % 10 == 0:
    with open('solvedmodel' + str(args.iteration) + '.pkl', mode='wb') as file:
        cloudpickle.dump(model, file)

N = len(model.T)

ar_SOC, ar_SOH, ar_DCC, ar_DDC, ar_I_c, ar_I_d = (np.zeros(N) for _ in range(6))

for i in range(N):
    ar_SOC[i] = model.battery.SOC[i].value
    ar_SOH[i] = model.battery.SOH[i].value
    ar_DCC[i] = model.battery.DC_CHARGE[i].value
    ar_DDC[i] = model.battery.DC_DISCHARGE[i].value
    ar_I_c[i] = model.battery.I_c[i].value
    ar_I_d[i] = model.battery.I_d[i].value

dates = dates_DA[t0:tf]
prired = price_DA[t0:tf]
loaded = pd.DataFrame.from_dict({'Datetime':dates, 'SOC':ar_SOC,'SOH':ar_SOH,'DCC':ar_DCC,'DDC':ar_DDC,'I_c':ar_I_c,'I_d':ar_I_d,})
loaded.to_csv('load_new.csv', index=False)

fig, axs = plt.subplots(nrows=5, ncols=1, figsize=(12, 10), sharex=True)
axs[0].plot(dates, ar_SOC); axs[0].set_title('SOC [-]')
axs[1].plot(dates, ar_SOH); axs[1].set_title('SOH [-]')
axs[2].plot(dates, ar_DCC); axs[2].set_title('DC Charge [kW]')
axs[3].plot(dates, ar_DDC); axs[3].set_title('DC Discharge [kW]')
axs[4].plot(dates, prired); axs[4].set_title('DA-Price [EUR/MWh]')

fig.tight_layout()
os.makedirs('plots', exist_ok=True)
fig.savefig('plots/bess_dispatch.png', dpi=150)
print(f'saved plot -> plots/bess_dispatch.png (backend: {matplotlib.get_backend()})')
plt.show()

'''
len(hour)/8760 * (optmodel.elec.FixedCost_d3 + optmodel.storage.FixedCost_d3 + \
            optmodel.heater.FixedCost_d3 + optmodel.fuelcell.FixedCost_d3) + \
            sum(price[n] * (optmodel.elec.P_AC[n] + optmodel.heater.P_heater[n] + optmodel.storage.P_comp[n] - \
            optmodel.fuelcell.P_net[n]) for n in hour) / 1000 #
#1st half
OPEX
            
#2nd half
for every time increment in hour, get the sum of the price.
price at time (n), multiplied by the total power decision at time n. 

'''