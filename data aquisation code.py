import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
import warnings

warnings.filterwarnings('ignore')

# -------------------------------
# 🔧 DATA FETCHING & CLEANING ENGINE
# -------------------------------
def parse_table_to_df(table):
    """
    Parse an HTML table element to a pandas DataFrame using BeautifulSoup.
    More reliable than pd.read_html for this website.
    """
    rows = table.find_all('tr')
    if not rows:
        return None
    
    data = []
    for row in rows:
        cells = row.find_all(['th', 'td'])
        row_data = [cell.get_text(strip=True) for cell in cells]
        if row_data:  # Skip empty rows
            data.append(row_data)
    
    if not data:
        return None
    
    # Create DataFrame with first row as header
    df = pd.DataFrame(data[1:], columns=data[0])
    return df


def clean_and_transpose(df):
    """
    Clean and transpose financial data DataFrame.
    """
    if df is None or df.empty:
        return None
        
    df = df.dropna(how='all').dropna(axis=1, how='all')
    
    if df.empty or df.shape[1] < 2:
        return None

    # Set first column as index and transpose
    first_col = df.columns[0]
    df = df.set_index(first_col)
    df = df.T

    # Extract only the 4-digit year (Drops 'TTM' and overlapping months)
    df.index = df.index.astype(str).str.extract(r'(\d{4})')[0]
    df = df[df.index.notna()]

    # Clean numeric values
    df = df.replace({',': '', '%': ''}, regex=True)
    df = df.apply(pd.to_numeric, errors='coerce').fillna(0)

    return df


def fetch_clean_10yr_data(ticker):
    """
    Fetches, cleans, and structures 10-year financial data.
    Returns Pandas DataFrames ready for vector analysis.
    """
    base_url = f"https://www.screener.in/company/{ticker}/consolidated/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(base_url, headers=headers, timeout=30)

    # Fallback to standalone if consolidated is missing
    if response.status_code != 200 or 'Page not found' in response.text:
        base_url = f"https://www.screener.in/company/{ticker}/"
        response = requests.get(base_url, headers=headers, timeout=30)
        if response.status_code != 200:
            raise ValueError(f"CRITICAL: Could not fetch data for {ticker}")

    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html5lib')
    data_bundles = {}

    # Extract P&L data from profit-loss section
    pl_section = soup.find('section', id='profit-loss')
    if pl_section:
        table = pl_section.find('table')
        if table:
            df = parse_table_to_df(table)
            if df is not None and not df.empty:
                data_bundles["pnl"] = clean_and_transpose(df)

    # Extract Balance Sheet data
    bs_section = soup.find('section', id='balance-sheet')
    if bs_section:
        table = bs_section.find('table')
        if table:
            df = parse_table_to_df(table)
            if df is not None and not df.empty:
                data_bundles["balance_sheet"] = clean_and_transpose(df)

    # Extract Cash Flow data
    cf_section = soup.find('section', id='cash-flow')
    if cf_section:
        table = cf_section.find('table')
        if table:
            df = parse_table_to_df(table)
            if df is not None and not df.empty:
                data_bundles["cash_flow"] = clean_and_transpose(df)

    if not data_bundles:
        raise ValueError(f"No financial tables found for {ticker}")

    return data_bundles


# -------------------------------
# 🚀 PROCESSING WRAPPER
# -------------------------------
def process_company(company):
    try:
        financials = fetch_clean_10yr_data(company)

        pnl = financials.get("pnl")
        
        print(f"\n✅ {company} DATA FETCHED")
        print(f"Years: {len(pnl.index) if pnl is not None else 0}")
        print(f"Metrics: {len(pnl.columns) if pnl is not None else 0}")

        # Smart column handling for print preview (works for banks + IT)
        if pnl is not None:
            top_line = next((col for col in ['Sales', 'Revenue', 'Interest'] if col in pnl.columns), None)
            bottom_line = 'Net Profit' if 'Net Profit' in pnl.columns else pnl.columns[-1]

            if top_line and bottom_line in pnl.columns:
                print(pnl[[top_line, bottom_line]].tail(2))

        return financials

    except Exception as e:
        print(f"❌ ERROR for {company}: {e}")
        return None


# -------------------------------
# 🧠 MAIN EXECUTION & DEMO FLOW
# -------------------------------
all_data = {}

print("\n🚀 PRELOADING WARM CACHE...\n")

warm_cache = [
    "YESBANK", "PNB", "ICICIBANK",   # Banking
    "INFY", "TCS", "WIPRO"           # IT
]

# Step 1: Warm cache (safe demo)
for company in warm_cache:
    data = process_company(company)
    if data:
        all_data[company] = data

# Step 2: Live input (judge test)
user_input = input("\n🔍 Enter ANY company name/ticker for live analysis (or press Enter to skip): ").upper().strip()

if user_input:
    print(f"\n⚡ LIVE FETCH MODE: {user_input}")
    
    data = process_company(user_input)

    if data:
        all_data[user_input] = data
    else:
        # The Fixed Fallback Logic
        fallback = user_input.replace(" ", "")
        if fallback != user_input:
            print(f"⚠️ Initial fetch failed. Trying fallback ticker: {fallback}")
            fallback_data = process_company(fallback)
            if fallback_data:
                all_data[fallback] = fallback_data
        else:
            print(f"❌ Check the exact Screener ticker for {user_input}.")


# -------------------------------
# 💾 SAVE DATA TO LOCAL CACHE
# -------------------------------
print("\n💾 SAVING DATA TO CSV...\n")

for company, data in all_data.items():
    try:
        if data.get("pnl") is not None:
            data["pnl"].to_csv(f"{company}_pnl.csv")

        if data.get("balance_sheet") is not None:
            data["balance_sheet"].to_csv(f"{company}_bs.csv")

        if data.get("cash_flow") is not None:
            data["cash_flow"].to_csv(f"{company}_cf.csv")

        print(f"✅ Saved: {company}")

    except Exception as e:
        print(f"⚠️ Save failed for {company}: {e}")

print("\n🎯 SYSTEM READY: Fast financial data pipeline operational.")
