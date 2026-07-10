from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional


class FileOperations:
    @staticmethod
    def ensure_dir(path: str) -> str:
        Path(path).mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def atomic_write(dest: str, content: str) -> None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".tmp",
            dir=os.path.dirname(dest),
        )
        tmp.write(content)
        tmp.close()
        os.replace(tmp.name, dest)

    @staticmethod
    def atomic_copy(src: str, dest: str) -> str:
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=Path(dest).suffix,
            dir=os.path.dirname(dest),
        )
        tmp.close()
        shutil.copy2(src, tmp.name)
        os.replace(tmp.name, dest)
        return dest

    @staticmethod
    def safe_delete(path: str) -> bool:
        try:
            p = Path(path)
            if p.is_dir():
                shutil.rmtree(str(p))
            else:
                p.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    @staticmethod
    def list_files(directory: str, pattern: str = "*") -> List[str]:
        return [str(p) for p in Path(directory).glob(pattern) if p.is_file()]
