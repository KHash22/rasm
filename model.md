# Model Statement #
A Battery Energy Storage System (BESS) is a collection of capacitors capable of supplying/aborbing charge from a central grid.

The model contained within this application is built using a 50 MWh capacity. At each time step t, where dt = 1 hr, the optimizer will state a charge/discharge decision limited to a maximum fixed rate, with the goal of maximising the total revenue generated across the horizon period (by default the model uses 1 year, equal to 8760 hours). 


## Definition of Terms ##
Horizon - the period of time $\Tau$ in which the revenue is optimized for.  
$t$ - A discrete timestep, for this model defined as $dt$ = 1.  
$t_0$ - The beginning of the horizon period.  
$\Tau$ - The set of all $t$, in ascending order (ie, $\Tau$ = {$t_0$, $t_1$, $t_2$, $t_3$ ... $t_f$})  
$SOC(t)$ - The state of charge - ie, the percentage (%) of the battery that is charged.
$SOH(t)$ - The state of health. The percentage (%) of the battery's initial capacity that remains undegraded and useable. $SOH(t)$ must always be greater than or equal to $SOC(t)$. See below for decay model.  
$c(t,m)$ - The charge rate going into the BESS at a given time $t$.  
$d(t,m)$ - The discharge rate going into the BESS at given time $t$.  
$\eta_{batt}$ - Charge/Discharge efficiency. ie, the percent (%) charge retained during charge/dicharge of the BESS  
$\eta_{deg}$ -  
$\sigma_{batt}$