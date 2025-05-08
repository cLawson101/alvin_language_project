import os
import sys
import re
import shutil
from datetime import datetime



#Supplementary file system is rooted at '.suppfs' in the current directory.


# Root directory for supplementary file system
SUPP_ROOT = os.path.join(os.getcwd(), '.suppfs')
if not os.path.exists(SUPP_ROOT):
    os.makedirs(SUPP_ROOT)


def sup_path(path):
    #Map a '+path' to the SFS location under SUPP_ROOT
    assert path.startswith('+'),# "Supplementary paths must start with '+'"
    # Remove leading '+' and normalize
    rel = path[1:].lstrip('/')
    return os.path.join(SUPP_ROOT, rel)


def fmt_time(epoch):
    #Format 
    return datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M:%S')


def cmd_cp(args):
    if len(args) != 3:
        print("cp: usage: cp <source> <destination>")
        return
    src, dst = args[1], args[2]
    # Determine source location
    if src.startswith('+'):
        s = sup_path(src)
    else:
        s = src
    if not os.path.isfile(s):
        print(f"cp: {src}: No such file or directory")
        return
    # Determine destination location
    if dst.startswith('+'):
        d = sup_path(dst)
        ddir = os.path.dirname(d)
        if ddir and not os.path.exists(ddir):
            print(f"cp: {dst}: No such directory")
            return
    else:
        d = dst
    try:
        shutil.copy2(s, d)
    except Exception as e:
        print(f"cp: error copying: {e}")


def cmd_rm(args):
    if len(args) != 2:
        print("rm: usage: rm <+file>")
        return
    path = args[1]
    if not path.startswith('+'):
        print("rm: can only remove supplementary files (prefix '+')")
        return
    p = sup_path(path)
    if not os.path.isfile(p):
        print(f"rm: {path}: No such file or directory")
        return
    try:
        os.remove(p)
    except Exception as e:
        print(f"rm: error removing: {e}")


def cmd_mkdir(args):
    if len(args) != 2 or not args[1].startswith('+'):
        print("mkdir: usage: mkdir <+directory>")
        return
    p = sup_path(args[1])
    if os.path.exists(p):
        print(f"mkdir: {args[1]}: File exists")
        return
    try:
        os.makedirs(p)
    except Exception as e:
        print(f"mkdir: error creating directory: {e}")


def cmd_rmdir(args):
    if len(args) != 2 or not args[1].startswith('+'):
        print("rmdir: usage: rmdir <+directory>")
        return
    p = sup_path(args[1])
    if not os.path.isdir(p):
        print(f"rmdir: {args[1]}: No such directory")
        return
    try:
        os.rmdir(p)
    except OSError:
        print(f"rmdir: {args[1]}: Directory not empty or cannot remove")


def cmd_ls(args):
    if len(args) != 2:
        print("ls: usage: ls <+file_or_directory>")
        return
    target = args[1]
    if not target.startswith('+'):
        print(f"ls: {target}: Not a supplementary path")
        return
    p = sup_path(target)
    if os.path.isdir(p):
        entries = os.listdir(p)
        for name in entries:
            full = os.path.join(p, name)
            mtime = fmt_time(os.path.getmtime(full))
            print(f"{name}\t{mtime}")
    elif os.path.isfile(p):
        name = target[1:]
        mtime = fmt_time(os.path.getmtime(p))
        print(f"{name}\t{mtime}")
    else:
        print(f"ls: {target}: No such file or directory")


def cmd_merge(args):
    if len(args) != 4:
        print("merge: usage: merge <file1> <file2> <destination>")
        return
    f1, f2, dst = args[1], args[2], args[3]
    # Open first input
    try:
        path1 = sup_path(f1) if f1.startswith('+') else f1
        path2 = sup_path(f2) if f2.startswith('+') else f2
        if not os.path.isfile(path1) or not os.path.isfile(path2):
            raise FileNotFoundError
        # Destination
        if dst.startswith('+'):
            dp = sup_path(dst)
            ddir = os.path.dirname(dp)
            if ddir and not os.path.exists(ddir):
                print(f"merge: {dst}: No such directory")
                return
        else:
            dp = dst
        # Concatenate
        with open(dp, 'w') as out, open(path1) as i1, open(path2) as i2:
            out.write(i1.read())
            out.write(i2.read())
    except FileNotFoundError:
        print("merge: input file not found")
    except Exception as e:
        print(f"merge: error: {e}")


def cmd_show(args):
    if len(args) != 2 or not args[1].startswith('+'):
        print("show: usage: show <+file>")
        return
    p = sup_path(args[1])
    if not os.path.isfile(p):
        print(f"show: {args[1]}: No such file")
        return
    with open(p) as f:
        sys.stdout.write(f.read())


def split_command(command):
    return re.findall(r'".*?"|\S+', command)


def do_command(command):
    command = command.strip()
    if not command:
        return
    # Handle built-in SFS commands
    parts = split_command(command)
    cmd = parts[0]
    if cmd in ('cp', 'rm', 'mkdir', 'rmdir', 'ls', 'merge', 'show'):
        if cmd == 'cp':      cmd_cp(parts)
        elif cmd == 'rm':    cmd_rm(parts)
        elif cmd == 'mkdir': cmd_mkdir(parts)
        elif cmd == 'rmdir': cmd_rmdir(parts)
        elif cmd == 'ls':    cmd_ls(parts)
        elif cmd == 'merge': cmd_merge(parts)
        elif cmd == 'show':  cmd_show(parts)
        return
 


def main():
    if len(sys.argv) > 1:
        pass
    while True:
        try:
            line = input('$ ')
        except EOFError:
            break
        if line.strip() == 'exit':
            break
        do_command(line)

if __name__ == '__main__':
    main()

