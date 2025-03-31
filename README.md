# AllCamp Southeastern Expansion - Exploratory Data Analysis

## Project Goal

This repository contains the code for an interactive Exploratory Data Analysis (EDA) dashboard built with Streamlit. The goal is to analyze historical data (primarily from **2028**) to inform AllCamp's strategy for expanding its private campground network into the **Southeastern United States** in **2029**.

The dashboard provides visualizations and key metrics related to existing campground supply, booking transactions, user search demand, and identifies potential areas for expansion based on supply/demand mismatches.

## Features

* **Interactive Multi-Page Dashboard:** Uses Streamlit for an easy-to-navigate user interface.
* **Overview KPIs:** Presents high-level statistics on campgrounds, bookings, and revenue for the year 2028.
* **Geospatial Analysis:** Utilizes **H3 hexagons (Level 4)** and **Pydeck** maps to visualize:
    * Campground locations and site counts.
    * Transaction volume and revenue hotspots.
    * Monthly occupancy rates.
    * Search demand origins and destinations.
    * Expansion opportunity scores and mismatch ratios.
* **Data Exploration:** Allows filtering and aggregation of data across different dimensions (e.g., campsite category, time periods, search types).
* **Occupancy Analysis:** Calculates and visualizes monthly occupancy rates, filterable by campsite category (All, Tent/RV, RV-only, Structure) and optionally for weekends only.
* **Search Demand Insights:** Analyzes search volume by origin, destination, marketing channel, and specific search types (e.g., RV, tent, glamping).
* **Expansion Opportunity Identification:**
    * Calculates a **Priority Score** (`Occupancy Rate * Total Searchers`) to highlight areas with high usage and high interest.
    * Computes **Mismatch Ratios** for RV, Tent, and Structure sites to identify areas where demand significantly exceeds supply.
    * Estimates potential **Lost Revenue** due to unmet demand based on actual conversion rates and average nightly rates in the Southeast.

## Data Sources

The analysis relies on three main CSV files:

1.  `campgrounds.csv`: Contains information about individual campgrounds
2.  `transactions.csv`: Includes details about individual bookings
3.  `searches.csv`: Provides aggregated search data

* **Note:** The script assumes these CSV files are located in the same directory where the script is run.

## Key Analyses & Metrics

The dashboard focuses on several key areas:

* **Campground Supply:** Visualizing the current distribution and density of live campgrounds and different site types (Tent, RV, Structure) across the Southeast. Includes Year-over-Year growth comparisons (2027 vs. 2028).
* **Booking Performance:** Analyzing 2028 booking volume and Gross Booking Value (GBV), prorated for trips spanning year boundaries. Explores performance by state and campsite category.
* **Occupancy Rates:** Assessing how utilized the existing capacity is, crucial for understanding market saturation. Calculated monthly and filterable.
* **Search Demand:** Understanding user interest patterns – where are users searching *from* and *to*? What types of camping experiences are they looking for?
* **Expansion Metrics:**
    * **Priority Score:** Identifies hexes that are both popular (high search) and already well-utilized (high occupancy).
    * **Mismatch Ratio:** Pinpoints hexes where specific site type demand (RV, Tent, Structure) significantly outstrips available supply, indicating direct expansion needs. Calculated as `(Adjusted Demand - Capacity) / Capacity` (or a high value if Capacity is 0 but Demand > 0).
    * **Lost Revenue:** Estimates the financial opportunity missed by not having enough supply in high-demand areas.

## Technology Stack

* Python 3.x
* Streamlit (for the web application interface)
* Pandas (for data manipulation and analysis)
* NumPy (for numerical operations)
* Pydeck (for H3 hexagon-based map visualizations)
* Altair (for statistical charts)
* Calendar (Python standard library for date calculations)

## Setup & Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/reidrhod/Allcamp.git](https://www.google.com/search?q=https://github.com/reidrhod/Allcamp.git)
    ```
2.  **Navigate to the project directory:**
    ```bash
    cd Allcamp
    ```
3.  **(Recommended)** Create and activate a Python virtual environment:
    ```bash
    # For Linux/macOS
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```
4.  **Install required packages:**
    ```bash
    pip install streamlit pandas numpy pydeck altair
    ```
5.  **Ensure Data Files:** Place `campgrounds.csv`, `transactions.csv`, and `searches.csv` in the root directory of the cloned repository (`Allcamp/`).

## How to Run

1.  Make sure your terminal is in the project directory (`Allcamp/`) and the virtual environment (if used) is activated.
2.  Run the Streamlit application:
    ```bash
    streamlit run your_script_name.py
    ```
    (Replace `your_script_name.py` with the actual name of the Python script file).
3.  The application should open automatically in your default web browser. If not, the terminal will provide a local URL (usually `http://localhost:8501`).

## Application Structure (Pages)

The dashboard is organized into the following pages accessible via the sidebar:

1.  **Home / Overview:** Displays high-level KPIs for 2028, project context, key objectives, and top states by booking value.
2.  **Campgrounds:** Focuses on the supply side – mapping live campgrounds, total sites, and site types. Includes YoY growth metrics.
3.  **Transactions:** Analyzes booking data – total bookings, gross booking value, average values, and performance breakdown by campsite category. Includes maps filtered by category.
4.  **Monthly Occupancy (By Category, 2028):** Provides interactive maps showing calculated occupancy rates for selected months and campsite categories, with an option to view weekend-only occupancy. Includes KPIs and top hexes by occupancy.
5.  **Search Demand:** Visualizes user search volume by origin and destination H3 hexes. Includes breakdowns by marketing channel and search type (RV, tent, family-friendly, etc.).
6.  **Expansion Opportunities:** The core strategic page. Integrates supply (capacity), demand (searches), and usage (occupancy) to calculate and map Priority Scores and Mismatch Ratios. Includes an estimation of Lost Revenue based on unmet demand.

