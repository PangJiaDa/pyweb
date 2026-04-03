from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pyweb.core.models import Fragment, Range, FileFragments
from pyweb.core.store import FragmentStore
from pyweb.core.anchorer import DiffAnchorer
from pyweb.core.sourcemap import SourceMap


@dataclass
class HierarchicalNode:
    fragment: Fragment
    code: str           # source code owned by this fragment (excluding children's code)
    children: list[HierarchicalNode] = field(default_factory=list)


class SyncEngine:
    def __init__(self, store: FragmentStore, project_root: Path) -> None:
        self.store = store
        self.project_root = project_root

    def expanded_view(self, file_path: str) -> str:
        """Returns the source file content (this IS the expanded view)."""
        source_path = self.project_root / file_path
        return source_path.read_text()

    def hierarchical_view(self, file_path: str) -> list[HierarchicalNode]:
        """Returns the fragment tree with code slices and prose for rendering."""
        ff = self.store.load_file(file_path)
        if ff is None:
            return []

        source_path = self.project_root / file_path
        if not source_path.exists():
            return []

        lines = source_path.read_text().splitlines(keepends=True)
        smap = SourceMap(ff)

        def build_node(frag: Fragment) -> HierarchicalNode:
            by_id = {f.id: f for f in ff.fragments}
            child_frags = [by_id[cid] for cid in frag.children
                           if cid in by_id and not by_id[cid].range.is_orphaned()]
            child_frags.sort(key=lambda f: (f.range.start_line, f.range.start_col))

            # Extract code owned by this fragment (lines within range, excluding child ranges)
            owned_lines: list[str] = []
            r = frag.range
            line_idx = r.start_line
            for child in child_frags:
                cr = child.range
                # Lines between current position and child start
                for i in range(line_idx, min(cr.start_line, r.end_line)):
                    if i < len(lines):
                        owned_lines.append(lines[i])
                line_idx = cr.end_line

            # Lines after last child
            for i in range(line_idx, r.end_line):
                if i < len(lines):
                    owned_lines.append(lines[i])

            code = "".join(owned_lines)
            child_nodes = [build_node(cf) for cf in child_frags]
            return HierarchicalNode(fragment=frag, code=code, children=child_nodes)

        roots = smap.roots
        return [build_node(r) for r in roots]

    def on_source_changed(self, file_path: str, old_content: str, new_content: str) -> None:
        """Source file was edited externally. Re-anchor fragments."""
        ff = self.store.load_file(file_path)
        if ff is None:
            return

        edits = DiffAnchorer.compute_line_edits(old_content, new_content)
        if not edits:
            return

        updated = DiffAnchorer.apply_edits(ff.fragments, edits)
        ff.fragments = updated
        ff.content_hash = self.store.content_hash(new_content)
        self.store.save_file(ff)
        self.store.save_cache(file_path, new_content)

    def on_fragment_content_changed(self, file_path: str, fragment_id: str, new_code: str) -> str:
        """User edited code in hierarchical view.

        Replaces the fragment's range in the source file with new_code.
        Re-anchors all fragments affected by the size change.
        Returns the full updated source file content.
        """
        ff = self.store.load_file(file_path)
        if ff is None:
            raise ValueError(f"No fragments for {file_path}")

        frag = None
        for f in ff.fragments:
            if f.id == fragment_id:
                frag = f
                break
        if frag is None:
            raise ValueError(f"Fragment '{fragment_id}' not found")

        source_path = self.project_root / file_path
        old_content = source_path.read_text()
        old_lines = old_content.splitlines(keepends=True)

        r = frag.range
        # Build new content: lines before fragment + new code + lines after fragment
        before = old_lines[:r.start_line]
        after = old_lines[r.end_line:]

        # Ensure new_code ends with newline for clean joining
        if new_code and not new_code.endswith("\n"):
            new_code += "\n"

        new_content = "".join(before) + new_code + "".join(after)

        # Write the new content
        source_path.write_text(new_content)

        # Re-anchor all fragments
        self.on_source_changed(file_path, old_content, new_content)

        return new_content

    def render_hierarchical_text(self, file_path: str, fragment_id: str | None = None) -> str:
        """Render the hierarchical view as readable text for CLI output."""
        nodes = self.hierarchical_view(file_path)

        if fragment_id is not None:
            # Find the specific subtree
            def find_node(nodes: list[HierarchicalNode], fid: str) -> HierarchicalNode | None:
                for n in nodes:
                    if n.fragment.id == fid or n.fragment.name == fid:
                        return n
                    found = find_node(n.children, fid)
                    if found:
                        return found
                return None

            node = find_node(nodes, fragment_id)
            if node is None:
                return f"Fragment '{fragment_id}' not found.\n"
            nodes = [node]

        if not nodes:
            return ""

        lines: list[str] = []
        self._render_nodes(nodes, lines, depth=0)
        return "".join(lines)

    def _render_nodes(self, nodes: list[HierarchicalNode], out: list[str], depth: int) -> None:
        for node in nodes:
            f = node.fragment
            # Header
            if depth == 0:
                out.append(f"=== {f.name} ===\n")
            else:
                out.append(f"--- {f.name} ---\n")

            # Prose
            if f.prose:
                out.append(f"{f.prose}\n\n")

            # Interleave owned code with child nodes at their positions
            # We need to reconstruct the ordering: owned code lines + children at their positions
            ff = self.store.load_file(f.file)
            source_path = self.project_root / f.file
            if not source_path.exists():
                out.append(node.code)
                continue

            all_lines = source_path.read_text().splitlines(keepends=True)
            by_id = {frag.id: frag for frag in ff.fragments}

            child_frags = [by_id[cid] for cid in f.children
                           if cid in by_id and not by_id[cid].range.is_orphaned()]
            child_frags.sort(key=lambda cf: (cf.range.start_line, cf.range.start_col))

            child_nodes_by_id = {cn.fragment.id: cn for cn in node.children}

            r = f.range
            line_idx = r.start_line
            for cf in child_frags:
                cr = cf.range
                # Owned lines before this child
                for i in range(line_idx, min(cr.start_line, r.end_line)):
                    if i < len(all_lines):
                        out.append(all_lines[i])
                # Render child
                cn = child_nodes_by_id.get(cf.id)
                if cn:
                    self._render_nodes([cn], out, depth + 1)
                line_idx = cr.end_line

            # Owned lines after last child
            for i in range(line_idx, r.end_line):
                if i < len(all_lines):
                    out.append(all_lines[i])
