from __future__ import annotations

from dataclasses import dataclass, field

from catalog_steward.tools import ToolSpec


def _object(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


@dataclass
class FixtureTools:
    calls: list[tuple[str, dict]] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)

    def echo(self, text: str) -> str:
        self.calls.append(("echo", {"text": text}))
        return text

    def add(self, a: int, b: int) -> dict:
        self.calls.append(("add", {"a": a, "b": b}))
        return {"sum": a + b}

    def fail(self) -> str:
        self.calls.append(("fail", {}))
        raise LookupError("fixture failed intentionally")

    def write_note(self, text: str) -> str:
        self.calls.append(("write_note", {"text": text}))
        self.writes.append(text)
        return "saved"

    @property
    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "echo",
                "Return text unchanged.",
                _object({"text": {"type": "string"}}, ["text"]),
                self.echo,
            ),
            ToolSpec(
                "add",
                "Add two integers.",
                _object({"a": {"type": "integer"}, "b": {"type": "integer"}}, ["a", "b"]),
                self.add,
            ),
            ToolSpec("fail", "Raise a test error.", _object({}, []), self.fail),
            ToolSpec(
                "write_note",
                "Save a note.",
                _object({"text": {"type": "string"}}, ["text"]),
                self.write_note,
                read_only=False,
            ),
        ]


def make_fixture_tools() -> FixtureTools:
    return FixtureTools()

