import os
import sys
import re
import time

def split_command(command):
    return re.findall(r'".*?"|\S+', command)


def find_path(command):
    paths = os.environ["PATH"].split(":") 
    for path in paths:
        executable = os.path.join(path, command)
        if os.path.isfile(executable) and os.access(executable, os.X_OK):
            return executable
    return None

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
                print("Syntax Error: Missing file for output redirection")
                return None, None, None
        elif arg[i] == "<":
            if i + 1 < len(arg):
                input_file = arg[i + 1]
                i += 1
            else:
                print("Syntax Error: Missing file for input redirection")
                return None, None, None
        else:
            arg1.append(arg[i])
        i += 1
    return arg1, input_file, output_file


def change_dir(arg):
    if len(arg) == 1:
        new_dir = os.environ.get("HOME", "/")
    else:
        new_dir = arg[1]
    try:
        os.chdir(new_dir)
    except FileNotFoundError:
        print(f"cd: {new_dir}: No such file or directory")
    except NotADirectoryError:
        print(f"cd: {new_dir}: Not a directory")


def do_pipe(command):
    cmd1, cmd2 = [cmd.strip() for cmd in command.split("|")]
    arg1 = [word.strip('"') for word in split_command(cmd1)]
    arg2 = [word.strip('"') for word in split_command(cmd2)]
    execute1 = find_path(arg1[0])
    execute2 = find_path(arg2[0])
    if not execute1 or not execute2:
        print("Command not found")
        return
    pr, pw = os.pipe()
    pid1 = os.fork()
    if pid1 == 0:
        os.dup2(pw, 1)
        os.close(pr)
        os.close(pw)
        os.execve(execute1, arg1, os.environ)
        sys.exit(1)
    pid2 = os.fork()
    if pid2 == 0:
        os.dup2(pr, 0)
        os.close(pr)
        os.close(pw)
        os.execve(execute2, arg2, os.environ)
        sys.exit(1)
    os.close(pr)
    os.close(pw)
    os.waitpid(pid1, 0)
    os.waitpid(pid2, 0)


