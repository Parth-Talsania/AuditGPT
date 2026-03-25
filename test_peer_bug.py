from auditgpt.api.engine import AuditGPT
from auditgpt.benchmarking.peer_stats import PeerStats
import json

# Test the peer stats directly
engine = AuditGPT(verbose=True)

# Get company data
company_data = engine._fetch_company_data('YESBANK')

print("=== YESBANK Company Data ===")
print("Keys:", list(company_data.keys()))
print("\nHas pnl?", 'pnl' in company_data)
print("Has balance_sheet?", 'balance_sheet' in company_data)
print("Has cash_flow?", 'cash_flow' in company_data)

if 'pnl' in company_data:
    print("\nP&L type:", type(company_data['pnl']))
    if hasattr(company_data['pnl'], 'columns'):
        print("P&L columns:", company_data['pnl'].columns.tolist())
    elif isinstance(company_data['pnl'], dict):
        print("P&L keys:", list(company_data['pnl'].keys()))

ratios = engine._calculate_ratios(company_data, 'BANK')

print("\n=== YESBANK Ratios ===")
print("Keys:", list(ratios.keys()))
print("\nrevenue_growth:", ratios.get('revenue_growth'))
print("np_growth:", ratios.get('np_growth'))
print("debt_equity:", ratios.get('debt_equity'))
print("debtor_days:", ratios.get('debtor_days'))
print("opm:", ratios.get('opm'))
print("roce:", ratios.get('roce'))
