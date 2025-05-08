import os
import sys
import re
import struct
import time

PFS_FILE = "private.pfs"
SUPERBLOCK_SIZE = 128
METADATA_ENTRY_SIZE = 128
MAX_ENTRIES = 100
METADATA_BLOCK_SIZE = METADATA_ENTRY_SIZE * MAX_ENTRIES
BITMAP_SIZE = MAX_ENTRIES
CONTENT_START = SUPERBLOCK_SIZE + BITMAP_SIZE + METADATA_BLOCK_SIZE

def initialize_pfs():
    if not os.path.exists(PFS_FILE):
        with open(PFS_FILE, "wb") as f:
            f.write(struct.pack("I", 0))  # number of files
            f.write(struct.pack("I", METADATA_ENTRY_SIZE))
            f.write(struct.pack("I", CONTENT_START))
            f.write(b'\x00' * (SUPERBLOCK_SIZE - 12))
            f.write(b'\x00' * BITMAP_SIZE)
            f.write(b'\x00' * METADATA_BLOCK_SIZE)
            print("[File system initialized in private.pfs]")

def find_free_metadata_slot():
    with open(PFS_FILE, "r+b") as f:
        f.seek(SUPERBLOCK_SIZE)
        bitmap = f.read(BITMAP_SIZE)
        for i in range(MAX_ENTRIES):
            if bitmap[i] == 0:
                f.seek(SUPERBLOCK_SIZE + i)
                f.write(b'\x01')
                return i
    return -1

def write_metadata(slot, name, file_type, size, offset):
    with open(PFS_FILE, "r+b") as f:
        entry_offset = SUPERBLOCK_SIZE + BITMAP_SIZE + (slot * METADATA_ENTRY_SIZE)
        f.seek(entry_offset)
        f.write(name.encode().ljust(32, b'\x00'))
        f.write(file_type.encode())  # 'F' or 'D'
        f.write(b'\x00' * 31)
        f.write(struct.pack("Q", size))
        f.write(struct.pack("Q", offset))
        f.write(time.ctime().encode().ljust(32, b'\x00'))
        f.write(b'\x00' * 15)

def read_supplemental_file(name):
    with open(PFS_FILE, "rb") as f:
        for i in range(MAX_ENTRIES):
            offset = SUPERBLOCK_SIZE + BITMAP_SIZE + i * METADATA_ENTRY_SIZE
            f.seek(offset)
            fname = f.read(32).rstrip(b'\x00').decode()
            ftype = f.read(1).decode()
            f.read(31)
            size = struct.unpack("Q", f.read(8))[0]
            content_offset = struct.unpack("Q", f.read(8))[0]
            f.read(32 + 15)
            if fname == name:
                f.seek(content_offset)
                return f.read(size)
    return None

def cp_command(src, dest):
    if not dest.startswith('+'):
        print("cp: destination must be supplemental (+)")
        return
    if src.startswith('+'):
        content = read_supplemental_file(src)
        if content is None:
            print("cp: source not found in supplemental FS")
            return
    else:
        try:
            with open(src, 'rb') as f:
                content = f.read()
        except:
            print("cp: source not found in normal FS")
            return
    with open(PFS_FILE, "ab") as f:
        offset = f.tell()
        f.write(content)
    slot = find_free_metadata_slot()
    if slot == -1:
        print("cp: no metadata space")
        return
    write_metadata(slot, dest, 'F', len(content), offset)

def show_command(name):
    content = read_supplemental_file(name)
    if content is None:
        print("show: file not found")
    else:
        print(content.decode(errors='ignore'))

def mkdir_command(name):
    if not name.startswith('+'):
        print("mkdir: supplemental dirs must start with +")
        return
    slot = find_free_metadata_slot()
    if slot == -1:
        print("mkdir: no metadata space")
        return
    with open(PFS_FILE, "ab") as f:
        offset = f.tell()
        f.write(b'')
    write_metadata(slot, name, 'D', 0, offset)

def rmdir_command(name):
    with open(PFS_FILE, "r+b") as f:
        for i in range(MAX_ENTRIES):
            offset = SUPERBLOCK_SIZE + BITMAP_SIZE + i * METADATA_ENTRY_SIZE
            f.seek(offset)
            fname = f.read(32).rstrip(b'\x00').decode()
            ftype = f.read(1).decode()
            if fname == name and ftype == 'D':
                f.seek(offset)
                f.write(b'EMPTY'.ljust(32, b'\x00'))
                f.write(b'\x00' * (METADATA_ENTRY_SIZE - 32))
                f.seek(SUPERBLOCK_SIZE + i)
                f.write(b'\x00')
                return
    print("rmdir: not found or not directory")

