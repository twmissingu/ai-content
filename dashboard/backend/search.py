"""Knowledge base search service with FTS5 + jieba Chinese tokenization.

Implements PRD 8.3: SQLite FTS5 + jieba 中文分词全文索引
Supports: keyword search, phrase search, section filtering
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import KB_DIR
from dashboard.backend.database import get_db

# Try to import jieba for Chinese tokenization
try:
    import jieba
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False
    print("[search] jieba not installed. Chinese tokenization disabled.")


def tokenize_chinese(text: str) -> str:
    """Tokenize Chinese text using jieba."""
    if not HAS_JIEBA:
        # Fallback: just return text with spaces between characters
        return ' '.join(text)
    
    # Use jieba to cut text into tokens
    tokens = jieba.cut_for_search(text)
    return ' '.join(tokens)


def clean_text(text: str) -> str:
    """Clean markdown text for indexing."""
    # Remove markdown syntax
    text = re.sub(r'#+\s+', '', text)  # Headers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)  # Italic
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # Links
    text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)  # Code blocks
    text = re.sub(r'`([^`]+)`', r'\1', text)  # Inline code
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)  # Images
    text = re.sub(r'\n{2,}', '\n', text)  # Multiple newlines
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces
    return text.strip()


def index_kb_file(file_path: Path, section: str = None) -> bool:
    """Index a single knowledge base file.
    
    Args:
        file_path: Path to the markdown file
        section: Knowledge base section (topics, viral, history, etc.)
    
    Returns:
        True if indexed successfully
    """
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        
        # Extract title (first heading or filename)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else file_path.stem
        
        # Clean content for indexing
        cleaned = clean_text(content)
        
        # Tokenize for FTS5
        tokenized_content = tokenize_chinese(cleaned)
        tokenized_title = tokenize_chinese(title)
        
        # Determine section from path if not provided
        if section is None:
            relative = file_path.relative_to(KB_DIR)
            section = relative.parts[0] if len(relative.parts) > 0 else 'root'
        
        path_str = str(file_path.relative_to(KB_DIR))
        
        with get_db() as conn:
            # Check if already indexed
            existing = conn.execute(
                "SELECT path FROM kb_search WHERE path = ?", 
                (path_str,)
            ).fetchone()
            
            if existing:
                # Update existing record
                conn.execute("""
                    UPDATE kb_search 
                    SET title = ?, content = ?, section = ?
                    WHERE path = ?
                """, (tokenized_title, tokenized_content, section, path_str))
            else:
                # Insert new record
                conn.execute("""
                    INSERT INTO kb_search (path, title, content, section)
                    VALUES (?, ?, ?, ?)
                """, (path_str, tokenized_title, tokenized_content, section))
        
        return True
        
    except Exception as e:
        print(f"[search] Error indexing {file_path}: {e}")
        return False


def index_all_kb(force: bool = False) -> dict:
    """Index all knowledge base files.
    
    Args:
        force: If True, reindex all files regardless of modification time
    
    Returns:
        Statistics about indexing
    """
    stats = {
        'total_files': 0,
        'indexed': 0,
        'skipped': 0,
        'errors': 0,
    }
    
    if not KB_DIR.exists():
        return stats
    
    # Get existing index with modification times
    existing_files = {}
    with get_db() as conn:
        rows = conn.execute("SELECT path FROM kb_search").fetchall()
        for row in rows:
            existing_files[row['path']] = True
    
    # Scan all markdown files
    for md_file in KB_DIR.rglob("*.md"):
        stats['total_files'] += 1
        
        try:
            relative_path = str(md_file.relative_to(KB_DIR))
            
            # Skip if already indexed and not forcing
            if not force and relative_path in existing_files:
                stats['skipped'] += 1
                continue
            
            # Determine section
            parts = md_file.relative_to(KB_DIR).parts
            section = parts[0] if len(parts) > 0 else 'root'
            
            # Index the file
            if index_kb_file(md_file, section):
                stats['indexed'] += 1
            else:
                stats['errors'] += 1
                
        except Exception as e:
            print(f"[search] Error processing {md_file}: {e}")
            stats['errors'] += 1
    
    print(f"[search] Indexed {stats['indexed']}/{stats['total_files']} files")
    return stats


def _escape_fts5_token(token: str) -> str:
    """Escape special FTS5 characters in a token.
    
    FTS5 special characters: " * ( ) AND OR NOT NEAR
    """
    # Remove or escape special characters
    # Replace double quotes with escaped version
    token = token.replace('"', '""')
    # Remove other special characters that could break the query
    for char in ['*', '(', ')']:
        token = token.replace(char, '')
    return token


def search_kb(query: str, section: str = None, limit: int = 20) -> list[dict]:
    """Search knowledge base using FTS5.
    
    Args:
        query: Search query (supports Chinese)
        section: Filter by section (topics, viral, history, etc.)
        limit: Maximum results to return
    
    Returns:
        List of search results with path, title, match snippet, section
    """
    if not query or len(query.strip()) < 2:
        return []
    
    # Tokenize query for FTS5
    tokenized_query = tokenize_chinese(query.strip())
    
    # Build FTS5 query with escaped tokens
    # Use prefix matching for better results
    escaped_tokens = []
    for token in tokenized_query.split():
        if token:
            escaped = _escape_fts5_token(token)
            if escaped:
                escaped_tokens.append(f'"{escaped}"*')
    
    fts_query = ' OR '.join(escaped_tokens)
    
    if not fts_query:
        return []
    
    results = []
    
    try:
        with get_db() as conn:
            if section:
                # Search within specific section
                rows = conn.execute("""
                    SELECT 
                        path, 
                        title, 
                        section,
                        snippet(kb_search, 2, '...', '...', 64) as match_snippet,
                        rank
                    FROM kb_search
                    WHERE kb_search MATCH ? AND section = ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_query, section, limit)).fetchall()
            else:
                # Search all sections
                rows = conn.execute("""
                    SELECT 
                        path, 
                        title, 
                        section,
                        snippet(kb_search, 2, '...', '...', 64) as match_snippet,
                        rank
                    FROM kb_search
                    WHERE kb_search MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_query, limit)).fetchall()
            
            for row in rows:
                result = {
                    'path': row['path'],
                    'title': row['title'],
                    'section': row['section'],
                    'match': row['match_snippet'],
                    'score': abs(row['rank']),
                }
                results.append(result)
    
    except Exception as e:
        print(f"[search] FTS5 search error: {e}")
        
        # Fallback to simple text search
        results = _fallback_search(query, section, limit)
    
    return results


def _fallback_search(query: str, section: str = None, limit: int = 20) -> list[dict]:
    """Fallback search using simple text matching."""
    results = []
    query_lower = query.lower()
    
    for md_file in KB_DIR.rglob("*.md"):
        if len(results) >= limit:
            break
        
        try:
            relative_path = str(md_file.relative_to(KB_DIR))
            parts = md_file.relative_to(KB_DIR).parts
            file_section = parts[0] if len(parts) > 0 else 'root'
            
            # Filter by section
            if section and file_section != section:
                continue
            
            content = md_file.read_text(encoding='utf-8', errors='ignore')
            
            if query_lower in content.lower():
                # Extract title
                title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else md_file.stem
                
                # Find matching line
                match_line = ""
                for line in content.split('\n'):
                    if query_lower in line.lower():
                        match_line = line.strip()[:100]
                        break
                
                results.append({
                    'path': relative_path,
                    'title': title,
                    'section': file_section,
                    'match': match_line,
                    'score': 1.0,
                })
        
        except Exception:
            continue
    
    return results


def get_index_stats() -> dict:
    """Get knowledge base index statistics."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as count FROM kb_search").fetchone()['count']
        
        by_section = conn.execute("""
            SELECT section, COUNT(*) as count 
            FROM kb_search 
            GROUP BY section 
            ORDER BY count DESC
        """).fetchall()
        
        return {
            'total_indexed': total,
            'by_section': {row['section']: row['count'] for row in by_section},
        }


