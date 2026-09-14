 # -*- coding: utf-8 -*-
"""
Created on Sun Apr 30 22:39:24 2023

@author: calvintsay
"""

import pandas as pd
import numpy as np
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('iteration', type=int)

args = parser.parse_args()

print('########### ITERATION ' + str(args.iteration) + ' ############')

#price_df = pd.read_csv('/Users/gdp17/Desktop/H2/prices.csv', header=None, index_col=0)
#price_df.to_csv('inputprice' + str(args.iteration) + '.csv', header=None)

#price = np.array(price_df.loc[:,1])[1:]

## need to get csv data from Patron
price_df = pd.read_csv('/Users/gdp17/Desktop/H2/ercot_lmp_da_hr_hubs_2022.csv', header=None, index_col=0)
price_df.to_csv('inputprice' + str(args.iteration) + '.csv', header=None)

price = np.array(price_df.loc[:,5])[1:]

from pyomo.core import Block, Objective, Constraint, Var, Set, Param
from pyomo.environ import ConcreteModel, SolverFactory, log

fixCapacities = False
iter_delta = 0.1 ** args.iteration
electrolyzerratio = 1.5
rateofchange = 0.2

######## PARAMETERS #############
#electrolyzer
L_ACDC = 1.05
L_aux = 0.05
beta = 1e-6 # 1e-4 percent to decimal
L_elec = 0.05
lifespan = 87600

L_degrade = 1 - beta * lifespan

#storage
I_H20 = 0
R_H2 = 1.1465e-6
Pr_min = 2e6
Pr_max = 20e6
T_storage = 298
rho_H2_P_max = 14.761
R_ig = 8.314
H2_kg_per_mol = 0.002016

#compressor
eta_comp = 0.7

#fuel cell
V_C = 0.7
F = 96485
L_ACDC_fuelcell = 0.95
L_aux_fuelcell = 0.05
L_degradationfactor_fuelcell = 1e-6
LIFE_fuelcell_stack_hr = 87600

#heater
eta_heater = 0.75
M_H2_DRI = 150000 
T_H2_DRI = 1100#1400
T_H2_electrolyzer = 298

#economics
WACC = 0.05
CAPEX_electrolyzer_stack = 150#300
CAPEX_electrolyzer_other = 250#500
CAPEX_fuelcell_stack = 150
CAPEX_fuelcell_other = 250
CAPEX_compressor = 50
CAPEX_storage = 1#0.2
CAPEX_heater = 50

LIFE_electrolyzer_stack = 10
LIFE_electrolyzer_other = 20
LIFE_fuelcell_stack = 10
LIFE_fuelcell_other = 20
LIFE_compressor = 10
LIFE_storage = 15
LIFE_heater = 10

FIXEDOPEX_electrolyzer_all = 2#4
FIXEDOPEX_fuelcell_all = 2
FIXEDOPEX_storage = 10e-3#0.2e-3
FIXEDOPEX_compressor = 1
FIXEDOPEX_heater = 1



######## DEFINE MODEL #############################################################################
t0 = 0; tf = 8736#8760
hour = np.arange(t0,tf)

mdl = ConcreteModel()
mdl.T = Set(initialize=hour)

mdl.elec = Block()
mdl.storage = Block()
mdl.heater = Block()
mdl.fuelcell = Block()

######## ELECTROLYZER - Variables ###########
mdl.elec.P_AC          = Var(hour, bounds =(0,None),                                   doc='[MW]') 
mdl.elec.P_DC          = Var(hour, bounds =(0,None),                                   doc='[MW]') 
mdl.elec.M_H2          = Var(hour, bounds =(0,None),                                   doc='[kg/h]')
mdl.elec.CAP           = Var(      bounds =(0,None),                                   doc='[kg/h]')   
mdl.elec.FixedCost_d3  = Var(      bounds =(0,None),                                   doc='[€]/1e3') 

######## ELECTROLYZER - Parmeters ###########
mdl.elec.EFFICIENCY_DC_to_H2 = Param(default=L_degrade/L_elec,                         doc='[MWh-DC/kg-H2]')
mdl.elec.EFFICIENCY_AC_to_DC = Param(default=L_ACDC+L_aux,                             doc='[MW-DC/MW-AC]')

######## ELECTROLYZER - Constraints ###########
def AC_to_DC_rule(_blk, t): # AC power to DC power 
    return _blk.P_AC[t] == _blk.P_DC[t] * _blk.EFFICIENCY_AC_to_DC
