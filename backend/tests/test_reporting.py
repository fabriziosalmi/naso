"""The forensic PDF must survive the evidence it reports.

fpdf2's core Courier font is Latin-1 only and raises
FPDFUnicodeEncodingException on the first character outside it. Model prose
(em dashes, curly quotes) and dark-web leak content are routinely UTF-8, so
the export used to 500 on exactly the artifacts worth exporting. The
generator now coerces every interpolated string through Latin-1 with visible
'?' replacement.
"""

from shared.utils.reporting import ForensicReportGenerator


def test_single_leak_pdf_survives_non_latin1_text():
    out = ForensicReportGenerator.generate_pdf(
        {"id": "0" * 36, "source": "tor—hidden’service"},
        {"thought": "…", "answer": "Verdetto — “sì”, severità 95 €, 好", "is_valid": True},
        "leaked content — 好, ’curly’, €100",
        "Tenant—X",
    )
    assert len(out) > 0


def test_single_leak_pdf_survives_string_ai_analysis():
    # The demo seeder writes ai_analysis as a plain string, not a dict.
    out = ForensicReportGenerator.generate_pdf(
        {"id": "1" * 36, "source": "pastebin"},
        "seeder-style plain verdict",
        "plain ascii content",
        "Tenant",
    )
    assert len(out) > 0
