#!/usr/bin/env python3
import os, sys, time, struct

PFS_PATH = 'private.pfs'
MAGIC = b'PFS1'
MAX_ENTRIES = 1024
NAME_SIZE = 64
BUFSIZE = 4096

TYPE_UNUSED = 0
TYPE_FILE   = 1
TYPE_DIR    = 2

class PFSEntry:
    struct_fmt = f'{NAME_SIZE}s B I Q Q Q'
    struct_len = struct.calcsize(struct_fmt)

    def __init__(self, name=b'', type=0, parent=0, size=0, offset=0, mtime=0):
        self.name   = name.rstrip(b'\x00')
        self.type   = type
        self.parent = parent
        self.size   = size
        self.offset = offset
        self.mtime  = mtime

    @classmethod
    def from_bytes(cls, data):
        name, type, parent, size, offset, mtime = struct.unpack(cls.struct_fmt, data)
        return cls(name, type, parent, size, offset, mtime)

    def to_bytes(self):
        name_padded = self.name.ljust(NAME_SIZE, b'\x00')
        return struct.pack(self.struct_fmt, name_padded, self.type,
                           self.parent, self.size, self.offset, self.mtime)

ENTRY_SIZE = PFSEntry.struct_len
SUPERBLOCK_SIZE = 16 
ENTRY_TABLE_OFFSET = SUPERBLOCK_SIZE
DATA_REGION_OFFSET = SUPERBLOCK_SIZE + MAX_ENTRIES * ENTRY_SIZE

class PFS:
    def __init__(self, path=PFS_PATH):
        self.fd = os.open(path, os.O_RDWR|os.O_CREAT, 0o600)
        self._init_if_empty()
        self._load_superblock()
        self._load_entries()

    def _init_if_empty(self):
        st = os.fstat(self.fd)
        if st.st_size < DATA_REGION_OFFSET:
            os.lseek(self.fd, 0, os.SEEK_SET)
            header = MAGIC + struct.pack('!III', 1, 1, DATA_REGION_OFFSET)
            os.write(self.fd, header)
            os.write(self.fd, b'\x00' * (MAX_ENTRIES * ENTRY_SIZE))

    def _load_superblock(self):
        os.lseek(self.fd, 0, os.SEEK_SET)
        data = os.read(self.fd, SUPERBLOCK_SIZE)
        magic, version, self.num_entries, self.next_data_offset = struct.unpack('!4sIII', data)
        if magic != MAGIC:
            raise RuntimeError("Not a PFS volume")

    def _load_entries(self):
        self.entries = []
        os.lseek(self.fd, ENTRY_TABLE_OFFSET, os.SEEK_SET)
        for _ in range(MAX_ENTRIES):
            raw = os.read(self.fd, ENTRY_SIZE)
            self.entries.append(PFSEntry.from_bytes(raw))

    def _write_entry(self, idx):
        os.lseek(self.fd, ENTRY_TABLE_OFFSET + idx * ENTRY_SIZE, os.SEEK_SET)
        os.write(self.fd, self.entries[idx].to_bytes())

    def _allocate_entry_index(self):
        for i, e in enumerate(self.entries):
            if e.type == TYPE_UNUSED:
                return i
        raise RuntimeError("PFS: entry table full")

    def _find_entry_idx(self, path):
        parts = path.strip('/').split('/')
        parent = 0
        for name in parts:
            for idx, e in enumerate(self.entries):
                if e.parent == parent and e.name == name.encode() and e.type != TYPE_UNUSED:
                    parent = idx
                    break
            else:
                return None
        return parent

    def _parent_and_name(self, path):
        parts = path.strip('/').rsplit('/', 1)
        if len(parts) == 2:
            parent_path, name = parts
            pidx = self._find_entry_idx(parent_path)
            if pidx is None or self.entries[pidx].type != TYPE_DIR:
                raise FileNotFoundError(parent_path)
            return pidx, name
        return 0, parts[0]

    def create_file(self, path):
        idx = self._allocate_entry_index()
        parent, name = self._parent_and_name(path)
        off = self.next_data_offset
        e = PFSEntry(name=name.encode(), type=TYPE_FILE,
                     parent=parent, size=0,
                     offset=off, mtime=int(time.time()))
        self.entries[idx] = e
        self._write_entry(idx)
        return idx

    def open_file(self, path):
        idx = self._find_entry_idx(path)
        if idx is None or self.entries[idx].type != TYPE_FILE:
            raise FileNotFoundError(path)
        return idx

    def read_file(self, idx, size, offset):
        e = self.entries[idx]
        os.lseek(self.fd, e.offset + offset, os.SEEK_SET)
        return os.read(self.fd, min(size, e.size - offset))

    def write_file(self, idx, data, offset):
        e = self.entries[idx]
        os.lseek(self.fd, e.offset + offset, os.SEEK_SET)
        os.write(self.fd, data)
        e.size = max(e.size, offset + len(data))
        e.mtime = int(time.time())
        self.entries[idx] = e
        self._write_entry(idx)

    def delete(self, path):
        idx = self._find_entry_idx(path)
        if idx is None:
            raise FileNotFoundError(path)
        self.entries[idx] = PFSEntry()
        self._write_entry(idx)

    def create_dir(self, path):
        idx = self._allocate_entry_index()
        parent, name = self._parent_and_name(path)
        e = PFSEntry(name=name.encode(), type=TYPE_DIR,
                     parent=parent, size=0, offset=0,
                     mtime=int(time.time()))
        self.entries[idx] = e
        self._write_entry(idx)
        return idx

    def remove_dir(self, path):
        idx = self._find_entry_idx(path)
        if idx is None or self.entries[idx].type != TYPE_DIR:
            raise FileNotFoundError(path)
        for e in self.entries:
            if e.parent == idx:
                raise OSError("Directory not empty")
        self.entries[idx] = PFSEntry()
        self._write_entry(idx)

    def list_dir(self, path):
        idx = self._find_entry_idx(path)
        if idx is None:
            raise FileNotFoundError(path)
        e = self.entries[idx]
        if e.type == TYPE_FILE:
            return [(e.name.decode(), e.mtime)]
        out = []
        for entry in self.entries:
            if entry.parent == idx and entry.type != TYPE_UNUSED:
                out.append((entry.name.decode(), entry.mtime))
        return out

    def update_mtime(self, path):
        idx = self._find_entry_idx(path)
        if idx is None:
            raise FileNotFoundError(path)
        e = self.entries[idx]
        e.mtime = int(time.time())
        self.entries[idx] = e
        self._write_entry(idx)


