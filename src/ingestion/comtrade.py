"""UN Comtrade arms trade data connector.

Fetches actual USD trade values for arms and ammunition (HS Chapter 93)
from the UN Comtrade API. Complements SIPRI TIV data with real financial values.

Free preview endpoint: max 500 records, no auth required.
Authenticated endpoint: max 100K records, free registration.

Reference: https://comtradedeveloper.un.org/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

COMTRADE_PREVIEW_URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
COMTRADE_AUTH_URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS"

# HS Chapter 93 subcodes for arms and ammunition
HS_ARMS_CODES = {
    "9301": "Military weapons (artillery, rockets, launchers)",
    "9302": "Revolvers and pistols",
    "9303": "Firearms (sporting/hunting/other)",
    "9304": "Other arms (air guns, spring guns, etc.)",
    "9305": "Parts and accessories of weapons",
    "9306": "Bombs, grenades, torpedoes, mines, missiles, ammunition",
    "9307": "Swords, bayonets, lances and similar",
}

# UN M49 country codes for major arms traders
COMTRADE_COUNTRY_CODES = {
    "United States": 842,
    "Russia": 643,
    "China": 156,
    "France": 251,
    "Germany": 276,
    "United Kingdom": 826,
    "Italy": 380,
    "Israel": 376,
    "South Korea": 410,
    "Spain": 724,
    "India": 699,
    "Saudi Arabia": 682,
    "Ukraine": 804,
    "Japan": 392,
    "Australia": 36,
    "Turkiye": 792,
    "Egypt": 818,
    "Brazil": 76,
    "Canada": 124,
    "Netherlands": 528,
    "Sweden": 752,
    "Norway": 578,
    "Poland": 616,
    "Pakistan": 586,
    "Iran": 364,
    "Taiwan": 490,
    "Qatar": 634,
    "Singapore": 702,
    "Indonesia": 360,
    "Thailand": 764,
    "Algeria": 12,
    "Iraq": 368,
    "Viet Nam": 704,
    "Kazakhstan": 398,
    "Belarus": 112,
    "Myanmar": 104,
    "Bangladesh": 50,
    "Nigeria": 566,
    "Serbia": 688,
}


@dataclass
class ComtradeRecord:
    """A single UN Comtrade arms trade record."""
    reporter: str
    reporter_iso: str
    partner: str
    partner_iso: str
    year: int
    flow: str  # "Export" or "Import"
    hs_code: str
    hs_description: str
    trade_value_usd: float
    quantity: float | None = None
    net_weight_kg: float | None = None


@dataclass
class ComtradeQuery:
    """Query parameters for UN Comtrade API."""
    reporter_codes: list[int] = field(default_factory=list)
    partner_codes: list[int] = field(default_factory=list)
    years: list[int] = field(default_factory=lambda: [2023])
    flow_codes: list[str] = field(default_factory=lambda: ["M", "X"])
    hs_codes: list[str] = field(default_factory=lambda: ["93"])
    include_descriptions: bool = True


# Known major buyer countries for adversary sellers (UN M49 codes)
ADVERSARY_BUYER_CODES: dict[str, list[int]] = {
    "Russia": [
        699,   # India
        12,    # Algeria
        818,   # Egypt
        368,   # Iraq
        704,   # Viet Nam
        398,   # Kazakhstan
        112,   # Belarus
        104,   # Myanmar
    ],
    "China": [
        586,   # Pakistan
        50,    # Bangladesh
        104,   # Myanmar
        12,    # Algeria
        764,   # Thailand
        566,   # Nigeria
        688,   # Serbia
    ],
}

# Reverse lookup: M49 code -> country name (built from COMTRADE_COUNTRY_CODES)
_M49_TO_NAME: dict[int, str] = {v: k for k, v in COMTRADE_COUNTRY_CODES.items()}


class ComtradeClient:
    """Client for the UN Comtrade arms trade API.

    Uses the free preview endpoint by default (500 records max, no auth).
    Set subscription_key for the authenticated endpoint (100K records).
    """

    def __init__(self, subscription_key: str | None = None, timeout: float = 30.0):
        self.subscription_key = subscription_key
        self.timeout = timeout

    def _build_params(self, query: ComtradeQuery) -> dict:
        """Build query parameters for the Comtrade API."""
        params = {
            "cmdCode": ",".join(query.hs_codes),
            "flowCode": ",".join(query.flow_codes),
            "period": ",".join(str(y) for y in query.years),
            "includeDesc": "true" if query.include_descriptions else "false",
        }

        if query.reporter_codes:
            params["reporterCode"] = ",".join(str(c) for c in query.reporter_codes)

        if query.partner_codes:
            params["partnerCode"] = ",".join(str(c) for c in query.partner_codes)
        else:
            params["partnerCode"] = "0"  # World aggregate

        return params

    async def fetch(self, query: ComtradeQuery) -> list[ComtradeRecord]:
        """Fetch arms trade data from UN Comtrade.

        Args:
            query: Query parameters.

        Returns:
            List of trade records.
        """
        params = self._build_params(query)

        if self.subscription_key:
            url = COMTRADE_AUTH_URL
            headers = {"Ocp-Apim-Subscription-Key": self.subscription_key}
        else:
            url = COMTRADE_PREVIEW_URL
            headers = {}
            params["maxRecords"] = 500

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info(
                "Fetching Comtrade: reporters=%s, years=%s, hs=%s",
                params.get("reporterCode", "all"),
                params["period"],
                params["cmdCode"],
            )
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

        data = response.json()

        if data.get("error"):
            logger.error("Comtrade API error: %s", data["error"])
            return []

        records = []
        for item in data.get("data", []):
            # Skip "World" aggregates unless the caller explicitly requested them
            if item.get("partnerCode") == 0 and not query.partner_codes:
                continue

            trade_value = item.get("primaryValue") or item.get("fobvalue") or item.get("cifvalue") or 0

            records.append(ComtradeRecord(
                reporter=item.get("reporterDesc", ""),
                reporter_iso=item.get("reporterISO", ""),
                partner=item.get("partnerDesc", ""),
                partner_iso=item.get("partnerISO", ""),
                year=item.get("refYear", 0),
                flow=item.get("flowDesc", ""),
                hs_code=item.get("cmdCode", ""),
                hs_description=item.get("cmdDesc", ""),
                trade_value_usd=trade_value,
                quantity=item.get("qty") if item.get("qty") and item["qty"] > 0 else None,
                net_weight_kg=item.get("netWgt") if item.get("netWgt") and item["netWgt"] > 0 else None,
            ))

        logger.info("Fetched %d Comtrade records", len(records))
        return records

    async def fetch_country_exports(
        self, country_name: str, years: list[int] | None = None
    ) -> list[ComtradeRecord]:
        """Fetch arms exports for a specific country with partner breakdown."""
        code = COMTRADE_COUNTRY_CODES.get(country_name)
        if code is None:
            raise ValueError(f"Unknown country: {country_name}")

        query = ComtradeQuery(
            reporter_codes=[code],
            years=years or [2022, 2023],
            flow_codes=["X"],
            hs_codes=["9301", "9302", "9303", "9304", "9305", "9306"],
        )
        return await self.fetch(query)

    async def fetch_country_imports(
        self, country_name: str, years: list[int] | None = None
    ) -> list[ComtradeRecord]:
        """Fetch arms imports for a specific country with partner breakdown."""
        code = COMTRADE_COUNTRY_CODES.get(country_name)
        if code is None:
            raise ValueError(f"Unknown country: {country_name}")

        query = ComtradeQuery(
            reporter_codes=[code],
            years=years or [2022, 2023],
            flow_codes=["M"],
            hs_codes=["9301", "9302", "9303", "9304", "9305", "9306"],
        )
        return await self.fetch(query)

    async def fetch_global_summary(
        self, years: list[int] | None = None
    ) -> list[ComtradeRecord]:
        """Fetch aggregate arms trade (HS 93) for major exporters."""
        top_exporters = [842, 251, 276, 380, 826, 156, 410, 724, 376, 643]
        query = ComtradeQuery(
            reporter_codes=top_exporters,
            partner_codes=[0],  # World aggregate (explicitly requested)
            years=years or [2020, 2021, 2022, 2023],
            flow_codes=["X"],
            hs_codes=["93"],
        )
        return await self.fetch(query)

    async def fetch_buyer_side_imports(
        self, seller_name: str, years: list[int]
    ) -> list[ComtradeRecord]:
        """Fetch what buyer countries report importing from a specific seller.

        Russia and China don't publish reliable arms export data, but their
        buyers do. This method queries known major buyers of a given seller
        for their HS 93 import records where the partner is the seller.

        The preview endpoint limits each call to 500 records, so we batch
        buyer countries in a single request (comma-separated reporterCodes)
        and set partnerCode to the seller.

        Args:
            seller_name: Country name of the seller (must be in ADVERSARY_BUYER_CODES).
            years: List of years to query.

        Returns:
            List of ComtradeRecords representing import reports from buyer countries.
        """
        seller_code = COMTRADE_COUNTRY_CODES.get(seller_name)
        if seller_code is None:
            raise ValueError(f"Unknown seller country: {seller_name}")

        buyer_codes = ADVERSARY_BUYER_CODES.get(seller_name)
        if buyer_codes is None:
            raise ValueError(
                f"No known buyer list for {seller_name}. "
                f"Supported sellers: {', '.join(ADVERSARY_BUYER_CODES.keys())}"
            )

        # Query: reporters = buyer countries, partner = the seller, flow = imports
        query = ComtradeQuery(
            reporter_codes=buyer_codes,
            partner_codes=[seller_code],
            years=years,
            flow_codes=["M"],
            hs_codes=["9301", "9302", "9303", "9304", "9305", "9306"],
        )

        logger.info(
            "Buyer-side mirror: querying %d buyers of %s for years %s",
            len(buyer_codes),
            seller_name,
            years,
        )

        return await self.fetch(query)


# ---------------------------------------------------------------------------
# PSI: Expanded HS codes for defense-critical materials ("Rocks" layer)
# ---------------------------------------------------------------------------

HS_DEFENSE_MATERIALS: dict[str, dict[str, str]] = {
    # Ores and concentrates
    "2602": {"name": "Manganese ore", "material": "manganese", "application": "Armor steel alloys, submarine hulls"},
    "2603": {"name": "Copper ore", "material": "copper", "application": "Ammunition casings, electronics, wiring"},
    "2604": {"name": "Nickel ore", "material": "nickel", "application": "Jet engine superalloys, armor plating"},
    "2605": {"name": "Cobalt ore", "material": "cobalt", "application": "Jet engine superalloys, battery cathodes"},
    "2607": {"name": "Lead ore", "material": "lead", "application": "Ammunition, radiation shielding"},
    "2608": {"name": "Zinc ore", "material": "zinc", "application": "Galvanization of military vehicles/ships"},
    "2609": {"name": "Tin ore", "material": "tin", "application": "Solder for electronics, bearing alloys"},
    "2610": {"name": "Chromium ore", "material": "chromium", "application": "Stainless steel, armor hardening"},
    "2611": {"name": "Tungsten ore", "material": "tungsten", "application": "Armor-piercing ammunition, kinetic penetrators"},
    "2612": {"name": "Uranium/thorium ore", "material": "uranium", "application": "Nuclear propulsion, DU ammunition/armor"},
    "2615": {"name": "Niobium/tantalum/zirconium ore", "material": "niobium", "application": "Superconductors, capacitors, nuclear cladding"},
    # Rare earths and radioactive
    "2846": {"name": "Rare earth compounds", "material": "rare_earth", "application": "Magnets for guidance, lasers, optics, motors"},
    "2844": {"name": "Radioactive elements", "material": "uranium", "application": "Nuclear warheads, reactor fuel, DU armor"},
    # Specialty metals
    "8101": {"name": "Tungsten articles", "material": "tungsten", "application": "AP rounds, kinetic energy penetrators"},
    "8102": {"name": "Molybdenum articles", "material": "molybdenum", "application": "High-strength steel alloys, reactor vessels"},
    "8103": {"name": "Tantalum articles", "material": "tantalum", "application": "Capacitors in every guided weapon"},
    "8104": {"name": "Magnesium articles", "material": "magnesium", "application": "Flares, incendiary munitions, lightweight airframes"},
    "8105": {"name": "Cobalt articles", "material": "cobalt", "application": "Superalloys for F110/F135 jet engines, permanent magnets"},
    "810520": {"name": "Cobalt unwrought/powder", "material": "cobalt", "application": "Feedstock for superalloy foundries, battery cathode precursors"},
    "810590": {"name": "Cobalt wrought articles", "material": "cobalt", "application": "Finished cobalt products, superalloy components, magnet blanks"},
    "282200": {"name": "Cobalt oxides/hydroxides", "material": "cobalt", "application": "Battery cathode material (NMC, NCA), catalyst precursors"},
    "8108": {"name": "Titanium articles", "material": "titanium", "application": "Airframes (F-22, F-35, Su-57), submarine hulls"},
    "8109": {"name": "Zirconium articles", "material": "zirconium", "application": "Nuclear cladding, armor ceramics"},
    "8110": {"name": "Antimony articles", "material": "antimony", "application": "Ammunition hardening, flame retardants, night vision"},
    "8112": {"name": "Beryllium/Germanium/Gallium/other", "material": "beryllium", "application": "Satellites, gyroscopes, IR optics, semiconductors"},
    # Semiconductors
    "8541": {"name": "Semiconductor devices", "material": "semiconductor", "application": "Guidance systems, radar, EW, seekers"},
    "8542": {"name": "Integrated circuits", "material": "semiconductor", "application": "Avionics, weapon computers, FPGAs"},
    # Propellants and explosives
    "3601": {"name": "Propellant powders", "material": "explosive_precursor", "application": "Ammunition and missile propulsion"},
    "3602": {"name": "Prepared explosives", "material": "explosive_precursor", "application": "Warheads, demolition charges"},
    "3603": {"name": "Detonating fuses", "material": "explosive_precursor", "application": "Fuzing systems for munitions"},
}

# Top mineral-producing countries for material flow queries (UN M49 codes)
MATERIAL_SOURCE_COUNTRIES: dict[str, list[int]] = {
    "cobalt": [180, 643, 36, 586, 104],    # DRC, Russia, Australia, Philippines, Myanmar
    "lithium": [36, 152, 156, 32, 76],      # Australia, Chile, China, Argentina, Brazil
    "rare_earth": [156, 104, 36, 699, 840], # China, Myanmar, Australia, India, USA
    "titanium": [156, 392, 643, 398, 804],  # China, Japan, Russia, Kazakhstan, Ukraine
    "tungsten": [156, 704, 643, 36, 40],    # China, Vietnam, Russia, Australia, Austria
    "chromium": [710, 792, 398, 699, 10],   # S. Africa, Turkey, Kazakhstan, India, Azerbaijan
    "nickel": [360, 608, 643, 156, 36],     # Indonesia, Philippines, Russia, China, Australia
    "tantalum": [180, 646, 76, 156, 36],    # DRC, Rwanda, Brazil, China, Australia
    "uranium": [398, 516, 124, 36, 508],    # Kazakhstan, Namibia, Canada, Australia, Mozambique
    "gallium": [156, 392, 410, 643, 276],   # China, Japan, S. Korea, Russia, Germany
    "germanium": [156, 56, 643, 124, 840],  # China, Belgium, Russia, Canada, USA
}


class ComtradeMaterialsClient(ComtradeClient):
    """Extended Comtrade client for querying defense-critical material trade flows.

    Queries HS codes beyond Chapter 93 to track the "Rocks" layer:
    ores, rare earths, specialty metals, semiconductors, propellants.
    """

    async def fetch_material_trade(
        self,
        material: str,
        years: list[int] | None = None,
    ) -> list[ComtradeRecord]:
        """Fetch global trade flows for a specific defense material.

        Args:
            material: Material key from MATERIAL_SOURCE_COUNTRIES.
            years: Years to query (default: [2022, 2023]).

        Returns:
            List of ComtradeRecords for the material's HS codes.
        """
        source_codes = MATERIAL_SOURCE_COUNTRIES.get(material)
        if source_codes is None:
            raise ValueError(f"Unknown material: {material}")

        # Find matching HS codes for this material
        hs_codes = [
            code for code, info in HS_DEFENSE_MATERIALS.items()
            if info["material"] == material
        ]
        if not hs_codes:
            raise ValueError(f"No HS codes mapped for material: {material}")

        query = ComtradeQuery(
            reporter_codes=source_codes,
            partner_codes=[0],  # World aggregate
            years=years or [2022, 2023],
            flow_codes=["X"],
            hs_codes=hs_codes,
        )

        logger.info(
            "Material trade query: %s (HS %s) from %d source countries",
            material, ",".join(hs_codes), len(source_codes),
        )
        return await self.fetch(query)

    async def fetch_material_imports_by_country(
        self,
        country_name: str,
        years: list[int] | None = None,
    ) -> list[ComtradeRecord]:
        """Fetch all defense-material imports for a specific country.

        Returns trade records for all HS codes in HS_DEFENSE_MATERIALS.
        """
        code = COMTRADE_COUNTRY_CODES.get(country_name)
        if code is None:
            raise ValueError(f"Unknown country: {country_name}")

        all_hs = list(HS_DEFENSE_MATERIALS.keys())
        query = ComtradeQuery(
            reporter_codes=[code],
            years=years or [2022, 2023],
            flow_codes=["M"],
            hs_codes=all_hs,
        )

        logger.info(
            "Material imports for %s: %d HS codes",
            country_name, len(all_hs),
        )
        return await self.fetch(query)
