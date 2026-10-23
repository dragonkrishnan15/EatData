"""Unit tests for AI recipe schema validator and code injection defense."""

import json

import pytest

from workbench.adapters.ai.recipe_schema import RecipeValidator
from workbench.domain.errors import InvalidRecipeError


def test_valid_recipe_parsing() -> None:
    validator = RecipeValidator()
    recipe_json = json.dumps(
        {
            "name": "Standard Clean",
            "version": "1.0",
            "steps": [
                {"name": "trim_whitespace", "columns": ["name", "city"]},
                {"name": "drop_duplicates", "columns": []},
                {
                    "name": "rename_column",
                    "columns": ["name"],
                    "parameters": {"new_name": "full_name"},
                },
            ],
        }
    )

    pipeline = validator.parse_and_validate(recipe_json)
    assert pipeline.name == "Standard Clean"
    assert len(pipeline.steps) == 3
    assert pipeline.steps[0].name == "trim_whitespace"
    assert pipeline.steps[1].name == "drop_duplicates"
    assert pipeline.steps[2].name == "rename_column"


def test_markdown_code_fence_stripping() -> None:
    validator = RecipeValidator()
    markdown_wrapped = """```json
    {
      "name": "Wrapped Recipe",
      "version": "1.0",
      "steps": [
        {"name": "trim_whitespace", "columns": []}
      ]
    }
    ```"""

    pipeline = validator.parse_and_validate(markdown_wrapped)
    assert pipeline.name == "Wrapped Recipe"
    assert len(pipeline.steps) == 1


def test_reject_unknown_operation() -> None:
    validator = RecipeValidator()
    malicious = {
        "name": "Bad Pipe",
        "steps": [
            {"name": "unauthorized_arbitrary_shell_call", "columns": []},
        ],
    }
    with pytest.raises(InvalidRecipeError, match="disallowed operation"):
        validator.parse_and_validate(malicious)


def test_reject_unauthorized_root_keys() -> None:
    validator = RecipeValidator()
    with pytest.raises(InvalidRecipeError, match="unauthorized root keys"):
        validator.parse_and_validate(
            {
                "name": "Pipe",
                "steps": [],
                "extra_unauthorized_field": "danger",
            }
        )


def test_reject_unauthorized_step_keys() -> None:
    validator = RecipeValidator()
    with pytest.raises(InvalidRecipeError, match="unauthorized keys"):
        validator.parse_and_validate(
            {
                "name": "Pipe",
                "steps": [
                    {
                        "name": "trim_whitespace",
                        "columns": [],
                        "malicious_hook": "do_something()",
                    }
                ],
            }
        )


@pytest.mark.parametrize(
    "code_snippet",
    [
        "import os; os.system('calc.exe')",
        "__import__('subprocess').call(['rm', '-rf', '/'])",
        "eval('2 + 2')",
        "exec('print(1)')",
        "lambda x: x + 1",
        "def exploit(): pass",
    ],
)
def test_reject_executable_code_patterns(code_snippet: str) -> None:
    validator = RecipeValidator()
    payload = {
        "name": "Injection Test",
        "steps": [
            {
                "name": "trim_whitespace",
                "columns": [code_snippet],
                "parameters": {},
            }
        ],
    }
    with pytest.raises(InvalidRecipeError, match="dangerous code pattern detected"):
        validator.parse_and_validate(payload)