def do_command(command):
    command = expand_variables(command)

    if command.startswith("cp "):
        args = split_command(command)
        if len(args) == 3 and (args[1].startswith('+') or args[2].startswith('+')):
            sfs_cp(args[1], args[2])
            return

    if command.startswith("show "):
        args = split_command(command)
        if len(args) == 2 and args[1].startswith('+'):
            sfs_show(args[1])
            return

    if command.startswith("rm "):
        args = split_command(command)
        if len(args) == 2 and args[1].startswith('+'):
            sfs_rm(args[1])
            return

    if command.startswith("mkdir "):
        args = split_command(command)
        if len(args) == 2 and args[1].startswith('+'):
            sfs_mkdir(args[1])
            return

    if command.startswith("rmdir "):
        args = split_command(command)
        if len(args) == 2 and args[1].startswith('+'):
            sfs_rmdir(args[1])
            return

    if command.startswith("ls "):
        args = split_command(command)
        if len(args) == 2 and args[1].startswith('+'):
            sfs_ls(args[1])
            return


    if "|" in command:
        do_pipe(command)
        return

    arg = split_command(command)
    arg = [word.strip('"') for word in arg]

    if not arg:
        return

    if arg[0] == "cd":
        change_dir(arg)
        return

    arg, input_file, output_file = redirection(arg)
    if arg is None:
        return

    run_in_background = False
    if arg[-1] == '&':
        run_in_background = True
        arg = arg[:-1]

    if not arg:
        return

    executable = find_path(arg[0])
    if not executable:
        print("Command not found")
        return

    if os.path.isfile(executable) and not os.access(executable, os.X_OK):
        print(f"{arg[0]}: Not executable")
        return

    pid = os.fork()
    if pid == 0:
        try:
            if input_file:
                fd_in = os.open(input_file, os.O_RDONLY)
                os.dup2(fd_in, 0)
                os.close(fd_in)
            if output_file:
                fd_out = os.open(output_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
                os.dup2(fd_out, 1)
                os.close(fd_out)
            os.execve(executable, arg, os.environ)
        except FileNotFoundError:
            print("Command execution failed")
        sys.exit(1)
    else:
        if not run_in_background:
            os.waitpid(pid, 0)

def process_in(fd):
    with fd as openfile:
        for line in openfile:
            command = line.strip()
            if not command or command.startswith("#"):
                continue
            if command.lower() == "exit": 
                sys.exit(0) 
            do_command(command)

##
def main():
    if len(sys.argv) > 1:
        try:
            fd = open(sys.argv[1], "r")
            process_in(fd)
            fd.close()
            return
        except FileNotFoundError:
            print(f"Error: File '{sys.argv[1]}' not found")
            return

    run = True
    while run:
        command = input("$ ").strip()
        if command.lower() == "exit":
            run = False
            break
        if command.lower() == "inspiration":
            phrase = os.environ.get("phrase")
            if phrase:
                print(phrase)
            else:
                print("There is no current 'inspirational' quote, but\nYou Got This!")
            continue
        do_command(command)



PFS_FILENAME = "private.pfs"


def sfs_read_all_entries():
    entries = []
    if not os.path.exists(PFS_FILENAME):
        return entries
    with open(PFS_FILENAME, "rb") as f:
        for line in f:
            parts = line.decode().strip().split("|", 4)
            if len(parts) == 5:
                entries.append(parts)
    return entries

###
def sfs_read_file(name):
    if not name.startswith('+'):
        print(f"Invalid supplementary file name: {name}")
        return ""
    entries = sfs_read_all_entries()
    for entry in entries:
        if entry[0] == 'F' and entry[1] == name:
            return entry[4].replace('\\n', '\n')
    print(f"{name} not found")
    return ""

##
def sfs_write_file(name, content):
    timestamp = str(int(time.time()))
    entry = f"F|{name}|{len(content)}|{timestamp}|{content.replace(chr(10), '\\n')}\n"
    with open(PFS_FILENAME, "ab") as f:
        f.write(entry.encode())

##
def sfs_show(name):
    content = sfs_read_file(name)
    if content:
        print(content)

##
def sfs_cp(src, dest):
    if src.startswith('+'):
        content = sfs_read_file(src)
    else:
        try:
            with open(src, "r") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"{src} not found")
            return

    if dest.startswith('+'):
        sfs_write_file(dest, content)
    else:
        print("Destination must be a supplementary file (starts with '+')")

###
def sfs_rm(name):
    try:
        with open(PFS_FILENAME, "r+b") as f:
            offset = 0
            for line in f:
                parts = line.decode().strip().split("|", 4)
                if len(parts) == 5 and parts[1] == name:
                    f.seek(offset)
                    f.write(b"X")
                    print(f"{name} removed from supplementary file system.")
                    return
                offset += len(line)
        print(f"{name} not found.")
    except FileNotFoundError:
        print("private.pfs not found")

#
def sfs_mkdir(name):
    timestamp = str(int(time.time()))
    entry = f"D|{name}|0|{timestamp}|\n"
    with open(PFS_FILENAME, "ab") as f:
        f.write(entry.encode())
    print(f"Directory {name} created.")

#
def sfs_rmdir(name):
    entries = sfs_read_all_entries()
    for entry in entries:
        if entry[0] == 'F' and entry[1].startswith(name + '/'):
            print(f"Cannot remove {name}: Directory not empty.")
            return
    with open(PFS_FILENAME, "r+b") as f:
        offset = 0
        for line in f:
            parts = line.decode().strip().split("|", 4)
            if len(parts) == 5 and parts[0] == 'D' and parts[1] == name:
                f.seek(offset)
                f.write(b"X")
                print(f"{name} removed.")
                return
            offset += len(line)

#################
def sfs_ls(name):
    entries = sfs_read_all_entries()
    for entry in entries:
        if entry[0] == 'F' and entry[1] == name:
            ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(entry[3])))
            print(f"{entry[1]} (Last Modified: {ts})")
            return
        elif entry[0] == 'D' and entry[1] == name:
            print(f"{name}/ contents:")
            for e in entries:
                if e[0] == 'F' and e[1].startswith(name + '/'):
                    ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(e[3])))
                    print(f"  {e[1].split('/')[-1]} (Last Modified: {ts})")
            return
    print(f"{name} not found.")



if __name__ == "__main__":
    main()
