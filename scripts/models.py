from __future__ import annotations
import re
from dataclasses import dataclass, field
import yaml


@dataclass
class Recipe:
    title: str
    source_url: str | None = None
    source_name: str | None = None
    cuisine: list[str] = field(default_factory=list)
    meal_type: list[str] = field(default_factory=list)
    status: str = "untried"
    effort: str = "medium"
    time_active: int | None = None
    time_total: int | None = None
    servings: int = 4
    appliances: list[str] = field(default_factory=list)
    dietary: list[str] = field(default_factory=list)
    last_made: str | None = None
    rating: int | None = None
    ingredients: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_markdown(cls, text: str) -> "Recipe":
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            raise ValueError("No YAML frontmatter found")

        fm = yaml.safe_load(match.group(1))
        body = match.group(2)

        return cls(
            title=fm.get("title", ""),
            source_url=fm.get("source_url"),
            source_name=fm.get("source_name"),
            cuisine=fm.get("cuisine") or [],
            meal_type=fm.get("meal_type") or [],
            status=fm.get("status", "untried"),
            effort=fm.get("effort", "medium"),
            time_active=fm.get("time_active"),
            time_total=fm.get("time_total"),
            servings=fm.get("servings", 4),
            appliances=fm.get("appliances") or [],
            dietary=fm.get("dietary") or [],
            last_made=fm.get("last_made"),
            rating=fm.get("rating"),
            ingredients=_parse_list_section(body, "Ingredients"),
            instructions=_parse_numbered_section(body, "Instructions"),
            notes=_parse_text_section(body, "Notes"),
        )

    def to_markdown(self) -> str:
        fm = {
            "title": self.title,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "cuisine": self.cuisine,
            "meal_type": self.meal_type,
            "status": self.status,
            "effort": self.effort,
            "time_active": self.time_active,
            "time_total": self.time_total,
            "servings": self.servings,
            "appliances": self.appliances,
            "dietary": self.dietary,
            "last_made": self.last_made,
            "rating": self.rating,
        }
        ingredients_block = "\n".join(f"- {i}" for i in self.ingredients)
        instructions_block = "\n".join(
            f"{n + 1}. {s}" for n, s in enumerate(self.instructions)
        )
        return (
            f"---\n{yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)}---\n\n"
            f"## Ingredients\n{ingredients_block}\n\n"
            f"## Instructions\n{instructions_block}\n\n"
            f"## Notes\n{self.notes}\n"
        )


def _parse_list_section(body: str, heading: str) -> list[str]:
    m = re.search(rf"## {heading}\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if not m:
        return []
    return [
        re.sub(r"^-\s*", "", line).strip()
        for line in m.group(1).strip().splitlines()
        if line.strip() and line.strip() != "-"
    ]


def _parse_numbered_section(body: str, heading: str) -> list[str]:
    m = re.search(rf"## {heading}\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if not m:
        return []
    return [
        re.sub(r"^\d+[.)]\s*", "", line).strip()
        for line in m.group(1).strip().splitlines()
        if line.strip()
    ]


def _parse_text_section(body: str, heading: str) -> str:
    # Notes is always the last section, so we match to end-of-document only.
    # This preserves any ## subheadings that may appear inside the notes body.
    if heading == "Notes":
        m = re.search(rf"## {heading}\n(.*?)(?=\Z)", body, re.DOTALL)
    else:
        m = re.search(rf"## {heading}\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    return m.group(1).strip() if m else ""
