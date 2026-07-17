"""Généré depuis genecrew/docs/swagger/openapi.json — NE PAS ÉDITER (ADR 0004)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, RootModel, constr


class Error(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    code: int | None = Field(None, description='Error code')
    status: str | None = Field(None, description='Error name')
    message: str | None = Field(None, description='Error message')
    errors: dict[str, Any] | None = Field(None, description='Errors')


class PaginationMetadata(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    total: int | None = Field(None, description='Total number of items.')
    total_pages: int | None = Field(None, description='Total number of pages.')
    first_page: int | None = Field(None, description='First available page number.')
    last_page: int | None = Field(None, description='Last available page number.')
    page: int | None = Field(None, description='Current page number.')
    previous_page: int | None = Field(None, description='Previous page number.')
    next_page: int | None = Field(None, description='Next page number.')


class Transaction(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    type: str | None = Field(
        None, description="Action type: 'add', 'update', or 'delete'."
    )
    field_class: str | None = Field(
        None, alias='_class', description="Object class name (e.g. 'Person', 'Event')."
    )
    handle: str | None = Field(None, description='Handle of the affected object.')
    old: Any | None = Field(
        None, description='Object state before the change (null for adds).'
    )
    new: Any | None = Field(
        None, description='Object state after the change (null for deletes).'
    )


class TaskReference(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    href: str | None = Field(None, description='URL of the task status endpoint.')
    id: str | None = Field(None, description='Unique identifier of the task.')


class Namespace(Enum):
    people = 'people'
    families = 'families'
    events = 'events'
    places = 'places'
    citations = 'citations'
    sources = 'sources'
    repositories = 'repositories'
    media = 'media'
    notes = 'notes'
    tags = 'tags'


class Handle(RootModel[constr(min_length=1)]):
    root: constr(min_length=1)


class DeleteObjectsByHandleArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    namespace: Namespace = Field(
        ..., description="Object type of the objects to delete (e.g. 'people')."
    )
    handles: list[Handle] = Field(
        ..., description='List of handles of the objects to delete.', min_length=1
    )


class UndoTransaction(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    id: int | None = Field(None, description='Transaction ID.')
    connection: Any | None = Field(None, description='Internal connection object.')
    first: int | None = Field(
        None, description='ID of the first change in this transaction.'
    )
    last: int | None = Field(
        None, description='ID of the last change in this transaction.'
    )
    undo: bool | None = Field(
        None, description='Whether this transaction is from an undo action.'
    )
    timestamp: float | None = Field(
        None, description='Unix timestamp when the transaction was committed.'
    )
    changes: list[Any] | None = Field(
        None, description='List of individual object changes.'
    )


class TokenLogin(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    username: constr(min_length=1) = Field(
        ..., description='The username for authentication.'
    )
    password: constr(min_length=1) = Field(..., description="The user's password.")


class TokenPair(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    access_token: str = Field(..., description='A valid JWT access token.')
    refresh_token: str = Field(..., description='A valid JWT refresh token.')


class Token(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    access_token: str = Field(..., description='A valid JWT access token.')


class TokenCreateOwnerPost(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    tree: str | None = Field(
        None, description='Tree ID to authenticate against (multi-tree mode).'
    )


class OIDCProvider(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    id: str | None = Field(None, description="Provider identifier (e.g. 'google').")
    name: str | None = Field(
        None, description="Human-readable provider name (e.g. 'Google')."
    )
    login_url: str | None = Field(
        None, description='URL to initiate login with this provider.'
    )


class OIDCConfig(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    enabled: bool | None = Field(
        None, description='Whether OIDC authentication is enabled.'
    )
    providers: list[OIDCProvider] | None = Field(
        None, description='List of configured OIDC providers.'
    )
    disable_local_auth: bool | None = Field(
        None, description='Whether local username/password authentication is disabled.'
    )
    auto_redirect: bool | None = Field(
        None,
        description='Whether to auto-redirect when only one provider is configured.',
    )


class EventProfile(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    citations: int | None = Field(
        None, description='Total number of citations supporting this event.'
    )
    confidence: int | None = Field(
        None, description='Highest confidence rating among the supporting citations.'
    )
    date: str | None = Field(
        None, description='Date of the event as a formatted string.'
    )
    place: str | None = Field(
        None, description='Name of the place where the event occurred.'
    )
    place_name: str | None = Field(None, description='Short name of the event place.')
    type: str | None = Field(
        None, description="Type of the event (e.g. 'Birth', 'Death')."
    )
    participants: dict[str, Any] | None = Field(
        None, description='People and families participating in this event.'
    )
    references: dict[str, Any] | None = Field(
        None, description='References to this event from other objects.'
    )


class TimelinePersonProfile(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    age: str | None = Field(
        None, description='Age of the person at the time of the event.'
    )
    birth: EventProfile | None = Field(None, description='Birth event profile.')
    death: EventProfile | None = Field(None, description='Death event profile.')
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier for the person.'
    )
    handle: str | None = Field(None, description='Unique handle for the person.')
    name_display: str | None = Field(None, description='Full display name.')
    name_given: str | None = Field(None, description='Given (first) name.')
    name_surname: str | None = Field(None, description='Surname.')
    name_suffix: str | None = Field(None, description='Name suffix.')
    relationship: str | None = Field(
        None, description='Relationship to the anchor person.'
    )
    sex: str | None = Field(None, description="Sex identifier ('M', 'F', 'X', or 'U').")


class PlaceProfile(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    alternate_names: list[str] | None = Field(
        None, description='Alternate names of the place.'
    )
    alternate_place_names: list[Any] | None = Field(
        None, description='Alternate names with associated dates.'
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier for the place.'
    )
    lat: float | None = Field(None, description='Geographic latitude.')
    long: float | None = Field(None, description='Geographic longitude.')
    name: str | None = Field(None, description='Place title.')
    parent_places: list[PlaceProfile] | None = Field(
        None, description='List of parent place profiles.'
    )
    direct_parent_places: list[Any] | None = Field(
        None, description='Direct parent places with corresponding dates.'
    )
    references: dict[str, Any] | None = Field(
        None, description='References to this place from other objects.'
    )


class TimelineEventProfile(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    age: str | None = Field(
        None, description='Age of the anchor person at the time of the event.'
    )
    citations: int | None = Field(
        None, description='Total number of supporting citations.'
    )
    confidence: int | None = Field(
        None, description='Highest confidence rating among citations.'
    )
    date: str | None = Field(
        None, description='Date of the event as a formatted string.'
    )
    description: str | None = Field(None, description='Description of the event.')
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier for the event.'
    )
    handle: str | None = Field(None, description='Unique handle for the event.')
    label: str | None = Field(
        None,
        description="Generated label accounting for the relationship (e.g. 'Birth of Stepsister').",
    )
    media: list[str] | None = Field(
        None, description='Handles of media items for this event.'
    )
    person: TimelinePersonProfile | None = Field(
        None, description='Profile of the person associated with this event.'
    )
    place: PlaceProfile | None = Field(
        None, description='Profile of the place where the event occurred.'
    )
    type: str | None = Field(None, description='Type of the event.')


class Schema(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )


class DnaSegment(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    chromosome: str | None = Field(None, description='Chromosome identifier.')
    start: int | None = Field(None, description='Start position of the segment.')
    stop: int | None = Field(None, description='End position of the segment.')
    side: str | None = Field(
        None, description="Side: 'M' (maternal), 'P' (paternal), or 'U' (unknown)."
    )
    cM: float | None = Field(None, description='Genetic distance in centiMorgans.')
    SNPs: int | None = Field(None, description='Number of matching SNPs.')
    comment: str | None = Field(None, description='Optional comment about the segment.')


class CladeAgeInfo(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    formed: float | None = Field(
        None, description='Estimated years ago the clade was formed.'
    )
    formed_confidence_interval: list[float] | None = Field(
        None, description='95% confidence interval [lower, upper] for the formed age.'
    )
    most_recent_common_ancestor: float | None = Field(
        None,
        description='Estimated years ago the most recent common ancestor was born.',
    )
    most_recent_common_ancestor_confidence_interval: list[float] | None = Field(
        None,
        description='95% confidence interval for the most recent common ancestor age.',
    )


class CladeInfo(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    name: str | None = Field(None, description="Clade ID (e.g. 'BY61636').")
    age_info: CladeAgeInfo | dict[str, Any] | None = Field(
        None, description='Age information for the clade.'
    )
    score: float | None = Field(None, description='Match score for this clade.')


class YDnaResponse(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    clade_lineage: list[CladeInfo] | None = Field(
        None,
        description='Ordered list of Y-DNA haplogroup clade assignments, from broadest to most specific.',
    )
    tree_version: str | None = Field(
        None, description='Version of the YFull tree used for clade assignment.'
    )
    raw_data: str | None = Field(
        None,
        description='Raw Y-DNA SNP data string. Only present if raw=true was requested.',
    )


class PersonMergeArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    family_merger: bool | None = Field(
        True,
        description='If true (default), merge duplicate spouse/parent families that result from merging the two persons.',
    )


class FamilyMergeArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    phoenix_father_handle: str | None = Field(
        None,
        description="Handle of the person to keep as father of the merged family. If omitted, the phoenix family's existing father is kept.",
    )
    phoenix_mother_handle: str | None = Field(
        None,
        description="Handle of the person to keep as mother of the merged family. If omitted, the phoenix family's existing mother is kept.",
    )


class Span(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    span: str | None = Field(
        None, description='Human-readable description of the elapsed time.'
    )


class Tree(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    name: str | None = Field(None, description='Human-readable name of the tree.')
    id: str | None = Field(None, description='Unique identifier of the tree.')
    quota_media: int | None = Field(
        None, description='Maximum total size in bytes for media objects.'
    )
    quota_people: int | None = Field(
        None, description='Maximum number of people allowed in the tree.'
    )
    usage_media: int | None = Field(
        None, description='Current total size of media objects in bytes.'
    )
    usage_people: int | None = Field(
        None, description='Current number of people in the tree.'
    )
    enabled: bool | None = Field(None, description='Whether the tree is enabled.')
    min_role_ai: int | None = Field(
        None, description='Minimum user role required to use the AI chat endpoint.'
    )


class TreeUpdateBodyArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    name: str | None = Field(None, description='The name of the tree.')
    quota_media: int | None = Field(
        None, description='Maximum total size in bytes for media objects.'
    )
    quota_people: int | None = Field(
        None, description='Maximum number of people allowed in the tree.'
    )
    min_role_ai: int | None = Field(
        None,
        description='Minimum user role level required to use the AI chat endpoint.',
    )


class TreeCreateBodyArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    name: str = Field(..., description='The name of the tree.')
    quota_media: int | None = Field(
        None, description='Maximum total size in bytes for media objects.'
    )
    quota_people: int | None = Field(
        None, description='Maximum number of people allowed in the tree.'
    )
    min_role_ai: int | None = Field(
        None,
        description='Minimum user role level required to use the AI chat endpoint.',
    )


class TreeConfig(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )


class TreeConfigBodyArgs(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )


class CustomTypes(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )


class DefaultTypeMap(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )


class DefaultTypes(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )


class Types(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    custom: CustomTypes | None = Field(None, description='User-defined custom types.')
    default: DefaultTypes | None = Field(None, description='Built-in default types.')


class NameFormat(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    number: int | None = Field(
        None, description='Numeric identifier for the name format.'
    )
    name: str | None = Field(None, description='Display name of the format.')
    format: str | None = Field(None, description='The format string.')
    active: bool | None = Field(
        None, description='If true, the format is currently in use.'
    )


class NameGroup(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    surname: str | None = Field(None, description='The surname to be grouped.')
    group: str | None = Field(
        None, description='The canonical surname this surname should be grouped with.'
    )


class Bookmarks(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )


class FilterRule(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    name: str | None = Field(None, description='Name of the filter rule class.')
    regex: bool | None = Field(
        None, description='Whether text values are treated as regular expressions.'
    )
    values: list[Any] | None = Field(None, description='Parameter values for the rule.')


class CustomFilter(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    comment: str | None = Field(
        None, description='Comment describing the purpose of the filter.'
    )
    function: str | None = Field(
        None, description="Logical operation: 'and', 'or', or 'one'."
    )
    invert: bool | None = Field(None, description='Whether the result set is inverted.')
    name: str | None = Field(None, description='Name of the custom filter.')
    rules: list[FilterRule] | None = Field(
        None, description='Rules that make up this filter.'
    )


class FilterRuleDescription(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    category: str | None = Field(None, description='Category of the filter rule.')
    description: str | None = Field(
        None, description='Long description of what the rule matches.'
    )
    labels: list[str] | None = Field(
        None, description="Labels for the rule's parameter fields."
    )
    name: str | None = Field(None, description='Display name of the rule.')
    rule: str | None = Field(None, description='Internal rule class name.')


class NamespaceFilters(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    filters: list[CustomFilter] | None = Field(
        None, description='Custom filters defined for this namespace.'
    )
    rules: list[FilterRuleDescription] | None = Field(
        None, description='All available built-in filter rules for this namespace.'
    )


class Rule(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    name: constr(min_length=1) = Field(
        ..., description="Rule class name (e.g. 'HasTag', 'MatchIdOf')."
    )
    values: list[Any] | None = Field(None, description='Parameter values for the rule.')
    regex: bool | None = Field(
        False, description='If true, treat text values as regular expressions.'
    )


class Function(Enum):
    and_ = 'and'
    or_ = 'or'
    one = 'one'


class Namespace1(Enum):
    Person = 'Person'
    Family = 'Family'
    Event = 'Event'
    Place = 'Place'
    Citation = 'Citation'
    Source = 'Source'
    Repository = 'Repository'
    Media = 'Media'
    Note = 'Note'


class CustomFilterCreate(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    function: Function | None = Field(
        'and',
        description="Logical operation applied across rules: 'and', 'or', or 'one'.",
    )
    invert: bool | None = Field(
        False, description='If true, invert the filter result set.'
    )
    namespace: Namespace1 | None = Field(
        None,
        description='If set on a nested sub-filter, evaluate it in this namespace and bridge results back to the parent namespace. Supported bridges: Event→Place, Person→Event, Person→Family, Family→Event, Family→Person, Citation→Source, Source→Repository.',
    )
    rules: list[Rule] = Field(..., description='List of rule specs.', min_length=1)
    name: constr(min_length=1) = Field(
        ..., description='Unique name for this custom filter.'
    )
    comment: str | None = Field(
        None, description='Optional comment describing the purpose of the filter.'
    )


class Translation(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    original: str | None = Field(None, description='The original (English) string.')
    translation: str | None = Field(None, description='The translated string.')


class TranslationPostArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    strings: list[str] = Field(..., description='The string(s) to translate.')


class Language(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    current: str | None = Field(
        None, description='Language name in the current locale.'
    )
    default: str | None = Field(
        None, description='Language name in the default (English) locale.'
    )
    language: str | None = Field(None, description="Language code (e.g. 'bg', 'de').")
    native: str | None = Field(
        None, description='Language name in its own native locale.'
    )


class DnaMatchParserBodyArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    string: str = Field(..., description='The raw DNA match data string to parse.')


class Relationship(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    relationship_string: str | None = Field(
        None, description='Human-readable relationship description.'
    )
    distance_common_origin: int | None = Field(
        None,
        description='Generations from person 1 to the common ancestor (-1 if none).',
    )
    distance_common_other: int | None = Field(
        None,
        description='Generations from person 2 to the common ancestor (-1 if none).',
    )


class RelationshipItem(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    relationship_string: str | None = Field(
        None, description='Human-readable relationship description.'
    )
    common_ancestors: list[str] | None = Field(
        None, description='Handles of common ancestors.'
    )


class Date(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    calendar: int | None = Field(None, description='The calendar format for the date.')
    dateval: list[Any] | None = Field(
        None, description='Mixed array of integers and booleans.'
    )
    modifier: int | None = Field(
        None, description='Date modifier (e.g. before/after/about).'
    )
    newyear: int | None = Field(None, description='Alternate new-year start.')
    quality: int | None = Field(None, description='Quality / confidence of the date.')
    sortval: int | None = Field(None, description='Value used for date sorting.')
    text: str | None = Field(None, description='Textual representation of the date.')
    year: int | None = Field(None, description='Year component of the date.')


class Address(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this address.'
    )
    city: str | None = Field(None, description='City.')
    country: str | None = Field(None, description='Country.')
    county: str | None = Field(None, description='County.')
    date: Date | None = Field(
        None, description='Date the person resided at this address.'
    )
    locality: str | None = Field(None, description='Locality.')
    note_list: list[str] | None = Field(
        None, description='Handles of research notes about this address.'
    )
    phone: str | None = Field(None, description='Phone number.')
    postal: str | None = Field(None, description='Postal code.')
    private: bool | None = Field(None, description='Private object indicator.')
    state: str | None = Field(None, description='State.')
    street: str | None = Field(None, description='Street address.')


class Surname(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    connector: str | None = Field(
        None, description='Connector word between given name and surname.'
    )
    origintype: str | None = Field(
        None, description="Name origin type (e.g. 'Inherited')."
    )
    prefix: str | None = Field(None, description="Surname prefix (e.g. 'von', 'de').")
    primary: bool | None = Field(
        None, description='Whether this is the primary surname.'
    )
    surname: str | None = Field(None, description='The surname text.')


class Name(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    call: str | None = Field(
        None, description='Call name (the name by which the person is known).'
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this name.'
    )
    date: Date | None = Field(
        None, description='Period during which this name was in use.'
    )
    display_as: int | None = Field(
        None, description='Identifier for how to display the name.'
    )
    famnick: str | None = Field(None, description='Family nickname.')
    first_name: str | None = Field(None, description='Given (first) name.')
    group_as: str | None = Field(None, description='Override for grouping this name.')
    nick: str | None = Field(None, description='Nickname.')
    note_list: list[str] | None = Field(
        None, description='Handles of research notes about this name.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    sort_as: int | None = Field(
        None, description='Identifier for how to sort the name.'
    )
    suffix: str | None = Field(None, description="Name suffix (e.g. 'Sr', 'Jr').")
    surname_list: list[Surname] | None = Field(
        None, description='List of surname components.'
    )
    title: str | None = Field(
        None, description="Name title or prefix (e.g. 'Dr.', 'Rev.')."
    )
    type: str | None = Field(
        None, description="Type of name (e.g. 'Birth Name', 'Also Known As')."
    )


class Attribute(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this attribute.'
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes about this attribute.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    type: str | None = Field(None, description='Type of the attribute.')
    value: str | None = Field(None, description='Value of the attribute.')


class Backlinks(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    person: list[str] | None = Field(
        None, description='Handles of people referring to this object.'
    )
    family: list[str] | None = Field(
        None, description='Handles of families referring to this object.'
    )
    event: list[str] | None = Field(
        None, description='Handles of events referring to this object.'
    )
    place: list[str] | None = Field(
        None, description='Handles of places referring to this object.'
    )
    source: list[str] | None = Field(
        None, description='Handles of sources referring to this object.'
    )
    citation: list[str] | None = Field(
        None, description='Handles of citations referring to this object.'
    )
    media: list[str] | None = Field(
        None, description='Handles of media items referring to this object.'
    )


class EventReference(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    attribute_list: list[Attribute] | None = Field(
        None, description="Attributes related to the person's role in the event."
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes about this participation.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    ref: str | None = Field(None, description='Handle of the referenced event.')
    role: str | None = Field(
        None, description='Role of the person or family in the event.'
    )


class LDSOrdination(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this LDS event.'
    )
    date: Date | None = Field(None, description='Date of the ordinance.')
    famc: str | None = Field(
        None, description='Handle of the family associated with this ordinance.'
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes about this ordinance.'
    )
    place: str | None = Field(
        None, description='Handle of the place where the ordinance was performed.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    status: int | None = Field(None, description='Status code of the ordinance.')
    temple: str | None = Field(
        None, description='Temple where the ordinance was performed.'
    )
    type: int | None = Field(None, description='Type code of the ordinance.')


class MediaReference(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    attribute_list: list[Attribute] | None = Field(
        None, description='Attributes related to this media reference.'
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this media reference.'
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes about this media reference.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    rect: list[float] | None = Field(
        None, description='Crop rectangle [left, top, right, bottom] as percentages.'
    )
    ref: str | None = Field(None, description='Handle of the referenced media object.')


class PersonReference(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this association.'
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes about this association.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    ref: str | None = Field(None, description='Handle of the referenced person.')
    rel: str | None = Field(
        None, description='Relationship type between the two people.'
    )


class URL(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    desc: str | None = Field(None, description='Description of the URL.')
    path: str | None = Field(None, description='The URL itself.')
    private: bool | None = Field(None, description='Private object indicator.')
    type: str | None = Field(None, description="Type of URL (e.g. 'Web Home').")


class Living(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    living: bool | None = Field(
        None, description='True if the person is estimated to be alive.'
    )


class Report(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    authors: list[str] | None = Field(None, description='Report author names.')
    authors_email: list[str] | None = Field(
        None, description='Email addresses of report authors.'
    )
    category: int | None = Field(None, description='Report category code.')
    description: str | None = Field(None, description='Description of the report.')
    id: str | None = Field(None, description='Report identifier.')
    name: str | None = Field(None, description='Display name of the report.')
    options_dict: dict[str, Any] | None = Field(
        None, description='All report options with their default values.'
    )
    options_help: dict[str, Any] | None = Field(
        None, description='Help information for all report options.'
    )
    report_modes: list[int] | None = Field(
        None, description='Supported report output modes.'
    )
    version: str | None = Field(None, description='Version of the report plugin.')


class RecordFactObject(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier.'
    )
    handle: str | None = Field(None, description='Unique handle for the object.')
    name: str | None = Field(None, description='Description of the object.')
    object: str | None = Field(None, description="Object type (e.g. 'Person').")
    value: str | None = Field(None, description='Value supporting the fact.')


class RecordFact(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    description: str | None = Field(
        None, description='Human-readable description of the fact.'
    )
    key: str | None = Field(None, description='Unique identifier for the fact type.')
    objects: list[RecordFactObject] | None = Field(
        None, description='Objects the fact is about.'
    )


class Exporter(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    description: str | None = Field(
        None, description='Description of the export format and its use.'
    )
    extension: str | None = Field(
        None, description='Default file extension for this format.'
    )
    module: str | None = Field(None, description='Plugin module name.')


class Importer(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    description: str | None = Field(
        None, description='Description of the import format and its use.'
    )
    extension: str | None = Field(
        None, description='File extension this importer handles.'
    )
    module: str | None = Field(None, description='Plugin module name.')


class ObjectCounts(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    citations: float | None = Field(None, description='Number of citations.')
    events: float | None = Field(None, description='Number of events.')
    families: float | None = Field(None, description='Number of families.')
    media: float | None = Field(None, description='Number of media objects.')
    notes: float | None = Field(None, description='Number of notes.')
    people: float | None = Field(None, description='Number of people.')
    places: float | None = Field(None, description='Number of places.')
    repositories: float | None = Field(None, description='Number of repositories.')
    sources: float | None = Field(None, description='Number of sources.')
    tags: float | None = Field(None, description='Number of tags.')


class Researcher(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    addr: str | None = Field(None, description='Address.')
    city: str | None = Field(None, description='City.')
    country: str | None = Field(None, description='Country.')
    county: str | None = Field(None, description='County.')
    email: str | None = Field(None, description='Email address.')
    locality: str | None = Field(None, description='Locality.')
    name: str | None = Field(None, description='Name of the researcher.')
    phone: str | None = Field(None, description='Phone number.')
    postal: str | None = Field(None, description='Postal code.')
    state: str | None = Field(None, description='State.')
    street: str | None = Field(None, description='Street address.')


class Metadata(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    database: dict[str, Any] | None = Field(
        None, description='Information about the active database.'
    )
    default_person: str | None = Field(
        None, description='Handle of the default person.'
    )
    gramps: dict[str, Any] | None = Field(
        None, description='Information about the active Gramps installation.'
    )
    gramps_webapi: dict[str, Any] | None = Field(
        None, description='Information about the Gramps Web API version.'
    )
    gramps_ql: dict[str, Any] | None = Field(
        None, description='Information about the Gramps QL library.'
    )
    object_ql: dict[str, Any] | None = Field(
        None, description='Information about the Object QL library.'
    )
    locale: dict[str, Any] | None = Field(
        None, description='Information about the active locale.'
    )
    object_counts: ObjectCounts | None = Field(
        None, description='Counts of primary object types.'
    )
    researcher: Researcher | None = Field(
        None, description='Information about the primary researcher.'
    )
    search: dict[str, Any] | None = Field(
        None, description='Information about search-related libraries.'
    )
    server: dict[str, Any] | None = Field(
        None, description='Information about server capabilities.'
    )
    surnames: list[str] | None = Field(
        None, description='All surnames found in the database (when requested).'
    )


class ResearcherUpdate(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    addr: str | None = Field(None, description='Address.')
    city: str | None = Field(None, description='City.')
    country: str | None = Field(None, description='Country.')
    county: str | None = Field(None, description='County.')
    email: str | None = Field(None, description='Email address.')
    locality: str | None = Field(None, description='Locality.')
    name: str | None = Field(None, description='Name of the researcher.')
    phone: str | None = Field(None, description='Phone number.')
    postal: str | None = Field(None, description='Postal code.')
    state: str | None = Field(None, description='State.')
    street: str | None = Field(None, description='Street address.')


class UserPostBodyArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    email: str = Field(..., description="The user's e-mail address.")
    full_name: str = Field(..., description="The user's full name.")
    password: str = Field(..., description="The user's password.")
    role: int = Field(..., description='Integer user role ID.')
    tree: str | None = Field(None, description='Tree ID the user belongs to.')


class UserPutBodyArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    email: str | None = Field(None, description="The user's e-mail address.")
    full_name: str | None = Field(None, description="The user's full name.")
    name_new: str | None = Field(
        None, description='New username when renaming the user.'
    )
    role: int | None = Field(None, description='Integer user role ID.')
    tree: str | None = Field(None, description='Tree ID the user belongs to.')


class UserRegisterBodyArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    email: str = Field(..., description="The user's e-mail address.")
    full_name: str = Field(..., description="The user's full name.")
    password: str = Field(..., description="The user's password.")
    tree: str | None = Field(None, description='Tree ID the user belongs to.')


class UserCreateOwnerBodyArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    email: str = Field(..., description="The user's e-mail address.")
    full_name: str = Field(..., description="The user's full name.")
    password: str = Field(..., description="The user's password.")
    tree: str | None = Field(None, description='Tree ID the user belongs to.')


class UserChangePasswordBodyArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    old_password: str = Field(..., description='The current (old) password.')
    new_password: str = Field(..., description='The new password.')


class UserResetPasswordBodyArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    new_password: str = Field(..., description='The new password.')


class SearchResult(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    handle: str | None = Field(None, description='Handle of the matching object.')
    object: Any | None = Field(None, description='The matching object data.')
    object_type: str | None = Field(
        None, description="Type of the matching object (e.g. 'person')."
    )
    score: float | None = Field(None, description='Relevance score.')


class ChatMessage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    role: str = Field(
        ...,
        description="Role of the message sender: one of 'human', 'ai', 'system', 'assistant', or 'error'.",
    )
    message: str = Field(..., description='The message content.')


class ChatBodyArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    query: str = Field(..., description='The chat prompt to answer.')
    history: list[ChatMessage] | None = Field(
        None,
        description='Optional list of prior conversation messages ({role, message}).',
    )
    message_history_raw: constr(max_length=1000000) | None = Field(
        None,
        description="Serialized message history from a previous response's message_history_raw field. Preserves full tool call context across turns. Takes precedence over history when both are provided.",
    )


class ChatResponse(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    response: str | None = Field(None, description="The assistant's answer.")
    metadata: dict[str, Any] | None = Field(
        None, description='Optional execution metadata (included when verbose=true).'
    )
    message_history_raw: str | None = Field(
        None,
        description='Serialized full message history for multi-turn conversations. Pass back in subsequent requests as message_history_raw to preserve tool call context.',
    )


class ConfigValueArgs(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    value: str = Field(..., description='The new value for the configuration setting.')


class TaskListItem(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    task_id: str | None = Field(None, description='The Celery task UUID.')
    name: str | None = Field(
        None, description="Celery task function name, e.g. 'import_file'."
    )
    created_at: AwareDatetime | None = Field(
        None, description='UTC timestamp when the task was dispatched.'
    )
    user_id: str | None = Field(
        None, description='UUID of the user who dispatched the task.'
    )
    user_name: str | None = Field(
        None, description='Username of the user who dispatched the task.'
    )
    state: str | None = Field(
        None,
        description="The current task state (e.g. 'PENDING', 'STARTED', 'SUCCESS', 'FAILURE'). Only populated when include_state=true.",
    )


class TaskStatus(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: str | None = Field(
        None,
        description="The current task state (e.g. 'PENDING', 'STARTED', 'SUCCESS', 'FAILURE').",
    )
    result_object: Any | None = Field(
        None, description='The task result object if available.'
    )
    info: str | None = Field(None, description='Human-readable status information.')
    result: str | None = Field(None, description='The task result as a string.')
    task_id: str | None = Field(None, description='The Celery task UUID.')
    name: str | None = Field(
        None, description="Celery task function name, e.g. 'import_file'."
    )
    created_at: AwareDatetime | None = Field(
        None, description='UTC timestamp when the task was dispatched.'
    )
    user_id: str | None = Field(
        None, description='UUID of the user who dispatched the task.'
    )
    user_name: str | None = Field(
        None, description='Username of the user who dispatched the task.'
    )


class SourceProfile(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    author: str | None = Field(None, description='Author of the source.')
    pubinfo: str | None = Field(None, description='Publication information.')
    title: str | None = Field(None, description='Title of the source.')
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier for the source.'
    )
    references: dict[str, Any] | None = Field(
        None, description='References to this source from other objects.'
    )


class CitationProfile(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    date: str | None = Field(
        None, description='Date of the citation as a formatted string.'
    )
    page: str | None = Field(None, description='Page cited from.')
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier for the citation.'
    )
    source: SourceProfile | None = Field(
        None, description='Profile of the cited source.'
    )
    references: dict[str, Any] | None = Field(
        None, description='References to this citation from other objects.'
    )


class Citation(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    field_class: str | None = Field(
        None, alias='_class', description="Object class name; must be 'Citation'."
    )
    attribute_list: list[Attribute] | None = Field(
        None, description='Attributes about this citation.'
    )
    backlinks: Backlinks | None = Field(
        None, description='Objects referring to this citation, grouped by type.'
    )
    change: float | None = Field(
        None, description='Unix timestamp of the last modification.'
    )
    confidence: int | None = Field(
        None, description='Confidence level of the information cited (0–4).'
    )
    date: Date | None = Field(None, description='Date of the citation.')
    extended: Any | None = Field(
        None, description='Optional extended section with full referenced records.'
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier.'
    )
    handle: str | None = Field(None, description='Unique handle for the citation.')
    media_list: list[MediaReference] | None = Field(
        None, description='Media references associated with this citation.'
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes related to this citation.'
    )
    page: str | None = Field(None, description='Page or location within the source.')
    private: bool | None = Field(None, description='Private object indicator.')
    profile: CitationProfile | None = Field(
        None, description='Optional summary of citation information.'
    )
    source_handle: str | None = Field(
        None, description='Handle of the source being cited.'
    )
    tag_list: list[str] | None = Field(
        None, description='Handles of tags attached to this citation.'
    )


class Event(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    field_class: str | None = Field(
        None, alias='_class', description="Object class name; must be 'Event'."
    )
    attribute_list: list[Attribute] | None = Field(
        None, description='Attributes about this event.'
    )
    backlinks: Backlinks | None = Field(
        None, description='Objects referring to this event, grouped by type.'
    )
    change: float | None = Field(
        None, description='Unix timestamp of the last modification.'
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this event.'
    )
    date: Date | None = Field(None, description='Date of the event.')
    description: str | None = Field(None, description='Description of the event.')
    extended: Any | None = Field(
        None, description='Optional extended section with full referenced records.'
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier.'
    )
    handle: str | None = Field(None, description='Unique handle for the event.')
    media_list: list[MediaReference] | None = Field(
        None, description='Media references associated with this event.'
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes related to this event.'
    )
    place: str | None = Field(
        None, description='Handle of the place where the event occurred.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    profile: EventProfile | None = Field(
        None, description='Optional summary of event information.'
    )
    tag_list: list[str] | None = Field(
        None, description='Handles of tags attached to this event.'
    )
    type: str | None = Field(
        None, description="Type of event (e.g. 'Birth', 'Marriage')."
    )


class ChildReference(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this child reference.'
    )
    frel: str | None = Field(
        None, description='Relationship between the child and the father.'
    )
    mrel: str | None = Field(
        None, description='Relationship between the child and the mother.'
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes about this child reference.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    ref: str | None = Field(
        None, description='Handle of the referenced child (person).'
    )


class MediaProfile(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    date: str | None = Field(
        None, description='Date of the media item as a formatted string.'
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier for the media object.'
    )
    references: dict[str, Any] | None = Field(
        None, description='References to this media item from other objects.'
    )


class Media(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    field_class: str | None = Field(
        None, alias='_class', description="Object class name; must be 'Media'."
    )
    attribute_list: list[Attribute] | None = Field(
        None, description='Attributes of the media object.'
    )
    backlinks: Backlinks | None = Field(
        None, description='Objects referring to this media item, grouped by type.'
    )
    change: float | None = Field(
        None, description='Unix timestamp of the last modification.'
    )
    checksum: str | None = Field(
        None, description='Checksum for file integrity validation.'
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this media object.'
    )
    date: Date | None = Field(
        None, description='Date associated with the media object.'
    )
    desc: str | None = Field(
        None, description='Description of the media object content.'
    )
    extended: Any | None = Field(
        None, description='Optional extended section with full referenced records.'
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier.'
    )
    handle: str | None = Field(None, description='Unique handle for the media object.')
    mime: str | None = Field(
        None, description="MIME type of the file (e.g. 'image/jpeg')."
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes related to this media object.'
    )
    path: str | None = Field(None, description='Storage path to locate the media file.')
    private: bool | None = Field(None, description='Private object indicator.')
    profile: MediaProfile | None = Field(
        None, description='Optional summary of media information.'
    )
    tag_list: list[str] | None = Field(
        None, description='Handles of tags attached to this media object.'
    )


class StyledTextTag(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    name: str | None = Field(
        None, description="Name of the tag (e.g. 'Bold', 'Italic')."
    )
    value: Any | None = Field(
        None, description='Value of the tag; may be null, string, or integer.'
    )
    ranges: list[list[int]] | None = Field(
        None, description='List of [start, end] character-offset pairs.'
    )


class StyledText(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    string: str | None = Field(None, description='The plain text content.')
    tags: list[StyledTextTag] | None = Field(
        None, description='List of formatting tags applied to spans of the text.'
    )


class Note(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    field_class: str | None = Field(
        None, alias='_class', description="Object class name; must be 'Note'."
    )
    backlinks: Backlinks | None = Field(
        None, description='Objects referring to this note, grouped by type.'
    )
    change: float | None = Field(
        None, description='Unix timestamp of the last modification.'
    )
    extended: Any | None = Field(
        None, description='Optional extended section with full referenced records.'
    )
    format: int | None = Field(
        None, description='Format identifier (0=plain text, 1=pre-formatted).'
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier.'
    )
    handle: str | None = Field(None, description='Unique handle for the note.')
    private: bool | None = Field(None, description='Private object indicator.')
    tag_list: list[str] | None = Field(
        None, description='Handles of tags attached to this note.'
    )
    text: StyledText | None = Field(
        None, description='The note text with optional inline formatting.'
    )
    type: str | None = Field(
        None, description="Type of note (e.g. 'Source text', 'General')."
    )


class Location(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    city: str | None = Field(None, description='City.')
    country: str | None = Field(None, description='Country.')
    county: str | None = Field(None, description='County.')
    locality: str | None = Field(None, description='Locality.')
    parish: str | None = Field(None, description='Parish.')
    phone: str | None = Field(None, description='Phone number.')
    postal: str | None = Field(None, description='Postal code.')
    state: str | None = Field(None, description='State.')
    street: str | None = Field(None, description='Street address.')


class PlaceName(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    date: Date | None = Field(
        None, description='Period during which this name was in use.'
    )
    lang: str | None = Field(None, description='Language the name is in.')
    value: str | None = Field(None, description='The place name text.')


class PlaceReference(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    date: Date | None = Field(None, description='Date of the place reference.')
    ref: str | None = Field(None, description='Handle of the referenced place.')


class Place(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    field_class: str | None = Field(
        None, alias='_class', description="Object class name; must be 'Place'."
    )
    alt_loc: list[Location] | None = Field(
        None, description='Alternate location descriptions for this place.'
    )
    alt_names: list[PlaceName] | None = Field(
        None, description='Alternate names for this place.'
    )
    backlinks: Backlinks | None = Field(
        None, description='Objects referring to this place, grouped by type.'
    )
    change: float | None = Field(
        None, description='Unix timestamp of the last modification.'
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this place.'
    )
    code: str | None = Field(None, description='Place code (e.g. postal code).')
    extended: Any | None = Field(
        None, description='Optional extended section with full referenced records.'
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier.'
    )
    handle: str | None = Field(None, description='Unique handle for the place.')
    lat: str | None = Field(None, description='Latitude as a decimal string.')
    long: str | None = Field(None, description='Longitude as a decimal string.')
    media_list: list[MediaReference] | None = Field(
        None, description='Media references associated with this place.'
    )
    name: PlaceName | None = Field(None, description='Primary name of the place.')
    note_list: list[str] | None = Field(
        None, description='Handles of research notes related to this place.'
    )
    place_type: str | None = Field(
        None, description="Type of place (e.g. 'City', 'Country')."
    )
    placeref_list: list[PlaceReference] | None = Field(
        None, description='References to parent places.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    profile: PlaceProfile | None = Field(
        None, description='Optional summary of place information.'
    )
    tag_list: list[str] | None = Field(
        None, description='Handles of tags attached to this place.'
    )
    title: str | None = Field(
        None, description="Full place title (e.g. 'Twin Falls, ID, USA')."
    )
    urls: list[URL] | None = Field(None, description='URLs associated with this place.')


class Repository(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    field_class: str | None = Field(
        None, alias='_class', description="Object class name; must be 'Repository'."
    )
    address_list: list[Address] | None = Field(
        None, description='Addresses of the repository.'
    )
    backlinks: Backlinks | None = Field(
        None, description='Objects referring to this repository, grouped by type.'
    )
    change: float | None = Field(
        None, description='Unix timestamp of the last modification.'
    )
    extended: Any | None = Field(
        None, description='Optional extended section with full referenced records.'
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier.'
    )
    handle: str | None = Field(None, description='Unique handle for the repository.')
    name: str | None = Field(None, description='Name of the repository.')
    note_list: list[str] | None = Field(
        None, description='Handles of research notes related to this repository.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    tag_list: list[str] | None = Field(
        None, description='Handles of tags attached to this repository.'
    )
    type: str | None = Field(
        None, description="Type of repository (e.g. 'Library', 'Archive')."
    )
    urls: list[URL] | None = Field(
        None, description='URLs associated with this repository.'
    )


class RepositoryReference(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    call_number: str | None = Field(
        None, description='Call number for the source at the repository.'
    )
    media_type: str | None = Field(
        None, description='Media format of the source at the repository.'
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes about this repository reference.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    ref: str | None = Field(None, description='Handle of the referenced repository.')


class Source(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    field_class: str | None = Field(
        None, alias='_class', description="Object class name; must be 'Source'."
    )
    abbrev: str | None = Field(None, description='Abbreviated name for the source.')
    attribute_list: list[Attribute] | None = Field(
        None, description='Attributes about the source.'
    )
    author: str | None = Field(None, description='Author of the source.')
    backlinks: Backlinks | None = Field(
        None, description='Objects referring to this source, grouped by type.'
    )
    change: float | None = Field(
        None, description='Unix timestamp of the last modification.'
    )
    extended: Any | None = Field(
        None, description='Optional extended section with full referenced records.'
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier.'
    )
    handle: str | None = Field(None, description='Unique handle for the source.')
    media_list: list[MediaReference] | None = Field(
        None, description='Media references associated with this source.'
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes related to this source.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    profile: SourceProfile | None = Field(
        None, description='Optional summary of source information.'
    )
    pubinfo: str | None = Field(None, description='Publication information.')
    reporef_list: list[RepositoryReference] | None = Field(
        None, description='References to repositories holding this source.'
    )
    tag_list: list[str] | None = Field(
        None, description='Handles of tags attached to this source.'
    )
    title: str | None = Field(None, description='Title of the source.')


class Tag(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    field_class: str | None = Field(
        None, alias='_class', description="Object class name; must be 'Tag'."
    )
    change: float | None = Field(
        None, description='Unix timestamp of the last modification.'
    )
    color: str | None = Field(None, description='Colour of the tag as a hex string.')
    handle: str | None = Field(None, description='Unique handle for the tag.')
    name: str | None = Field(None, description='Tag name.')
    priority: int | None = Field(None, description='Display priority of the tag.')


class FamilyProfile(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    children: list[PersonProfile] | None = Field(
        None, description='Profiles of children in the family.'
    )
    divorce: EventProfile | None = Field(
        None, description='Divorce event profile (or best available fallback).'
    )
    events: list[EventProfile] | None = Field(
        None, description='All event profiles for this family.'
    )
    family_surname: str | None = Field(
        None, description='Surname of the family (from father, or mother if no father).'
    )
    father: PersonProfile | None = Field(None, description='Profile of the father.')
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier for the family.'
    )
    handle: str | None = Field(None, description='Unique handle for the family.')
    marriage: EventProfile | None = Field(
        None, description='Marriage event profile (or best available fallback).'
    )
    mother: PersonProfile | None = Field(None, description='Profile of the mother.')
    references: dict[str, Any] | None = Field(
        None, description='References to this family from other objects.'
    )
    relationship: str | None = Field(
        None, description='Type of relationship between the parents.'
    )


class PersonProfile(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    birth: EventProfile | None = Field(
        None, description='Birth event profile (or best available fallback).'
    )
    death: EventProfile | None = Field(
        None, description='Death event profile (or best available fallback).'
    )
    events: list[EventProfile] | None = Field(
        None, description='All event profiles for this person.'
    )
    families: list[FamilyProfile] | None = Field(
        None, description='Profiles of families this person is a parent of.'
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier for the person.'
    )
    handle: str | None = Field(None, description='Unique handle for the person.')
    name_display: str | None = Field(None, description='Full display name.')
    name_given: str | None = Field(None, description='Given (first) name.')
    name_surname: str | None = Field(None, description='Surname.')
    name_suffix: str | None = Field(None, description='Name suffix.')
    other_parent_families: list[FamilyProfile] | None = Field(
        None, description='Profiles of non-primary parent families.'
    )
    primary_parent_family: FamilyProfile | None = Field(
        None, description='Profile of the primary parent family.'
    )
    references: dict[str, Any] | None = Field(
        None, description='References to this person from other objects.'
    )
    sex: str | None = Field(
        None, description="Sex of the person ('M', 'F', 'X', or 'U')."
    )


class DnaMatch(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    handle: str | None = Field(None, description='Handle of the matching person.')
    relation: str | None = Field(
        None, description='Estimated relationship to the matching person.'
    )
    ancestor_handles: list[str] | None = Field(
        None, description='Handles of latest common ancestors.'
    )
    ancestor_profiles: list[list[PersonProfile]] | None = Field(
        None, description='Profiles of latest common ancestors.'
    )
    segments: list[DnaSegment] | None = Field(
        None, description='Details of each matching chromosome segment.'
    )
    person_ref_idx: int | None = Field(
        None, description="Index into the person's person_ref_list for this match."
    )
    note_handles: list[str] | None = Field(
        None, description="Handles of notes associated with the match's segments."
    )
    raw_data: list[str] | None = Field(
        None, description='Raw note strings containing segment data.'
    )


class Person(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    field_class: str | None = Field(
        None, alias='_class', description="Object class name; must be 'Person'."
    )
    address_list: list[Address] | None = Field(
        None, description='Addresses associated with this person.'
    )
    alternate_names: list[Name] | None = Field(
        None, description='Alternate names used by this person.'
    )
    attribute_list: list[Attribute] | None = Field(
        None, description='Attributes about this person.'
    )
    backlinks: Backlinks | None = Field(
        None, description='Objects referring to this person, grouped by type.'
    )
    birth_ref_index: int | None = Field(
        None, description='Index into event_ref_list for the birth event, or -1.'
    )
    change: float | None = Field(
        None, description='Unix timestamp of the last modification.'
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this person.'
    )
    death_ref_index: int | None = Field(
        None, description='Index into event_ref_list for the death event, or -1.'
    )
    event_ref_list: list[EventReference] | None = Field(
        None, description='References to events this person participated in.'
    )
    extended: Any | None = Field(
        None, description='Optional extended section with full referenced records.'
    )
    family_list: list[str] | None = Field(
        None, description='Handles of families this person is a parent of.'
    )
    gender: int | None = Field(
        None, description='Gender code (0=female, 1=male, 2=unknown, 3=other).'
    )
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier.'
    )
    handle: str | None = Field(None, description='Unique handle for the person.')
    lds_ord_list: list[LDSOrdination] | None = Field(
        None, description='LDS ordinance events for this person.'
    )
    media_list: list[MediaReference] | None = Field(
        None, description='Media references associated with this person.'
    )
    note_list: list[str] | None = Field(
        None, description='Handles of research notes related to this person.'
    )
    parent_family_list: list[str] | None = Field(
        None, description='Handles of families this person is a child of.'
    )
    person_ref_list: list[PersonReference] | None = Field(
        None,
        description='References to other people this person has a relationship with.',
    )
    primary_name: Name | None = Field(None, description='Primary name of this person.')
    private: bool | None = Field(None, description='Private object indicator.')
    profile: PersonProfile | None = Field(
        None, description='Optional summary of key biographical information.'
    )
    tag_list: list[str] | None = Field(
        None, description='Handles of tags attached to this person.'
    )
    urls: list[URL] | None = Field(
        None, description='URLs associated with this person.'
    )


class LivingDates(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    birth: str | None = Field(None, description='Estimated birth date.')
    death: str | None = Field(None, description='Estimated death date.')
    explain: str | None = Field(
        None, description='Explanation of how the dates were determined.'
    )
    other: Person | None = Field(
        None, description='Related person record used in the estimation.'
    )


class Family(BaseModel):
    model_config = ConfigDict(
        extra='allow',
    )
    field_class: str | None = Field(
        None, alias='_class', description="Object class name; must be 'Family'."
    )
    attribute_list: list[Attribute] | None = Field(
        None, description='Attributes about this family.'
    )
    backlinks: Backlinks | None = Field(
        None, description='Objects referring to this family, grouped by type.'
    )
    change: float | None = Field(
        None, description='Unix timestamp of the last modification.'
    )
    child_ref_list: list[ChildReference] | None = Field(
        None, description='References to children in this family.'
    )
    citation_list: list[str] | None = Field(
        None, description='Handles of citations supporting this family.'
    )
    event_ref_list: list[EventReference] | None = Field(
        None, description='References to events the family participated in.'
    )
    extended: Any | None = Field(
        None, description='Optional extended section with full referenced records.'
    )
    father_handle: str | None = Field(None, description='Handle of the father.')
    gramps_id: str | None = Field(
        None, description='Alternate user-managed identifier.'
    )
    handle: str | None = Field(None, description='Unique handle for the family.')
    lds_ord_list: list[LDSOrdination] | None = Field(
        None, description='LDS ordinance events for this family.'
    )
    media_list: list[MediaReference] | None = Field(
        None, description='Media references associated with this family.'
    )
    mother_handle: str | None = Field(None, description='Handle of the mother.')
    note_list: list[str] | None = Field(
        None, description='Handles of research notes related to this family.'
    )
    private: bool | None = Field(None, description='Private object indicator.')
    profile: FamilyProfile | None = Field(
        None, description='Optional summary of family information.'
    )
    tag_list: list[str] | None = Field(
        None, description='Handles of tags attached to this family.'
    )
    type: str | None = Field(
        None, description="Relationship type between the parents (e.g. 'Married')."
    )


PlaceProfile.model_rebuild()
FamilyProfile.model_rebuild()