def delete_from_index(path: str):
    """Remove a file from the search index."""
    with get_db() as conn:
        conn.execute("DELETE FROM kb_search WHERE path = ?", (path,))


# ── Auto-index on startup ─────────────────────────────────────────

def auto_index_if_needed():
    """Check if index needs updating and rebuild if necessary."""
    with get_db() as conn:
        # Check if kb_search table exists and has data
        try:
            count = conn.execute("SELECT COUNT(*) as count FROM kb_search").fetchone()['count']
            
            # If index is empty or very small, rebuild
            if count < 10:
                print("[search] Index empty or small, rebuilding...")
                return index_all_kb(force=True)
            
            # Check for new files not in index
            indexed_paths = set()
            rows = conn.execute("SELECT path FROM kb_search").fetchall()
            for row in rows:
                indexed_paths.add(row['path'])
            
            new_files = 0
            for md_file in KB_DIR.rglob("*.md"):
                relative = str(md_file.relative_to(KB_DIR))
                if relative not in indexed_paths:
                    new_files += 1
            
            if new_files > 5:
                print(f"[search] Found {new_files} new files, updating index...")
                return index_all_kb(force=False)
            
            return {'status': 'up_to_date', 'indexed': count}
            
        except Exception as e:
            print(f"[search] Error checking index: {e}")
            return index_all_kb(force=True)


# ── CLI interface ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Knowledge base search indexer")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild entire index")
    parser.add_argument("--search", "-s", help="Search query")
    parser.add_argument("--section", help="Filter by section")
    parser.add_argument("--stats", action="store_true", help="Show index statistics")
    
    args = parser.parse_args()
    
    if args.rebuild:
        print("Rebuilding search index...")
        stats = index_all_kb(force=True)
        print(f"Done: {stats}")
    
    elif args.search:
        results = search_kb(args.search, section=args.section)
        print(f"Found {len(results)} results:")
        for r in results:
            print(f"  [{r['section']}] {r['title']}")
            if r['match']:
                print(f"    Match: {r['match']}")
            print(f"    Path: {r['path']}")
            print()
    
    elif args.stats:
        stats = get_index_stats()
        print(f"Index statistics:")
        print(f"  Total indexed: {stats['total_indexed']}")
        print(f"  By section:")
        for section, count in stats['by_section'].items():
            print(f"    {section}: {count}")
    
    else:
        # Default: show stats and auto-index if needed
        stats = get_index_stats()
        print(f"Current index: {stats['total_indexed']} documents")
        
        if stats['total_indexed'] < 10:
            print("Index appears empty. Run with --rebuild to index all files.")