mdl.elec.AC_to_DC = Constraint(hour, rule=AC_to_DC_rule)  

def P_STACK_to_H2_rule(_blk, t): # Power to H2 production for each stack
    return _blk.M_H2[t] == _blk.P_DC[t] * _blk.EFFICIENCY_DC_to_H2
mdl.elec.P_STACK_to_H2 = Constraint(hour, rule=P_STACK_to_H2_rule)

# Production always below capacity for each stack
def P_STACK_below_CAP_rule(_blk, t): 
    return _blk.P_DC[t] <= _blk.CAP 
mdl.elec.P_STACK_below_CAP = Constraint(hour, rule=P_STACK_below_CAP_rule)

if rateofchange:
    def roc1rule(_blk, t):
        if t == 0: return Constraint.Skip
        else: return _blk.P_DC[t-1] - _blk.P_DC[t] <= 0.2 * _blk.CAP
    mdl.elec.roc1rule = Constraint(hour, rule = roc1rule)
    
    def roc2rule(_blk, t):
        if t == 0: return Constraint.Skip
        else: return _blk.P_DC[t] - _blk.P_DC[t-1] <= 0.2 * _blk.CAP
    mdl.elec.roc2rule = Constraint(hour, rule = roc2rule)

costFactor = CAPEX_electrolyzer_stack * (WACC * (1+WACC)**LIFE_electrolyzer_stack)/((1+WACC)**LIFE_electrolyzer_stack-1) + \
             CAPEX_electrolyzer_other * (WACC * (1+WACC)**LIFE_electrolyzer_other)/((1+WACC)**LIFE_electrolyzer_other-1) + FIXEDOPEX_electrolyzer_all

def cost(_b):
    return _b.FixedCost_d3 ==  _b.CAP * costFactor * 0.9
mdl.elec.constraintCost = Constraint(rule=cost)

######## STORAGE - Variables ###########
#mdl.storage.I_H2_d3     = Var(hour, bounds=(0,None),                                doc='[kg]') # [kg]
mdl.storage.Pr_H2       = Var(hour, bounds=(Pr_min,Pr_max),                         doc='[Pa]') # [Pa]
mdl.storage.P_comp      = Var(hour, bounds=(0,None),                                doc='[MW]') # [MW]
mdl.storage.M_H2_in     = Var(hour, bounds=(10,None),                                doc='[kg]') # [kg]
mdl.storage.M_H2_out    = Var(hour, bounds=(0,None),                                doc='[kg]') # [kg]
mdl.storage.CAP_H2      = Var(      bounds=(100, None),                             doc='[kg]') # [kg]
mdl.storage.CAP_comp    = Var(      bounds=(100, None),                             doc='[MW]') # [MW]
mdl.storage.FixedCost_d3= Var(      bounds=(0,None),                                doc='[€]') # [€]
mdl.storage.V_storage   = Var(      bounds=(0,None),                                doc='[m3]') # [m3]
mdl.storage.rho   	= Var(      bounds=(0,20000),                                doc='[1/m3]') # [1/m3]
mdl.storage.surr     	= Var(hour, bounds=(0,None),                                doc='[kg/m3]') # [kg/m3]
mdl.storage.I_H2_d3     = Var(hour, bounds=(0,20000),                                doc='[kg]') # [kg]

######## STORAGE - Parameters ###########
mdl.storage.R_H2            = Param(default=R_H2, doc='[MWh/kg/K]')
mdl.storage.eta_comp        = Param(default=eta_comp, doc='[-]')
mdl.storage.Pr_min          = Param(default=Pr_min, doc='[Pa]')
mdl.storage.Pr_max          = Param(default=Pr_max, doc='[Pa]')
mdl.storage.I_H20           = Param(default=I_H20, doc='[kg]')
mdl.storage.T_storage       = Param(default=T_storage, doc='[K]')
mdl.storage.rho_H2_P_max    = Param(default=rho_H2_P_max, doc='[kg/m3]')
mdl.storage.R_ig            = Param(default=R_ig, doc='[J/K/mol]')
mdl.storage.H2_kg_per_mol   = Param(default=H2_kg_per_mol, doc='[kg/mol]')
mdl.storage.T_H2_in         = Param(default=298, doc='[K]', mutable=True) # [K]
mdl.storage.T_H2_out        = Param(default=T_storage, doc='[K]') # [K]
mdl.storage.Pr_H2_in        = Param(default=1e6, doc='[Pa]', mutable=True) # [Pa]

