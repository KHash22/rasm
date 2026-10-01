from util.filehandler               import FileHandler
from util.plotter                   import ts_plotter
from util.market_parser             import MarketParser
from dotenv                         import load_dotenv
from model.bess                     import build_bess
from constraints.bess_constraint    import BESSConstraints
import pandas               as pd
import pyomo.environ        as pyo
import matplotlib
import matplotlib.pyplot    as plt
import inspect
import os

load_dotenv()

## merge_parquests(directory="market")
"""
re1.to_csv('output.csv', index=False)

ts_plotter(re1, column_date, [column_da])

df = pd.read_csv('data/merged.csv')
print(df.head)

ts_plotter(df, 'Interval Start', ['LMP'])"""

### Run Settings
START_DATE      = pd.Timestamp('2025-01-01')
HORIZON_HOURS   = 8760
SOLVER          = 'gurobi'
SOLVER_TEE      = False
PLOT_DIR        = 'plots'
RESULTS_DIR     = 'results'

### Config + Price Data
Hnd = FileHandler()
params = Hnd.reader_json(os.getenv('BESS_CONFIG'))

re = pd.read_csv(os.getenv('MARKET_CSV'))
column_date = os.getenv('COL_Date')
column_da   = os.getenv('COL_DA')
re[column_date] = pd.to_datetime(re[column_date], format='%d/%m/%Y %H:%M')
end_date = START_DATE + pd.Timedelta(HORIZON_HOURS, unit='h')
re = re[(re[column_date] >= START_DATE) & (re[column_date] < end_date)]  # slice out only the horizon
re1 = MarketParser().da_hour_mean(db=re, col_date=column_date, col_da=column_da)

dates_DA = re1[column_date].to_numpy()
price_DA = re1[column_da].to_numpy()
if len(price_DA) != HORIZON_HOURS:
    raise ValueError(f'expected {HORIZON_HOURS} hourly prices from {START_DATE}, got {len(price_DA)}')

### Constraints
# a rule's index argument name decides which set it is built over: t -> hours, d -> days
INDEX_SETS = {"t": lambda m: m.T,
              "d": lambda m: m.battery.D}

def available_constraints(cls):
    # vars() keeps definition order, unlike inspect.getmembers
    return [name for name, fn in vars(cls).items() if getattr(fn, "_is_constraint", False)]

def attach_constraints(m, cons, names):
    missing = [r for r in cons.REQUIRES if not (hasattr(m.battery, r) or hasattr(m, r))]
    if missing:
        raise AttributeError(f'model is missing components required by {type(cons).__name__}: {missing}')

    for name in names:
        rule = getattr(cons, name)
        idx_arg = list(inspect.signature(rule).parameters)[-1]
        if idx_arg not in INDEX_SETS:
            raise ValueError(f'constraint {name} has unknown index argument "{idx_arg}"')
        setattr(m.battery, name, pyo.Constraint(INDEX_SETS[idx_arg](m), rule=rule))
    return m

def select_constraints(config):
    available = available_constraints(BESSConstraints)
    chosen = config.get("constraints", available)
    unknown = sorted(set(chosen) - set(available))
    if unknown:
        raise ValueError(f'{config["config_name"]}: unknown constraints {unknown}, available: {available}')
    return chosen

### Build / Solve
def build(config, prices):
    m = build_bess(0, HORIZON_HOURS, config, prices)
    attach_constraints(m, BESSConstraints(), select_constraints(config))
    return m

def solve(m):
    solver = pyo.SolverFactory(SOLVER, solver_io='direct')
    results = solver.solve(m, tee=SOLVER_TEE)
    status = str(results.solver.status)
    termination = str(results.solver.termination_condition)
    ok = results.solver.termination_condition in (pyo.TerminationCondition.optimal,
                                                  pyo.TerminationCondition.feasible)
    return ok, status, termination

##### POST PROCESSING #####
def extract(m):
    hours = list(m.T)
    blk = m.battery
    return pd.DataFrame({'Datetime':dates_DA[hours],
                         'SOC':     [blk.SOC[t].value for t in hours],
                         'SOH':     [blk.SOH[t].value for t in hours],
                         'DCC':     [blk.DC_CHARGE[t].value for t in hours],
                         'DDC':     [blk.DC_DISCHARGE[t].value for t in hours],
                         'I_c':     [blk.I_c[t].value for t in hours],
                         'I_d':     [blk.I_d[t].value for t in hours],
                         'Price':   price_DA[hours]})

def plot_dispatch(df, name):
    fig, axs = plt.subplots(nrows=5, ncols=1, figsize=(12, 10), sharex=True)
    axs[0].plot(df['Datetime'], df['SOC']);   axs[0].set_title('SOC [-]')
    axs[1].plot(df['Datetime'], df['SOH']);   axs[1].set_title('SOH [-]')
    axs[2].plot(df['Datetime'], df['DCC']);   axs[2].set_title('DC Charge [kW]')
    axs[3].plot(df['Datetime'], df['DDC']);   axs[3].set_title('DC Discharge [kW]')
    axs[4].plot(df['Datetime'], df['Price']); axs[4].set_title('DA-Price [EUR/MWh]')
    fig.suptitle(f'BESS dispatch - {name}', fontweight='bold')
    fig.tight_layout()

    os.makedirs(PLOT_DIR, exist_ok=True)
    path = os.path.join(PLOT_DIR, f'bess_dispatch_{name}.png')
    fig.savefig(path, dpi=150)
    print(f'saved plot -> {path} (backend: {matplotlib.get_backend()})')
    return

def summarise(df, name, objective, status, termination):
    # power is in kW over 1h steps -> kWh, /1000 -> MWh
    return {'config':           name,
            'status':           status,
            'termination':      termination,
            'revenue [EUR]':    round(objective, 2),
            'charged [MWh]':    round(df['DCC'].sum() / 1000, 2),
            'discharged [MWh]': round(df['DDC'].sum() / 1000, 2),
            'final SOH [-]':    round(df['SOH'].iloc[-1], 6)}

if __name__ == "__main__":
    summary = []
    for pset in params:
        name = pset["config_name"]
        print(f'\n===== {name} =====')
        m = build(pset, price_DA)
        ok, status, termination = solve(m)
        print(f'solver status: {status}, termination: {termination}')
        if not ok:
            summary.append({'config': name, 'status': status, 'termination': termination})
            continue

        objective = pyo.value(m.obj)
        print(f'objective (revenue): {objective:,.2f}')

        df = extract(m)
        os.makedirs(RESULTS_DIR, exist_ok=True)
        csv_path = os.path.join(RESULTS_DIR, f'bess_{name}.csv')
        df.to_csv(csv_path, index=False)
        print(f'saved results -> {csv_path}')

        plot_dispatch(df, name)
        summary.append(summarise(df, name, objective, status, termination))

    print('\n===== SUMMARY =====')
    print(pd.DataFrame(summary).to_string(index=False))
    plt.show()
