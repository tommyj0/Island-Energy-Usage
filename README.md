# Island-Energy-Usage

Energy and solar finance analysis for two dog shelter locations, using weather/solar CSV exports in `res/`:

- Many Tears Rescue (Wales): https://www.manytearsrescue.org/
- Pet Rescue Italia (Italy): https://www.petrescueitalia.org/

## What it does

- Loads monthly climate and solar generation data from:
	- `res/WalesData.csv`
	- `res/ItalyData.csv`
- Estimates monthly and annual shelter energy consumption.
- Estimates solar financial performance:
	- self-consumption
	- export revenue
	- avoided grid cost (savings)
	- total benefit
	- initial cost impact
	- simple payback
- Generates multi-year financial comparison graphs:
	- cumulative cost for `Solar + Grid` vs `Grid Only`
	- break-even marker and annotation (if break-even occurs in horizon)

## Project files

- `dog_shelter_energy.py`: main analysis script
- `res/WalesData.csv`: Wales climate + generation source
- `res/ItalyData.csv`: Italy climate + generation source

## Requirements

- Python 3.10+
- `pandas`
- `matplotlib`

Install dependencies (inside your virtual environment):

```bash
pip install pandas matplotlib
```

## Run

From the project root:

```bash
python dog_shelter_energy.py
```

## Outputs

The script produces CSV and SVG files in the project root.

For Wales (`Many Tears Rescue`):
- `Many_Tears_Rescue_Wales_solar_financials.csv`
- `Many_Tears_Rescue_Wales_financial_comparison.svg`
- `Many Tears Rescue Wales_monthly_energy.svg`

For Italy (`Pet Rescue Italia`):
- `APS_solar_financials.csv`
- `APS_financial_comparison.svg`
- `APS_monthly_energy.svg`

## Key configuration

In `dog_shelter_energy.py` inside `main()`:

- `export_price`: export tariff per kWh
- `energy_price`: import/grid price per kWh
- `solar_panel_lifetime`: default financial comparison horizon (years)
- `uk_initial_cost`, `italy_initial_cost`: upfront solar install cost assumptions

Update these values to match your real tariffs, project cost, and expected panel lifetime.

## Notes

- Monthly climate and generation values come directly from the CSV columns:
	- temperature: `T_Amb`
	- solar generation: `EArray`
- Solar generation data is sourced from PVsyst export files (read from the `EArray` column).
- Financial comparison repeats the monthly profile across the selected analysis horizon.