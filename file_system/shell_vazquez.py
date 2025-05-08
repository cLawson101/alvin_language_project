#!/usr/bin/env python3
import os
import sys
import time

PFS_FILE = 'private.pfs'

def load_pfs_records(): #Loads pfs records into directories
    if not os.path.exists(PFS_FILE):
        open(PFS_FILE, 'wb').close()
    records = []
    with open(PFS_FILE, 'rb') as f:
        while True:
            header = f.readline()
            if not header:
                break
            header = header.rstrip(b'\n')
            parts = header.split(b'|')
            tag = parts[0].decode()
            if tag == 'DIR':
                records.append({
                    'type': 'DIR',
                    'name': parts[1].decode(),
                    'ts': parts[2].decode()
                })
            elif tag == 'FILE':
                path = parts[1].decode()
                size = int(parts[2].decode())
                ts = parts[3].decode()
                data = f.read(size)
                f.read(1)
                records.append({
                    'type': 'FILE',
                    'path': path,
                    'size': size,
                    'ts': ts,
                    'data': data
                })
            else:
                break
    return records


def save_pfs_records(records): #saves pfs records onto pfs file
    with open(PFS_FILE, 'wb') as f:
        for rec in records:
            if rec['type'] == 'DIR':
                f.write(f"DIR|{rec['name']}|{rec['ts']}\n".encode())
            else:
                f.write(f"FILE|{rec['path']}|{rec['size']}|{rec['ts']}\n".encode())
                f.write(rec['data'])
                f.write(b"\n")


def find_dir(records, name): #finds directories in pfs file
    for rec in records:
        if rec['type'] == 'DIR' and rec['name'] == name:
            return rec
    return None


def find_file(records, path): #finds files in pfs file
    for rec in records:
        if rec['type'] == 'FILE' and rec['path'] == path:
            return rec
    return None


def read_src(src, records): #gets data from files, both disk files and pfs files
    if src.startswith('+'):
        rec = find_file(records, src.lstrip('+'))
        return None if not rec else rec['data']
    if not os.path.exists(src):
        return None
    raw = open(src, 'rb').read()
    return raw.rstrip(b'\n')


def write_file_to_pfs(path, data, records):#appends file record with its data
    if '/' in path:
        parent = path.split('/', 1)[0]
        if not find_dir(records, parent):
            print(f"merge/write: parent '+{parent}' not found")
            return False
    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    records.append({
        'type': 'FILE',
        'path': path,
        'size': len(data),
        'ts': ts,
        'data': data
    })
    return True


def cmd_mkdir(records, arg):#handles mkdir for pfs
    name = arg.lstrip('+')
    if find_dir(records, name):
        print(f"mkdir: '{arg}' exists")
    else:
        ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        records.append({'type': 'DIR', 'name': name, 'ts': ts})


def cmd_rmdir(records, arg):#handles rmdir for pfs
    name = arg.lstrip('+')
    dirrec = find_dir(records, name)
    if not dirrec:
        print(f"rmdir: '{arg}' not found")
    else:
        prefix = name + '/'
        if any(r['type'] == 'FILE' and r['path'].startswith(prefix) for r in records):
            print(f"rmdir: '{arg}' not empty")
        else:
            records.remove(dirrec)


def cmd_ls(records, arg):#handles ls for pfs
    name = arg.lstrip('+')
    frec = find_file(records, name)
    if frec:
        print(name, frec['ts'])
        return
    dirrec = find_dir(records, name)
    if not dirrec:
        print(f"ls: '{arg}' not found")
        return
    prefix = name + '/'
    for r in records:
        if r['type'] == 'FILE' and r['path'].startswith(prefix):
            sub = r['path'].split('/', 1)[1]
            print(sub, r['ts'])


def cmd_show(records, arg):#handles show for pfs
    frec = find_file(records, arg.lstrip('+'))
    if not frec:
        print(f"show: '{arg}' not found")
    else:
        sys.stdout.buffer.write(frec['data'])
        sys.stdout.write("\n")


def cmd_cp(records, args):#handles cp for pfs
    src, dest = args
    data = read_src(src, records)
    if data is None:
        print(f"cp: '{src}' not found")
        return
    dname = dest.lstrip('+')
    if find_file(records, dname):
        print(f"cp: '{dest}' exists")
        return
    write_file_to_pfs(dname, data, records)


def cmd_merge(records, args):#handles merge for pfs
    src1, src2, dest = args
    d1 = read_src(src1, records)
    if d1 is None:
        print(f"merge: '{src1}' not found")
        return
    d2 = read_src(src2, records)
    if d2 is None:
        print(f"merge: '{src2}' not found")
        return
    merged = d1 + b"\n" + d2
    dname = dest.lstrip('+')
    if find_file(records, dname):
        print(f"merge: '{dest}' exists")
        return
    write_file_to_pfs(dname, merged, records)


def cmd_rm(records, arg):#handles rm for pfs
    rec = find_file(records, arg.lstrip('+'))
    if not rec:
        print(f"rm: '{arg}' not found")
    else:
        records.remove(rec)


def main():#main loop
    cmds = {
        'mkdir': cmd_mkdir,
        'rmdir': cmd_rmdir,
        'ls': cmd_ls,
        'show': cmd_show,
        'cp': cmd_cp,
        'merge': cmd_merge,
        'rm': cmd_rm
    }
    while True:
        try:
            line = input('$ ')
        except EOFError:
            break
        if not line.strip():
            continue
        parts = line.split()
        op, args = parts[0], parts[1:]
        if op == 'quit':
            break
        if op == 'cd':
            if args:
                try: os.chdir(args[0])
                except Exception as e: print(f"cd: {e}")
            continue
        records = load_pfs_records()
        if op in ['mkdir','rmdir','ls','show','rm'] and args and args[0].startswith('+'):
            cmds[op](records, args[0])
        elif op == 'cp' and len(args) == 2 and args[1].startswith('+'):
            cmd_cp(records, args)
        elif op == 'merge' and len(args) == 3 and args[0].startswith('+') and args[2].startswith('+'):
            cmd_merge(records, args)
        else:
            os.system(line)#handles all system calls where there is no pfs involved
        save_pfs_records(records)

if __name__ == '__main__':
    main()
