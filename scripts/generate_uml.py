import ast
import os
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / 'program' / 'src'

class ClassCollector(ast.NodeVisitor):
    def __init__(self):
        self.classes = {}

    def visit_ClassDef(self, node):
        bases = [b.id if isinstance(b, ast.Name) else getattr(b, 'attr', None) for b in node.bases]
        self.classes[node.name] = [b for b in bases if b]
        self.generic_visit(node)

def collect_classes():
    collector = ClassCollector()
    for py_file in SRC_DIR.rglob('*.py'):
        try:
            tree = ast.parse(py_file.read_text())
        except Exception:
            continue
        collector.visit(tree)
    return collector.classes


def generate_mermaid(classes):
    lines = ['```mermaid', 'classDiagram']
    for cls in classes:
        lines.append(f"    class {cls}")
    for cls, bases in classes.items():
        for base in bases:
            if base in classes:
                lines.append(f"    {base} <|-- {cls}")
    lines.append('```')
    return '\n'.join(lines)

if __name__ == '__main__':
    classes = collect_classes()
    diagram = generate_mermaid(classes)
    print(diagram)
