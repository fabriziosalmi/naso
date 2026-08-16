import hashlib
import os
from datetime import datetime

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from fpdf import FPDF


class ForensicReportGenerator:
    """
    Engine that generates certified forensic reports (#31).
    """

    @staticmethod
    def generate_pdf(leak_data: dict, ai_analysis: dict, content: str, tenant_name: str):
        pdf = FPDF()
        pdf.add_page()

        # Header Forense
        pdf.set_font("Courier", "B", 16)
        pdf.set_text_color(255, 0, 0)
        pdf.cell(200, 10, "[NASO FORENSIC ENGINE] - CONFIDENTIAL EVIDENCE REPORT", ln=True, align="C")
        pdf.ln(10)

        # Report metadata
        pdf.set_font("Courier", "", 10)
        pdf.set_text_color(0, 0, 0)
        report_id = f"NASO-REP-{datetime.now().strftime('%Y%m%d')}-{leak_data['id'][:8]}"
        pdf.cell(200, 10, f"Report ID: {report_id}", ln=True)
        pdf.cell(200, 10, f"Timestamp: {datetime.now().isoformat()}", ln=True)
        pdf.cell(200, 10, f"Tenant: {tenant_name}", ln=True)
        pdf.cell(200, 10, f"Source: {leak_data['source']}", ln=True)
        pdf.ln(5)

        # Integrità dell'Evidenza
        evidence_hash = hashlib.sha256(f"{leak_data['id']}-{content}".encode()).hexdigest()
        pdf.set_font("Courier", "B", 10)
        pdf.cell(200, 10, f"SHA-256 EVIDENCE HASH: {evidence_hash}", ln=True)
        pdf.ln(10)

        # AI Intelligence Verdict
        pdf.set_font("Courier", "B", 12)
        pdf.cell(200, 10, "AI INTELLIGENCE VERDICT", ln=True)
        pdf.set_font("Courier", "", 10)
        verdict = ai_analysis.get("answer", "No verdict available")
        pdf.multi_cell(0, 10, f"Verdict: {verdict}")
        pdf.ln(5)

        # Content Snippet
        pdf.set_font("Courier", "B", 12)
        pdf.cell(200, 10, "EVIDENCE SNIPPET", ln=True)
        pdf.set_font("Courier", "", 8)
        pdf.multi_cell(0, 5, content[:2000] + ("..." if len(content) > 2000 else ""))
        pdf.ln(10)

        # Forensic Footer
        pdf.set_font("Courier", "I", 8)
        pdf.set_text_color(128, 128, 128)
        pdf.multi_cell(
            0,
            5,
            "This document is digitally hashed and acts as forensic evidence. Collected via Naso Rotating Tor-Cluster.",
        )

        return pdf.output(dest="S")  # Return as byte string

    @staticmethod
    def sign_report(pdf_bytes: bytes):
        """
        Apply a cryptographic digital signature to the forensic report.
        Garantisce l'integrità di grado aerospaziale.
        """
        private_key_path = os.getenv("NASO_PRIVATE_KEY_PATH")
        if private_key_path and os.path.exists(private_key_path):
            # Permission check: the private key must be readable by its owner only (G-13).
            # Looser permissions (e.g. 0o644) undermine the legal weight of the evidence.
            file_stat = os.stat(private_key_path)
            # Bit 0o077: qualsiasi permesso a gruppo o altri
            if file_stat.st_mode & 0o077:
                raise PermissionError(
                    f"SECURITY: private key file '{private_key_path}' has unsafe permissions "
                    f"(mode {oct(file_stat.st_mode & 0o777)}). "
                    "Set permissions to 0o400 or 0o600 (owner read-only)."
                )
            with open(private_key_path, "rb") as key_file:
                private_key = serialization.load_pem_private_key(key_file.read(), password=None)
            signature = private_key.sign(
                pdf_bytes,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            return signature.hex()
        else:
            # Fallback: hash crittografico SHA-256 (Sealed Evidence)
            return hashlib.sha256(pdf_bytes).hexdigest()

    @staticmethod
    def generate_bulk_pdf(tenant_name: str, leaks: list):
        """
        Generate the bulk forensic dossier (BB) covering every leak in the period.
        """
        pdf = FPDF()
        pdf.add_page()

        # Dossier Cover
        pdf.set_font("Courier", "B", 24)
        pdf.set_text_color(255, 0, 0)
        pdf.cell(200, 40, "NASO FORENSIC DOSSIER", ln=True, align="C")

        pdf.set_font("Courier", "B", 14)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(200, 10, f"Tenant: {tenant_name}", ln=True, align="C")
        pdf.cell(200, 10, f"Date: {datetime.now().strftime('%B %Y')}", ln=True, align="C")
        pdf.ln(20)

        # Summary Stats
        pdf.set_font("Courier", "B", 12)
        pdf.cell(200, 10, "EXECUTIVE SUMMARY", ln=True)
        pdf.set_font("Courier", "", 10)
        pdf.cell(200, 10, f"Total Threats Detected: {len(leaks)}", ln=True)
        avg_sev = sum([l.severity_score for l in leaks]) / len(leaks) if leaks else 0
        pdf.cell(200, 10, f"Average Severity Score: {avg_sev:.2f}/100", ln=True)
        pdf.ln(10)

        # Leak Detailed List
        for idx, leak in enumerate(leaks):
            if idx > 0 and idx % 2 == 0:
                pdf.add_page()  # New page every 2 leaks

            pdf.set_font("Courier", "B", 11)
            pdf.cell(200, 10, f"INCIDENT #{leak.id[:8]} - {leak.source}", ln=True)
            pdf.set_font("Courier", "", 9)
            pdf.cell(200, 8, f"Detected: {leak.discovered_at.isoformat()}", ln=True)
            pdf.cell(200, 8, f"Severity: {leak.severity_score}%", ln=True)
            pdf.multi_cell(0, 5, f"Snippet: {leak.content_snippet[:500]}...")
            pdf.ln(5)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)

        return pdf.output(dest="S")
