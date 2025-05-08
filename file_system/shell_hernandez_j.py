import os
import sys
import time
import re

PFS_FILENAME = "private.pfs"

class SupplementaryFileSystem:
    def __init__(self, filename=PFS_FILENAME):
        self.filename = filename

    def _read_directory(self):
        entries = {}
        try:
            with open(self.filename, 'rb') as f:
                while True:
                    pos = f.tell()
                    line = f.readline()
                    if not line:
                        break
                    if line[0:1] == b'X':
                        continue
                    if len(line) < 93:
                        continue
                    type_char = chr(line[0])
                    name = line[1:65].split(b'\x00', 1)[0].decode()
                    size = int(line[65:73])
                    timestamp = int(line[73:83])
                    offset = int(line[83:93])
                    entries[name] = {'type': type_char, 'size': size, 'timestamp': timestamp, 'offset': offset}
        except FileNotFoundError:
            pass
        return entries

    def _write_entry(self, entry):
        with open(self.filename, 'ab') as f:
            f.write(entry.encode('utf-8'))

    def cp(self, source, destination):
        if not destination.startswith('+'):
            print("Destination must be a supplementary file.")
            return
        entries = self._read_directory()

        if source.startswith('+'):
            source_name = source[1:]
            if source_name not in entries:
                print("Source file not found.")
                return
            meta = entries[source_name]
            with open(self.filename, 'rb') as f:
                f.seek(meta['offset'])
                content = f.read(meta['size'])
        else:
            try:
                with open(source, 'rb') as f:
                    content = f.read()
            except FileNotFoundError:
                print("Source file not found.")
                return

        # Mark old destination if exists
        dest_name = destination[1:]
        if dest_name in entries:
            self._mark_deleted(dest_name)

        with open(self.filename, 'ab') as f:
            offset = f.tell()
            f.write(content)
        entry = f"F{dest_name.ljust(64, chr(0))}{len(content):08d}{int(time.time()):010d}{offset:010d}\n"
        self._write_entry(entry)

    def _mark_deleted(self, name):
        try:
            with open(self.filename, 'r+b') as f:
                while True:
                    pos = f.tell()
                    line = f.readline()
                    if not line:
                        break
                    if line[0:1] == b'X':
                        continue
                    entry_name = line[1:65].split(b'\x00', 1)[0].decode()
                    if entry_name == name:
                        f.seek(pos)
                        f.write(b'X')
                        return
        except FileNotFoundError:
            pass

    def rm(self, filename):
        if not filename.startswith('+'):
            print("Must remove supplementary files.")
            return
        name = filename[1:]
        entries = self._read_directory()
        if name not in entries:
            print("File not found.")
            return
        self._mark_deleted(name)

    def mkdir(self, dirname):
        if not dirname.startswith('+'):
            print("Must create supplementary directories.")
            return
        name = dirname[1:]
        entry = f"D{name.ljust(64, chr(0))}{0:08d}{int(time.time()):010d}{0:010d}\n"
        self._write_entry(entry)

    def rmdir(self, dirname):
        if not dirname.startswith('+'):
            print("Must remove supplementary directories.")
            return
        name = dirname[1:]
        entries = self._read_directory()
        # Check if any files belong to this dir
        has_files = any(entry.startswith(name + "/") for entry in entries)
        if has_files:
            print("Directory not empty.")
            return
        if name in entries and entries[name]['type'] == 'D':
            self._mark_deleted(name)
        else:
            print("Directory not found.")

    def ls(self, target):
        entries = self._read_directory()
        if target.startswith('+'):
            name = target[1:]
            if name in entries:
                meta = entries[name]
                if meta['type'] == 'F':
                    print(f"{name}  {time.ctime(meta['timestamp'])}")
                elif meta['type'] == 'D':
                    for entry, meta in entries.items():
                        if entry.startswith(name + "/"):
                            print(f"{entry}  {time.ctime(meta['timestamp'])}")
                else:
                    print("Target not found.")
            else:
                print("Target not found.")
        else:
            print("Target must be a supplementary file or directory.")

    def merge(self, file1, file2, merged_filename):
        entries = self._read_directory()
        files = []
        for src in [file1, file2]:
            if src.startswith('+'):
                src_name = src[1:]
                if src_name not in entries:
                    print(f"File {src} not found.")
                    return
                meta = entries[src_name]
                with open(self.filename, 'rb') as f:
                    f.seek(meta['offset'])
                    content = f.read(meta['size'])
            else:
                try:
                    with open(src, 'rb') as f:
                        content = f.read()
                except FileNotFoundError:
                    print(f"File {src} not found.")
                    return
            files.append(content)
        merged_content = files[0] + files[1]
        merged_name = merged_filename[1:]
        with open(self.filename, 'ab') as f:
            offset = f.tell()
            f.write(merged_content)
        entry = f"F{merged_name.ljust(64, chr(0))}{len(merged_content):08d}{int(time.time()):010d}{offset:010d}\n"
        self._write_entry(entry)

    def show(self, filename):
        if not filename.startswith('+'):
            print("Must show supplementary files.")
            return
        name = filename[1:]
        entries = self._read_directory()
        if name not in entries:
            print("File not found.")
            return
        meta = entries[name]
        with open(self.filename, 'rb') as f:
            f.seek(meta['offset'])
            content = f.read(meta['size'])
            print(content.decode('utf-8'))

# Shell Code Below

def split_command(command):
    return re.findall(r'".*?"|\S+', command)

def expand_variables(command):
    words = command.split()
    for i in range(len(words)):
        if words[i].startswith("$"):
            var_name = words[i][1:]
            words[i] = os.environ.get(var_name, words[i])
    return " ".join(words)

def do_command(command):
    command = expand_variables(command)

    arg = split_command(command)
    arg = [word.strip('"') for word in arg]

    if not arg:
        return

    if arg[0] in ["cp", "rm", "mkdir", "rmdir", "ls", "merge", "show"]:
        pfs = SupplementaryFileSystem()
        if arg[0] == "cp":
            pfs.cp(arg[1], arg[2])
        elif arg[0] == "rm":
            pfs.rm(arg[1])
        elif arg[0] == "mkdir":
            pfs.mkdir(arg[1])
        elif arg[0] == "rmdir":
            pfs.rmdir(arg[1])
        elif arg[0] == "ls":
            pfs.ls(arg[1])
        elif arg[0] == "merge":
            pfs.merge(arg[1], arg[2], arg[3])
        elif arg[0] == "show":
            pfs.show(arg[1])
        return
    else:
        print("Command not found in supplemental file system.")

def main():
    print("Welcome to the Supplemental Shell. Type 'exit' to quit.")
    while True:
        try:
            command = input("$ ").strip()
            if not command:
                continue
            if command.lower() == "exit":
                break
            do_command(command)
        except EOFError:
            break

if __name__ == "__main__":
    main()
