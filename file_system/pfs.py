import os
import time

PFS_FILENAME = "private.pfs"



def read_metadata():
    if not os.path.exists(PFS_FILENAME):
        return []

    entries = []
    with open(PFS_FILENAME, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.strip().split(':', 4)
            if parts[0] == "FILE" and len(parts) == 5:
                entry = {
                    'type': parts[0],
                    'path': parts[1],
                    'offset': int(parts[2]),
                    'size': int(parts[3]),
                    'timestamp': int(parts[4])
                }
                entries.append(entry)
            elif parts[0] == "DIR" and len(parts) == 3:
                entry = {
                    'type': parts[0],
                    'path': parts[1],
                    'timestamp': int(parts[2])
                }
                entries.append(entry)
            else:
                
                continue
    return entries

def write_metadata(entries):
    with open(PFS_FILENAME, 'w', encoding='utf-8') as f:
        for entry in entries:
            if entry['type'] == "FILE":
                f.write(f"FILE:{entry['path']}:{entry['offset']}:{entry['size']}:{entry['timestamp']}\n")
            elif entry['type'] == "DIR":
                f.write(f"DIR:{entry['path']}:{entry['timestamp']}\n")

def append_content(data):
    with open(PFS_FILENAME, 'ab') as f:
        f.seek(0, os.SEEK_END)
        offset = f.tell()
        f.write(data.encode('utf-8'))
        return offset

def find_entry(path):
    for entry in read_metadata():
        if entry['path'] == path:
            return entry
    return None

def remove_entry(path):
    entries = read_metadata()
    new_entries = [e for e in entries if e['path'] != path]
    write_metadata(new_entries)

def is_in_directory(file_path, dir_path):
    return file_path.startswith(dir_path.rstrip('/') + '/')



def cp_pfs(src, dst):
    if not dst.startswith('+'):
        print("cp_pfs only supports copying TO supplementary files.")
        return

    
    if not src.startswith('+'):
        if not os.path.exists(src):
            print(f"cp_pfs: Source file '{src}' not found.")
            return
        with open(src, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        entry = find_entry(src)
        if not entry or entry['type'] != 'FILE':
            print(f"cp_pfs: Supplemental file '{src}' not found.")
            return
        with open(PFS_FILENAME, 'rb') as f:
            f.seek(entry['offset'])
            content = f.read(entry['size']).decode('utf-8')

    offset = append_content(content)
    size = len(content)
    timestamp = int(time.time())

    entries = read_metadata()
    entries.append({
        'type': 'FILE',
        'path': dst,
        'offset': offset,
        'size': size,
        'timestamp': timestamp
    })
    write_metadata(entries)

def rm_pfs(path):
    entry = find_entry(path)
    if not entry or entry['type'] != 'FILE':
        print(f"rm: '{path}' not found or not a file.")
        return
    remove_entry(path)

def mkdir_pfs(path):
    if not path.startswith('+'):
        print("mkdir_pfs only supports supplemental directories.")
        return
    if find_entry(path):
        print(f"mkdir: Directory '{path}' already exists.")
        return
    entries = read_metadata()
    entries.append({
        'type': 'DIR',
        'path': path,
        'timestamp': int(time.time())
    })
    write_metadata(entries)

def rmdir_pfs(path):
    entry = find_entry(path)
    if not entry or entry['type'] != 'DIR':
        print(f"rmdir: '{path}' not found or not a directory.")
        return
    
    for e in read_metadata():
        if e['type'] == 'FILE' and is_in_directory(e['path'], path):
            print(f"rmdir: Directory '{path}' is not empty.")
            return
    remove_entry(path)

def ls_pfs(path=None):
    entries = read_metadata()
    if not path:
        for entry in entries:
            print(f"{entry['path']} (last modified: {time.ctime(entry['timestamp'])})")
        return

    entry = find_entry(path)
    if not entry:
        print(f"ls: '{path}' not found.")
        return

    if entry['type'] == 'FILE':
        print(f"{path} (last modified: {time.ctime(entry['timestamp'])})")
    elif entry['type'] == 'DIR':
        for e in entries:
            if e['type'] == 'FILE' and is_in_directory(e['path'], path):
                print(f"{e['path']} (last modified: {time.ctime(e['timestamp'])})")

def merge_pfs(src1, src2, dst):
    content = ""
    for src in [src1, src2]:
        if src.startswith('+'):
            entry = find_entry(src)
            if not entry or entry['type'] != 'FILE':
                print(f"merge: Source '{src}' not found or not a file.")
                return
            with open(PFS_FILENAME, 'rb') as f:
                f.seek(entry['offset'])
                content += f.read(entry['size']).decode('utf-8')
        else:
            if not os.path.exists(src):
                print(f"merge: Normal file '{src}' not found.")
                return
            with open(src, 'r', encoding='utf-8') as f:
                content += f.read()

    offset = append_content(content)
    size = len(content)
    timestamp = int(time.time())

    entries = read_metadata()
    entries.append({
        'type': 'FILE',
        'path': dst,
        'offset': offset,
        'size': size,
        'timestamp': timestamp
    })
    write_metadata(entries)

def show_pfs(path):
    entry = find_entry(path)
    if not entry or entry['type'] != 'FILE':
        print(f"show: File '{path}' not found.")
        return
    with open(PFS_FILENAME, 'rb') as f:
        f.seek(entry['offset'])
        content = f.read(entry['size']).decode('utf-8')
        print(content)