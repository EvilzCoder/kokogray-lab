"""Build responsive text diagrams without changing their copyable ASCII source."""

from html import escape
import re


DIAGRAM_TYPES = {"boxes", "sequence", "tree", "calculation", "bytes", "halves"}
BYTE = re.compile(r"\[([0-9a-fA-F]{2})\]")
EXPRESSION = re.compile(r"^([\w.()]+)\s*([:=])\s*([0-9a-fA-Fx]+(?:[ =]+[0-9a-fA-Fx]+)*)$")
RULE = re.compile(r"^\s*-{3,}\s*$")


def span(css, content, attributes=""):
    return f'<span class="{css}"{attributes}>{content}</span>'


def inline(text):
    return re.sub(
        r"\b0x[0-9a-fA-F]{16,}\b",
        r'<span class="diagram-value">\g<0></span>',
        escape(text.strip()),
    )


def row(text, css="diagram-row"):
    return span(css, inline(text)) + "\n"


def byte_cells(text):
    values = BYTE.findall(text)
    if not values or BYTE.sub("", text).strip():
        raise ValueError("Byte diagrams require bracketed two-digit bytes")
    # Eight-byte chunks retain the high/low ordering when a row has to wrap.
    chunks = [
        span("diagram-byte-chunk", " ".join(span("diagram-byte", escape(value)) for value in values[start:start + 8]))
        for start in range(0, len(values), 8)
    ]
    return span("diagram-bytes", " ".join(chunks))


def render_bytes(lines):
    result = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if BYTE.match(line):
            label = re.fullmatch(r"((?:\[[0-9a-fA-F]{2}\])+)[ \t]+---[ \t]+(.+)", line)
            if label:
                result.append(span("diagram-linked-bytes", byte_cells(label[1]) + " " + row(label[2], "diagram-byte-label")))
            else:
                rows = [line]
                while index + 1 < len(lines) and re.fullmatch(r"(?:\[[0-9a-fA-F]{2}\])+", lines[index + 1]):
                    index += 1
                    rows.append(lines[index])
                result.append(byte_cells("".join(rows)))
        else:
            result.append(row(line))
        index += 1
    return "\n".join(result)


def render_halves(lines):
    result = [row(lines[0])]
    labels = re.fullmatch(r"\[([^\]]+)\]\s*\[([^\]]+)\]", lines[1])
    columns = [[], []]
    index = 2
    if labels:
        for column, label in zip(columns, labels.groups(), strict=True):
            column.append(row(label, "diagram-half-label"))
    else:
        headings = re.split(r"\s{2,}", lines[1].strip())
        if len(headings) != 2:
            raise ValueError("Half diagrams require two aligned columns")
        for column, heading in zip(columns, headings, strict=True):
            column.append(row(heading, "diagram-half-label"))
    while index < len(lines):
        parts = re.split(r"\s{2,}", lines[index].strip())
        if len(parts) != 2 or re.search(r"[:=]", lines[index]):
            break
        for column, part in zip(columns, parts, strict=True):
            column.append(byte_cells(part) if BYTE.match(part) else row(part))
        index += 1
    result.append(span("diagram-halves", "\n".join(span("diagram-half", "\n".join(column)) for column in columns)))
    result.extend(row(line) for line in lines[index:])
    return "\n".join(result)


def render_calculation(lines):
    result = []
    index = 0
    while index < len(lines):
        if not EXPRESSION.fullmatch(lines[index]):
            if RULE.fullmatch(lines[index]):
                raise ValueError("Calculation separator has no operands")
            result.append(row(lines[index]))
            index += 1
            continue
        expressions = []
        after_rule = False
        while index < len(lines):
            line = lines[index]
            if RULE.fullmatch(line):
                if not expressions or after_rule:
                    raise ValueError("Calculation separator must precede a result")
                after_rule = True
                index += 1
                continue
            match = EXPRESSION.fullmatch(line)
            if not match:
                break
            label, operator, value = match.groups()
            css = "diagram-equation" + (" diagram-result" if after_rule else "")
            expressions.append(span(css, span("diagram-operand", escape(label + " " + operator)) + " " + span("diagram-number", escape(value))))
            after_rule = False
            index += 1
        if after_rule:
            raise ValueError("Calculation separator is missing its result")
        result.append(span("diagram-calculation", "\n".join(expressions)))
    return "\n".join(result)


def render_sequence(lines):
    if len(lines) < 4 or len(lines) % 3 != 1:
        raise ValueError("Sequence diagrams require a line and arrow between steps")
    for index in range(1, len(lines), 3):
        if lines[index:index + 2] != ["│", "▼"]:
            raise ValueError("Sequence diagrams require connected downward arrows")
    return span(
        "diagram-sequence",
        "\n".join(span("diagram-step", inline(line), ' role="listitem"') for line in lines[::3]),
        ' role="list" aria-label="Steps connected in order"',
    )


