from __future__ import annotations

from .acuite_parser import AcuiteParser
from .base import BaseAgencyParser
from .brickwork_parser import BrickworkParser
from .care_parser import CareParser
from .crisil_parser import CrisilParser
from .icra_parser import IcraParser
from .india_ratings_parser import IndiaRatingsParser
from .infomerics_parser import InfomericsParser


PARSER_REGISTRY: dict[str, type[BaseAgencyParser]] = {
    "crisil": CrisilParser,
    "care": CareParser,
    "india_ratings": IndiaRatingsParser,
    "acuite": AcuiteParser,
    "brickwork": BrickworkParser,
    "infomerics": InfomericsParser,
    "icra": IcraParser,
}


def get_parser(agency_name: str) -> BaseAgencyParser:
    try:
        parser_cls = PARSER_REGISTRY[agency_name]
    except KeyError as exc:
        raise ValueError(f"No parser registered for agency {agency_name!r}") from exc
    return parser_cls()


__all__ = [
    "AcuiteParser",
    "BaseAgencyParser",
    "BrickworkParser",
    "CareParser",
    "CrisilParser",
    "IcraParser",
    "IndiaRatingsParser",
    "InfomericsParser",
    "PARSER_REGISTRY",
    "get_parser",
]
