# Model Statement #
A Battery Energy Storage System (BESS) is a collection of capacitors capable of supplying/aborbing charge from a central grid.

The model contained within this application is built using a 50 MWh capacity. At each time step t, where dt = 1 hr, the optimizer will state a charge/discharge decision limited to a maximum fixed rate, with the goal of maximising the total revenue generated across the horizon period (by default the model uses 1 year, equal to 8760 hours). 

At its core, the BESS consists of two primary components: The inverter, and the capacitor. The inverter converts betwee AC grid energy and the BESS capacitor, which operates in DC. The total flow of charge across either the inverter or capacitor is limited by $C_{inv}$ and $C_{max}$, which describe the maximum charge flow in [kW].

At the time of writing, this model will strictly consider ONLY the Day-Ahead Market;  $\implies$ $M = {m_{DA}}$, **Thus**

## Definition of Terms ##
Horizon - the period of time $\Tau$ in which the revenue is optimized for.  
$m$ - Participating markets. Examples include Day Ahead, Intra-day, Load Balancing Markets. **This script only considers the Day-Ahead market**
$t$ - A discrete timestep, for this model defined as $dt$ = 1.  
$t_0$ - The beginning of the horizon period.  
$\Tau$ - The set of all $t$, in ascending order (ie, $\Tau$ = {$t_0$, $t_1$, $t_2$, $t_3$ ... $t_f$})  
$SOC(t)$ - The state of charge - ie, the percentage (%) of the battery that is charged.
$SOH(t)$ - The state of health. The percentage (%) of the battery's initial capacity that remains undegraded and useable. $SOH(t)$ must always be greater than or equal to $SOC(t)$. See below for decay model.  
$c(t,m)$ - The charge rate going into the BESS at a given time $t$.  
$d(t,m)$ - The discharge rate going into the BESS at given time $t$.  
$\eta_{batt}$ - Charge/Discharge efficiency. ie, the percent (%) charge retained during charge/dicharge of the BESS  
$\eta_{deg}$ - The portion of which the battery degrades by relative to the quantity discharged over a time step.  
$\sigma_{batt}$ - The passive drain of charge over the time step $t$ from the BESS
$C_{inv}$ - The maximum flow of charge [kW] that the AC-DC inverter can handle.
$C_{max}$ -  The maximum flow of charge [kW] that the BESS can handle.  

## Constraints ##
1. Charge/Discharge Model  
$SOC(t) = (1-\sigma_{batt})SOC(t-1)+\eta_{batt}\sum\limits_{m ∈ E} c(t,m) - \frac{1}{\eta_{batt}}\sum\limits_{m ∈ E} d(t,m); \forall t \in T \backslash t_{0}$  
The above states that the SOC at time t is decribed as the prior SOC, plus the net charge/discharge  of the capacitor for the current time step. For t = 0, SOC is assumed to be 0.  
2.  SOC limit     
$0 \leq SOC(t) \leq SOH(t)$  
This states that the SOC cannot be greater than the maximum capacity after degredation (commonly known as SOH) at time $t$.
3. Capacity limits  
Before proceeding, read: $I_c$ and $I_d$ represnt a binary variable, where $I$ can only equal 0 or 1. This forces the solver to only make one decision - either to charge or discharge. It may never conduct both at the same time in the same time step.  
$0 \leq c(t, m) \leq I_c(t,m) C_{inv}; \forall t \in T, M $  
$0 \leq d(t, m) \leq I_d(t,m) C_{inv}; \forall t \in T, M $  
Recall, m is only one market. This is the same as stating  
$0 \leq c(t) \leq I_c(t) C_{inv}; \forall t \in T $  
$0 \leq d(t) \leq I_d(t) C_{inv}; \forall t \in T $  
4. Charge decision limit  
$I_c(t,m) + I_d(t,m) \leq 1$  
This means that any given moment, the BESS can either charge, discharge, or neither. It may never both charge and discharge at the same time. 
5. State of Health  
$SOH(t) = SOH(t-1)-\eta_{deg}\sum\limits_{m ∈ E} d(t,m); \forall t \in T \backslash t_{0}$  
For single-market optimization,  
$SOH(t) = SOH(t-1)-\eta_{deg}d(t); \forall t \in T \backslash t_{0}$  
This model describes the state of health at a given time t. Note that the SOH degrades every time the BESS discharges.
6. Degredation Limit  
$\frac{1}{\eta_{batt}}\sum\limits_{t \in T}\sum\limits_{m \in M} d(t,m) \leq \frac{1}{24}C_{max} \sum\limits_{t \in T}SOH(t)$  
This states that the discharge across all of t and m must be less than the total availability throughout the year, limited to 24 charge decisions per day at most. 

