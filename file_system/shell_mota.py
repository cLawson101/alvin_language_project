# Joe Mota and Daniel Reyes
#!/usr/bin/env python3
import os
import sys
import time
import re

# --- Persistent Supplementary File System (PFS) ---
PFS_FILE = 'private.pfs'
META_HEADER = 'PFS_META_V1'


class PFSEntry:
    def __init__(self, type_char, name, parent, length, modified, data_bytes=None):
        self.type = type_char        # 'F', 'D', or 'X'
        self.name = name             # string
        self.parent = parent         # string
        self.length = length         # int
        self.modified = modified     # int (epoch)
        self.data_bytes = data_bytes  # bytes for file content
        self.offset = None           # int (set in load)


class PFSManager:
    def __init__(self, filename=PFS_FILE):
        self.filename = filename
        self.entries = []
        # ensure file exists
        if not os.path.exists(self.filename):
            open(self.filename, 'wb').close()
        self._load()

    def _load(self):
        """
        Load metadata header and file contents into memory.
        Format:
        PFS_META_V1\n
        <type>|<name>|<parent>|<length>|<modified>\n ...\n
        blank line, then raw data blocks in entry order.
        """
        with open(self.filename, 'rb') as f:
            # read header
            first = f.readline().decode(errors='ignore').rstrip('\n')
            if first != META_HEADER:
                # no metadata header => empty PFS
                self.entries = []
                return
            # read metadata lines
            meta_lines = []
            while True:
                line = f.readline().decode(errors='ignore')
                if not line or line == '\n':
                    break
                meta_lines.append(line.rstrip('\n'))
            # parse entries
            self.entries = []
            for ln in meta_lines:
                parts = ln.split('|')
                if len(parts) != 5:
                    continue
                typ, name, parent, length, mod = parts
                entry = PFSEntry(typ, name, parent, int(length), int(mod))
                self.entries.append(entry)
            # read data blocks sequentially
            for e in self.entries:
                if e.type == 'F':
                    e.offset = f.tell()
                    e.data_bytes = f.read(e.length)
                else:
                    e.offset = None
                    e.data_bytes = None

    def _save(self):
        """
        Rewrite full PFS file: metadata header + metadata lines + data blocks.
        """
        with open(self.filename, 'wb') as f:
            # header
            f.write((META_HEADER + '\n').encode())
            # metadata
            for e in self.entries:
                line = f"{e.type}|{e.name}|{e.parent}|{e.length}|{e.modified}\n"
                f.write(line.encode())
            f.write(b"\n")  # end of metadata
            # data blocks
            for e in self.entries:
                if e.type == 'F' and e.data_bytes is not None:
                    f.write(e.data_bytes)
        # reload to reset offsets
        self._load()

    def list(self, path='+'):
        prefix = path.lstrip('+')
        out = []
        for e in self.entries:
            if e.type != 'X' and (path == '+' or e.parent == prefix):
                out.append((e.name, time.ctime(e.modified)))
        return out

    def show(self, filepath):
        name = filepath.lstrip('+')
        for e in self.entries:
            if e.name == name and e.type == 'F':
                return e.data_bytes.decode()
        raise FileNotFoundError(filepath)

    def mkdir(self, dirname):
        name = dirname.lstrip('+')
        entry = PFSEntry('D', name, 'ROOT', 0, int(time.time()))
        self.entries.append(entry)
        self._save()

    def rmdir(self, dirname):
        name = dirname.lstrip('+')
        # ensure empty
        for e in self.entries:
            if e.parent == name and e.type != 'X':
                raise OSError('Directory not empty')
        # mark delete
        for e in self.entries:
            if e.name == name and e.type == 'D':
                e.type = 'X'
        self._save()

    def rm(self, filepath):
        name = filepath.lstrip('+')
        for e in self.entries:
            if e.name == name and e.type == 'F':
                e.type = 'X'
        self._save()

    def cp(self, src, dst):
        # read source bytes
        if src.startswith('+'):
            data = self.show(src).encode()
        else:
            with open(src, 'rb') as f:
                data = f.read()
        name = dst.lstrip('+')
        entry = PFSEntry('F', name, 'ROOT', len(data), int(time.time()), data)
        self.entries.append(entry)
        self._save()

    def merge(self, a, b, out):
        da = (self.show(a) if a.startswith('+') else open(a).read()).encode()
        db = (self.show(b) if b.startswith('+') else open(b).read()).encode()
        name = out.lstrip('+')
        entry = PFSEntry('F', name, 'ROOT', len(
            da+db), int(time.time()), da+db)
        self.entries.append(entry)
        self._save()