def mass_balance_rule(_b, n): # Equation (15) of MVP1 description
    if n == 0: return _b.I_H2_d3[n] == _b.I_H20 * 1e-3
    else: return _b.I_H2_d3[n] == _b.I_H2_d3[n-1] + 1e-3*(_b.M_H2_in[n] - _b.M_H2_out[n])
mdl.storage.constraint1 = Constraint(hour, rule=mass_balance_rule)

mdl.storage.initialflow = Constraint(expr= mdl.storage.M_H2_out[0] == 0)
# Equation (16) of MVP1 description
#def terminal_constraint(_b):
#    return _b.I_H2_d3[0] == _b.I_H2_d3[len(hour)-1]
#mdl.storage.constraint2 = Constraint(rule=terminal_constraint)
    
mdl.storage.constraint3 = Constraint(expr= mdl.storage.V_storage == mdl.storage.CAP_H2/mdl.storage.rho_H2_P_max) #divided by 1000

#Z = 1 + (Pr_min + Pr_max)/300e6

# Equation (17) of MVP1 description
def constraint4(_b, n): # Equation (18) of MVP1 description, NONLINEAR
#    return _b.Pr_H2[n] * _b.V_storage == _b.Pr_min * _b.V_storage + (1 + (_b.Pr_min + _b.Pr_max)/300e6) * \
#                              (_b.I_H2_d3[n] / _b.H2_kg_per_mol * _b.R_ig * _b.T_storage) # / _b.V_storage)
    return _b.Pr_H2[n] == _b.Pr_min + (1 + (_b.Pr_min + _b.Pr_max)/300e6) * \
                              (_b.surr[n] / _b.H2_kg_per_mol * _b.R_ig * _b.T_storage) # / _b.V_storage)
mdl.storage.constraint4 = Constraint(hour, rule=constraint4)

# Invert V to have bilinear term
#def constraint13(_b): 
#    return _b.rho == 1/_b.V_storage
#mdl.storage.constraint13 = Constraint(rule=constraint13)

# McCormick Envelope 1
def constraint10(_b, n): 
    return _b.surr[n] >= 20000*_b.I_H2_d3[n] + _b.rho*20000 - 20000*20000
mdl.storage.constraint10 = Constraint(hour, rule=constraint10)

# McCormick Envelope 2
def constraint11(_b, n): 
    return _b.surr[n] <= _b.rho*20000 
mdl.storage.constraint11 = Constraint(hour, rule=constraint11)

# McCormick Envelope 3
def constraint12(_b, n): 
     return _b.surr[n] <= 20000*_b.I_H2_d3[n]
mdl.storage.constraint12 = Constraint(hour, rule=constraint12)

def constraint5(_b, n): # Equation (21) of MVP1 description, NONLINEAR, DISJUNCTION
    Pr_H2_0 = float(mdl.storage.Pr_min.value); Pr_H2_1 = float(mdl.storage.Pr_max.value)  # [Pa]
    return _b.P_comp[n] == _b.R_H2 / _b.eta_comp * _b.M_H2_in[n] * _b.T_H2_in * log((Pr_H2_0+Pr_H2_1)/2/_b.Pr_H2_in)  #dP/dM_H2_in
mdl.storage.constraint5 = Constraint(hour, rule=constraint5)

def constraint7(_b, n): # Equation (23) of MVP1 description
    return _b.P_comp[n] <= _b.CAP_comp
mdl.storage.constraint7 = Constraint(hour, rule=constraint7)

def constraint8(_b, n): 
    return _b.I_H2_d3[n] <= _b.CAP_H2
mdl.storage.constraint8 = Constraint(hour, rule=constraint8)

costFactor_compressor = CAPEX_compressor * (WACC * (1+WACC)**LIFE_compressor)/((1+WACC)**LIFE_compressor-1) + FIXEDOPEX_compressor

costFactor_storage = CAPEX_storage * (WACC * (1+WACC)**LIFE_storage)/((1+WACC)**LIFE_storage-1) + FIXEDOPEX_storage
def cost(_b):
    return _b.FixedCost_d3 ==  _b.CAP_comp * costFactor_compressor + _b.CAP_H2 * costFactor_storage * 1000
mdl.storage.constraintCost = Constraint(rule=cost)

######## FUELCELL - Variables ###########
mdl.fuelcell.P_net          = Var(hour, bounds=(0,None), doc='[MW]') # [MW]
mdl.fuelcell.M_H2           = Var(hour, bounds=(0,None), doc='[kg]') # [kg]
mdl.fuelcell.CAP            = Var(bounds=(0, None), doc='[MW]') # [MW]
mdl.fuelcell.FixedCost_d3   = Var(bounds=(0,None), doc='[€]') # [€]

