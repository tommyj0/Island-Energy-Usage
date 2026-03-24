import matplotlib.pyplot as plt
import csv
from pathlib import Path
import re

import pandas as pd


MONTH_ORDER = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def load_monthly_data(csv_path):
    """Load monthly ambient temperature and solar generation from PVsyst-like CSV exports."""
    data = pd.read_csv(csv_path, skiprows=2)

    # First column is month names (often exported as unnamed); keep only month rows.
    month_col = data.columns[0]
    data = data.rename(columns={month_col: "Month"})
    data["Month"] = data["Month"].astype(str).str.strip()
    data = data[data["Month"].isin(MONTH_ORDER)].copy()

    # Keep expected month order for predictable calculations and plotting.
    data["Month"] = pd.Categorical(data["Month"], categories=MONTH_ORDER, ordered=True)
    data = data.sort_values("Month")

    climate = {row["Month"]: float(row["T_Amb"]) for _, row in data.iterrows()}
    solar_generation = {row["Month"]: float(row["EArray"]) for _, row in data.iterrows()}

    return climate, solar_generation


def load_monthly_solar_generation(csv_path):
    """Load monthly solar generation from scenario CSVs.

    Supports both PVsyst balance exports using EArray and energy-use exports using E_Avail.
    """
    data = pd.read_csv(csv_path, skiprows=2)

    month_col = data.columns[0]
    data = data.rename(columns={month_col: "Month"})
    data["Month"] = data["Month"].astype(str).str.strip()
    data = data[data["Month"].isin(MONTH_ORDER)].copy()

    data["Month"] = pd.Categorical(data["Month"], categories=MONTH_ORDER, ordered=True)
    data = data.sort_values("Month")

    if "EArray" in data.columns:
        solar_col = "EArray"
    elif "E_Avail" in data.columns:
        solar_col = "E_Avail"
    else:
        raise ValueError(f"No solar generation column found in {csv_path}; expected EArray or E_Avail")

    return {row["Month"]: float(row[solar_col]) for _, row in data.iterrows()}


def load_self_consumption_rates_from_pv_csv(csv_path):
    """Load monthly and annual self-consumption rates from XXPV.csv exports.

    Self-consumption rate is computed as:
    (E_Avail - E_Grid) / E_Avail
    where E_Avail is PV generation and E_Grid is exported energy.
    """
    data = pd.read_csv(csv_path, skiprows=2)

    month_col = data.columns[0]
    data = data.rename(columns={month_col: "Month"})
    data["Month"] = data["Month"].astype(str).str.strip()

    monthly = data[data["Month"].isin(MONTH_ORDER)].copy()
    if monthly.empty:
        raise ValueError(f"No monthly rows found in PV file: {csv_path}")

    monthly["Month"] = pd.Categorical(monthly["Month"], categories=MONTH_ORDER, ordered=True)
    monthly = monthly.sort_values("Month")

    monthly_rates = []
    for _, row in monthly.iterrows():
        e_avail = float(row["E_Avail"])
        e_grid = float(row["E_Grid"])
        if e_avail <= 0:
            monthly_rates.append(0.0)
            continue
        monthly_rates.append(max(0.0, min(1.0, (e_avail - e_grid) / e_avail)))

    year_rows = data[data["Month"] == "Year"]
    annual_rate = None
    if not year_rows.empty:
        year_row = year_rows.iloc[0]
        year_e_avail = float(year_row["E_Avail"])
        year_e_grid = float(year_row["E_Grid"])
        if year_e_avail > 0:
            annual_rate = max(0.0, min(1.0, (year_e_avail - year_e_grid) / year_e_avail))

    if annual_rate is None:
        total_e_avail = monthly["E_Avail"].astype(float).sum()
        total_e_grid = monthly["E_Grid"].astype(float).sum()
        annual_rate = 0.0 if total_e_avail <= 0 else max(0.0, min(1.0, (total_e_avail - total_e_grid) / total_e_avail))

    return {
        "monthly_rates": monthly_rates,
        "annual_rate": annual_rate,
    }