# instantiate
pfs = PFSManager()

# --- Standard Microshell (unaltered) ---


def split_command(cmd): return re.findall(r'".*?"|\S+', cmd)


def find_path(cmd):
    for p in os.environ.get('PATH', '').split(os.pathsep):
        exe = os.path.join(p, cmd)
        if os.path.isfile(exe) and os.access(exe, os.X_OK):
            return exe
    return None


def expand_variables(cmd):
    parts = cmd.split()
    for i, w in enumerate(parts):
        if w.startswith('$'):
            parts[i] = os.getenv(w[1:], w)
    return ' '.join(parts)


def redirection(args):
    inf = outf = None
    clean = []
    i = 0
    while i < len(args):
        if args[i] == '>':
            outf = args[i+1]
            i += 1
        elif args[i] == '<':
            inf = args[i+1]
            i += 1
        else:
            clean.append(args[i])
        i += 1
    return clean, inf, outf


def change_dir(args):
    tgt = args[1] if len(args) > 1 else os.getenv('HOME', '/')
    try:
        os.chdir(tgt)
    except Exception as e:
        print(f'cd: {e}')


def do_pipe(cmd):
    L, R = [c.strip() for c in cmd.split('|', 1)]
    a1 = [w.strip('"') for w in split_command(L)]
    a2 = [w.strip('"') for w in split_command(R)]
    p1 = find_path(a1[0])
    p2 = find_path(a2[0])
    if not p1 or not p2:
        print('Command not found')
        return
    r, w = os.pipe()
    if os.fork() == 0:
        os.dup2(w, 1)
        os.close(r)
        os.close(w)
        os.execve(p1, a1, os.environ)
    if os.fork() == 0:
        os.dup2(r, 0)
        os.close(r)
        os.close(w)
        os.execve(p2, a2, os.environ)
    os.close(r)
    os.close(w)
    os.wait()
    os.wait()


def do_command(cmd):
    cmd = expand_variables(cmd)
    if '|' in cmd:
        return do_pipe(cmd)
    args = [w.strip('"') for w in split_command(cmd)]
    if not args:
        return
    if args[0] == 'cd':
        return change_dir(args)
    # PFS
    if args[0] in ('ls', 'show', 'mkdir', 'rmdir', 'cp', 'merge', 'rm') and any(a.startswith('+') for a in args[1:]):
        c = args[0]
        try:
            if c == 'ls':
                for n, mt in pfs.list(args[1]):
                    print(f'{n}\t{mt}')
            elif c == 'show':
                print(pfs.show(args[1]))
            elif c == 'mkdir':
                pfs.mkdir(args[1])
            elif c == 'rmdir':
                pfs.rmdir(args[1])
            elif c == 'rm':
                pfs.rm(args[1])
            elif c == 'cp':
                pfs.cp(args[1], args[2])
            elif c == 'merge':
                pfs.merge(args[1], args[2], args[3])
        except Exception as e:
            print(f'PFS Error: {e}')
        return
    # external with redirection
    args, inf, outf = redirection(args)
    if args is None:
        return
    bg = False
    if args and args[-1] == '&':
        bg = True
        args = args[:-1]
    if not args:
        return
    exe = find_path(args[0])
    if not exe:
        print('Command not found')
        return
    pid = os.fork()
    if pid == 0:
        if inf:
            fd = os.open(inf, os.O_RDONLY)
            os.dup2(fd, 0)
            os.close(fd)
        if outf:
            fd = os.open(outf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            os.dup2(fd, 1)
            os.close(fd)
        os.execve(exe, args, os.environ)
        sys.exit(1)
    if not bg:
        os.waitpid(pid, 0)


def main():
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1]) as f:
                for ln in f:
                    ln = ln.strip()
                    if ln and not ln.startswith('#'):
                        do_command(ln)
        except FileNotFoundError:
            print(f"File not found: {sys.argv[1]}")
        return
    while True:
        try:
            ln = input('$ ').strip()
        except EOFError:
            break
        if not ln:
            continue
        if ln.lower() == 'exit':
            break
        do_command(ln)


if __name__ == '__main__':
    main()
