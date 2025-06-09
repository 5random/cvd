import ast
import io
import tokenize
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / 'program' / 'src'


def extract_comments(source: str) -> dict[int, str]:
    """Return a mapping of line numbers to inline comment text."""
    comments: dict[int, str] = {}
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            line = tok.start[0]
            text = tok.string.lstrip('#').strip()
            if text:
                comments[line] = text
    return comments

class ClassCollector(ast.NodeVisitor):
    """Collect classes with their bases, attributes, methods and docstrings."""

    def __init__(self):
        self.classes: dict[str, dict] = {}
        self.current_comments: dict[int, str] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)
        attrs: dict[str, str] = {}
        methods: list[dict[str, str]] = []
        class_doc = ast.get_docstring(node) or ""

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name.startswith("_") and item.name != "__init__":
                    continue
                m_doc = ast.get_docstring(item) or ""
                methods.append({
                    "name": item.name,
                    "doc": m_doc.splitlines()[0] if m_doc else "",
                })
                for stmt in ast.walk(item):
                    if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                        targets = []
                        if isinstance(stmt, ast.Assign):
                            targets = stmt.targets
                        else:
                            targets = [stmt.target]
                        for t in targets:
                            if (
                                isinstance(t, ast.Attribute)
                                and isinstance(t.value, ast.Name)
                                and t.value.id == "self"
                            ):
                                if isinstance(stmt, ast.AnnAssign) and stmt.annotation:
                                    annotation = ast.unparse(stmt.annotation)
                                else:
                                    annotation = ""
                                if isinstance(stmt, ast.Assign) and stmt.value:
                                    value = ast.unparse(stmt.value)
                                elif isinstance(stmt, ast.AnnAssign) and stmt.value:
                                    value = ast.unparse(stmt.value)
                                else:
                                    value = ""
                                comment = self.current_comments.get(stmt.lineno, "")
                                note = " ".join(
                                    filter(None, [annotation, value and f"= {value}", comment])
                                )
                                if not t.attr.startswith("_"):
                                    attrs[t.attr] = note
            elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        if isinstance(item, ast.AnnAssign) and item.annotation:
                            annotation = ast.unparse(item.annotation)
                        else:
                            annotation = ""
                        if isinstance(item, ast.Assign) and item.value:
                            value = ast.unparse(item.value)
                        elif isinstance(item, ast.AnnAssign) and item.value:
                            value = ast.unparse(item.value)
                        else:
                            value = ""
                        comment = self.current_comments.get(item.lineno, "")
                        note = " ".join(
                            filter(None, [annotation, value and f"= {value}", comment])
                        )
                        if not t.id.startswith("_"):
                            attrs[t.id] = note

        self.classes[node.name] = {
            "bases": [b for b in bases if b],
            "attrs": attrs,
            "methods": methods,
            "doc": class_doc.splitlines()[0] if class_doc else "",
        }

        # continue walking to support nested classes
        self.generic_visit(node)

def collect_classes():
    collector = ClassCollector()
    for py_file in SRC_DIR.rglob('*.py'):
        try:
            source = py_file.read_text()
            tree = ast.parse(source)
        except Exception:
            continue
        collector.current_comments = extract_comments(source)
        collector.visit(tree)
    return collector.classes


def generate_mermaid(classes: dict[str, dict]) -> str:
    lines = ["```mermaid", "classDiagram"]

    for cls in sorted(classes):
        info = classes[cls]
        if info.get("doc"):
            lines.append(f"    %% {info['doc']}")
        lines.append(f"    class {cls} {{")
        for attr, note in sorted(info["attrs"].items()):
            if note:
                lines.append(f"        %% {attr}: {note}")
            lines.append(f"        +{attr}")
        for method in sorted(info["methods"], key=lambda m: m["name"]):
            if method.get("doc"):
                lines.append(f"        %% {method['name']}: {method['doc']}")
            lines.append(f"        +{method['name']}()")
        lines.append("    }")

    for cls in sorted(classes):
        info = classes[cls]
        for base in info["bases"]:
            if base in classes:
                lines.append(f"    {base} <|-- {cls}")

    lines.append("```")
    return "\n".join(lines)

if __name__ == '__main__':
    classes = collect_classes()
    diagram = generate_mermaid(classes)
    print(diagram)
