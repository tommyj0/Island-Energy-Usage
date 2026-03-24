import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path


def visualise_simulation_results():
    """Load consolidated simulation results and create one figure per location."""
    base_dir = Path(__file__).resolve().parent
    output_dir = base_dir / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "module_simulation_results.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"Results CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    locations = df["location"].unique()

    for location in sorted(locations):
        location_data = df[df["location"] == location].sort_values("module_count")

        fig, axes = plt.subplots(2, 2, figsize=(15.5, 10.5))
        axes = axes.flatten()
        fig.suptitle(f"{location} Solar Simulation Results", fontsize=16, fontweight="bold")

        # Use numeric positions for x-axis (for proper bar centring)
        x_pos = np.arange(len(location_data), dtype=float)
        module_counts = location_data["module_count"].values
        upfront_label_offset = max(float(location_data["upfront_cost"].max()) * 0.05, 40.0)
        npv_label_offset = max(float(location_data["npv"].max()) * 0.05, 40.0)
        self_consumption_label_offset = 0.8
        baseline_payback = float(location_data["payback_years"].iloc[0])
        payback_change = location_data["payback_years"] - baseline_payback

        # Plot 1: Upfront Cost vs Module Count
        ax = axes[0]
        ax.plot(
            x_pos,
            location_data["upfront_cost"],
            marker="o",
            linewidth=2.5,
            markersize=8,
            color="#D55E00",
            label="Upfront Cost",
        )
        ax.fill_between(x_pos, location_data["upfront_cost"], alpha=0.2, color="#D55E00")
        ax.set_xlabel("Module Count")
        ax.set_ylabel("Upfront Cost (£)")
        ax.set_title("Upfront Installation Cost")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(module_counts)
        ax.grid(axis="y", alpha=0.3)
        for i, pos in enumerate(x_pos):
            ax.text(
                pos,
                location_data["upfront_cost"].iloc[i] + upfront_label_offset,
                f"£{location_data['upfront_cost'].iloc[i]:.0f}",
                ha="center",
                fontsize=9,
            )

        # Plot 2: NPV vs Module Count
        ax = axes[1]
        ax.plot(
            x_pos,
            location_data["npv"],
            marker="s",
            linewidth=2.5,
            markersize=8,
            color="#56B4E9",
        )
        ax.fill_between(x_pos, location_data["npv"], alpha=0.2, color="#56B4E9")
        ax.axhline(0, color="red", linestyle="--", linewidth=1, alpha=0.5, label="Break-even")
        ax.set_xlabel("Module Count")
        ax.set_ylabel("NPV (£)")
        ax.set_title("Net Present Value (25 years)")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(module_counts)
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        for i, pos in enumerate(x_pos):
            ax.text(
                pos,
                location_data["npv"].iloc[i] + npv_label_offset,
                f"£{location_data['npv'].iloc[i]:.0f}",
                ha="center",
                fontsize=9,
            )

        # Plot 3: Self-consumption vs Module Count
        ax = axes[2]
        profile_rate_pct = location_data["pv_profile_self_consumption_rate"] * 100
        realised_rate_pct = location_data["self_consumption_rate"] * 100
        ax.plot(
            x_pos,
            profile_rate_pct,
            marker="^",
            linewidth=2.3,
            markersize=8,
            color="#009E73",
            label="PV profile self-consumption",
        )
        ax.plot(
            x_pos,
            realised_rate_pct,
            marker="D",
            linewidth=2.3,
            markersize=7,
            color="#CC79A7",
            label="Realised in financials",
        )
        ax.set_xlabel("Module Count")
        ax.set_ylabel("Self-consumption (%)")
        ax.set_title("Self-consumption Rate")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(module_counts)
        ymin = max(0, float(min(profile_rate_pct.min(), realised_rate_pct.min()) - 3))
        ymax = min(100, float(max(profile_rate_pct.max(), realised_rate_pct.max()) + 3))
        ax.set_ylim(ymin, ymax)
        ax.grid(axis="y", alpha=0.3)
        ax.legend()
        for i, pos in enumerate(x_pos):
            ax.text(
                pos,
                profile_rate_pct.iloc[i] + self_consumption_label_offset,
                f"{profile_rate_pct.iloc[i]:.1f}%",
                ha="center",
                fontsize=8,
                color="#009E73",
            )
            ax.text(
                pos,
                realised_rate_pct.iloc[i] - self_consumption_label_offset,
                f"{realised_rate_pct.iloc[i]:.1f}%",
                ha="center",
                va="top",
                fontsize=8,
                color="#CC79A7",
            )

        # Plot 4: Change in Payback Time vs Module Count
        ax = axes[3]
        ax.plot(
            x_pos,
            payback_change,
            marker="o",
            linewidth=2.3,
            markersize=8,
            color="#0072B2",
            label="Change vs lowest module count",
        )
        ax.axhline(0, color="#444444", linewidth=1, linestyle="--", alpha=0.7)
        ax.set_xlabel("Module Count")
        ax.set_ylabel("Payback Change (years)")
        ax.set_title("Change in Simple Payback Time")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(module_counts)
        ax.grid(axis="y", alpha=0.3)
        ax.legend()
        for i, pos in enumerate(x_pos):
            delta = float(payback_change.iloc[i])
            sign = "+" if delta > 0 else ""
            ax.text(
                pos,
                delta + (0.03 if delta >= 0 else -0.03),
                f"{sign}{delta:.2f}y",
                ha="center",
                va="bottom" if delta >= 0 else "top",
                fontsize=8,
            )

        fig.subplots_adjust(left=0.07, right=0.98, top=0.90, bottom=0.10, wspace=0.28, hspace=0.30)

        safe_location = location.replace(" ", "_")
        output_file = output_dir / f"simulation_results_{safe_location}.svg"
        plt.savefig(output_file, format="svg", dpi=150)
        print(f"Saved visualisation: {output_file}")
        plt.close(fig)


if __name__ == "__main__":
    visualise_simulation_results()
