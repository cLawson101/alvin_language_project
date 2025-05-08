# file_system_logic.py

import os
from datetime import datetime

FILENAME = "private.pfs"
index = {}

def open_or_create_pfs():
    if not os.path.exists(FILENAME):
        with open(FILENAME, "wb") as f:
            pass  # create empty file

def load_index():
    global index
    index = {}
    
    if not os.path.exists(FILENAME):
        return

    with open(FILENAME, "rb") as f:
        lines = f.read().split(b"\n")
    
    for line in lines:
        if not line.strip():
            continue
        try:
            text = line.decode()
            type_, path, offset, length, timestamp = text.strip().split("|")
            index[path] = {
                "type": type_,
                "offset": int(offset),
                "length": int(length),
                "timestamp": timestamp
            }
        except Exception:
            break  

def update_index(path, type_, length, content_bytes):
    index[path] = {
        "type": type_,
        "offset": 0,  
        "length": length,
        "timestamp": datetime.now().isoformat(),
        "content": content_bytes
    }

def compute_offsets():
    lines = []
    for path, meta in index.items():
        lines.append(f"{meta['type']}|{path}|0|{meta['length']}|{meta['timestamp']}")
    encoded = ("\n".join(lines) + "\n").encode()


    pad = (16 - len(encoded) % 16) % 16
    header_size = len(encoded) + pad

    offset = header_size
    for path, meta in index.items():
        if meta["type"] == "F" and "content" in meta:
            meta["offset"] = offset
            offset += meta["length"]

def build_header():
    """Build the final metadata header after offsets are assigned."""
    lines = []
    for path, meta in index.items():
        lines.append(f"{meta['type']}|{path}|{meta['offset']}|{meta['length']}|{meta['timestamp']}")
    header = ("\n".join(lines) + "\n").encode()
    pad = (16 - len(header) % 16) % 16
    return header + b"" * pad

def write_metadata():
    """Write metadata and content to private.pfs."""
    compute_offsets()
    header = build_header()


    content_blocks = []

    for path, meta in index.items():
        if meta["type"] == "F":
            if "content" not in meta:
                # Load file content if missing
                with open(FILENAME, "rb") as f:
                    f.seek(meta["offset"])
                    meta["content"] = f.read(meta["length"])
            # Refresh length to be 100% safe
            meta["length"] = len(meta["content"])
            content_blocks.append((path, meta["content"]))

    with open(FILENAME, "wb") as f:
        f.write(header)
        for _, content in content_blocks:
            f.write(content)
    
def hydrate_all_content():
    """Ensure all file entries in index have their content and correct length."""
    if not os.path.exists(FILENAME):
        return
    with open(FILENAME, "rb") as f:
        for meta in index.values():
            if meta["type"] == "F":
                f.seek(meta["offset"])
                content = f.read(meta["length"])
                meta["content"] = content
                meta["length"] = len(content)

def cp(source, dest):
    load_index()

    if not dest.startswith("+"):
        print("Error: Destination must be a supplemental file starting with '+'")
        return

    # Copy from supplemental source
    if source.startswith("+"):
        if source not in index or index[source]["type"] != "F":
            print(f"Error: Supplemental file '{source}' not found")
            return
        with open(FILENAME, "rb") as f:
            f.seek(index[source]["offset"])
            content = f.read(index[source]["length"])

    # Copy from normal source
    else:
        if not os.path.exists(source):
            print(f"Error: Normal file '{source}' not found on disk")
            return
        with open(source, "rb") as f:
            content = f.read()

    update_index(dest, "F", len(content), content)
    write_metadata()
    print(f"Copied {source} -> {dest}")

def show(path):
    load_index()
    if path not in index:
        print("File not found in supplemental FS")
        return
    meta = index[path]
    with open(FILENAME, "rb") as f:
        f.seek(meta["offset"])
        content = f.read(meta["length"])
    print(content.decode("utf-8").strip())

def ls(path):
    load_index()
    
    if path not in index:
        print("File or directory not found in supplemental FS")
        return

    meta = index[path]

    if meta["type"] == "F":
        print(f"{path}  {meta['timestamp']}")
    elif meta["type"] == "D":
        for other_path, other_meta in index.items():
            if other_path.startswith(path + "/"):
                print(f"{other_path}  {other_meta['timestamp']}")

def mkdir(path):
    if not path.startswith("+"):
        raise ValueError("Supplemental directory must start with '+'")

    if path in index:
        print("Directory already exists")
        return

    index[path] = {
        "type": "D",
        "offset": 0,
        "length": 0,
        "timestamp": datetime.now().isoformat()
    }

    hydrate_all_content()
    write_metadata()
    print(f"Directory created: {path}")

def merge(src1, src2, dest):
    load_index()

    # Must write to a supplemental file
    if not dest.startswith("+"):
        raise ValueError("Destination must be a supplemental file (+)")

    # Load source 1 (supplemental required)
    if not src1.startswith("+"):
        raise ValueError("First source must be a supplemental file starting with '+'")
    if src1 not in index or index[src1]["type"] != "F":
        raise FileNotFoundError(f"{src1} not found in supplemental FS")

    with open(FILENAME, "rb") as f:
        f.seek(index[src1]["offset"])
        content1 = f.read(index[src1]["length"])

    # Load source 2 (can be normal or supplemental)
    if src2.startswith("+"):
        if src2 not in index or index[src2]["type"] != "F":
            raise FileNotFoundError(f"{src2} not found in supplemental FS")
        with open(FILENAME, "rb") as f:
            f.seek(index[src2]["offset"])
            content2 = f.read(index[src2]["length"])
    else:
        if not os.path.exists(src2):
            raise FileNotFoundError(f"{src2} not found on disk")
        with open(src2, "rb") as f:
            content2 = f.read()

    combined = content1 + content2
    update_index(dest, "F", len(combined), combined)
    write_metadata()
    print(f"Merged {src1} + {src2} -> {dest}")

def rmdir(path):
    load_index()

    if path not in index or index[path]["type"] != "D":
        print("Directory not found in supplemental FS")
        return

    # Check if any files start with path + '/'
    prefix = path + "/"
    children = [p for p in index if p.startswith(prefix)]

    if children:
        print("Directory not empty. Cannot remove.")
        return

    del index[path]
    write_metadata()
    print(f"Removed directory: {path}")

def rm(path):
    load_index()

    if path not in index or index[path]["type"] != "F":
        print(f"Error: Supplemental file '{path}' not found or is not a file")
        return

    del index[path]
    write_metadata()
    print(f"Removed file: {path}")
