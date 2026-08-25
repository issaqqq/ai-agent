import re
from pathlib import Path
from typing import List, Dict, Any
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
KB_DIR = BASE_DIR / "knowledge-base"

class KnowledgeBaseIndexer:
    def __init__(self, kb_dir: Path = KB_DIR):
        self.kb_dir = kb_dir
        self.documents: List[Dict[str, Any]] = []
        self._load_and_index()

    def _parse_frontmatter(self, text: str) -> tuple[Dict[str, Any], str]:
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                    return meta, parts[2].strip()
                except yaml.YAMLError:
                    pass
        return {}, text.strip()

    def _load_and_index(self):
        if not self.kb_dir.exists():
            return

        for file_path in self.kb_dir.glob("*.md"):
            raw_text = file_path.read_text(encoding="utf-8")
            meta, content = self._parse_frontmatter(raw_text)
            
            # Identify legacy or migration files
            status = meta.get("status", "active")
            is_internal = meta.get("internal", False) or "migration" in file_path.name.lower() or "legacy" in file_path.name.lower()
            
            sections = re.split(r'\n(?=#{1,3}\s)', content)
            for sec in sections:
                lines = sec.strip().split("\n")
                heading = lines[0].lstrip("#").strip() if lines[0].startswith("#") else "General"
                body = "\n".join(lines[1:]).strip() if len(lines) > 1 else lines[0]
                
                self.documents.append({
                    "file": file_path.name,
                    "heading": heading,
                    "text": body,
                    "status": status,
                    "is_internal": is_internal
                })

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        query_words = set(re.findall(r'\w+', query.lower()))
        scored_docs = []
        
        for doc in self.documents:
            # Exclude legacy and internal files from serving as active policy
            if doc["status"] == "legacy" or doc["is_internal"]:
                continue
                
            doc_words = set(re.findall(r'\w+', (doc["heading"] + " " + doc["text"]).lower()))
            score = len(query_words.intersection(doc_words))
            if score > 0:
                scored_docs.append((score, doc))
                
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored_docs[:top_k]]