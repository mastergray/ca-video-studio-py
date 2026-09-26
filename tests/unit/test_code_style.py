import ast  # Inspect source structure without importing application modules
from pathlib import Path  # Traverse Python source files

SOURCE_ROOT = Path(__file__).parents[2] / "src"


def test_class_methods_and_attributes_follow_project_naming() -> None:
    for sourcePath in SOURCE_ROOT.rglob("*.py"):
        source = sourcePath.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert ast.get_docstring(tree, clean=False) is None, f"module docstring in {sourcePath}"

        lines = source.splitlines()
        for classNode in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
            for member in classNode.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not (member.name.startswith("__") and member.name.endswith("__")):
                    normalizedName = member.name.lstrip("_")
                    assert "_" not in normalizedName, f"snake_case method {classNode.name}.{member.name}"

                contextStart = max(0, member.lineno - 6)
                signatureContext = lines[contextStart : member.lineno - 1]
                assert any("::" in line and line.lstrip().startswith("#") for line in signatureContext), (
                    f"missing signature comment for {classNode.name}.{member.name}"
                )

                if member.name != "__init__":
                    continue
                for node in ast.walk(member):
                    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                        continue
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if not (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"
                        ):
                            continue
                        assert target.attr.startswith("_"), (
                            f"public instance attribute {classNode.name}.{target.attr}"
                        )
                        assert "_" not in target.attr[1:], (
                            f"snake_case instance attribute {classNode.name}.{target.attr}"
                        )
