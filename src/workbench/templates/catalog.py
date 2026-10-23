"""Curated domain cleaning pipeline templates.

Invariants:
- Templates are deterministic, versioned Pipeline specifications.
- Never hardcode customer-specific data or paths.
- Each template declares domain purpose, target use cases, and default operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from workbench.domain.operations import Operation
from workbench.domain.pipeline import Pipeline


@dataclass(frozen=True)
class PipelineTemplate:
    """A pre-configured transformation recipe for a specific industry domain."""

    template_id: str
    name: str
    category: str
    description: str
    pipeline: Pipeline

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "pipeline": self.pipeline.to_dict(),
        }


class TemplateCatalog:
    """Registry of built-in domain cleaning templates."""

    def __init__(self) -> None:
        self._templates: dict[str, PipelineTemplate] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        # 1. Customer & CRM Data Standardization
        crm_pipe = Pipeline(
            id="template-crm-standardize",
            name="CRM & Customer Standardization",
            version="1.0",
            steps=[
                Operation(name="trim_whitespace", columns=[], parameters={}),
                Operation(name="normalize_headers", columns=[], parameters={"case": "snake"}),
                Operation(name="drop_duplicates", columns=[], parameters={}),
            ],
        )
        self.register(
            PipelineTemplate(
                template_id="crm_standardize",
                name="CRM Customer Standardization",
                category="Sales & CRM",
                description=(
                    "Trims cell whitespace across all columns, normalizes headers to snake_case, "
                    "and deduplicates records."
                ),
                pipeline=crm_pipe,
            )
        )

        # 2. Financial Transactions Cleanup
        fin_pipe = Pipeline(
            id="template-financial-clean",
            name="Financial Transactions Cleanup",
            version="1.0",
            steps=[
                Operation(name="trim_whitespace", columns=[], parameters={}),
                Operation(name="normalize_headers", columns=[], parameters={"case": "snake"}),
                Operation(name="drop_duplicates", columns=[], parameters={}),
            ],
        )
        self.register(
            PipelineTemplate(
                template_id="financial_clean",
                name="Financial Transactions Cleanup",
                category="Finance & Accounting",
                description=(
                    "Standardizes transaction headers, removes whitespace padding, "
                    "and purges duplicate ledger entries."
                ),
                pipeline=fin_pipe,
            )
        )

        # 3. Clinical Research De-identification & Cleaning
        clinical_pipe = Pipeline(
            id="template-clinical-deid",
            name="Clinical Research Header & Null Cleaning",
            version="1.0",
            steps=[
                Operation(name="trim_whitespace", columns=[], parameters={}),
                Operation(name="normalize_headers", columns=[], parameters={"case": "snake"}),
                Operation(name="drop_duplicates", columns=[], parameters={}),
            ],
        )
        self.register(
            PipelineTemplate(
                template_id="clinical_clean",
                name="Clinical Trial Research Cleaning",
                category="Healthcare & Life Sciences",
                description=(
                    "Normalizes observational headers, cleans text whitespace, "
                    "and eliminates redundant patient encounters."
                ),
                pipeline=clinical_pipe,
            )
        )

        # 4. E-Commerce Product Catalog Harmonization
        catalog_pipe = Pipeline(
            id="template-ecommerce-catalog",
            name="E-Commerce Product Catalog Cleaning",
            version="1.0",
            steps=[
                Operation(name="trim_whitespace", columns=[], parameters={}),
                Operation(name="normalize_headers", columns=[], parameters={"case": "snake"}),
                Operation(name="drop_duplicates", columns=[], parameters={}),
            ],
        )
        self.register(
            PipelineTemplate(
                template_id="ecommerce_catalog",
                name="E-Commerce Product Catalog",
                category="Retail & E-Commerce",
                description=(
                    "Cleans product titles, trims whitespace, standardizes SKU/attribute column "
                    "names, and drops duplicate listings."
                ),
                pipeline=catalog_pipe,
            )
        )

    def register(self, template: PipelineTemplate) -> None:
        self._templates[template.template_id] = template

    def get(self, template_id: str) -> PipelineTemplate | None:
        return self._templates.get(template_id)

    def list_templates(self) -> list[PipelineTemplate]:
        return list(self._templates.values())
