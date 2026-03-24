import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML


def generate_financial_report(
    client_data: dict,
    risk_data: dict,
    retirement_data: dict,
    education_data: dict,
    allocation_data: dict,
    portfolio_data: dict,
    recommended_funds: list,
    monte_carlo_prob: float,
    sip_projections: dict = None,
    expected_returns: dict = None,
    ai_intel: dict = None,
    macro_context: dict = None,
    output_path: str = "report.pdf",
):
    """
    Generates a PDF report using Jinja2 and WeasyPrint.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(current_dir))
    template = env.get_template("template.html")

    # Load disclaimer
    disclaimer_path = os.path.join(current_dir, "..", "..", "DISCLAIMER.txt")
    try:
        with open(disclaimer_path, "r") as f:
            disclaimer_text = f.read()
    except FileNotFoundError:
        disclaimer_text = "Market performance is not guaranteed."

    html_out = template.render(
        client=client_data,
        risk=risk_data,
        retirement=retirement_data,
        education=education_data,
        allocation=allocation_data,
        portfolio=portfolio_data,
        funds=recommended_funds,
        monte_carlo_prob=monte_carlo_prob,
        sip_projections=sip_projections or {},
        expected_returns=expected_returns or {},
        ai_intel=ai_intel or {},
        macro_context=macro_context or {},
        disclaimer=disclaimer_text,
    )

    HTML(string=html_out).write_pdf(output_path)
    return output_path