class DogShelter:
    def __init__(
        self,
        name,
        area,
        heat_loss_coef,
        climate,
        miscellaneous_per_area_watts=3,
        cooling_coef=2,
        heating_efficiency=0.9,
        cooling_efficiency=3.0,
    ):
        self.name = name
        self.area = area  # m²
        self.heat_loss_coef = heat_loss_coef  # W/(m²·K) - Heat loss coefficient (typically 0.5-1.5 for buildings)
        self.cooling_coef = cooling_coef  # W/(m²·K) - Cooling/AC coefficient (typically 1.5-2.5)
        self.heating_efficiency = heating_efficiency  # Boiler efficiency or heating COP equivalent
        self.cooling_efficiency = cooling_efficiency  # Cooling COP/EER equivalent
        self.climate = climate

        if self.heating_efficiency <= 0:
            raise ValueError("heating_efficiency must be greater than 0")
        if self.cooling_efficiency <= 0:
            raise ValueError("cooling_efficiency must be greater than 0")

        # Placeholder value for lighting energy per m² in watts
        self.lighting_energy_per_area_watts = 2
        # Miscellaneous energy for appliances, small equipment, etc. per m² in watts
        self.miscellaneous_per_area_watts = miscellaneous_per_area_watts
        self.monthly_heating = []
        self.monthly_lighting = []
        self.monthly_miscellaneous = []
        self.monthly_ac = []
        self.monthly_energy = []
        self.energy_consumption = self.calculate_total_energy()

    def print(self):
        print(f"Shelter Name: {self.name}")
        print(f"Area (m²): {self.area}")
        print(f"Heat Loss Coefficient (W/(m²·K)): {self.heat_loss_coef}")
        print(f"Heating Efficiency/COP: {self.heating_efficiency}")
        print(f"Cooling Efficiency/COP: {self.cooling_efficiency}")
        print(f"Climate: {self.climate}")
        print(f"Estimated Annual Total Energy Consumption (kWh): {
              self.energy_consumption:.2f}")

    def calculate_heating(self, temp_diff):
        """Calculate heating energy for a given temperature difference.
        Formula:
        Thermal Demand (W) = Heat Loss (W) × Area (m²) × Temp Diff (K)
        Input Energy (kWh) = Thermal Demand × Hours/Month ÷ (1000 × heating_efficiency)
        """
        # temp_diff in K, area in m², 730 hours/month average, divide by 1000 to convert W to kW
        heating_energy = (
            temp_diff * self.area * self.heat_loss_coef * 730
            / (1000 * self.heating_efficiency)
        )
        return heating_energy

    def calculate_lighting(self):
        """Calculate lighting energy for the shelter."""
        lighting_energy = self.area * self.lighting_energy_per_area_watts * \
            730 / 1000  # Convert to kWh
        return lighting_energy

    def calculate_miscellaneous(self):
        """Calculate miscellaneous energy for appliances, equipment, and other small draws."""
        miscellaneous_energy = self.area * self.miscellaneous_per_area_watts * \
            730 / 1000  # Convert to kWh
        return miscellaneous_energy

    def calculate_ac(self, temp_diff_cooling):
        """Calculate air conditioning energy for a given temperature difference above ideal."""
        # Convert from W to kWh and account for cooling system efficiency/COP.
        ac_energy = (
            temp_diff_cooling * self.area * self.cooling_coef * 730
            / (1000 * self.cooling_efficiency)
        )
        return ac_energy

    def calculate_total_energy(self, heating_setpoint=18, cooling_setpoint=24):
        """Calculate total energy consumption by iterating through months and calling helper functions.
        Comfort band: no heating/cooling required between heating_setpoint and cooling_setpoint."""
        total_energy = 0
        self.monthly_energy = []
        self.monthly_heating = []
        self.monthly_lighting = []
        self.monthly_miscellaneous = []
        self.monthly_ac = []

        for month, temp in self.climate.items():
            # Calculate temperature difference for heating (only when below heating setpoint)
            temp_diff_heating = max(0, heating_setpoint - temp)
            # Calculate temperature difference for cooling (only when above cooling setpoint)
            temp_diff_cooling = max(0, temp - cooling_setpoint)

            # Call helper functions for each energy type
            heating_energy = self.calculate_heating(temp_diff_heating)
            lighting_energy = self.calculate_lighting()
            miscellaneous_energy = self.calculate_miscellaneous()
            ac_energy = self.calculate_ac(temp_diff_cooling)

            # Store heating, lighting, miscellaneous, and AC separately
            self.monthly_heating.append(heating_energy)
            self.monthly_lighting.append(lighting_energy)
            self.monthly_miscellaneous.append(miscellaneous_energy)
            self.monthly_ac.append(ac_energy)

            # Total energy for this month
            monthly_total = heating_energy + lighting_energy + miscellaneous_energy + ac_energy
            self.monthly_energy.append(monthly_total)
            total_energy += monthly_total

        return total_energy

    def plot_monthly_energy(self, output_dir=None):
        months = list(self.climate.keys())

        plt.figure(figsize=(12, 6))
        x_pos = range(len(months))

        # Create stacked bar chart
        bars1 = plt.bar(x_pos, self.monthly_heating,
                        label='Heating', color='#FF6B6B')
        bars2 = plt.bar(x_pos, self.monthly_lighting,
                        bottom=self.monthly_heating, label='Lighting', color='#FFA500')
        
        # Calculate bottom for miscellaneous (heating + lighting)
        heating_plus_lighting = [self.monthly_heating[i] + self.monthly_lighting[i] 
                                 for i in range(len(months))]
        bars3 = plt.bar(x_pos, self.monthly_miscellaneous,
                        bottom=heating_plus_lighting, label='Appliances', color='#CC79A7')
        
        # Calculate bottom for AC (heating + lighting + miscellaneous)
        heating_lighting_misc = [self.monthly_heating[i] + self.monthly_lighting[i] + self.monthly_miscellaneous[i]
                                 for i in range(len(months))]
        bars4 = plt.bar(x_pos, self.monthly_ac,
                        bottom=heating_lighting_misc, label='Air Conditioning', color='#0072B2')

        monthly_totals = [
            self.monthly_heating[i] + self.monthly_lighting[i] + self.monthly_miscellaneous[i] + self.monthly_ac[i]
            for i in range(len(months))
        ]
        plt.ylim(0, max(monthly_totals) * 1.12)

        # Add value labels on top of each bar
        for i, month in enumerate(months):
            total = monthly_totals[i]
            plt.text(i, total, f'{total:.1f}',
                     ha='center', va='bottom', fontsize=9)

        plt.xlabel('Month')
        plt.ylabel('Energy Consumption (kWh)')
        plt.title(f'Monthly Energy Consumption Split for {self.name}')
        plt.xticks(x_pos, months, rotation=45, ha='right')
        plt.legend()
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        output_dir = Path(output_dir) if output_dir is not None else Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{self.name}_monthly_energy.svg"
        plt.savefig(output_path)
        plt.close()
        return str(output_path)

    def build_financial_comparison(self, financials, analysis_years=1, annual_discount_rate=0.0):
        """Build cumulative discounted cost series for solar versus grid-only operation."""
        monthly_financials = financials["monthly"]
        annual_financials = financials["annual"]
        months = list(monthly_financials.keys())
        buy_price_per_kwh = annual_financials["buy_price_per_kwh"]
        initial_cost = annual_financials["initial_cost"]

        months_elapsed = [0]
        grid_only_cumulative_cost = [0]
        solar_cumulative_cost = [initial_cost]
        solar_advantage = [-initial_cost]
        break_even_month = None

        running_grid_only_cost = 0
        running_solar_cost = initial_cost
        month_counter = 0

        for _ in range(analysis_years):
            for month in months:
                values = monthly_financials[month]
                grid_only_monthly_cost = values["consumption_kwh"] * buy_price_per_kwh
                solar_monthly_cost = (
                    values["net_grid_import_kwh"] * buy_price_per_kwh
                    - values["revenue"]
                )

                discount_factor = (1 + annual_discount_rate) ** (month_counter / 12)
                discounted_grid_only_monthly_cost = grid_only_monthly_cost / discount_factor
                discounted_solar_monthly_cost = solar_monthly_cost / discount_factor

                previous_advantage = running_grid_only_cost - running_solar_cost
                running_grid_only_cost += discounted_grid_only_monthly_cost
                running_solar_cost += discounted_solar_monthly_cost
                month_counter += 1
                current_advantage = running_grid_only_cost - running_solar_cost

                months_elapsed.append(month_counter)
                grid_only_cumulative_cost.append(running_grid_only_cost)
                solar_cumulative_cost.append(running_solar_cost)
                solar_advantage.append(current_advantage)

                if break_even_month is None and previous_advantage < 0 <= current_advantage:
                    advantage_delta = current_advantage - previous_advantage
                    if advantage_delta == 0:
                        break_even_month = float(month_counter)
                    else:
                        break_even_month = (month_counter - 1) + ((0 - previous_advantage) / advantage_delta)

        return {
            "months_elapsed": months_elapsed,
            "grid_only_cumulative_cost": grid_only_cumulative_cost,
            "solar_cumulative_cost": solar_cumulative_cost,
            "solar_advantage": solar_advantage,
            "break_even_month": break_even_month,
            "analysis_years": analysis_years,
        }

    def plot_financial_comparison(
        self,
        financials,
        analysis_years=1,
        currency_symbol="£",
        annual_discount_rate=0.0,
        output_dir=None,
    ):
        """Plot cumulative discounted solar and grid-only costs, including upfront solar cost."""
        comparison = self.build_financial_comparison(
            financials,
            analysis_years=analysis_years,
            annual_discount_rate=annual_discount_rate,
        )
        months_elapsed = comparison["months_elapsed"]
        grid_only_cumulative_cost = comparison["grid_only_cumulative_cost"]
        solar_cumulative_cost = comparison["solar_cumulative_cost"]
        solar_advantage = comparison["solar_advantage"]
        break_even_month = comparison["break_even_month"]

        fig, (ax_costs, ax_advantage) = plt.subplots(
            2,
            1,
            figsize=(12, 9),
            sharex=True,
            gridspec_kw={"height_ratios": [2, 1]},
        )

        ax_costs.plot(
            months_elapsed,
            grid_only_cumulative_cost,
            linewidth=2.5,
            color="#D55E00",
            label="Grid only",
        )
        ax_costs.plot(
            months_elapsed,
            solar_cumulative_cost,
            linewidth=2.5,
            color="#009E73",
            label="Solar + grid import",
        )
        ax_costs.set_ylabel(f"Cumulative Discounted Cost ({currency_symbol})")
        ax_costs.set_title(
            f"Solar vs Grid-Only Financial Comparison for {self.name}"
            f" ({annual_discount_rate * 100:.1f}% discount rate)"
        )
        ax_costs.grid(axis="y", alpha=0.3)
        ax_costs.legend()

        ax_advantage.axhline(0, color="#444444", linewidth=1)
        ax_advantage.plot(
            months_elapsed,
            solar_advantage,
            linewidth=2.5,
            color="#0072B2",
            label="Solar advantage vs grid only",
        )
        ax_advantage.fill_between(
            months_elapsed,
            solar_advantage,
            0,
            where=[value >= 0 for value in solar_advantage],
            color="#009E73",
            alpha=0.2,
            interpolate=True,
        )
        ax_advantage.fill_between(
            months_elapsed,
            solar_advantage,
            0,
            where=[value < 0 for value in solar_advantage],
            color="#D55E00",
            alpha=0.2,
            interpolate=True,
        )
        ax_advantage.set_ylabel(f"+/- Discounted vs Grid ({currency_symbol})")
        ax_advantage.set_xlabel("Time")
        ax_advantage.grid(axis="y", alpha=0.3)

        final_advantage = solar_advantage[-1]
        ax_advantage.text(
            months_elapsed[-1],
            final_advantage,
            f" {currency_symbol}{final_advantage:.0f}",
            va="bottom" if final_advantage >= 0 else "top",
            ha="left",
            fontsize=9,
        )

        tick_positions = [0] + [year * 12 for year in range(1, analysis_years + 1)]
        tick_labels = ["Initial"] + [f"Year {year}" for year in range(1, analysis_years + 1)]
        ax_advantage.set_xticks(tick_positions)
        ax_advantage.set_xticklabels(tick_labels, rotation=45, ha="right")

        if break_even_month is None:
            break_even_text = f"No break-even within {analysis_years} years"
        else:
            break_even_years = break_even_month / 12
            ax_advantage.axvline(break_even_month, color="#009E73", linestyle="--", linewidth=1.5)
            ax_advantage.scatter([break_even_month], [0], color="#009E73", zorder=5)
            break_even_text = (
                f"Break-even after {break_even_years:.1f} years\n"
                f"(~month {break_even_month:.1f})"
            )
            ax_advantage.annotate(
                break_even_text,
                xy=(break_even_month, 0),
                xytext=(12, 18),
                textcoords="offset points",
                bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "alpha": 0.9},
                arrowprops={"arrowstyle": "->", "color": "#009E73"},
                fontsize=9,
            )

        if break_even_month is None:
            ax_advantage.text(
                0.02,
                0.95,
                break_even_text,
                transform=ax_advantage.transAxes,
                va="top",
                ha="left",
                fontsize=9,
                bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "alpha": 0.9},
            )

        plt.tight_layout()

        safe_name = self.name.replace(" ", "_")
        output_dir = Path(output_dir) if output_dir is not None else Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{safe_name}_financial_comparison.svg"
        plt.savefig(output_path)
        plt.close(fig)
        return str(output_path)

    def calculate_variable_self_consumption_rate(
        self,
        monthly_solar_generation,
        monthly_consumption=None,
    ):
        """Calculate realistic self-consumption rate based on demand/generation curve matching.
        
        Assumes flexible load: in each month, the maximum self-consumable is limited by 
        whichever is smaller (generation or consumption). This represents the best-case 
        scenario with demand shifting within the month.
        
        Args:
            monthly_solar_generation: dict month->kWh or list of monthly kWh values.
            monthly_consumption: optional dict/list of kWh consumed; defaults to this shelter's monthly energy.
            
        Returns:
            Dict with 'monthly_rates' (list of monthly rates 0-1), 'annual_rate' (weighted average),
            and 'monthly_breakdown' (dict of month -> {consumption, solar, self_consumable, rate}).
        """
        months = list(self.climate.keys())
        
        if monthly_consumption is None:
            consumption_values = list(self.monthly_energy)
        elif isinstance(monthly_consumption, dict):
            consumption_values = [monthly_consumption[month] for month in months]
        else:
            consumption_values = list(monthly_consumption)
        
        if isinstance(monthly_solar_generation, dict):
            solar_values = [monthly_solar_generation[month] for month in months]
        else:
            solar_values = list(monthly_solar_generation)
        
        if len(consumption_values) != len(solar_values):
            raise ValueError("Consumption and solar generation must have the same number of months")
        
        monthly_rates = []
        monthly_breakdown = {}
        total_self_consumable = 0
        total_solar = 0
        
        for index, month in enumerate(months):
            consumption_kwh = consumption_values[index]
            solar_kwh = solar_values[index]
            
            # Only this fraction of consumption can occur during daylight when solar generates
            daylight_consumption_kwh = consumption_kwh * 0.5
        
            # Self-consumable is limited by both daylight consumption and actual generation
            self_consumable_kwh = min(daylight_consumption_kwh, solar_kwh)
            total_self_consumable += self_consumable_kwh
            total_solar += solar_kwh
            
            # Monthly self-consumption rate
            monthly_rate = self_consumable_kwh / solar_kwh if solar_kwh > 0 else 0
            monthly_rates.append(monthly_rate)
            
            monthly_breakdown[month] = {
                "consumption_kwh": consumption_kwh,
                "solar_kwh": solar_kwh,
                "daylight_consumption_kwh": daylight_consumption_kwh,
                "self_consumable_kwh": self_consumable_kwh,
                "monthly_rate": monthly_rate,
            }
        
        # Annual rate: what fraction of total annual solar can be self-consumed
        annual_rate = total_self_consumable / total_solar if total_solar > 0 else 0
        
        return {
            "monthly_rates": monthly_rates,
            "annual_rate": annual_rate,
            "monthly_breakdown": monthly_breakdown,
        }

    def estimate_solar_financials(
        self,
        monthly_solar_generation,
        sell_price_per_kwh,
        monthly_consumption=None,
        buy_price_per_kwh=None,
        initial_cost=0,
        assumed_self_consumption_rate=None,
        use_variable_self_consumption=False,
        monthly_self_consumption_rates=None,
    ):
        """Estimate monthly and annual earnings from solar export.

        Args:
            monthly_solar_generation: dict month->kWh generated, or list of monthly kWh values.
            sell_price_per_kwh: selling price in currency/kWh (e.g. £/kWh).
            monthly_consumption: optional dict/list of kWh consumed; defaults to this shelter's monthly energy.
            buy_price_per_kwh: purchase price in currency/kWh for imported energy; used to calculate savings.
            initial_cost: optional upfront installation cost in currency units.
            assumed_self_consumption_rate: optional fixed self-consumption share of solar generation (0-1).
            use_variable_self_consumption: if True, calculate rate from demand/generation curves; 
                                          overrides assumed_self_consumption_rate if both provided.
            monthly_self_consumption_rates: optional list of 12 monthly self-consumption rates (0-1),
                                            typically derived from XXPV.csv.

        Returns:
            Dict with monthly breakdown and annual totals. Includes 'variable_self_consumption_rate'
            when use_variable_self_consumption is True.
        """
        if buy_price_per_kwh is None:
            # Backward-compatible default if only one tariff is supplied.
            buy_price_per_kwh = sell_price_per_kwh

        months = list(self.climate.keys())

        if initial_cost < 0:
            raise ValueError("Initial cost cannot be negative")
        if (
            assumed_self_consumption_rate is not None
            and not (0 <= assumed_self_consumption_rate <= 1)
        ):
            raise ValueError("assumed_self_consumption_rate must be between 0 and 1")
        if monthly_self_consumption_rates is not None:
            if len(monthly_self_consumption_rates) != len(months):
                raise ValueError("monthly_self_consumption_rates must have the same number of months")
            if any((rate < 0 or rate > 1) for rate in monthly_self_consumption_rates):
                raise ValueError("monthly_self_consumption_rates must contain values between 0 and 1")

        if monthly_consumption is None:
            consumption_values = list(self.monthly_energy)
        elif isinstance(monthly_consumption, dict):
            consumption_values = [monthly_consumption[month] for month in months]
        else:
            consumption_values = list(monthly_consumption)

        if isinstance(monthly_solar_generation, dict):
            solar_values = [monthly_solar_generation[month] for month in months]
        else:
            solar_values = list(monthly_solar_generation)

        if len(consumption_values) != len(solar_values):
            raise ValueError("Consumption and solar generation must have the same number of months")

        # Calculate variable self-consumption if requested
        variable_sc_data = None
        effective_self_consumption_rate = assumed_self_consumption_rate
        if use_variable_self_consumption:
            variable_sc_data = self.calculate_variable_self_consumption_rate(
                monthly_solar_generation=solar_values,
                monthly_consumption=consumption_values,
            )
            effective_self_consumption_rate = variable_sc_data["annual_rate"]

        monthly_results = {}
        annual_consumption = 0
        annual_solar = 0
        annual_self_consumed = 0
        annual_exported = 0
        annual_revenue = 0
        annual_savings = 0
        annual_total_benefit = 0

        for index, month in enumerate(months):
            consumption_kwh = consumption_values[index]
            solar_kwh = solar_values[index]

            if use_variable_self_consumption:
                # Use the realistic self-consumption for this month
                self_consumed_kwh = min(consumption_kwh, solar_kwh)
            elif monthly_self_consumption_rates is not None:
                self_consumed_kwh = min(
                    consumption_kwh,
                    solar_kwh * monthly_self_consumption_rates[index],
                )
            elif effective_self_consumption_rate is None:
                self_consumed_kwh = min(consumption_kwh, solar_kwh)
            else:
                self_consumed_kwh = min(
                    consumption_kwh,
                    solar_kwh * effective_self_consumption_rate,
                )
            
            exported_kwh = max(0, solar_kwh - self_consumed_kwh)
            # Grid import must be based on what is self-consumed, not total generation.
            # With a fixed self-consumption assumption (e.g. 30%), only that portion offsets imports.
            net_grid_import_kwh = max(0, consumption_kwh - self_consumed_kwh)
            revenue = exported_kwh * sell_price_per_kwh
            savings = self_consumed_kwh * buy_price_per_kwh
            total_benefit = revenue + savings

            monthly_results[month] = {
                "consumption_kwh": consumption_kwh,
                "solar_generation_kwh": solar_kwh,
                "self_consumed_kwh": self_consumed_kwh,
                "exported_kwh": exported_kwh,
                "net_grid_import_kwh": net_grid_import_kwh,
                "revenue": revenue,
                "savings": savings,
                "total_benefit": total_benefit,
            }

            annual_consumption += consumption_kwh
            annual_solar += solar_kwh
            annual_self_consumed += self_consumed_kwh
            annual_exported += exported_kwh
            annual_revenue += revenue
            annual_savings += savings
            annual_total_benefit += total_benefit

        net_benefit_after_initial_cost = annual_total_benefit - initial_cost
        simple_payback_years = None
        if initial_cost > 0 and annual_total_benefit > 0:
            simple_payback_years = initial_cost / annual_total_benefit

        return {
            "monthly": monthly_results,
            "annual": {
                "consumption_kwh": annual_consumption,
                "solar_generation_kwh": annual_solar,
                "self_consumed_kwh": annual_self_consumed,
                "exported_kwh": annual_exported,
                "revenue": annual_revenue,
                "savings": annual_savings,
                "total_benefit": annual_total_benefit,
                "initial_cost": initial_cost,
                "net_benefit_after_initial_cost": net_benefit_after_initial_cost,
                "simple_payback_years": simple_payback_years,
                "sell_price_per_kwh": sell_price_per_kwh,
                "buy_price_per_kwh": buy_price_per_kwh,
            },
            "pv_informed_self_consumption_rate": (
                annual_self_consumed / annual_solar if annual_solar > 0 else 0.0
            ),
            "variable_self_consumption_rate": (
                variable_sc_data["annual_rate"]
                if use_variable_self_consumption and variable_sc_data is not None
                else None
            ),
        }

    def print_solar_financials_table(self, financials, currency_symbol="£"):
        """Print a month-by-month financial table from estimate_solar_financials output."""
        print("\nMonthly Solar Financial Breakdown")
        print(
            f"{'Month':<10} {'Use (kWh)':>12} {'Solar (kWh)':>12} {'Self-use':>12} "
            f"{'Export':>12} {'Grid Import':>12} {'Revenue':>12} {'Savings':>12} {'Benefit':>12}"
        )
        print("-" * 120)

        for month, values in financials["monthly"].items():
            print(
                f"{month:<10} "
                f"{values['consumption_kwh']:>12.1f} "
                f"{values['solar_generation_kwh']:>12.1f} "
                f"{values['self_consumed_kwh']:>12.1f} "
                f"{values['exported_kwh']:>12.1f} "
                f"{values['net_grid_import_kwh']:>12.1f} "
                f"{currency_symbol}{values['revenue']:>11.2f} "
                f"{currency_symbol}{values['savings']:>11.2f} "
                f"{currency_symbol}{values['total_benefit']:>11.2f}"
            )

        annual = financials["annual"]
        print("-" * 120)
        print(
            f"{'TOTAL':<10} "
            f"{annual['consumption_kwh']:>12.1f} "
            f"{annual['solar_generation_kwh']:>12.1f} "
            f"{annual['self_consumed_kwh']:>12.1f} "
            f"{annual['exported_kwh']:>12.1f} "
            f"{(annual['consumption_kwh'] - annual['self_consumed_kwh']):>12.1f} "
            f"{currency_symbol}{annual['revenue']:>11.2f} "
            f"{currency_symbol}{annual['savings']:>11.2f} "
            f"{currency_symbol}{annual['total_benefit']:>11.2f}"
        )

        print(f"\nInitial cost: {currency_symbol}{annual['initial_cost']:.2f}")
        print(f"Year 1 net benefit after initial cost: {currency_symbol}{annual['net_benefit_after_initial_cost']:.2f}")
        if annual["simple_payback_years"] is None:
            print("Simple payback: n/a")
        else:
            print(f"Simple payback: {annual['simple_payback_years']:.2f} years")

    def save_solar_financials_csv(self, financials, file_path=None, output_dir=None):
        """Save the month-by-month financial table to a CSV file."""
        output_dir = Path(output_dir) if output_dir is not None else Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        if file_path is None:
            safe_name = self.name.replace(" ", "_")
            file_path = output_dir / f"{safe_name}_solar_financials.csv"
        else:
            file_path = Path(file_path)

        with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([
                "Month",
                "Use (kWh)",
                "Solar (kWh)",
                "Self-use (kWh)",
                "Export (kWh)",
                "Grid Import (kWh)",
                "Revenue",
                "Savings",
                "Total Benefit",
            ])

            for month, values in financials["monthly"].items():
                writer.writerow([
                    month,
                    round(values["consumption_kwh"], 2),
                    round(values["solar_generation_kwh"], 2),
                    round(values["self_consumed_kwh"], 2),
                    round(values["exported_kwh"], 2),
                    round(values["net_grid_import_kwh"], 2),
                    round(values["revenue"], 2),
                    round(values["savings"], 2),
                    round(values["total_benefit"], 2),
                ])

            annual = financials["annual"]
            writer.writerow([
                "TOTAL",
                round(annual["consumption_kwh"], 2),
                round(annual["solar_generation_kwh"], 2),
                round(annual["self_consumed_kwh"], 2),
                round(annual["exported_kwh"], 2),
                round(annual["consumption_kwh"] - annual["self_consumed_kwh"], 2),
                round(annual["revenue"], 2),
                round(annual["savings"], 2),
                round(annual["total_benefit"], 2),
            ])

            writer.writerow(["Initial Cost", "", "", "", "", "", "", "", round(annual["initial_cost"], 2)])
            writer.writerow([
                "Year 1 Net Benefit",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                round(annual["net_benefit_after_initial_cost"], 2),
            ])
            writer.writerow([
                "Simple Payback (years)",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                ""
                if annual["simple_payback_years"] is None
                else round(annual["simple_payback_years"], 2),
            ])

        return str(file_path)


