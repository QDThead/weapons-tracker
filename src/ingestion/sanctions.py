"""Arms sanctions and embargo data connector.

Provides three data sources:
1. Hardcoded list of countries under active arms embargoes (UN/EU/US/other)
2. OFAC SDN (Specially Designated Nationals) list from US Treasury
3. EU Consolidated Sanctions list

The embargo list is curated from publicly available embargo registries
and should be reviewed periodically for accuracy.

References:
  - OFAC SDN: https://www.treasury.gov/ofac/downloads/sdn.csv
  - EU Sanctions: https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList/content
  - UN Arms Embargoes: https://www.un.org/securitycouncil/sanctions/information
  - SIPRI Arms Embargoes DB: https://www.sipri.org/databases/embargoes
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import date

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OFAC SDN download URL (free, no auth)
# ---------------------------------------------------------------------------
OFAC_SDN_URL = "https://sanctionslistservice.ofac.treas.gov/api/publicationpreview/exports/sdn.csv"

# ---------------------------------------------------------------------------
# EU Consolidated Sanctions download URL (free, no auth)
# ---------------------------------------------------------------------------
EU_SANCTIONS_URL = (
    "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList"
    "/content?token=dG9rZW4tMjAxNw"
)

# ---------------------------------------------------------------------------
# Defense / military keywords for filtering OFAC SDN entries
# ---------------------------------------------------------------------------
DEFENSE_KEYWORDS: list[str] = [
    "military",
    "defense",
    "defence",
    "arms",
    "weapon",
    "ammunition",
    "missile",
    "nuclear",
    "ballistic",
    "rocket",
    "munition",
    "ordnance",
    "fighter",
    "warship",
    "tank",
    "artillery",
    "drone",
    "uav",
    "explosive",
    "aerospace",
    "armament",
    "naval",
    "army",
    "air force",
    "ministry of defense",
    "ministry of defence",
    "armed forces",
    "guard corps",
    "irgc",
    "kpa",  # Korean People's Army
    "korean people",
    "reconnaissance general bureau",
    "munitions industry",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ArmsEmbargo:
    """An active arms embargo against a country or entity."""

    country: str
    iso3: str
    embargo_type: str  # "comprehensive", "partial", "entity-level"
    imposing_bodies: list[str]
    since_year: int
    description: str
    notes: str = ""


@dataclass
class SDNEntity:
    """A defense-related entity from the OFAC SDN list."""

    name: str
    entity_type: str  # "individual", "entity", "vessel", "aircraft"
    program: str
    remarks: str
    aliases: list[str] = field(default_factory=list)


@dataclass
class EUSanctionEntry:
    """An entry from the EU Consolidated Sanctions list."""

    name: str
    entity_type: str
    programme: str
    remark: str


# ---------------------------------------------------------------------------
# Hardcoded embargo registry
#
# Sources consulted (as of March 2026):
#   - UN Security Council sanctions committees
#   - EU Council arms embargo decisions
#   - US State Dept / ITAR / EAR country restrictions
#   - UK Export Control Joint Unit
#   - SIPRI Arms Embargoes Database
#
# Each entry records: target country, ISO-3166-1 alpha-3 code, embargo scope,
# which international bodies imposed it, start year, and a short description.
# ---------------------------------------------------------------------------

ARMS_EMBARGOES: list[ArmsEmbargo] = [
    ArmsEmbargo(
        country="Russia",
        iso3="RUS",
        embargo_type="comprehensive",
        imposing_bodies=["EU", "US", "UK", "Canada", "Australia", "Japan", "Switzerland"],
        since_year=2014,
        description=(
            "EU arms embargo since 2014 (Crimea annexation), massively expanded in 2022 "
            "following full-scale invasion of Ukraine. US, UK, Canada, Australia, Japan, "
            "and others imposed comprehensive sanctions including arms embargoes."
        ),
        notes="Expanded to near-total trade restrictions in Feb-Mar 2022.",
    ),
    ArmsEmbargo(
        country="Belarus",
        iso3="BLR",
        embargo_type="comprehensive",
        imposing_bodies=["EU", "US", "UK", "Canada"],
        since_year=2011,
        description=(
            "EU arms embargo since 2011 (domestic repression). Expanded in 2022 due to "
            "complicity in Russia's invasion of Ukraine. US, UK, Canada followed."
        ),
        notes="Linked to Russia sanctions since 2022.",
    ),
    ArmsEmbargo(
        country="Iran",
        iso3="IRN",
        embargo_type="comprehensive",
        imposing_bodies=["UN", "EU", "US"],
        since_year=2007,
        description=(
            "UN arms embargo since 2007 (UNSCR 1747) over nuclear program. "
            "Partially lifted under JCPOA in 2015, UN conventional arms embargo expired "
            "Oct 2020 per UNSCR 2231. US maintains comprehensive sanctions (ITAR). "
            "EU maintains restrictive measures on missiles and nuclear-capable systems."
        ),
        notes="US unilateral sanctions remain the most restrictive globally.",
    ),
    ArmsEmbargo(
        country="North Korea",
        iso3="PRK",
        embargo_type="comprehensive",
        imposing_bodies=["UN", "EU", "US"],
        since_year=2006,
        description=(
            "UN arms embargo since 2006 (UNSCR 1718) over nuclear weapons program. "
            "Repeatedly strengthened (UNSCR 1874, 2094, 2270, 2321, 2356, 2371, 2375, 2397). "
            "One of the most comprehensive multilateral arms embargoes in force."
        ),
        notes="Covers all arms, dual-use goods, luxury goods, and most trade.",
    ),
    ArmsEmbargo(
        country="Myanmar",
        iso3="MMR",
        embargo_type="comprehensive",
        imposing_bodies=["EU", "US", "UK", "Canada"],
        since_year=2018,
        description=(
            "EU arms embargo since 2018 (Rohingya crisis). Expanded after Feb 2021 "
            "military coup. US, UK, Canada imposed additional sanctions."
        ),
        notes="No UN arms embargo due to China/Russia vetoes; EU/US/UK embargoes are unilateral.",
    ),
    ArmsEmbargo(
        country="Syria",
        iso3="SYR",
        embargo_type="comprehensive",
        imposing_bodies=["EU", "US", "Arab League"],
        since_year=2011,
        description=(
            "EU arms embargo since 2011 (Syrian civil war). US comprehensive sanctions "
            "under Syria Accountability Act and Caesar Act. Arab League suspended Syria."
        ),
        notes="No UN embargo due to Russia/China vetoes. EU briefly modified for opposition supply in 2013.",
    ),
    ArmsEmbargo(
        country="Somalia",
        iso3="SOM",
        embargo_type="partial",
        imposing_bodies=["UN"],
        since_year=1992,
        description=(
            "UN arms embargo since 1992 (UNSCR 733). Originally total, "
            "partially lifted for the Federal Government of Somalia in 2013 (UNSCR 2093). "
            "Embargo remains on Al-Shabaab and non-state actors. "
            "Notification/exemption regime for government arms imports."
        ),
        notes="Longest-running UN arms embargo. Government exemptions expanded over time.",
    ),
    ArmsEmbargo(
        country="Central African Republic",
        iso3="CAF",
        embargo_type="partial",
        imposing_bodies=["UN", "EU"],
        since_year=2013,
        description=(
            "UN arms embargo since 2013 (UNSCR 2127). Exemptions for government security "
            "forces with advance notification. EU also maintains embargo."
        ),
        notes="Exemptions for MINUSCA and French forces.",
    ),
    ArmsEmbargo(
        country="South Sudan",
        iso3="SSD",
        embargo_type="comprehensive",
        imposing_bodies=["UN", "EU"],
        since_year=2018,
        description=(
            "UN arms embargo since 2018 (UNSCR 2428). EU embargo since 2011 "
            "(pre-independence, as part of Sudan embargo, maintained separately after split)."
        ),
        notes="UN embargo renewed annually; most recently UNSCR 2633 (2022).",
    ),
    ArmsEmbargo(
        country="Libya",
        iso3="LBY",
        embargo_type="comprehensive",
        imposing_bodies=["UN", "EU"],
        since_year=2011,
        description=(
            "UN arms embargo since 2011 (UNSCR 1970) during Libyan civil war. "
            "Covers all arms transfers to Libya. EU implements and extends UN measures. "
            "Operation IRINI (EU naval mission) enforces the embargo in the Mediterranean."
        ),
        notes="Widely violated per UN Panel of Experts reports.",
    ),
    ArmsEmbargo(
        country="Yemen",
        iso3="YEM",
        embargo_type="partial",
        imposing_bodies=["UN"],
        since_year=2015,
        description=(
            "UN arms embargo on Houthi forces (Ansar Allah) since 2015 (UNSCR 2216). "
            "Does not apply to the internationally recognized government. "
            "Targeted embargo on listed individuals and entities."
        ),
        notes="Does not restrict arms sales to Saudi-led coalition or recognized government.",
    ),
    ArmsEmbargo(
        country="Mali",
        iso3="MLI",
        embargo_type="partial",
        imposing_bodies=["ECOWAS"],
        since_year=2022,
        description=(
            "ECOWAS sanctions including arms embargo imposed Jan 2022 after "
            "military junta delayed elections. Partially lifted Dec 2022. "
            "UN targeted sanctions on coup leaders remain."
        ),
        notes="ECOWAS economic sanctions were the primary tool; arms component was secondary.",
    ),
    ArmsEmbargo(
        country="China",
        iso3="CHN",
        embargo_type="entity-level",
        imposing_bodies=["EU", "US"],
        since_year=1989,
        description=(
            "EU arms embargo since 1989 (Tiananmen Square). Non-binding political commitment "
            "among EU members. US maintains Entity List restrictions on specific Chinese "
            "defense and tech firms (BIS Entity List, ITAR restrictions). "
            "Not a comprehensive embargo — significant gray areas."
        ),
        notes=(
            "EU embargo is a political declaration, not a legally binding Council Decision. "
            "Individual EU member states interpret scope differently."
        ),
    ),
    ArmsEmbargo(
        country="Sudan",
        iso3="SDN",
        embargo_type="partial",
        imposing_bodies=["UN", "EU", "US"],
        since_year=2004,
        description=(
            "UN arms embargo on Darfur region since 2004 (UNSCR 1556). "
            "Extended and modified multiple times. EU and US maintain broader sanctions."
        ),
        notes="Darfur-focused; does not cover all arms transfers to Government of Sudan.",
    ),
    ArmsEmbargo(
        country="Democratic Republic of the Congo",
        iso3="COD",
        embargo_type="partial",
        imposing_bodies=["UN", "EU"],
        since_year=2003,
        description=(
            "UN arms embargo since 2003 (UNSCR 1493). Applies to non-governmental armed "
            "groups. Government of DRC exempted since 2008. "
            "Notification regime for government imports."
        ),
        notes="M23 and other armed groups are primary targets.",
    ),
    ArmsEmbargo(
        country="Iraq",
        iso3="IRQ",
        embargo_type="partial",
        imposing_bodies=["UN"],
        since_year=2003,
        description=(
            "Residual UN measures from UNSCR 1483 (2003). Most sanctions lifted; "
            "remaining restrictions on proliferation-sensitive items. "
            "US is a major arms supplier to Iraqi government."
        ),
        notes="Largely superseded by bilateral agreements; legacy framework.",
    ),
    ArmsEmbargo(
        country="Lebanon",
        iso3="LBN",
        embargo_type="partial",
        imposing_bodies=["UN"],
        since_year=2006,
        description=(
            "UN arms embargo on non-governmental entities in Lebanon (UNSCR 1701, 2006). "
            "Targeted at Hezbollah and other armed groups. "
            "Does not restrict arms to Lebanese Armed Forces."
        ),
        notes="Enforcement is limited; Hezbollah continues to receive arms from Iran.",
    ),
]


# ---------------------------------------------------------------------------
# Client class
# ---------------------------------------------------------------------------


class SanctionsClient:
    """Client for arms sanctions and embargo data.

    Provides:
    - Hardcoded registry of countries under active arms embargoes
    - OFAC SDN list parser (downloads from US Treasury)
    - EU Consolidated Sanctions list parser
    """

    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout

    # ── Embargoes (hardcoded) ─────────────────────────────────────────

    def get_embargoed_countries(self) -> list[ArmsEmbargo]:
        """Return all countries currently under arms embargoes.

        Returns:
            List of ArmsEmbargo dataclass instances sorted by country name.
        """
        return sorted(ARMS_EMBARGOES, key=lambda e: e.country)

    def check_country(self, name: str) -> dict:
        """Check whether a country is under an arms embargo.

        Args:
            name: Country name (case-insensitive) or ISO3 code.

        Returns:
            Dict with ``embargoed`` bool and details if applicable.
        """
        name_lower = name.lower().strip()
        for embargo in ARMS_EMBARGOES:
            if (
                embargo.country.lower() == name_lower
                or embargo.iso3.lower() == name_lower
            ):
                return {
                    "embargoed": True,
                    "country": embargo.country,
                    "iso3": embargo.iso3,
                    "embargo_type": embargo.embargo_type,
                    "imposing_bodies": embargo.imposing_bodies,
                    "since_year": embargo.since_year,
                    "description": embargo.description,
                    "notes": embargo.notes,
                }
        return {
            "embargoed": False,
            "country": name,
            "iso3": None,
            "embargo_type": None,
            "imposing_bodies": [],
            "since_year": None,
            "description": "No active arms embargo found for this country.",
            "notes": "",
        }

    # ── OFAC SDN list ─────────────────────────────────────────────────

    async def fetch_ofac_sdn_list(
        self,
        filter_defense: bool = True,
    ) -> list[SDNEntity]:
        """Download and parse the OFAC SDN CSV for defense-related entities.

        The SDN CSV has no header row. Columns (by position):
          0: ent_num  — internal ID
          1: SDN_Name — entity name
          2: SDN_Type — "individual", "Entity", "Vessel", "Aircraft"
          3: Program  — sanctions programme(s)
          4: Title    — title/position
          5: Call_Sign
          6: Vess_type
          7: Tonnage
          8: GRT
          9: Vess_flag
          10: Vess_owner
          11: Remarks

        Args:
            filter_defense: If True, only return entities whose name,
                program, or remarks contain defense/military keywords.

        Returns:
            List of SDNEntity dataclass instances.
        """
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            logger.info("Downloading OFAC SDN list from %s", OFAC_SDN_URL)
            response = await client.get(OFAC_SDN_URL)
            response.raise_for_status()

        text = response.text
        reader = csv.reader(io.StringIO(text))

        entities: list[SDNEntity] = []
        for row in reader:
            if len(row) < 12:
                continue

            name = row[1].strip().strip('"')
            entity_type = row[2].strip().strip('"').lower()
            program = row[3].strip().strip('"')
            remarks = row[11].strip().strip('"')

            if not name:
                continue

            # Map SDN types to our taxonomy
            type_map = {
                "individual": "individual",
                "entity": "entity",
                "vessel": "vessel",
                "aircraft": "aircraft",
                "-0-": "entity",  # OFAC uses -0- for untyped entries (usually entities)
            }
            entity_type = type_map.get(entity_type, entity_type or "entity")

            if filter_defense:
                combined = f"{name} {program} {remarks}".lower()
                if not any(kw in combined for kw in DEFENSE_KEYWORDS):
                    continue

            entities.append(SDNEntity(
                name=name,
                entity_type=entity_type,
                program=program,
                remarks=remarks,
            ))

        logger.info(
            "Parsed %d %sentities from OFAC SDN list",
            len(entities),
            "defense-related " if filter_defense else "",
        )
        return entities

    # ── EU Consolidated Sanctions ─────────────────────────────────────

    async def fetch_eu_sanctions(
        self,
        filter_defense: bool = True,
    ) -> list[EUSanctionEntry]:
        """Download and parse the EU Consolidated Sanctions CSV.

        The EU CSV uses a semicolon delimiter and has a header row.
        Key columns: Entity_SubjectType, NameAlias_WholeName,
        Entity_Regulation_Programme, Entity_Remark.

        Args:
            filter_defense: If True, only return entries whose name,
                programme, or remark contain defense/military keywords.

        Returns:
            List of EUSanctionEntry dataclass instances.
        """
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            logger.info("Downloading EU Consolidated Sanctions list")
            response = await client.get(EU_SANCTIONS_URL)
            response.raise_for_status()

        text = response.text
        # Strip BOM if present
        if text.startswith("\ufeff"):
            text = text[1:]
        reader = csv.DictReader(io.StringIO(text), delimiter=";")

        entries: list[EUSanctionEntry] = []
        seen_names: set[str] = set()

        for row in reader:
            name = (
                row.get("Naal_wholename", "")
                or row.get("Naal_lastname", "")
            ).strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            entity_type = row.get("Subject_type", "").strip().lower()
            programme = row.get("Programme", "").strip()
            remark = row.get("Entity_remark", "").strip()

            if filter_defense:
                combined = f"{name} {programme} {remark}".lower()
                if not any(kw in combined for kw in DEFENSE_KEYWORDS):
                    continue

            entries.append(EUSanctionEntry(
                name=name,
                entity_type=entity_type or "unknown",
                programme=programme,
                remark=remark[:500],  # Truncate lengthy remarks
            ))

        logger.info(
            "Parsed %d %sentries from EU Consolidated Sanctions list",
            len(entries),
            "defense-related " if filter_defense else "",
        )
        return entries
