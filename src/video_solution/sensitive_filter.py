"""Sensitive word filtering and censorship mapping.

Uses Trie (prefix tree) for efficient matching.
"""
from pathlib import Path
from typing import List, Dict, Tuple, Set
import re


class SensitiveWordFilter:
    """Efficient sensitive word filter using Trie data structure."""
    
    def __init__(self, wordlist_path: Optional[str] = None):
        """
        Args:
            wordlist_path: Path to sensitive word list file (one word per line)
        """
        self.trie = {}
        self.words: Set[str] = set()
        
        if wordlist_path:
            self.load_wordlist(wordlist_path)
    
    def load_wordlist(self, filepath: str):
        """Load sensitive words from file."""
        path = Path(filepath)
        if not path.exists():
            print(f"⚠️  Wordlist not found: {filepath}")
            return
        
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word and not word.startswith("#"):
                    self.add_word(word)
        
        print(f"✓ Loaded {len(self.words)} sensitive words")
    
    def add_word(self, word: str):
        """Add a word to the filter."""
        word = word.lower()
        self.words.add(word)
        
        # Build trie
        node = self.trie
        for char in word:
            if char not in node:
                node[char] = {}
            node = node[char]
        node["#"] = True  # End marker
    
    def find_sensitive_words(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Find all sensitive words in text.
        
        Args:
            text: Input text
        
        Returns:
            List of (start_pos, end_pos, word) tuples
        """
        text_lower = text.lower()
        matches = []
        n = len(text_lower)
        i = 0
        
        while i < n:
            node = self.trie
            j = i
            last_match = None
            
            # Try to match longest word starting at position i
            while j < n and text_lower[j] in node:
                node = node[text_lower[j]]
                if "#" in node:
                    last_match = j + 1
                j += 1
            
            if last_match:
                matches.append((i, last_match, text[i:last_match]))
                i = last_match
            else:
                i += 1
        
        return matches
    
    def filter_text(self, text: str, replace_char: str = "*") -> str:
        """
        Replace sensitive words with asterisks or other character.
        
        Args:
            text: Input text
            replace_char: Character to replace with
        
        Returns:
            Filtered text
        """
        matches = self.find_sensitive_words(text)
        
        if not matches:
            return text
        
        # Replace from end to start to preserve indices
        result = list(text)
        for start, end, word in reversed(matches):
            result[start:end] = replace_char * (end - start)
        
        return "".join(result)
    
    def map_to_timestamps(
        self,
        segments: List[Dict],
        text_field: str = "text"
    ) -> List[Dict]:
        """
        Find sensitive words in segments and map to time ranges.
        
        Args:
            segments: List of segments with 'start', 'end', and text field
            text_field: Field name containing text
        
        Returns:
            List of time ranges to censor: [{"start": float, "end": float, "word": str}]
        """
        censor_ranges = []
        
        for seg in segments:
            text = seg.get(text_field, "")
            matches = self.find_sensitive_words(text)
            
            if matches:
                seg_duration = seg["end"] - seg["start"]
                text_length = len(text)
                
                for char_start, char_end, word in matches:
                    # Estimate time position based on character position
                    # (Simple linear interpolation)
                    time_start = seg["start"] + (char_start / text_length) * seg_duration
                    time_end = seg["start"] + (char_end / text_length) * seg_duration
                    
                    censor_ranges.append({
                        "start": time_start,
                        "end": time_end,
                        "word": word,
                        "segment_index": segments.index(seg)
                    })
                    
                    print(f"  🚫 Found '{word}' at {time_start:.2f}s - {time_end:.2f}s")
        
        return censor_ranges


def download_chinese_wordlist(output_path: str = "data/sensitive_words.txt") -> str:
    """
    Download Chinese sensitive word list from GitHub.
    
    Args:
        output_path: Where to save the wordlist
    
    Returns:
        Path to downloaded file
    """
    import urllib.request
    
    url = "https://raw.githubusercontent.com/fwwdn/sensitive-stop-words/master/%E6%95%8F%E6%84%9F%E8%AF%8D%E5%BA%93.txt"
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    print(f"📥 Downloading Chinese sensitive word list...")
    try:
        urllib.request.urlretrieve(url, output_path)
        print(f"✓ Saved to: {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Download failed: {e}")
        print(f"   Manually download from: {url}")
        return None


def create_custom_wordlist(words: List[str], output_path: str) -> str:
    """Create a custom sensitive word list file."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Custom Sensitive Words\n")
        f.write("# One word per line\n\n")
        for word in words:
            f.write(f"{word}\n")
    
    print(f"✓ Created wordlist: {output_path}")
    return output_path