def print_financial_summary(
    financials,
    report_title,
    export_price,
    energy_price,
    analysis_years,
):
    """Print the annual solar finance summary."""
    annual = financials["annual"]

    print(f"\n{report_title}")
    print(f"Annual consumption (kWh): {annual['consumption_kwh']:.1f}")
    print(f"Annual solar generation (kWh): {annual['solar_generation_kwh']:.1f}")
    print(f"Annual export (kWh): {annual['exported_kwh']:.1f}")
    print(f"Annual revenue (@ {export_price:.2f}/kWh): {annual['revenue']:.2f}")
    print(f"Annual savings (@ {energy_price:.2f}/kWh): {annual['savings']:.2f}")
    print(f"Annual total benefit: {annual['total_benefit']:.2f}")
    print(f"Initial cost: {annual['initial_cost']:.2f}")
    print(f"Year 1 net benefit after initial cost: {annual['net_benefit_after_initial_cost']:.2f}")
    print(f"Comparison horizon: {analysis_years} years")
    if annual["simple_payback_years"] is None:
        print("Simple payback: n/a")
    else:
        print(f"Simple payback: {annual['simple_payback_years']:.2f} years")


def run_shelter_analysis(
    shelter,
    monthly_solar_generation,
    export_price,
    energy_price,
    initial_cost,
    report_title,
    analysis_years,
):
    """Run financial analysis, print a summary, and save related outputs."""
    shelter.print()
    financials = shelter.estimate_solar_financials(
        monthly_solar_generation=monthly_solar_generation,
        sell_price_per_kwh=export_price,
        buy_price_per_kwh=energy_price,
        initial_cost=initial_cost,
    )

    print_financial_summary(
        financials=financials,
        report_title=report_title,
        export_price=export_price,
        energy_price=energy_price,
        analysis_years=analysis_years,
    )

    saved_csv_path = shelter.save_solar_financials_csv(financials)
    print(f"Saved financial CSV: {saved_csv_path}")

    financial_plot_path = shelter.plot_financial_comparison(
        financials,
        analysis_years=analysis_years,
    )
    print(f"Saved financial graph: {financial_plot_path}")

    shelter.plot_monthly_energy()


