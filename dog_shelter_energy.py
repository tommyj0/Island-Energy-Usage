import matplotlib.pyplot as plt
class DogShelter:
  def __init__(self, name, area, heat_loss_coef, climate):
    self.name = name
    self.area = area
    self.heat_loss_ceof = heat_loss_coef  # Unit: W/(m²·K)
    self.climate = climate
    self.lighting_energy_per_area_watts = 2  # Placeholder value for lighting energy per m² in watts
    self.monthly_heating = []
    self.monthly_lighting = []
    self.monthly_energy = []
    self.energy_consumption = self.calculate_total_energy()
    
  def print(self):
    print(f"Shelter Name: {self.name}")
    print(f"Area (m²): {self.area}")
    print(f"Heat Loss Coefficient (W/(m²·K)): {self.heat_loss_ceof}")
    print(f"Climate: {self.climate}")
    print(f"Estimated Annual Total Energy Consumption (kWh): {self.energy_consumption:.2f}")

  def calculate_heating(self, temp_diff):
    """Calculate heating energy for a given temperature difference."""
    # Convert from W to kWh: multiply by hours in month (730 average) and divide by 1000
    heating_energy = temp_diff * self.area * self.heat_loss_ceof * 730 / 1000
    return heating_energy
  
  def calculate_lighting(self):
    """Calculate lighting energy for the shelter."""
    # Placeholder for lighting calculation
    lighting_energy = self.area * self.lighting_energy_per_area_watts * 730 / 1000  # Convert to kWh
    return lighting_energy
  
  def calculate_total_energy(self, ideal_temperature=20):
    """Calculate total energy consumption by iterating through months and calling helper functions."""
    total_energy = 0
    self.monthly_energy = []
    self.monthly_heating = []
    self.monthly_lighting = []
    
    for month, temp in self.climate.items():
      # Calculate temperature difference (only for heating needs)
      temp_diff = max(0, ideal_temperature - temp)
      
      # Call helper functions for each energy type
      heating_energy = self.calculate_heating(temp_diff)
      lighting_energy = self.calculate_lighting()
      
      # Store heating and lighting separately
      self.monthly_heating.append(heating_energy)
      self.monthly_lighting.append(lighting_energy)
      
      # Total energy for this month
      monthly_total = heating_energy + lighting_energy
      self.monthly_energy.append(monthly_total)
      total_energy += monthly_total
    
    return total_energy

  def plot_monthly_energy(self):
    months = list(self.climate.keys())
    
    plt.figure(figsize=(12, 6))
    x_pos = range(len(months))
    
    # Create stacked bar chart
    bars1 = plt.bar(x_pos, self.monthly_heating, label='Heating', color='#FF6B6B')
    bars2 = plt.bar(x_pos, self.monthly_lighting, bottom=self.monthly_heating, label='Lighting', color='#FFA500')
    
    # Add value labels on top of each bar
    for i, month in enumerate(months):
      total = self.monthly_heating[i] + self.monthly_lighting[i]
      plt.text(i, total, f'{total:.1f}', ha='center', va='bottom', fontsize=9)
    
    plt.xlabel('Month')
    plt.ylabel('Energy Consumption (kWh)')
    plt.title(f'Monthly Energy Consumption Split for {self.name}')
    plt.xticks(x_pos, months, rotation=45, ha='right')
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{self.name}_monthly_energy.png")
    plt.show()
    
  
  
if __name__ == "__main__":
  standard_hl_coef = 4

  crosshands_monthly_temps = {
    "January": 5,
    "February": 4,
    "March": 6,     
    "April": 8,
    "May": 11,
    "June": 13,
    "July": 15,
    "August": 15,
    "September": 13,
    "October": 10,
    "November": 7,
    "December": 5
  }

  cornaredo_monthly_temps = {
    "January": 2,
    "February": 4,
    "March": 9,     
    "April": 13,
    "May": 17,
    "June": 21,
    "July": 24,
    "August": 23,
    "September": 19,
    "October": 13,
    "November": 7,
    "December": 3
  }

  ukshelter = DogShelter("Many Tears Rescue Wales", 150, standard_hl_coef, crosshands_monthly_temps)
  italyshelter = DogShelter("APS", 300, standard_hl_coef, cornaredo_monthly_temps)
  ukshelter.print()
  italyshelter.print()
  ukshelter.plot_monthly_energy()
  italyshelter.plot_monthly_energy()