######## FUELCELL - Parameters ###########
mdl.fuelcell.L_ACDC_fuelcell        = Param(default=L_ACDC_fuelcell, doc='[-]')
mdl.fuelcell.L_aux_fuelcell         = Param(default=L_aux_fuelcell, doc='[-]')
mdl.fuelcell.L_degradationfactor    = Param(default=L_degradationfactor_fuelcell, doc='[%/1000h]')
mdl.fuelcell.LIFE_fuelcell_stack_hr = Param(default=LIFE_fuelcell_stack_hr, doc='[h]')

######## FUELCELL - Constraints ###########
def fc_constraint1(_b, n): # Compute P_net
    return _b.P_net[n] == 2 * _b.M_H2[n] * V_C  * F / H2_kg_per_mol / 1e6 / 3600 * \
            (1 - _b.L_degradationfactor * _b.LIFE_fuelcell_stack_hr / 2e5) * (_b.L_ACDC_fuelcell + _b.L_aux_fuelcell)# [MW]
mdl.fuelcell.constraint1 = Constraint(hour, rule=fc_constraint1)

def fc_constraint2(_b, n): # Equation (5) of MVP1 description
    return _b.P_net[n] / (_b.L_ACDC_fuelcell + _b.L_aux_fuelcell) <= _b.CAP
mdl.fuelcell.constraint2 = Constraint(hour, rule=fc_constraint2)

costFactor = CAPEX_fuelcell_stack * (WACC * (1+WACC)**LIFE_fuelcell_stack)/((1+WACC)**LIFE_fuelcell_stack-1) + \
             CAPEX_fuelcell_other * (WACC * (1+WACC)**LIFE_fuelcell_other)/((1+WACC)**LIFE_fuelcell_other-1) + FIXEDOPEX_fuelcell_all

def fc_cost(_b):
    return _b.FixedCost_d3 ==  _b.CAP * costFactor
mdl.fuelcell.constraintCost = Constraint(rule=fc_cost)

######## HEATER - Variables ###########
mdl.heater.P_heater =               Var(hour, bounds=(0,None), doc='[MW]') # [MW]
mdl.heater.M_H2_electrolyzer =      Var(hour, bounds=(0,None), doc='[kg]') # [kg]
mdl.heater.M_H2_storage =           Var(hour, bounds=(0,None), doc='[kg]') # [kg]
mdl.heater.CAP =                    Var(      bounds=(0,None), doc='[MW]') # [MW]
mdl.heater.FixedCost_d3 =           Var(      bounds=(0,None), doc='[€]') # [€]

######## HEATER - Parameters ###########
mdl.heater.eta_heater =             Param(default=eta_heater, doc='[-]')
mdl.heater.M_H2_DRI =               Param(default=M_H2_DRI, doc='[kg]') # [kg]

A_CP = 33.066178; B_CP = -11.3634417; C_CP = 11.432816; D_CP = -2.772874; E_CP = -0.158558

CP_DRI = 1.377865e-7 * (A_CP + B_CP*T_H2_DRI/1000 + C_CP*(T_H2_DRI/1000)**2 +
                        D_CP*(T_H2_DRI/1000)**3 + E_CP/(T_H2_DRI/1000)**2 )
CP_elec = 1.377865e-7 * (A_CP + B_CP*T_H2_electrolyzer/1000 + C_CP*(T_H2_electrolyzer/1000)**2 +
                        D_CP*(T_H2_electrolyzer/1000)**3 + E_CP/(T_H2_electrolyzer/1000)**2 )

######## HEATER - Constraints ###########
def heat_constraint1(_b, n):
    return _b.P_heater[n] == (_b.M_H2_electrolyzer[n] + _b.M_H2_storage[n]) * \
            (T_H2_DRI-T_H2_electrolyzer) * (CP_elec+CP_DRI)/2/_b.eta_heater
mdl.heater.constraint1 = Constraint(hour, rule=heat_constraint1)

def heat_constraint2(_b, n): # Heater mass balance
    return _b.M_H2_electrolyzer[n] + _b.M_H2_storage[n] >= _b.M_H2_DRI #make equality, check pressure profile 
mdl.heater.constraint2 = Constraint(hour, rule=heat_constraint2)