def find_module_count_csvs(res_dir, prefix):
    """Find CSV files like Prefix10.csv and return sorted (module_count, path) pairs."""
    pattern = re.compile(rf"^{re.escape(prefix)}(?P<count>\d+)\.csv$")
    scenarios = []

    for file_path in res_dir.iterdir():
        if not file_path.is_file():
            continue

        match = pattern.match(file_path.name)
        if not match:
            continue

        module_count = int(match.group("count"))
        scenarios.append((module_count, file_path))

    return sorted(scenarios, key=lambda item: item[0])


def resolve_pv_profile_csv(res_dir, file_prefix, module_count):
    """Resolve module-specific PV profile CSV, with fallback to location-level PV CSV.

    Preferred: <prefix>PV<count>.csv, e.g. WalesDataPV12.csv
    Fallback: <prefix>PV.csv, e.g. WalesDataPV.csv
    """
    module_specific = res_dir / f"{file_prefix}PV{module_count}.csv"
    if module_specific.exists():
        return module_specific

    location_level = res_dir / f"{file_prefix}PV.csv"
    if location_level.exists():
        return location_level

    raise FileNotFoundError(
        f"No PV profile CSV found for {file_prefix} module {module_count}. "
        f"Expected {module_specific.name} or {location_level.name}."
    )


