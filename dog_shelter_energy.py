import matplotlib.pyplot as plt
import csv
from pathlib import Path

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

    def calculate_total_energy(self, ideal_temperature=20):
        """Calculate total energy consumption by iterating through months and calling helper functions."""
        total_energy = 0
        self.monthly_energy = []
        self.monthly_heating = []
        self.monthly_lighting = []
        self.monthly_miscellaneous = []
        self.monthly_ac = []

        for month, temp in self.climate.items():
            # Calculate temperature difference for heating (only when below ideal)
            temp_diff_heating = max(0, ideal_temperature - temp)
            # Calculate temperature difference for cooling (only when above ideal)
            temp_diff_cooling = max(0, temp - ideal_temperature)

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

    def plot_monthly_energy(self):
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
        plt.savefig(f"{self.name}_monthly_energy.svg")

    def build_financial_comparison(self, financials, analysis_years=1):
        """Build cumulative cost series for solar versus grid-only operation."""
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

                previous_advantage = running_grid_only_cost - running_solar_cost
                running_grid_only_cost += grid_only_monthly_cost
                running_solar_cost += solar_monthly_cost
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

    def plot_financial_comparison(self, financials, analysis_years=1, currency_symbol="£"):
        """Plot cumulative solar and grid-only costs, including upfront solar cost."""
        comparison = self.build_financial_comparison(financials, analysis_years=analysis_years)
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
        ax_costs.set_ylabel(f"Cumulative Cost ({currency_symbol})")
        ax_costs.set_title(f"Solar vs Grid-Only Financial Comparison for {self.name}")
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
        ax_advantage.set_ylabel(f"+/- vs Grid ({currency_symbol})")
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
        output_path = f"{safe_name}_financial_comparison.svg"
        plt.savefig(output_path)
        plt.close(fig)
        return output_path

    def estimate_solar_financials(
        self,
        monthly_solar_generation,
        sell_price_per_kwh,
        monthly_consumption=None,
        buy_price_per_kwh=None,
        initial_cost=0,
    ):
        """Estimate monthly and annual earnings from solar export.

        Args:
            monthly_solar_generation: dict month->kWh generated, or list of monthly kWh values.
            sell_price_per_kwh: selling price in currency/kWh (e.g. £/kWh).
            monthly_consumption: optional dict/list of kWh consumed; defaults to this shelter's monthly energy.
            buy_price_per_kwh: purchase price in currency/kWh for imported energy; used to calculate savings.
            initial_cost: optional upfront installation cost in currency units.

        Returns:
            Dict with monthly breakdown and annual totals.
        """
        if buy_price_per_kwh is None:
            # Backward-compatible default if only one tariff is supplied.
            buy_price_per_kwh = sell_price_per_kwh

        if initial_cost < 0:
            raise ValueError("Initial cost cannot be negative")

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

            self_consumed_kwh = min(consumption_kwh, solar_kwh)
            exported_kwh = max(0, solar_kwh - consumption_kwh)
            net_grid_import_kwh = max(0, consumption_kwh - solar_kwh)
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

    def save_solar_financials_csv(self, financials, file_path=None):
        """Save the month-by-month financial table to a CSV file."""
        if file_path is None:
            safe_name = self.name.replace(" ", "_")
            file_path = f"{safe_name}_solar_financials.csv"

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

        return file_path


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


def main():
    base_dir = Path(__file__).resolve().parent
    wales_csv = base_dir / "res" / "WalesData.csv"
    italy_csv = base_dir / "res" / "ItalyData.csv"

    crosshands_monthly_temps, uk_monthly_solar_generation = load_monthly_data(wales_csv)
    cornaredo_monthly_temps, italy_monthly_solar_generation = load_monthly_data(italy_csv)

    # Heat loss coefficient: 1.0 W/(m²·K) = typical older building with average insulation
    standard_hl_coef = 1.0
    heating_efficiency = 0.9
    cooling_efficiency = 3.0
    ukshelter = DogShelter("Many_Tears_Rescue_Wales", 175,
                           standard_hl_coef, crosshands_monthly_temps,
                           heating_efficiency=heating_efficiency,
                           cooling_efficiency=cooling_efficiency)
    italyshelter = DogShelter(
        "APS", 188, standard_hl_coef, cornaredo_monthly_temps,
        heating_efficiency=heating_efficiency,
        cooling_efficiency=cooling_efficiency)

    # Example tariffs (e.g. £/kWh)
    # TODO: change these to accurate values for each country, and ideally make them dynamic inputs
    export_price = 0.15
    energy_price = 0.30
    solar_panel_lifetime = 25
    uk_initial_cost = 18000
    italy_initial_cost = 22000

    run_shelter_analysis(
        shelter=ukshelter,
        monthly_solar_generation=uk_monthly_solar_generation,
        export_price=export_price,
        energy_price=energy_price,
        initial_cost=uk_initial_cost,
        report_title="UK Shelter Solar Financial Estimate",
        analysis_years=solar_panel_lifetime,
    )

    run_shelter_analysis(
        shelter=italyshelter,
        monthly_solar_generation=italy_monthly_solar_generation,
        export_price=export_price,
        energy_price=energy_price,
        initial_cost=italy_initial_cost,
        report_title="Italy Shelter Solar Financial Estimate",
        analysis_years=solar_panel_lifetime,
    )

if __name__ == "__main__":
    main()
