from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from pyweb.core.models import FileFragments, Fragment, Range, _new_id


class ValidationError(Exception):
    pass


class FragmentStore:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.pyweb_dir = self.project_root / ".pyweb"
        self.fragments_dir = self.pyweb_dir / "fragments"
        self.cache_dir = self.pyweb_dir / "cache"

    def is_initialized(self) -> bool:
        return self.pyweb_dir.exists() and (self.pyweb_dir / "config.json").exists()

    def init(self) -> None:
        self.pyweb_dir.mkdir(exist_ok=True)
        self.fragments_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)
        config_path = self.pyweb_dir / "config.json"
        if not config_path.exists():
            config_path.write_text(json.dumps({"version": 1, "tracked_files": []}, indent=2))

    # --- persistence ---

    def _frag_path(self, file_path: str) -> Path:
        return self.fragments_dir / (file_path + ".json")

    def _cache_path(self, file_path: str) -> Path:
        return self.cache_dir / file_path

    def load_file(self, file_path: str) -> FileFragments | None:
        p = self._frag_path(file_path)
        if not p.exists():
            return None
        return FileFragments.from_json(p.read_text())

    def save_file(self, file_frags: FileFragments) -> None:
        p = self._frag_path(file_frags.file)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(file_frags.to_json())

    def load_cache(self, file_path: str) -> str | None:
        p = self._cache_path(file_path)
        if not p.exists():
            return None
        return p.read_text()

    def save_cache(self, file_path: str, content: str) -> None:
        p = self._cache_path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    @staticmethod
    def content_hash(content: str) -> str:
        return "sha256:" + hashlib.sha256(content.encode()).hexdigest()

    # --- queries ---

    def get_fragment(self, file_path: str, fragment_id: str) -> Fragment | None:
        ff = self.load_file(file_path)
        if ff is None:
            return None
        for f in ff.fragments:
            if f.id == fragment_id:
                return f
        return None

    def get_fragment_by_name(self, file_path: str, name: str) -> Fragment | None:
        ff = self.load_file(file_path)
        if ff is None:
            return None
        for f in ff.fragments:
            if f.name == name:
                return f
        return None

    def get_roots(self, file_path: str) -> list[Fragment]:
        ff = self.load_file(file_path)
        if ff is None:
            return []
        child_ids: set[str] = set()
        for f in ff.fragments:
            child_ids.update(f.children)
        return [f for f in ff.fragments if f.id not in child_ids]

    def get_children(self, file_path: str, fragment_id: str) -> list[Fragment]:
        ff = self.load_file(file_path)
        if ff is None:
            return []
        frag = self._find_fragment(ff, fragment_id)
        if frag is None:
            return []
        by_id = {f.id: f for f in ff.fragments}
        return [by_id[cid] for cid in frag.children if cid in by_id]

    def fragment_at(self, file_path: str, line: int, col: int) -> Fragment | None:
        ff = self.load_file(file_path)
        if ff is None:
            return None
        best: Fragment | None = None
        for f in ff.fragments:
            r = f.range
            start = (r.start_line, r.start_col)
            end = (r.end_line, r.end_col)
            pos = (line, col)
            if start <= pos < end:
                if best is None or f.range.contains(best.range):
                    pass  # best is more specific
                elif best.range.contains(f.range):
                    best = f  # f is more specific (smaller)
                else:
                    best = f
        # Actually, we want the deepest (most specific) fragment
        best = None
        for f in ff.fragments:
            r = f.range
            start = (r.start_line, r.start_col)
            end = (r.end_line, r.end_col)
            pos = (line, col)
            if start <= pos < end:
                if best is None:
                    best = f
                elif best.range.contains(f.range) and f.range != best.range:
                    best = f  # f is strictly inside best, so more specific
        return best

    # --- mutations ---

    def create_fragment(
        self,
        file_path: str,
        name: str,
        range: Range,
        parent_id: str | None = None,
        prose: str | None = None,
    ) -> Fragment:
        ff = self.load_file(file_path)
        if ff is None:
            source_path = self.project_root / file_path
            content = source_path.read_text() if source_path.exists() else ""
            ff = FileFragments(
                file=file_path,
                content_hash=self.content_hash(content),
                fragments=[],
            )

        # Validate unique name
        for f in ff.fragments:
            if f.name == name:
                raise ValidationError(f"Fragment name '{name}' already exists in {file_path}")

        frag = Fragment(
            id=_new_id(),
            name=name,
            file=file_path,
            range=range,
            children=[],
            prose=prose,
        )

        if parent_id is not None:
            parent = self._find_fragment(ff, parent_id)
            if parent is None:
                raise ValidationError(f"Parent fragment '{parent_id}' not found")
            if not parent.range.contains(range):
                raise ValidationError(
                    f"Child range {range} not contained by parent range {parent.range}"
                )
            # Check no overlap with existing siblings
            by_id = {f.id: f for f in ff.fragments}
            for sib_id in parent.children:
                sib = by_id.get(sib_id)
                if sib and sib.range.overlaps(range):
                    raise ValidationError(
                        f"New fragment overlaps with sibling '{sib.name}'"
                    )
            parent.children.append(frag.id)
        else:
            # Root fragment — check no overlap with other roots
            roots = self._get_roots(ff)
            for root in roots:
                if root.range.overlaps(range):
                    raise ValidationError(
                        f"New fragment overlaps with root fragment '{root.name}'"
                    )

        ff.fragments.append(frag)
        self.save_file(ff)
        return frag

    def delete_fragment(self, file_path: str, fragment_id: str) -> None:
        ff = self.load_file(file_path)
        if ff is None:
            raise ValidationError(f"No fragments for {file_path}")

        frag = self._find_fragment(ff, fragment_id)
        if frag is None:
            raise ValidationError(f"Fragment '{fragment_id}' not found")

        # Reparent children to parent (or make them roots)
        parent = self._find_parent(ff, fragment_id)
        if parent is not None:
            idx = parent.children.index(fragment_id)
            parent.children = (
                parent.children[:idx] + frag.children + parent.children[idx + 1:]
            )
        # else children become roots (no action needed, they're just not in any parent's children list)

        # Remove the fragment
        ff.fragments = [f for f in ff.fragments if f.id != fragment_id]
        self.save_file(ff)

    def rename_fragment(self, file_path: str, fragment_id: str, new_name: str) -> None:
        ff = self.load_file(file_path)
        if ff is None:
            raise ValidationError(f"No fragments for {file_path}")

        # Check unique name
        for f in ff.fragments:
            if f.name == new_name and f.id != fragment_id:
                raise ValidationError(f"Fragment name '{new_name}' already exists")

        frag = self._find_fragment(ff, fragment_id)
        if frag is None:
            raise ValidationError(f"Fragment '{fragment_id}' not found")

        frag.name = new_name
        self.save_file(ff)

    def move_fragment(self, file_path: str, fragment_id: str, new_parent_id: str | None) -> None:
        ff = self.load_file(file_path)
        if ff is None:
            raise ValidationError(f"No fragments for {file_path}")

        frag = self._find_fragment(ff, fragment_id)
        if frag is None:
            raise ValidationError(f"Fragment '{fragment_id}' not found")

        # Remove from old parent
        old_parent = self._find_parent(ff, fragment_id)
        if old_parent is not None:
            old_parent.children.remove(fragment_id)

        if new_parent_id is not None:
            new_parent = self._find_fragment(ff, new_parent_id)
            if new_parent is None:
                raise ValidationError(f"New parent '{new_parent_id}' not found")
            if not new_parent.range.contains(frag.range):
                raise ValidationError("Fragment range not contained by new parent")
            # Check no overlap with new siblings
            by_id = {f.id: f for f in ff.fragments}
            for sib_id in new_parent.children:
                sib = by_id.get(sib_id)
                if sib and sib.range.overlaps(frag.range):
                    raise ValidationError(f"Overlaps with sibling '{sib.name}'")
            new_parent.children.append(fragment_id)

        self.save_file(ff)

    def set_prose(self, file_path: str, fragment_id: str, prose: str | None) -> None:
        ff = self.load_file(file_path)
        if ff is None:
            raise ValidationError(f"No fragments for {file_path}")

        frag = self._find_fragment(ff, fragment_id)
        if frag is None:
            raise ValidationError(f"Fragment '{fragment_id}' not found")

        frag.prose = prose
        self.save_file(ff)

    # --- validation ---

    def validate(self, file_path: str) -> list[str]:
        """Returns list of validation error messages. Empty = valid."""
        ff = self.load_file(file_path)
        if ff is None:
            return []

        errors: list[str] = []
        by_id = {f.id: f for f in ff.fragments}

        # Check unique names
        names: dict[str, str] = {}
        for f in ff.fragments:
            if f.name in names:
                errors.append(f"Duplicate name '{f.name}' (IDs: {names[f.name]}, {f.id})")
            names[f.name] = f.id

        # Check children exist and parent contains children
        for f in ff.fragments:
            for cid in f.children:
                child = by_id.get(cid)
                if child is None:
                    errors.append(f"Fragment '{f.name}' references nonexistent child '{cid}'")
                elif not f.range.contains(child.range):
                    errors.append(
                        f"Child '{child.name}' range {child.range} not contained by "
                        f"parent '{f.name}' range {f.range}"
                    )

        # Check sibling overlaps
        for f in ff.fragments:
            children = [by_id[cid] for cid in f.children if cid in by_id]
            for i, a in enumerate(children):
                for b in children[i + 1:]:
                    if a.range.overlaps(b.range):
                        errors.append(f"Siblings '{a.name}' and '{b.name}' overlap")

        # Check root overlaps
        roots = self._get_roots(ff)
        for i, a in enumerate(roots):
            for b in roots[i + 1:]:
                if a.range.overlaps(b.range):
                    errors.append(f"Root fragments '{a.name}' and '{b.name}' overlap")

        # Check no cycles (child is not an ancestor)
        def ancestors(fid: str) -> set[str]:
            result: set[str] = set()
            for f in ff.fragments:
                if fid in f.children:
                    result.add(f.id)
                    result.update(ancestors(f.id))
            return result

        for f in ff.fragments:
            for cid in f.children:
                if f.id in ancestors(f.id):
                    errors.append(f"Cycle detected involving fragment '{f.name}'")
                    break

        return errors

    # --- file bounds validation ---

    def validate_bounds(self, file_path: str) -> list[str]:
        """Check that fragment ranges are within the source file bounds."""
        source_path = self.project_root / file_path
        if not source_path.exists():
            return [f"Source file '{file_path}' does not exist"]

        content = source_path.read_text()
        lines = content.split("\n")
        num_lines = len(lines)

        ff = self.load_file(file_path)
        if ff is None:
            return []

        errors: list[str] = []
        for f in ff.fragments:
            r = f.range
            if r.is_orphaned():
                errors.append(f"Fragment '{f.name}' is orphaned")
                continue
            if r.end_line > num_lines:
                errors.append(
                    f"Fragment '{f.name}' end_line {r.end_line} exceeds file length {num_lines}"
                )
            if r.start_line >= num_lines:
                errors.append(
                    f"Fragment '{f.name}' start_line {r.start_line} exceeds file length {num_lines}"
                )

        return errors

    # --- helpers ---

    @staticmethod
    def _find_fragment(ff: FileFragments, fragment_id: str) -> Fragment | None:
        for f in ff.fragments:
            if f.id == fragment_id:
                return f
        return None

    @staticmethod
    def _find_parent(ff: FileFragments, fragment_id: str) -> Fragment | None:
        for f in ff.fragments:
            if fragment_id in f.children:
                return f
        return None

    @staticmethod
    def _get_roots(ff: FileFragments) -> list[Fragment]:
        child_ids: set[str] = set()
        for f in ff.fragments:
            child_ids.update(f.children)
        return [f for f in ff.fragments if f.id not in child_ids]