def module_based_initial_cost(module_count, watt_per_module, cost_per_kwatt):
    """Calculate upfront cost from module count, module wattage, and cost per kW."""
    if module_count < 0:
        raise ValueError("module_count cannot be negative")
    if watt_per_module <= 0:
        raise ValueError("watt_per_module must be greater than 0")
    if cost_per_kwatt < 0:
        raise ValueError("cost_per_kwatt cannot be negative")

    total_kw = (module_count * watt_per_module) / 1000
    return total_kw * cost_per_kwatt


def calculate_discounted_metrics(
    annual_return,
    initial_cost,
    years,
    discount_rate,
    residual_value=0.0,
    annual_investments=None,
    annual_degradation_rate=0.0,
):
    """Calculate NPV, PI, DPP, and IRR using discounted cash flow formulations."""
    if years <= 0:
        raise ValueError("years must be greater than 0")
    if discount_rate <= -1:
        raise ValueError("discount_rate must be greater than -1")
    if not (0 <= annual_degradation_rate < 1):
        raise ValueError("annual_degradation_rate must be between 0 and 1")

    if annual_investments is None:
        # I_j terms in Eq. (3-4-6), j=0..n-1; default is all investment at j=0.
        annual_investments = [0.0] * years
        annual_investments[0] = initial_cost
    elif len(annual_investments) != years:
        raise ValueError("annual_investments must have length equal to years")

    discounted_returns = sum(
        (annual_return * ((1 - annual_degradation_rate) ** (year - 1)))
        / ((1 + discount_rate) ** year)
        for year in range(1, years + 1)
    )
    discounted_residual = residual_value / ((1 + discount_rate) ** years)
    discounted_investments = sum(
        annual_investments[j] / ((1 + discount_rate) ** j)
        for j in range(years)
    )

    # Eq. (3) expressed as NPV at alpha/discount rate.
    npv_value = discounted_returns - discounted_investments + discounted_residual

    # Eq. (4)
    profitability_index = None
    if discounted_investments != 0:
        profitability_index = (discounted_returns + discounted_residual) / discounted_investments

    # Eq. (6) with linear interpolation for fractional-year DPP.
    cumulative_discounted_returns = 0.0
    dpp_years = None
    target_investments = discounted_investments - discounted_residual
    if target_investments <= 0:
        dpp_years = 0.0
    else:
        for year in range(1, years + 1):
            degraded_return = annual_return * ((1 - annual_degradation_rate) ** (year - 1))
            current = degraded_return / ((1 + discount_rate) ** year)
            prev_cumulative = cumulative_discounted_returns
            cumulative_discounted_returns += current
            if cumulative_discounted_returns >= target_investments:
                if current == 0:
                    dpp_years = float(year)
                else:
                    fraction = (target_investments - prev_cumulative) / current
                    dpp_years = (year - 1) + fraction
                break

    def irr_equation(rate):
        if rate <= -1:
            return float("inf")
        returns_term = sum(
            (annual_return * ((1 - annual_degradation_rate) ** (year - 1)))
            / ((1 + rate) ** year)
            for year in range(1, years + 1)
        )
        investments_term = sum(
            annual_investments[j] / ((1 + rate) ** j)
            for j in range(years)
        )
        residual_term = residual_value / ((1 + rate) ** years)
        return returns_term - investments_term + residual_term

    # Solve Eq. (3) for IRR via bisection where a sign change exists.
    irr_value = None
    low = -0.95
    high = 1.0
    f_low = irr_equation(low)
    f_high = irr_equation(high)
    attempts = 0
    while f_low * f_high > 0 and attempts < 25:
        high *= 2
        f_high = irr_equation(high)
        attempts += 1

    if f_low * f_high <= 0:
        for _ in range(120):
            mid = (low + high) / 2
            f_mid = irr_equation(mid)
            if abs(f_mid) < 1e-9:
                irr_value = mid
                break
            if f_low * f_mid <= 0:
                high = mid
                f_high = f_mid
            else:
                low = mid
                f_low = f_mid
        if irr_value is None:
            irr_value = (low + high) / 2

    return {
        "npv": npv_value,
        "pi": profitability_index,
        "dpp_years": dpp_years,
        "irr": irr_value,
    }


