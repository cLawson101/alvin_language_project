import os
import sys
import re
import time

# Name of the private file system file
PFS_FILENAME = "private.pfs"

# --- Utility Functions ---

def split_command(command):
    """Split command string into arguments, respecting quoted strings."""
    return re.findall(r'".*?"|\S+', command)

def find_path(command):
    """Find the full path to an executable using the PATH environment variable."""
    paths = os.environ["PATH"].split(":")
    for path in paths:
        executable = os.path.join(path, command)
        if os.path.isfile(executable) and os.access(executable, os.X_OK):
            return executable
    return None

def expand_variables(command):
    """Replace $VAR with its environment variable value."""
    words = command.split()
    for i in range(len(words)):
        if words[i].startswith("$"):
            var_name = words[i][1:]
            words[i] = os.environ.get(var_name, words[i])
    return " ".join(words)

def redirection(arg):
    """Handle input/output redirection (<, >) and return cleaned args with filenames."""
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
    """Change the current working directory."""
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
    """Handle piping between two commands (cmd1 | cmd2)."""
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
        os.dup2(pw, 1)  # stdout -> pipe write
        os.close(pr)
        os.close(pw)
        os.execve(execute1, arg1, os.environ)
        sys.exit(1)
    pid2 = os.fork()
    if pid2 == 0:
        os.dup2(pr, 0)  # stdin <- pipe read
        os.close(pr)
        os.close(pw)
        os.execve(execute2, arg2, os.environ)
        sys.exit(1)
    os.close(pr)
    os.close(pw)
    os.waitpid(pid1, 0)
    os.waitpid(pid2, 0)

# --- PFS (Private File System) Functions ---

def find_pfs_entry(name):
    """Find a file or directory entry in PFS."""
    with open(PFS_FILENAME, "r") as pfs:
        for line in pfs:
            parts = line.strip().split("|")
            if len(parts) > 1 and parts[1] == name and parts[0] != 'X':
                return parts
    return None

def write_pfs_entry(entry):
    """Write or update an entry in PFS."""
    entries = []
    updated = False
    with open(PFS_FILENAME, "r") as pfs:
        for line in pfs:
            parts = line.strip().split("|")
            if len(parts) > 1 and parts[1] == entry[1] and parts[0] != 'X':
                entries.append("|".join(entry) + "\n")
                updated = True
            else:
                entries.append(line)
    if not updated:
        entries.append("|".join(entry) + "\n")
    with open(PFS_FILENAME, "w") as pfs:
        pfs.writelines(entries)

def cp_supplemental(source, destination):
    """Copy file to or from PFS."""
    content = ""
    if source.startswith("+"):
        src_name = source[1:]
        entry = find_pfs_entry(src_name)
        if entry:
            content = entry[5]
        else:
            print(f"Source {source} not found in PFS")
            return
    else:
        try:
            with open(source, "r") as f:
                content = f.read().strip()
        except FileNotFoundError:
            print(f"File {source} not found")
            return
    dest_name = destination[1:] if destination.startswith("+") else destination
    parent = "root"
    if "/" in dest_name:
        parent, dest_name = dest_name.split("/")
    now = int(time.time())
    entry = ['F', dest_name, parent, str(now), str(len(content)), content]
    write_pfs_entry(entry)

def rm_supplemental(name):
    """Remove a file from PFS."""
    name = name[1:]
    entry = find_pfs_entry(name)
    if not entry:
        print(f"File {name} not found in PFS")
        return
    entry[0] = 'X'
    write_pfs_entry(entry)

def mkdir_supplemental(name):
    """Create a directory in PFS."""
    name = name[1:]
    now = int(time.time())
    entry = ['D', name, 'root', str(now), '0', '']
    write_pfs_entry(entry)

def rmdir_supplemental(name):
    """Remove a directory in PFS if empty."""
    name = name[1:]
    children = []
    with open(PFS_FILENAME, "r") as pfs:
        for line in pfs:
            parts = line.strip().split("|")
            if len(parts) > 2 and parts[2] == name and parts[0] != 'X':
                children.append(parts[1])
    if children:
        print(f"Directory {name} not empty")
        return
    entry = find_pfs_entry(name)
    if entry:
        entry[0] = 'X'
        write_pfs_entry(entry)

def ls_supplemental(target):
    """List a file or directory in PFS."""
    name = target[1:]
    if '/' in name:
        parent, file = name.split('/')
    else:
        parent, file = 'root', name
    entry = find_pfs_entry(name)
    if entry:
        print(f"{entry[1]} {entry[3]}")
        return
    with open(PFS_FILENAME, "r") as pfs:
        for line in pfs:
            parts = line.strip().split("|")
            if len(parts) > 2 and parts[2] == name and parts[0] != 'X':
                print(f"{parts[1]} {parts[3]}")

def merge_supplemental(file1, file2, destination):
    """Merge contents of two files and store in destination (PFS)."""
    def get_content(name):
        if name.startswith("+"):
            entry = find_pfs_entry(name[1:])
            return entry[5] if entry else ""
        else:
            try:
                with open(name, "r") as f:
                    return f.read().strip()
            except:
                return ""
    content = get_content(file1) + get_content(file2)
    dest_name = destination[1:] if destination.startswith("+") else destination
    parent = "root"
    if "/" in dest_name:
        parent, dest_name = dest_name.split("/")
    now = int(time.time())
    entry = ['F', dest_name, parent, str(now), str(len(content)), content]
    write_pfs_entry(entry)

def show_supplemental(name):
    """Show contents of a file in PFS."""
    name = name[1:]
    entry = find_pfs_entry(name)
    if entry:
        print(entry[5])
    else:
        print(f"File {name} not found")

def handle_supplemental(arg):
    """Dispatch function to handle all PFS supplemental commands."""
    if arg[0] == "cp" and (arg[1].startswith("+") or arg[2].startswith("+")):
        cp_supplemental(arg[1], arg[2])
        return True
    elif arg[0] == "rm" and arg[1].startswith("+"):
        rm_supplemental(arg[1])
        return True
    elif arg[0] == "mkdir" and arg[1].startswith("+"):
        mkdir_supplemental(arg[1])
        return True
    elif arg[0] == "rmdir" and arg[1].startswith("+"):
        rmdir_supplemental(arg[1])
        return True
    elif arg[0] == "ls" and arg[1].startswith("+"):
        ls_supplemental(arg[1])
        return True
    elif arg[0] == "merge" and arg[1].startswith("+") and arg[3].startswith("+"):
        merge_supplemental(arg[1], arg[2], arg[3])
        return True
    elif arg[0] == "show" and arg[1].startswith("+"):
        show_supplemental(arg[1])
        return True
    return False

# --- Command Execution ---

def do_command(command):
    """Main function to parse and execute a shell command."""
    command = expand_variables(command)
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
    if arg and arg[-1] == '&':
        run_in_background = True
        arg = arg[:-1]
    if handle_supplemental(arg):
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

# --- Input Processing ---

def process_in(fd):
    """Process commands from a file."""
    with fd as openfile:
        for line in openfile:
            command = line.strip()
            if not command or command.startswith("#"):
                continue
            if command.lower() == "exit":
                sys.exit(0)
            do_command(command)

# --- Main Program ---

def main():
    """Entry point: process script file or interactive shell."""
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
            print(phrase if phrase else "There is no current 'inspirational' quote, but\nYou Got This!")
            continue
        do_command(command)

if __name__ == "__main__":
    # Create the PFS file if it doesn't exist
    if not os.path.exists(PFS_FILENAME):
        with open(PFS_FILENAME, "w") as f:
            pass
    main()
