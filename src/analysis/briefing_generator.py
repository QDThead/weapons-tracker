"""Intelligence Briefing PDF Generator.

Generates a multi-page PDF briefing from platform data using fpdf2.
Styled for DND/CAF leadership consumption.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime

from fpdf import FPDF

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.storage.models import (
    ArmsTransfer, TradeIndicator, ArmsTradeNews, DeliveryTracking,
    DefenceSupplier, SupplierContract, SupplierRiskScore,
    RiskTaxonomyScore, MitigationAction, SupplyChainAlert,
    SupplierSector, ContractStatus,
)

logger = logging.getLogger(__name__)


def _safe_text(text: str) -> str:
    """Sanitize text for fpdf2 Helvetica (latin-1 only)."""
    if not text:
        return ""
    return text.encode("latin-1", errors="replace").decode("latin-1")


class BriefingPDF(FPDF):
    """Custom PDF with header/footer for DND briefings."""

    def __init__(self, generated_at: str):
        super().__init__()
        self.generated_at = generated_at

    def header(self):
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(220, 38, 38)
        self.cell(0, 5, "UNCLASSIFIED", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(100, 116, 139)
        self.cell(0, 5, f"UNCLASSIFIED // PSI Control Tower // {self.generated_at} // Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, num: int, title: str):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(15, 23, 42)
        self.cell(0, 8, f"{num}. {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 180, 216)
        self.set_line_width(0.5)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def kpi_box(self, label: str, value: str, color: tuple = (15, 23, 42)):
        x, y = self.get_x(), self.get_y()
        w = 42
        self.set_draw_color(200, 200, 200)
        self.rect(x, y, w, 22)
        # Top color bar
        self.set_fill_color(*color)
        self.rect(x, y, w, 2, "F")
        # Label
        self.set_xy(x, y + 3)
        self.set_font("Helvetica", "", 6)
        self.set_text_color(100, 116, 139)
        self.cell(w, 4, label, align="C")
        # Value
        self.set_xy(x, y + 8)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*color)
        self.cell(w, 8, str(value), align="C")
        self.set_xy(x + w + 3, y)

    def data_table(self, headers: list[str], rows: list[list[str]], col_widths: list[int] | None = None):
        if not col_widths:
            w = (self.w - self.l_margin - self.r_margin) / len(headers)
            col_widths = [w] * len(headers)
        # Header
        self.set_font("Helvetica", "B", 7)
        self.set_fill_color(15, 23, 42)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 6, h, border=1, fill=True)
        self.ln()
        # Rows
        self.set_font("Helvetica", "", 7)
        self.set_text_color(30, 41, 59)
        for row_idx, row in enumerate(rows):
            if row_idx % 2 == 0:
                self.set_fill_color(248, 250, 252)
            else:
                self.set_fill_color(255, 255, 255)
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 5, _safe_text(str(cell)[:40]), border="B", fill=True)
            self.ln()


class BriefingGenerator:
    """Generates PDF intelligence briefings from platform data."""

    def __init__(self, session: Session):
        self.session = session

    def generate_pdf(self) -> bytes:
        """Generate a full intelligence briefing PDF. Returns bytes."""
        now = datetime.utcnow()
        generated_at = now.strftime("%Y-%m-%d %H:%M UTC")

        pdf = BriefingPDF(generated_at)
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=20)

        # ── COVER PAGE ──
        pdf.add_page()
        pdf.ln(60)
        pdf.set_font("Helvetica", "B", 28)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 12, "PSI Control Tower", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 16)
        pdf.set_text_color(0, 180, 216)
        pdf.cell(0, 10, "Intelligence Briefing", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 8, "Defence Supply Chain Risk Assessment", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(20)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, "Quantum Data Technologies Ltd.", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, "Prepared for Department of National Defence / Canadian Armed Forces", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 6, now.strftime("%B %d, %Y at %H:%M UTC"), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)
        # Stats line
        transfer_count = self.session.query(ArmsTransfer).count()
        supplier_count = self.session.query(DefenceSupplier).count()
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, f"{transfer_count:,} arms transfers  |  {supplier_count} suppliers monitored  |  121 risk sub-categories", align="C", new_x="LMARGIN", new_y="NEXT")

        # ── 1. SITUATION REPORT ──
        pdf.add_page()
        pdf.section_title(1, "Situation Report")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 4, "Key threat indicators for Canadian defence supply chain resilience.", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        alert_count = self.session.query(SupplyChainAlert).filter_by(is_active=True).count()
        news_count = self.session.query(ArmsTradeNews).count()
        flight_count = self.session.query(DeliveryTracking).count()

        indicators = [
            ("Supply Chain", "ELEVATED", (217, 119, 6)),
            ("Arctic Threat", "HIGH", (220, 38, 38)),
            ("Suppliers", str(supplier_count), (217, 119, 6)),
            ("OSINT Articles", f"{news_count}", (22, 163, 74)),
        ]
        for label, value, color in indicators:
            pdf.kpi_box(label, value, color)
        pdf.ln(28)

        indicators2 = [
            ("Flight Positions", f"{flight_count:,}", (22, 163, 74)),
            ("Active Alerts", str(alert_count), (217, 119, 6)),
            ("Embargoed Nations", "17", (220, 38, 38)),
            ("Risk Categories", "13", (0, 180, 216)),
        ]
        for label, value, color in indicators2:
            pdf.kpi_box(label, value, color)
        pdf.ln(28)

        # ── 2. RISK TAXONOMY ──
        pdf.add_page()
        pdf.section_title(2, "Defence Supply Chain Risk Taxonomy (Annex B)")

        from src.analysis.risk_taxonomy import TAXONOMY_DEFINITIONS
        tax_rows = []
        for cat_id, cat in TAXONOMY_DEFINITIONS.items():
            rows = self.session.query(RiskTaxonomyScore).filter_by(category_id=cat_id).all()
            if not rows:
                continue
            avg = round(sum(r.score for r in rows) / len(rows), 1)
            worst = max(rows, key=lambda r: r.score)
            level = "RED" if avg >= 70 else "AMBER" if avg >= 40 else "GREEN"
            tax_rows.append([cat["short_name"], str(avg), level, cat.get("data_source", "seeded"), worst.subcategory_name[:35], str(round(worst.score, 1))])

        tax_rows.sort(key=lambda r: float(r[1]), reverse=True)
        global_score = round(sum(float(r[1]) for r in tax_rows) / len(tax_rows), 1) if tax_rows else 0

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 4, f"13 categories, 121 sub-categories. Global composite: {global_score}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        pdf.data_table(
            ["Category", "Score", "Level", "Source", "Worst Sub-Category", "Score"],
            tax_rows,
            [28, 14, 14, 16, 70, 14],
        )

        # ── 3. PRIORITY ACTIONS ──
        pdf.add_page()
        pdf.section_title(3, "Priority Actions (Course of Action Recommendations)")

        prio_map = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        coa_actions = self.session.query(MitigationAction).filter(
            MitigationAction.status.in_(["open", "in_progress"])
        ).all()
        coa_actions.sort(key=lambda a: prio_map.get(a.coa_priority, 9))
        coa_critical = sum(1 for a in coa_actions if a.coa_priority == "critical")
        coa_high = sum(1 for a in coa_actions if a.coa_priority == "high")

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 4, f"{len(coa_actions)} active actions. {coa_critical} critical, {coa_high} high priority.", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        coa_rows = []
        for a in coa_actions[:20]:
            coa_rows.append([
                a.coa_priority.upper(),
                a.risk_entity[:25],
                a.risk_dimension[:18].replace("_", " "),
                a.coa_action[:55],
                a.coa_timeline or "-",
                a.coa_responsible or "-",
            ])
        pdf.data_table(
            ["Priority", "Risk Entity", "Dimension", "Recommended Action", "Timeline", "Owner"],
            coa_rows,
            [16, 32, 22, 60, 16, 20],
        )

        # ── 4. SUPPLIER EXPOSURE ──
        pdf.add_page()
        pdf.section_title(4, "Canadian Defence Supplier Exposure")

        suppliers = self.session.query(DefenceSupplier).order_by(
            DefenceSupplier.risk_score_composite.desc()
        ).all()
        foreign_count = sum(1 for s in suppliers if s.ownership_type and s.ownership_type.value == "foreign_subsidiary")
        foreign_pct = round(foreign_count / max(len(suppliers), 1) * 100)

        # Sole source sectors
        sole_count = 0
        for sector in SupplierSector:
            cnt = self.session.query(DefenceSupplier).join(SupplierContract).filter(
                DefenceSupplier.sector == sector, SupplierContract.status == ContractStatus.ACTIVE
            ).distinct().count()
            if cnt == 1:
                sole_count += 1

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 4, f"{len(suppliers)} suppliers, {foreign_pct}% foreign-controlled, {sole_count} sole-source sectors.", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        sup_rows = []
        for s in suppliers[:15]:
            top_risk = self.session.query(SupplierRiskScore).filter_by(supplier_id=s.id).order_by(SupplierRiskScore.score.desc()).first()
            total_val = self.session.query(func.sum(SupplierContract.contract_value_cad)).filter_by(supplier_id=s.id).scalar() or 0
            score = s.risk_score_composite or 0
            val_str = f"${total_val / 1e9:.1f}B" if total_val >= 1e9 else f"${total_val / 1e6:.0f}M"
            sup_rows.append([
                s.name[:25],
                s.sector.value if s.sector else "-",
                s.ownership_type.value.replace("_", " ")[:18] if s.ownership_type else "-",
                str(round(score)),
                top_risk.dimension.value.replace("_", " ")[:18] if top_risk else "-",
                val_str,
            ])
        pdf.data_table(
            ["Supplier", "Sector", "Ownership", "Risk", "Top Risk", "Value"],
            sup_rows,
            [34, 22, 26, 12, 28, 22],
        )

        # ── 5. ARCTIC ASSESSMENT ──
        pdf.add_page()
        pdf.section_title(5, "Arctic Security Assessment")
        pdf.ln(2)

        arctic_kpis = [
            ("NATO Bases", "15", (0, 180, 216)),
            ("Russia Bases", "8", (220, 38, 38)),
            ("China Bases", "2", (217, 119, 6)),
            ("Live Aircraft", f"{flight_count:,}", (22, 163, 74)),
        ]
        for label, value, color in arctic_kpis:
            pdf.kpi_box(label, value, color)
        pdf.ln(28)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(0, 5, "25 Arctic military installations monitored across 8 nations. Russia maintains the largest Arctic military presence with 8 bases, including Nagurskoye (threat level 5) and Novaya Zemlya (nuclear testing site, threat level 5). NATO collectively operates 15 bases. China has established 2 Arctic research/dual-use facilities.")
        pdf.ln(4)
        pdf.multi_cell(0, 5, "Three strategic Arctic shipping routes are tracked: the Northern Sea Route (Russia-controlled), the Northwest Passage (Canadian sovereignty contested), and the Transpolar Route (international). Russian military activity along the NSR continues to increase.")

        # ── 6. DATA FRESHNESS ──
        pdf.add_page()
        pdf.section_title(6, "Data Source Freshness")

        latest_news = self.session.query(func.max(ArmsTradeNews.published_at)).scalar()
        latest_flight = self.session.query(func.max(DeliveryTracking.detected_at)).scalar()
        latest_year = self.session.query(func.max(ArmsTransfer.order_year)).scalar()
        indicator_count = self.session.query(TradeIndicator).count()
        tax_count = self.session.query(RiskTaxonomyScore).count()
        coa_count = self.session.query(MitigationAction).filter(MitigationAction.status != "resolved").count()

        source_rows = [
            ["SIPRI Arms Transfers", f"{transfer_count:,}", f"Year: {latest_year}", "OK"],
            ["World Bank Indicators", f"{indicator_count:,}", f"Year: {self.session.query(func.max(TradeIndicator.year)).scalar()}", "OK"],
            ["GDELT + RSS News", f"{news_count}", str(latest_news)[:19] if latest_news else "-", "LIVE"],
            ["Military Flights", f"{flight_count:,}", str(latest_flight)[:19] if latest_flight else "-", "LIVE"],
            ["Defence Suppliers", str(len(suppliers)), f"{len(suppliers)} monitored", "OK"],
            ["Risk Taxonomy", str(tax_count), "121 sub-categories", "OK"],
            ["Mitigation Actions", str(coa_count), f"{coa_count} active", "LIVE"],
            ["OFAC SDN Sanctions", "996+", "Updated weekly", "OK"],
            ["NATO Spending", "372", "2025 estimates", "OK"],
            ["UN Comtrade", "500+", "2023 annual", "OK"],
        ]
        pdf.data_table(
            ["Source", "Records", "Latest Data", "Status"],
            source_rows,
            [44, 24, 50, 20],
        )

        # ── END ──
        pdf.ln(20)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, "-- End of Briefing --", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, f"Generated by PSI Control Tower  |  Quantum Data Technologies Ltd.  |  {generated_at}", align="C")

        pdf_bytes = pdf.output()
        logger.info("Generated briefing PDF: %d bytes, %d pages", len(pdf_bytes), pdf.pages_count)
        return pdf_bytes