def main():
    base_dir = Path(__file__).resolve().parent
    res_dir = base_dir / "res"
    output_dir = base_dir / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    watt_per_module = 400
    cost_per_kwatt_uk = 1701
    cost_per_kwatt_it = 1450

    # Heat loss coefficient: 1.0 W/(m²·K) = typical older building with average insulation
    standard_hl_coef = 0.5
    heating_efficiency = 0.9
    cooling_efficiency = 3.0

    solar_panel_lifetime = 25
    discount_rate = 0.05
    residual_value = 0.0
    assumed_self_consumption_rate = 0.30
    annual_degradation_rate = 0.005

    shelter_configs = [
        {
            "location": "Wales",
            "shelter_name": "Many_Tears_Rescue_Wales",
            "area": 175,
            "file_prefix": "WalesData",
            "climate_file": "WalesData.csv",
            "cost_per_kwatt": cost_per_kwatt_uk,
            "export_price": 0.10,
            "energy_price": 0.2818,
        },
        {
            "location": "Italy",
            "shelter_name": "APS",
            "area": 188,
            "file_prefix": "ItalyData",
            "climate_file": "ItalyData.csv",
            "cost_per_kwatt": cost_per_kwatt_it,
            "export_price": 0.043,
            "energy_price": 0.29,
        },
    ]

    summary_rows = []

    for config in shelter_configs:
        climate_file_path = res_dir / config["climate_file"]
        climate, _ = load_monthly_data(climate_file_path)

        scenarios = find_module_count_csvs(res_dir, config["file_prefix"])
        if not scenarios:
            print(f"No module-count scenarios found for {config['location']}")
            continue

        for module_count, csv_path in scenarios:
            monthly_solar_generation = load_monthly_solar_generation(csv_path)
            pv_profile_path = resolve_pv_profile_csv(
                res_dir=res_dir,
                file_prefix=config["file_prefix"],
                module_count=module_count,
            )
            pv_self_consumption = load_self_consumption_rates_from_pv_csv(pv_profile_path)

            shelter = DogShelter(
                name=f"{config['shelter_name']}_{module_count}modules",
                area=config["area"],
                heat_loss_coef=standard_hl_coef,
                climate=climate,
                heating_efficiency=heating_efficiency,
                cooling_efficiency=cooling_efficiency,
            )

            upfront_cost = module_based_initial_cost(
                module_count=module_count,
                watt_per_module=watt_per_module,
                cost_per_kwatt=config["cost_per_kwatt"],
            )

            financials = shelter.estimate_solar_financials(
                monthly_solar_generation=monthly_solar_generation,
                sell_price_per_kwh=config["export_price"],
                buy_price_per_kwh=config["energy_price"],
                initial_cost=upfront_cost,
                monthly_self_consumption_rates=pv_self_consumption["monthly_rates"],
            )

            annual = financials["annual"]
            payback_years = annual["simple_payback_years"]
            self_consumption_rate = 0.0
            if annual["solar_generation_kwh"] > 0:
                self_consumption_rate = annual["self_consumed_kwh"] / annual["solar_generation_kwh"]

            discounted_metrics = calculate_discounted_metrics(
                annual_return=annual["total_benefit"],
                initial_cost=upfront_cost,
                years=solar_panel_lifetime,
                discount_rate=discount_rate,
                residual_value=residual_value,
                annual_degradation_rate=annual_degradation_rate,
            )

            print(f"\n{config['location']} - {module_count} modules:")
            print(f"  Annual Consumption: {annual['consumption_kwh']:.1f} kWh")
            print(f"  Annual Solar Generation: {annual['solar_generation_kwh']:.1f} kWh")
            print(f"  Annual Self-consumed: {annual['self_consumed_kwh']:.1f} kWh")
            print(f"  Annual Exported: {annual['exported_kwh']:.1f} kWh")
            print(f"  Export price: {config['export_price']:.2f}/kWh")
            print(f"  Energy price: {config['energy_price']:.2f}/kWh")
            print(f"  PV profile file: {pv_profile_path.name}")
            print(f"  Revenue: {annual['revenue']:.2f}")
            print(f"  Savings: {annual['savings']:.2f}")
            print(f"  Total Benefit: {annual['total_benefit']:.2f}")
            print(
                f"  Self-consumption rate (PV-informed): {self_consumption_rate * 100:.2f}% "
                f"(profile annual {pv_self_consumption['annual_rate'] * 100:.2f}%)"
            )
            print(f"  NPV ({solar_panel_lifetime}y @ {discount_rate * 100:.1f}%): {discounted_metrics['npv']:.2f}")
            print(f"  Panel degradation: {annual_degradation_rate * 100:.2f}%/year")
            print(f"  PI: {discounted_metrics['pi']:.4f}" if discounted_metrics["pi"] is not None else "  PI: n/a")
            print(
                f"  Discounted payback period (years): {discounted_metrics['dpp_years']:.2f}"
                if discounted_metrics["dpp_years"] is not None
                else "  Discounted payback period (years): n/a"
            )
            print(
                f"  IRR: {discounted_metrics['irr'] * 100:.2f}%"
                if discounted_metrics["irr"] is not None
                else "  IRR: n/a"
            )

            financial_plot_path = shelter.plot_financial_comparison(
                financials=financials,
                analysis_years=solar_panel_lifetime,
                annual_discount_rate=discount_rate,
                output_dir=output_dir,
            )
            print(f"  Saved financial graph: {financial_plot_path}")

            monthly_plot_path = shelter.plot_monthly_energy(output_dir=output_dir)
            print(f"  Saved monthly demand graph: {monthly_plot_path}")

            financial_csv_path = shelter.save_solar_financials_csv(financials, output_dir=output_dir)
            print(f"  Saved financial CSV: {financial_csv_path}")

            summary_rows.append(
                {
                    "location": config["location"],
                    "source_file": csv_path.name,
                    "module_count": module_count,
                    "pv_profile_file": pv_profile_path.name,
                    "upfront_cost": round(upfront_cost, 2),
                    "annual_consumption_kwh": round(annual["consumption_kwh"], 2),
                    "annual_solar_generation_kwh": round(annual["solar_generation_kwh"], 2),
                    "export_price_per_kwh": config["export_price"],
                    "energy_price_per_kwh": config["energy_price"],
                    "annual_revenue": round(annual["revenue"], 2),
                    "annual_savings": round(annual["savings"], 2),
                    "annual_total_benefit": round(annual["total_benefit"], 2),
                    "year_1_net_benefit": round(annual["net_benefit_after_initial_cost"], 2),
                    "payback_years": None if payback_years is None else round(payback_years, 2),
                    "pv_profile_self_consumption_rate": round(pv_self_consumption["annual_rate"], 4),
                    "self_consumption_rate": round(self_consumption_rate, 4),
                    "npv": round(discounted_metrics["npv"], 2),
                    "pi": None if discounted_metrics["pi"] is None else round(discounted_metrics["pi"], 4),
                    "dpp_years": None
                    if discounted_metrics["dpp_years"] is None
                    else round(discounted_metrics["dpp_years"], 2),
                    "irr": None if discounted_metrics["irr"] is None else round(discounted_metrics["irr"], 6),
                }
            )

    if not summary_rows:
        raise ValueError("No module-count scenario files found. Expected names like WalesData10.csv")

    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values(["location", "module_count"]).reset_index(drop=True)

    output_csv_path = output_dir / "module_simulation_results.csv"
    summary_df.to_csv(output_csv_path, index=False)
    print(f"Saved consolidated simulation results: {output_csv_path}")

if __name__ == "__main__":
    main()
