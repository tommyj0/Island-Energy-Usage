import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path


def visualise_simulation_results():
    """Load consolidated simulation results and create separate plot files per location."""
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

        # Use numeric positions for x-axis (for proper bar centring)
        x_pos = np.arange(len(location_data), dtype=float)
        module_counts = location_data["module_count"].values
        upfront_label_offset = max(float(location_data["upfront_cost"].max()) * 0.05, 40.0)
        npv_label_offset = max(float(location_data["npv"].max()) * 0.05, 40.0)
        self_consumption_label_offset = 0.8
        baseline_payback = float(location_data["payback_years"].iloc[0])
        payback_change = location_data["payback_years"] - baseline_payback
        safe_location = location.replace(" ", "_")

        # Plot 1: Upfront Cost vs Module Count
        fig, ax = plt.subplots(figsize=(8.2, 6.2))
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
        ax.set_xlabel("Module Count", fontsize=15)
        ax.set_ylabel("Upfront Cost (£)", fontsize=15)
        ax.set_title("Upfront Cost", fontsize=18)
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
        fig.tight_layout()
        upfront_file = output_dir / f"simulation_results_{safe_location}_upfront_cost.svg"
        plt.savefig(upfront_file, format="svg", dpi=150)
        print(f"Saved visualisation: {upfront_file}")
        plt.close(fig)

        # Plot 2: NPV vs Module Count
        fig, ax = plt.subplots(figsize=(8.2, 6.2))
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
        ax.set_xlabel("Module Count", fontsize=15)
        ax.set_ylabel("NPV (£)", fontsize=15)
        ax.set_title("NPV (25y)", fontsize=18)
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
        fig.tight_layout()
        npv_file = output_dir / f"simulation_results_{safe_location}_npv.svg"
        plt.savefig(npv_file, format="svg", dpi=150)
        print(f"Saved visualisation: {npv_file}")
        plt.close(fig)

        # Plot 3: Self-consumption vs Module Count
        fig, ax = plt.subplots(figsize=(8.2, 6.2))
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
        ax.set_xlabel("Module Count", fontsize=15)
        ax.set_ylabel("Self-consumption (%)", fontsize=15)
        ax.set_title("Self-Consumption", fontsize=18)
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
        fig.tight_layout()
        self_consumption_file = output_dir / f"simulation_results_{safe_location}_self_consumption.svg"
        plt.savefig(self_consumption_file, format="svg", dpi=150)
        print(f"Saved visualisation: {self_consumption_file}")
        plt.close(fig)

        # Plot 4: Change in Payback Time vs Module Count
        fig, ax = plt.subplots(figsize=(8.2, 6.2))
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
        ax.set_xlabel("Module Count", fontsize=15)
        ax.set_ylabel("Payback Change (years)", fontsize=15)
        ax.set_title("Payback Change", fontsize=18)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(module_counts)
        ax.grid(axis="y", alpha=0.3)
        ax.legend()
        for i, pos in enumerate(x_pos):
            delta = float(payback_change.iloc[i])
            sign = "+" if delta > 0 else ""
            ax.annotate(
                f"{sign}{delta:.2f}y",
                xy=(pos, delta),
                xytext=(0, 8 if delta >= 0 else -10),
                textcoords="offset points",
                ha="center",
                va="bottom" if delta >= 0 else "top",
                fontsize=8,
                bbox={"boxstyle": "round,pad=0.15", "facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
            )
        fig.tight_layout()
        payback_change_file = output_dir / f"simulation_results_{safe_location}_payback_change.svg"
        plt.savefig(payback_change_file, format="svg", dpi=150)
        print(f"Saved visualisation: {payback_change_file}")
        plt.close(fig)

        # Plot 5: Discounted vs Non-discounted Payback Time
        fig, ax = plt.subplots(figsize=(8.2, 6.2))
        simple_payback = pd.to_numeric(location_data["payback_years"], errors="coerce")
        discounted_payback = pd.to_numeric(location_data["dpp_years"], errors="coerce")
        ax.plot(
            x_pos,
            simple_payback,
            marker="o",
            linewidth=2.3,
            markersize=8,
            color="#E69F00",
            label="Simple payback (non-discounted)",
        )
        ax.plot(
            x_pos,
            discounted_payback,
            marker="s",
            linewidth=2.3,
            markersize=8,
            color="#0072B2",
            label="Discounted payback",
        )
        ax.set_xlabel("Module Count", fontsize=15)
        ax.set_ylabel("Payback Time (years)", fontsize=15)
        ax.set_title("Payback: Discounted vs Simple", fontsize=18)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(module_counts)
        ax.grid(axis="y", alpha=0.3)
        ax.legend()

        for i, pos in enumerate(x_pos):
            if pd.notna(simple_payback.iloc[i]):
                ax.annotate(
                    f"{float(simple_payback.iloc[i]):.2f}y",
                    xy=(pos, float(simple_payback.iloc[i])),
                    xytext=(0, 8),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color="#E69F00",
                    bbox={"boxstyle": "round,pad=0.15", "facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
                )
            if pd.notna(discounted_payback.iloc[i]):
                ax.annotate(
                    f"{float(discounted_payback.iloc[i]):.2f}y",
                    xy=(pos, float(discounted_payback.iloc[i])),
                    xytext=(0, -10),
                    textcoords="offset points",
                    ha="center",
                    va="top",
                    fontsize=8,
                    color="#0072B2",
                    bbox={"boxstyle": "round,pad=0.15", "facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
                )

        fig.tight_layout()
        payback_compare_file = output_dir / f"simulation_results_{safe_location}_payback_comparison.svg"
        plt.savefig(payback_compare_file, format="svg", dpi=150)
        print(f"Saved visualisation: {payback_compare_file}")
        plt.close(fig)


if __name__ == "__main__":
    visualise_simulation_results()