def render_tree(lines):
    root = {"label": lines[0], "notes": [], "children": []}
    stack = [(-1, root)]
    for line in lines[1:]:
        if not line.strip(" │"):
            continue
        branch = re.fullmatch(r"(\s*)[├└]──\s*(.+)", line)
        if branch:
            depth = len(branch[1])
            while stack[-1][0] >= depth:
                stack.pop()
            node = {"label": branch[2], "notes": [], "children": []}
            stack[-1][1]["children"].append(node)
            stack.append((depth, node))
        else:
            stack[-1][1]["notes"].append(line.strip(" │"))

    def render_node(node):
        content = row(node["label"], "diagram-tree-label")
        content += "".join(row(note, "diagram-note") for note in node["notes"])
        if node["children"]:
            content += span("diagram-tree-children", "\n".join(span("diagram-tree-node", render_node(child)) for child in node["children"]))
        return content

    if not root["children"]:
        raise ValueError("Tree diagrams require connected branches")
    return span("diagram-tree", render_node(root))


def render_boxes(lines):
    intro = []
    boxes = []
    current = None
    for line in lines:
        if re.fullmatch(r"┌─+┐", line):
            if current is not None:
                raise ValueError("Diagram boxes must not overlap")
            current = []
        elif re.fullmatch(r"└─+┘(?:\s*│)?", line):
            if not current:
                raise ValueError("Diagram box is missing its contents")
            boxes.append(current)
            current = None
        elif current is not None:
            if not line.startswith("│"):
                raise ValueError("Diagram box is missing its left border")
            content = re.split(r"│|┼", line[1:], maxsplit=1)[0].strip().rstrip("─").rstrip()
            if content:
                current.append(content)
        elif line.strip(" │▼"):
            if boxes:
                raise ValueError("Unexpected text between connected boxes")
            intro.append(line.lstrip("│ "))
    if current is not None or len(boxes) < 2 or not intro:
        raise ValueError("Box diagrams require an introduction and closed, connected boxes")

    result = [span("diagram-intro", " ".join(inline(line) for line in intro))]
    result.append(span("diagram-link", "", ' aria-hidden="true"'))
    for index, box in enumerate(boxes):
        groups = []
        reference = []
        reference_index = None
        for line in box[1:]:
            if line == "TARGET":
                if reference:
                    raise ValueError("A box must have only one TARGET reference")
                reference_index = len(groups)
                reference.append(line)
            elif reference and len(reference) == 1:
                reference.append(line)
            elif line.startswith(("├──", "└──")):
                if not groups:
                    raise ValueError("Box branches require a section heading")
                groups[-1][1].append(line[3:].strip())
            else:
                groups.append((line, []))
        content = row(box[0], "diagram-box-title")
        sections = []
        for heading, children in groups:
            css = "diagram-section" + (" diagram-functions" if children and all(re.fullmatch(r"[\w]+\([^)]*\)", child) for child in children) else "")
            sections.append(span(css, row(heading, "diagram-section-title") + "".join(row(child, "diagram-branch") for child in children)))
        if reference:
            if index + 1 >= len(boxes) or len(reference) != 2:
                raise ValueError("TARGET must point to the following box")
            target = escape(boxes[index + 1][0], quote=True)
            arm = span("diagram-reference-arm", "", ' aria-hidden="true"')
            label = span("diagram-reference-label", inline(reference[0]) + arm)
            connection = span("diagram-reference", label + " " + inline(reference[1]), f' data-target="{target}" role="group" aria-label="TARGET points to {target}"')
            # Keep TARGET in source order; route its line past the remaining sections to the next box.
            route = connection + "".join(sections[reference_index:]) + span("diagram-reference-stem", "", ' aria-hidden="true"')
            content += "".join(sections[:reference_index]) + span("diagram-reference-route", route)
        else:
            content += "".join(sections)
        result.append(span("diagram-box", content, f' role="group" aria-label="{escape(box[0], quote=True)}"'))
        if index + 1 < len(boxes):
            if not reference:
                raise ValueError("Connected boxes require an explicit TARGET reference")
            result.append(span("diagram-link diagram-reference-link", "", ' aria-hidden="true"'))
    return "\n".join(result)


def render_diagram(kind, source):
    renderers = {
        "boxes": render_boxes,
        "sequence": render_sequence,
        "tree": render_tree,
        "calculation": render_calculation,
        "bytes": render_bytes,
        "halves": render_halves,
    }
    if kind not in renderers:
        raise ValueError(f"Unknown text diagram type: {kind}")
    # Indentation encodes the parent/child relationship only in a call tree.
    lines = source.strip("\n").splitlines()
    if kind != "tree":
        lines = [line.strip() for line in lines]
    content = renderers[kind](lines)
    return span(f"diagram-content diagram-kind-{kind}", content)
