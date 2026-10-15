"""Editable, source-based starting drafts. No inference, enrichment or sending."""
from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints, field_validator

from shortlist.domain import Evidence, Profile, Research, Value, new_id, utcnow

Identity = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]


class DraftText(Value):
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]

    @field_validator("subject")
    @classmethod
    def single_line(cls, value):
        if any(ord(character) < 32 for character in value):
            raise ValueError("Subject must be a single line")
        return value


class StartEmailDraft(Value):
    request_key: str = Field(min_length=8, max_length=100)
    previous_id: Identity | None = None
    person_id: Identity | None = None


class EditEmailDraft(DraftText):
    request_key: str = Field(min_length=8, max_length=100)
    previous_id: Identity


class EmailDraft(DraftText):
    id: Identity = Field(default_factory=new_id)
    person_id: Identity | None = None
    basis: tuple[Evidence, ...] = Field(default=(), max_length=2)
    edited: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


def starting_draft(profile: Profile, research: Research, person_id: str | None) -> EmailDraft:
    person = next((person for person in research.people if person.id == person_id), None)
    if person_id is not None and person is None:
        raise ValueError("Choose a person from this company's saved research")
    evidence = next((fact.evidence for fact in research.company_facts if fact.kind == "description"), None)
    if evidence is None:
        evidence = next((finding.evidence[0] for finding in research.findings if finding.status == "supported"), None)
    company = " ".join(research.name.split())
    greeting = f"Hi {person.name}," if person else f"Hi {company} team,"
    context = f'Your company page says: "{evidence.passage}"\n\n' if evidence else ""
    body = (greeting + "\n\n" + context + "I'm reaching out about this offer:\n" + profile.offer
            + f"\n\nWould it be useful to discuss whether this is relevant to {company}?\n\nBest,\n[Your name]")
    basis = ((person.evidence,) if person else ()) + ((evidence,) if evidence else ())
    return EmailDraft(subject=f"A conversation with {company}"[:200], body=body, person_id=person_id, basis=basis)
