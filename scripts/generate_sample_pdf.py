"""One-off script: generates synthetic 10-K sample PDF for local testing. Not part of app runtime."""
from fpdf import FPDF

SECTIONS = [
    ("Item 1. Business", """
Acme Financial Holdings, Inc. (the "Company") is a diversified bank holding company headquartered in Springfield, Delaware. The Company, through its wholly owned subsidiary Acme National Bank, provides commercial banking, consumer banking, wealth management, and treasury services to customers across the United States. As of the fiscal year ended December 31, 2025, the Company operated 412 branch locations across 18 states and employed approximately 9,800 full-time equivalent employees.

The Company's primary business segments are Retail Banking, Commercial Banking, and Wealth Management. Retail Banking offers deposit accounts, residential mortgages, auto loans, and credit cards to individual customers. Commercial Banking provides lending, treasury management, and merchant services to small and mid-sized businesses. Wealth Management offers investment advisory, trust, and brokerage services to high-net-worth individuals and institutions.

Competition in the banking industry remains intense. The Company competes with national banks, regional banks, credit unions, and a growing number of financial technology companies offering digital-first banking products.
"""),
    ("Item 1A. Risk Factors", """
An investment in the Company's common stock involves risks. The following are among the most significant risk factors that could affect our business, financial condition, and results of operations.

Credit Risk. The Company's loan portfolio is subject to the risk of borrower default. A deterioration in economic conditions, particularly in the commercial real estate sector, could result in increased loan losses and require the Company to increase its allowance for credit losses.

Interest Rate Risk. Changes in market interest rates set by the Federal Reserve affect the Company's net interest margin, the value of its securities portfolio, and demand for loans and deposits. A rapid rise in rates could reduce the value of the Company's fixed-rate securities holdings.

Cybersecurity Risk. The Company relies on information technology systems to conduct its business. A successful cyberattack, data breach, or systems failure could disrupt operations, result in the unauthorized disclosure of customer data, and expose the Company to regulatory penalties and reputational harm.

Regulatory Risk. The Company operates in a highly regulated industry. Changes in banking regulations, including capital requirements imposed by the Basel III framework, could increase compliance costs or restrict the Company's ability to grow its balance sheet.

Liquidity Risk. The Company depends on customer deposits and wholesale funding markets to meet its liquidity needs. A sudden and significant withdrawal of deposits, similar to events experienced by other regional banks in 2023, could materially impair the Company's liquidity position.
"""),
    ("Item 7. Management's Discussion and Analysis", """
Net income for fiscal year 2025 was $342.6 million, compared to $318.1 million in fiscal year 2024, an increase of 7.7%. The increase was primarily driven by growth in net interest income and disciplined expense management.

Net interest income increased to $1.21 billion for fiscal year 2025, compared to $1.14 billion for fiscal year 2024. The increase was driven by a 40 basis point improvement in net interest margin, reflecting the repricing of the securities portfolio and disciplined deposit pricing.

Total deposits at December 31, 2025 were $28.4 billion, compared to $27.1 billion at December 31, 2024. Noninterest-bearing deposits represented 24% of total deposits, consistent with the prior year.

The provision for credit losses was $48.2 million for fiscal year 2025, compared to $52.7 million for fiscal year 2024, reflecting stable asset quality trends across the commercial and consumer loan portfolios.

The Company's common equity tier 1 capital ratio was 11.4% at December 31, 2025, well above the regulatory minimum, reflecting the Company's continued focus on maintaining a strong capital position.
"""),
    ("Item 8. Financial Statements", """
Consolidated Balance Sheet Highlights (in millions):
Total assets: $34,820
Total loans, net of allowance: $22,150
Total deposits: $28,400
Total shareholders' equity: $3,610

Consolidated Statement of Income Highlights (in millions):
Total interest income: $1,680
Total interest expense: $470
Net interest income: $1,210
Noninterest income: $410
Noninterest expense: $980
Net income: $342.6

The accompanying notes are an integral part of these consolidated financial statements. The Company's independent registered public accounting firm has issued an unqualified opinion on these financial statements.
"""),
]

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.set_font("Helvetica", size=11)

pdf.add_page()
pdf.set_font("Helvetica", "B", 16)
pdf.multi_cell(0, 10, "ACME FINANCIAL HOLDINGS, INC.\nForm 10-K - Annual Report\nFiscal Year Ended December 31, 2025")
pdf.set_font("Helvetica", size=11)

for title, body in SECTIONS:
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(0, 8, title)
    pdf.ln(2)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, body.strip())

pdf.output("data/filings/sample-10k.pdf")
print("Generated data/filings/sample-10k.pdf")