def heat_constraint3(_b, n): # Equation (5) of MVP1 description
    return _b.P_heater[n] <= _b.CAP
mdl.heater.constraint3 = Constraint(hour, rule=heat_constraint3)

costFactor = CAPEX_heater * (WACC * (1+WACC)**LIFE_heater)/((1+WACC)**LIFE_heater-1) + FIXEDOPEX_heater
def heat_cost(_b):
    return _b.FixedCost_d3 ==  _b.CAP * costFactor
mdl.heater.constraintCost = Constraint(rule=heat_cost)

######## MASS BALANCES
def mass_balance_1(_m, t): 
    return _m.elec.M_H2[t] == _m.storage.M_H2_in[t] + _m.heater.M_H2_electrolyzer[t]
mdl.mb1 = Constraint(hour, rule=mass_balance_1)

def mass_balance_2(_m, t): 
    return _m.storage.M_H2_out[t] == _m.fuelcell.M_H2[t] + _m.heater.M_H2_storage[t]
mdl.mb2 = Constraint(hour, rule=mass_balance_2)

def power_balance(_m, t):
    return _m.elec.P_AC[t] + _m.heater.P_heater[t] + _m.storage.P_comp[t] - _m.fuelcell.P_net[t] <= 9964 * electrolyzerratio
mdl.pb = Constraint(hour, rule=power_balance)

def obj_rule(optmodel):
    return len(hour)/8760 * (optmodel.elec.FixedCost_d3 + optmodel.storage.FixedCost_d3 + \
            optmodel.heater.FixedCost_d3 + optmodel.fuelcell.FixedCost_d3) + \
            sum(price[n] * (optmodel.elec.P_AC[n] + optmodel.heater.P_heater[n] + optmodel.storage.P_comp[n] - \
            optmodel.fuelcell.P_net[n]) for n in hour) / 1000 # 

mdl.obj = Objective(rule=obj_rule)

if fixCapacities:
    mdl.elec.CAP.fix()

solver = SolverFactory('gurobi')
solver.options['NonConvex'] = -1
results = solver.solve(mdl, tee=True)


######################## POST PROCESSING $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
import cloudpickle

if args.iteration % 10 == 0:
    with open('solvedmodel' + str(args.iteration) + '.pkl', mode='wb') as file:
        cloudpickle.dump(mdl, file)

N = len(mdl.T)
P_elec = np.zeros(N); P_comp = np.zeros(N); P_heat = np.zeros(N); P_fc = np.zeros(N); P_fc = np.zeros(N); P_stor = np.zeros(N)

for i in range(N):
    P_elec[i] = mdl.elec.P_AC[i].value
    P_comp[i] = mdl.storage.P_comp[i].value
    P_heat[i] = mdl.heater.P_heater[i].value
    P_fc[i] = mdl.fuelcell.P_net[i].value
   #pytho P_stor[i] = mdl.storage.Pr_H2[i].valueI_H2_d3
    P_stor[i] = mdl.storage.I_H2_d3[i].value

P_net = P_elec + P_comp + P_heat + P_fc
loadsdf = pd.DataFrame.from_dict({'elec':P_elec, 'comp':P_comp, 'heat':P_heat, 'fc':P_fc, 'net':P_net, 'pres':P_stor})
loadsdf.to_csv('load_new' + str(args.iteration) + '.csv')
print('Electrolizer capacity = ' + str(mdl.elec.CAP.value) + ' GW')
print('Storage capacity = ' + str(mdl.storage.CAP_H2.value) + ' GW')
print('Heater capacity = ' + str(mdl.heater.CAP.value) + ' GW')
print('Compressor capacity = ' + str(mdl.storage.CAP_comp.value) + ' GW')
print('Fuel cell capacity = ' + str(mdl.fuelcell.CAP.value) + ' GW')
print(mdl.storage.V_storage.value)

print('Cperating cost = ' +str(sum(price[n] * (optmodel.elec.P_AC[n] + optmodel.heater.P_heater[n] + optmodel.storage.P_comp[n] - \
optmodel.fuelcell.P_net[n]) for n in hour) / 1000))

'''TODO

1. fix all capacties at the optimal deterministic value
2. shorten time horizon to delta T (this is a degree of freedom, maybe start with daily)
3. write code to take DNN-generated dispatch and fix model dispatch to that value
4. write a model output that gives you the reward

'''

mdl.elec.CAP.fix(12899.54627522421) #extend to all other units
optmodel.heater.P_heater_RT.fix('''VALUE FROM DNN''') #extend to all other units



