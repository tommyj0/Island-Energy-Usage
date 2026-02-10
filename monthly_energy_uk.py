import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict

def calculate_monthly_usage(postcode: str, actual_households: int, monthly_relative_usage: Dict[str, float], domestic_percentage: float = 0.406) -> Dict[str, float]:
  """
  Calculate monthly energy usage for a postcode based on actual households and monthly trends.
  
  Args:
    postcode: Postcode area to lookup (e.g., 'IV47', 'EH1')
    actual_households: Number of households to scale to
    monthly_relative_usage: Dictionary mapping month names to relative usage factors
                           (e.g., {'January': 1.2, 'February': 1.15, ...})
    domestic_percentage: Fraction of total energy consumption that is domestic (default: 0.406 for 40.6%)
  
  Returns:
    Dictionary with monthly consumption values in MWh
  """
  df = pd.read_csv("Postcode_level_all_meters_electricity_2024.csv")
  
  # Filter data for the postcode
  postcode_data = df[df['Postcode'].str.startswith(postcode, na=False)]
  
  if postcode_data.empty:
    raise ValueError(f"Postcode '{postcode}' not found in dataset")
  
  # Get total annual consumption from data
  total_consumption_data = postcode_data['Total_cons_kwh'].sum()
  total_households_data = postcode_data['Num_meters'].sum()
  
  if total_households_data == 0:
    raise ValueError(f"No household data found for postcode '{postcode}'")
  
  # Calculate consumption per household
  consumption_per_household = total_consumption_data / total_households_data
  
  # Calculate total usage for actual number of households
  total_annual_consumption = consumption_per_household * actual_households
  
  # The calculated result is domestic_percentage of total energy consumption
  # Scale up to get the full total (e.g., if domestic is 40.6%, scale up by 1/0.406)
  total_annual_consumption = total_annual_consumption / domestic_percentage
  
  # Normalize monthly relative usage so that it sums to 12 (average of 1.0 per month)
  sum_relative = sum(monthly_relative_usage.values())
  normalized_monthly = {month: factor / sum_relative * 12 for month, factor in monthly_relative_usage.items()}
  
  # Calculate monthly consumption in MWh (divide by 1000)
  monthly_consumption = {}
  for month, relative_factor in normalized_monthly.items():
    monthly_consumption[month] = (total_annual_consumption / 12) * relative_factor / 1000
  
  return monthly_consumption

def make_relative(monthly_consumption: Dict[str, float]) -> Dict[str, float]:
  """
  Convert monthly consumption values to relative proportions.
  
  Args:
    monthly_consumption: Dictionary mapping months to consumption values
  
  Returns:
    Dictionary with each month's proportion of total annual consumption (sums to 1.0)
  """
  total = sum(monthly_consumption.values())
  if total == 0:
    return monthly_consumption
  
  return {month: consumption / total for month, consumption in monthly_consumption.items()}

def plot_monthly_usage(monthly_consumption: Dict[str, float], title: str = "Monthly Energy Usage"):
  """
  Create a bar graph of monthly energy usage.
  
  Args:
    monthly_consumption: Dictionary mapping months to MWh values
    title: Title for the graph
  """
  months = list(monthly_consumption.keys())
  consumption = list(monthly_consumption.values())
  
  plt.figure(figsize=(12, 6))
  bars = plt.bar(months, consumption, color='steelblue')
  
  # Add value labels on top of each bar
  for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2., height,
            f'{height:.1f}',
            ha='center', va='bottom', fontsize=9)
  
  plt.xlabel('Month')
  plt.ylabel('Energy Consumption (MWh)')
  plt.title(title)
  plt.xticks(rotation=45, ha='right')
  plt.grid(axis='y', alpha=0.3)
  plt.tight_layout()
  
  return plt

if __name__ == "__main__":
  # Example usage
  postcode = "IV49"
  actual_households = 540
  
  # Monthly relative usage factors (e.g., winter months use more)
  national_monthly_usage = {
    'January': 1.88,
    'February': 1.77,
    'March': 1.63,
    'April': 1.54,
    'May': 1.55,
    'June': 1.54,
    'July': 1.54,
    'August': 1.51,
    'September': 1.58,
    'October': 1.72,
    'November': 1.8,
    'December': 1.85
  }
  national_monthly_relative_usage = make_relative(national_monthly_usage)
  print(national_monthly_relative_usage)
  
  # Calculate monthly usage
  monthly_usage = calculate_monthly_usage(postcode, actual_households, national_monthly_relative_usage)
  
  # Print results
  print(f"Monthly Energy Usage for Postcode {postcode} ({actual_households} households)\n")
  print(f"{'Month':<15} {'Consumption (MWh)':>20}")
  print("-" * 37)
  total = 0
  for month, consumption in monthly_usage.items():
    print(f"{month:<15} {consumption:>20,.2f}")
    total += consumption
  print("-" * 37)
  print(f"{'Total':<15} {total:>20,.2f}")
  
  # Create and save graph
  plt_obj = plot_monthly_usage(monthly_usage, f"Monthly Energy Usage - Postcode {postcode}")
  plt_obj.savefig("monthly_energy_usage.png", dpi=300, bbox_inches='tight')
  print(f"\nGraph saved to monthly_energy_usage.png")