def rm_command(name):
    with open(PFS_FILE, "r+b") as f:
        for i in range(MAX_ENTRIES):
            offset = SUPERBLOCK_SIZE + BITMAP_SIZE + i * METADATA_ENTRY_SIZE
            f.seek(offset)
            fname = f.read(32).rstrip(b'\x00').decode()
            if fname == name:
                f.seek(offset)
                f.write(b'EMPTY'.ljust(32, b'\x00'))
                f.write(b'\x00' * (METADATA_ENTRY_SIZE - 32))
                f.seek(SUPERBLOCK_SIZE + i)
                f.write(b'\x00')
                return
    print("rm: file not found")

def ls_command(target=None):
    with open(PFS_FILE, "rb") as f:
        for i in range(MAX_ENTRIES):
            offset = SUPERBLOCK_SIZE + BITMAP_SIZE + i * METADATA_ENTRY_SIZE
            f.seek(offset)
            fname = f.read(32).rstrip(b'\x00').decode()
            ftype = f.read(1).decode()
            f.read(31 + 8 + 8)
            timestamp = f.read(32).rstrip(b'\x00').decode()
            f.read(15)
            if fname != '' and fname != 'EMPTY':
                if target is None or fname == target:
                    print(f"{fname} (modified: {timestamp})")

def merge_command(f1, f2, dest):
    if not (f1.startswith('+') and f2.startswith('+') and dest.startswith('+')):
        print("merge: all files must be supplemental (start with '+')")
        return
    data1 = read_supplemental_file(f1)
    data2 = read_supplemental_file(f2)
    
    if data1 is None or data2 is None:
        print("merge: source(s) not found")
        return
    combined = data1 + data2
    
    with open(PFS_FILE, "ab") as f:
        offset = f.tell()
        f.write(combined)

    slot = find_free_metadata_slot()
    if slot == -1:
        print("merge: no metadata space")
        return

    write_metadata(slot, dest, 'F', len(combined), offset)
    
def split_command(command):
    return re.findall(r'".*?"|\S+', command)

def expand_variables(command):
    words = command.split()
    for i in range(len(words)):
        if words[i].startswith("$"):
            var_name = words[i][1:]
            words[i] = os.environ.get(var_name, words[i])
    return " ".join(words)

def redirection(arg):
    input_file = None
    output_file = None
    arg1 = []
    i = 0
    while i < len(arg):
        if arg[i] == ">":
            if i + 1 < len(arg):
                output_file = arg[i+1]
                i += 1
            else:
                return None, None, None
        elif arg[i] == "<":
            if i + 1 < len(arg):
                input_file = arg[i + 1]
                i += 1
            else:
                return None, None, None
        else:
            arg1.append(arg[i])
        i += 1
    return arg1, input_file, output_file

def do_command(command):
    command = expand_variables(command)
    if "|" in command:
        print("Piping not supported in supplemental FS")
        return
    arg = split_command(command)
    arg = [w.strip('"') for w in arg]
    if not arg:
        return

    # Custom commands
    if arg[0] == "cp" and len(arg) == 3:
        cp_command(arg[1], arg[2]); return
    if arg[0] == "rm" and len(arg) == 2:
        rm_command(arg[1]); return
    if arg[0] == "mkdir" and len(arg) == 2:
        mkdir_command(arg[1]); return
    if arg[0] == "rmdir" and len(arg) == 2:
        rmdir_command(arg[1]); return
    if arg[0] == "ls":
        ls_command(arg[1] if len(arg) > 1 else None); return
    if arg[0] == "show" and len(arg) == 2:
        show_command(arg[1]); return
    if arg[0] == "merge" and len(arg) == 4:
        merge_command(arg[1], arg[2], arg[3]); return

    executable = arg[0]
    path = os.environ.get("PATH", "").split(":")
    for p in path:
        full = os.path.join(p, executable)
        if os.path.exists(full) and os.access(full, os.X_OK):
            pid = os.fork()
            if pid == 0:
                os.execve(full, arg, os.environ)
            else:
                os.waitpid(pid, 0)
            return
    print("Command not found")

def main():
    initialize_pfs()
    while True:
        try:
            command = input("$ ").strip()
            if command.lower() == "exit":
                break
            do_command(command)
        except EOFError:
            break

if __name__ == "__main__":
    main()