# Instantiate PFS
pfs = PFS()

###################### Shell command functions ##################################################3

def cmd_cp(src, dst):
    # open source
    if src.startswith('+'):
        si = pfs.open_file(src[1:])
        def read_chunk():
            buf = pfs.read_file(si, BUFSIZE, read_chunk.offset)
            read_chunk.offset += len(buf)
            return buf
        read_chunk.offset = 0
    else:
        sf = os.open(src, os.O_RDONLY)
        def read_chunk():
            return os.read(sf, BUFSIZE)

    # open/create destination
    if dst.startswith('+'):
        try: pfs.delete(dst[1:])
        except: pass
        di = pfs.create_file(dst[1:])
        def write_chunk(data):
            nonlocal di
            pfs.write_file(di, data, write_chunk.offset)
            write_chunk.offset += len(data)
        write_chunk.offset = 0
    else:
        df = os.open(dst, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o644)
        def write_chunk(data):
            os.write(df, data)

    # copy loop
    while True:
        buf = read_chunk()
        if not buf: break
        write_chunk(buf)

    if dst.startswith('+'):
        pfs.update_mtime(dst[1:])

def cmd_rm(*paths):
    for path in paths:
        if not path.startswith('+'):
            print(f"rm: only supplementary paths allowed: {path}", file=sys.stderr)
            continue
        pfs.delete(path[1:])

def cmd_mkdir(*paths):
    for path in paths:
        if not path.startswith('+'):
            print(f"mkdir: only supplementary dirs allowed: {path}", file=sys.stderr)
            continue
        pfs.create_dir(path[1:])

def cmd_rmdir(*paths):
    for path in paths:
        if not path.startswith('+'):
            print(f"rmdir: only supplementary dirs allowed: {path}", file=sys.stderr)
            continue
        try:
            pfs.remove_dir(path[1:])
        except OSError:
            print(f"rmdir: {path}: directory not empty", file=sys.stderr)

def cmd_ls(path):
    if not path.startswith('+'):
        print(f"ls: only supplementary paths allowed: {path}", file=sys.stderr)
        return
    items = pfs.list_dir(path[1:])
    for name, mtime in items:
        print(f"+{name}\t{time.ctime(mtime)}")

def cmd_merge(src1, src2, dst):
    if not dst.startswith('+'):
        print("merge: destination must be a supplementary path (+...)", file=sys.stderr)
        return

    def make_reader(path):
        if path.startswith('+'):
            idx = pfs.open_file(path[1:])
            def reader():
                buf = pfs.read_file(reader.idx, BUFSIZE, reader.offset)
                reader.offset += len(buf)
                return buf
            reader.idx = idx
            reader.offset = 0
            return reader
        else:
            fd = os.open(path, os.O_RDONLY)
            def reader():
                return os.read(fd, BUFSIZE)
            return reader

    r1 = make_reader(src1)
    r2 = make_reader(src2)

    dpath = dst[1:]
    try: pfs.delete(dpath)
    except: pass
    di = pfs.create_file(dpath)

    def write_dest(data):
        nonlocal di
        pfs.write_file(di, data, write_dest.offset)
        write_dest.offset += len(data)
    write_dest.offset = 0

    for r in (r1, r2):
        while True:
            buf = r()
            if not buf: break
            write_dest(buf)

    pfs.update_mtime(dpath)

def cmd_show(path):
    if not path.startswith('+'):
        print(f"show: only supplementary paths allowed: {path}", file=sys.stderr)
        return
    idx = pfs.open_file(path[1:])
    offset = 0
    while True:
        buf = pfs.read_file(idx, BUFSIZE, offset)
        if not buf: break
        os.write(1, buf)
        offset += len(buf)

######################## CLI dispatch ##############################################################

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: pfs.py <cmd> [args...]", file=sys.stderr)
        sys.exit(1)
    cmd, *args = sys.argv[1:]
    try:
        if   cmd == 'cp'    and len(args)==2: cmd_cp(*args)
        elif cmd == 'rm':        cmd_rm(*args)
        elif cmd == 'mkdir':     cmd_mkdir(*args)
        elif cmd == 'rmdir':     cmd_rmdir(*args)
        elif cmd == 'ls'    and len(args)==1: cmd_ls(args[0])
        elif cmd == 'merge' and len(args)==3: cmd_merge(*args)
        elif cmd == 'show'  and len(args)==1: cmd_show(args[0])
        else:
            print(f"Unknown or invalid args for '{cmd}'", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
