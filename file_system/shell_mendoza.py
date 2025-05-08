import os
import sys
import time
import base64

PFS_FILENAME = 'private.pfs'

#initialize container file

def init_pfs():
    if not os.path.exists(PFS_FILENAME):
        open(PFS_FILENAME, 'w').close()

# timestamp as string

def get_timestamp():
    return str(int(time.time()))

# load everything from private.pfs
# name | timestamp | size | encoded_content

def load_entries():
    entries = []
    if not os.path.exists(PFS_FILENAME):
        return entries
    with open(PFS_FILENAME, 'r') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            parts = line.split('|', 3)
            if len(parts) != 4:
                continue
            name, ts, size_str, encoded = parts
            try:
                content = base64.b64decode(encoded).decode('utf-8')
            except Exception:
                content = ''
            entries.append({
                'name': name,
                'timestamp': ts,
                'size': int(size_str),
                'content': content
            })
    return entries

#overwrite file with updated entry

def save_entries(entries):
    with open(PFS_FILENAME, 'w') as f:
        for e in entries:
            encoded = base64.b64encode(e['content'].encode('utf-8')).decode('utf-8')
            f.write(f"{e['name']}|{e['timestamp']}|{e['size']}|{encoded}\n")

#find entry by name

def find_entry(entries, name):
    for e in entries:
        if e['name'] == name:
            return e
    return None

#create or update a PFS file/directory entry

def write_file(name, content):
    entries = load_entries()
    ts = get_timestamp()
    size = len(content)
    existing = find_entry(entries, name)
    if existing:
        existing['timestamp'] = ts
        existing['size'] = size
        existing['content'] = content
    else:
        entries.append({
            'name': name,
            'timestamp': ts,
            'size': size,
            'content': content
        })
    save_entries(entries)

#Delete

def delete_entry(name):
    entries = load_entries()
    new_entries = [e for e in entries if e['name'] != name]
    if len(new_entries) == len(entries):
        return False
    save_entries(new_entries)
    return True

#display files contents

def show_file(path):
    if not path.startswith('+'):
        try:
            print(open(path, 'r').read(), end='')
        except FileNotFoundError:
            print(f"Error: '{path}' not found")
        return
    name = path[1:]
    entries = load_entries()
    e = find_entry(entries, name)
    if not e:
        for ent in entries:
            if ent['name'] == name or ent['name'].endswith('/' + name):
                e = ent
                break
    if e:
        print(e['content'], end='')
    else:
        print("Error: File not found.")

#list single file or all entries if path is +
def ls_file(path):
    if not path.startswith('+'):
        os.system(f"ls {path}")
        return
    name = path[1:]
    entries = load_entries()
    if name in ('', '.'):  # list all
        for e in entries:
            print(f"{e['name']}\t{e['size']} bytes\tLast Modified: {time.ctime(int(e['timestamp']))}")
    else:
        e = find_entry(entries, name)
        if not e:
            for ent in entries:
                if ent['name'] == name or ent['name'].endswith('/' + name):
                    e = ent
                    break
        if e:
            print(f"{e['name']}\t{e['size']} bytes\tLast Modified: {time.ctime(int(e['timestamp']))}")
        else:
            print("Error: File not found.")

#copy from OS or PFS into OS or PFS

def cp_file(src, dst):
    if src.startswith('+'):
        e = find_entry(load_entries(), src[1:])
        if not e:
            print("Source file not found.")
            return
        content = e['content']
    else:
        try:
            with open(src, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"cp: cannot stat '{src}': No such file or directory")
            return
    if dst.startswith('+'):
        write_file(dst[1:], content)
    else:
        try:
            with open(dst, 'w') as f:
                f.write(content)
        except Exception as ex:
            print(f"cp: error writing '{dst}': {ex}")

#make a directory entry 

def mkdir_fs(path):
    if not path.startswith('+'):
        try:
            os.mkdir(path)
        except FileExistsError:
            print(f"mkdir: cannot create directory '{path}': File exists")
        return
    name = path[1:].rstrip('/') + '/'
    write_file(name, '')

#remove directory only if empty

def rmdir_fs(path):
    if not path.startswith('+'):
        try:
            os.rmdir(path)
        except Exception as ex:
            print(f"rmdir: {ex}")
        return
    name = path[1:].rstrip('/') + '/'
    entries = load_entries()
    e = find_entry(entries, name)
    if not e:
        print(f"rmdir: failed to remove '{path}': No directory")
        return
    #check children
    children = [ent for ent in entries if ent['name'].startswith(name) and ent['name'] != name]
    if children:
        print(f"rmdir: failed to remove '{path}': Directory is not empty")
    else:
        delete_entry(name)
#Merge two files
def merge_files(f1, f2, dst):
    #get content 1
    if f1.startswith('+'):
        name1 = f1[1:]
        entries = load_entries()
        e1 = find_entry(entries, name1) or find_entry(entries, name1 + '.txt')
        if not e1:
            print("One of the files does not exist.")
            return
        c1 = e1['content']
    else:
        try:
            c1 = open(f1, 'r').read()
        except Exception:
            print("One of the files does not exist.")
            return
    #get content 2
    if f2.startswith('+'):
        name2 = f2[1:]
        entries = load_entries()
        e2 = find_entry(entries, name2) or find_entry(entries, name2 + '.txt')
        if not e2:
            print("One of th files does not exist.")
            return
        c2 = e2['content']
    else:
        try:
            c2 = open(f2, 'r').read()
        except Exception:
            print("One of the files does not exist.")
            return
    #merge
    merged = c1 + "\n" + c2
    if dst.startswith('+'):
        write_file(dst[1:], merged)
    else:
        with open(dst, 'w') as f:
            f.write(merged)

#remove file entry 

def rm_file(path):
    if path.startswith('+'):
        if not delete_entry(path[1:]):
            print(f"rm: cannot remove '{path}': No file or directory")
    else:
        try:
            os.remove(path)
        except Exception:
            print(f"rm: cannot remove '{path}': No file or directory")

#main loop

def main():
    init_pfs()
    while True:
        try:
            parts = input('>>> ').strip().split()
        except EOFError:
            break
        if not parts:
            continue
        cmd, args = parts[0], parts[1:]
        if cmd == 'exit':
            break
        elif cmd == 'cp' and len(args) == 2:
            cp_file(args[0], args[1])
        elif cmd == 'show' and len(args) == 1:
            show_file(args[0])
        elif cmd == 'ls' and len(args) == 1:
            ls_file(args[0])
        elif cmd == 'mkdir' and len(args) == 1:
            mkdir_fs(args[0])
        elif cmd == 'rmdir' and len(args) == 1:
            rmdir_fs(args[0])
        elif cmd == 'merge' and len(args) == 3:
            merge_files(args[0], args[1], args[2])
        elif cmd == 'rm' and len(args) == 1:
            rm_file(args[0])
        else:
            print('Unknown command')

if __name__ == '__main__':
    main()