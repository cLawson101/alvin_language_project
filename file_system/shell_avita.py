
import os
import sys
import re
import time

PFS_FILE = "private.pfs"
METADATA_SIZE = 4096  # Reserved bytes at start
DELIMITER = "|"

def do_cp(src, dest):
    ensure_pfs()

    with open(PFS_FILE, "r+b") as pfs:
        pfs.seek(0)
        meta = pfs.read(METADATA_SIZE).decode(errors="ignore").rstrip("\x00")
        entries = meta.strip().splitlines()

        # Prevent overwriting an existing file (optional)
        for line in entries:
            parts = line.strip().split("|")
            if len(parts) != 5:
                continue
            if parts[0] == dest:
                print(f"{dest} already exists.")
                return

        # Case 1: Normal file to supplemental
        if not src.startswith("+") and dest.startswith("+"):
            try:
                with open(src, "rb") as infile:
                    content = infile.read()
            except FileNotFoundError:
                print(f"{src} not found.")
                return

        # Case 2: Supplemental file to supplemental
        elif src.startswith("+") and dest.startswith("+"):
            content = None
            for line in entries:
                parts = line.strip().split("|")
                if len(parts) != 5:
                    continue
                name, ftype, offset, size, timestamp = parts
                if name == src and ftype == "file":
                    pfs.seek(int(offset))
                    content = pfs.read(int(size))
                    break
            if content is None:
                print(f"{src} not found in supplemental file system.")
                return

        else:
            print("Unsupported cp direction.")
            return

        # Write content to end of file
        pfs.seek(0, os.SEEK_END)
        offset = pfs.tell()
        pfs.write(content)

        # Add new metadata entry
        new_entry = f"{dest}|file|{offset}|{len(content)}|{int(time.time())}"
        updated_meta = entries + [new_entry]
        new_meta_block = "\n".join(updated_meta) + "\n"
        meta_bytes = new_meta_block.encode()
        meta_bytes += b"\x00" * (METADATA_SIZE - len(meta_bytes))

        pfs.seek(0)
        pfs.write(meta_bytes)
        print(f"{dest} copied.")

def do_show(filename):
    
    with open(PFS_FILE, "rb") as pfs:
        pfs.seek(0)
        meta = pfs.read(METADATA_SIZE).decode(errors="ignore")
        for line in meta.strip().splitlines():
            # Skip empty or malformed lines
            parts = line.strip().split("|")
            if len(parts) != 5:
                continue
            name, ftype, offset, size, timestamp = parts
            if name == filename and ftype == "file":
                pfs.seek(int(offset))
                content = pfs.read(int(size)).decode(errors="ignore")
                print(content)
                return
        print(f"{filename} not found in supplemental file system.")

def do_rm(filename):
    ensure_pfs()
    
    with open(PFS_FILE, "r+b") as pfs:
        # Read metadata region (first 4096 bytes)
        pfs.seek(0)
        meta = pfs.read(METADATA_SIZE).decode(errors="ignore").rstrip("\x00")
        entries = meta.strip().splitlines()
        
        # Filter out the entry that matches the file to delete
        new_entries = []
        found = False
        for line in entries:
            parts = line.strip().split("|")
            if len(parts) != 5:
                continue
            if parts[0] == filename:
                found = True
                continue  # skip this file (delete it)
            new_entries.append(line)

        if not found:
            print(f"{filename} not found in supplemental file system.")
            return
        
        # Rewrite metadata: join the remaining entries
        new_meta_block = "\n".join(new_entries) + "\n"
        meta_bytes = new_meta_block.encode()
        
        # Pad to fill the 4096-byte metadata block
        meta_bytes += b"\x00" * (METADATA_SIZE - len(meta_bytes))
        
        # Write back to metadata region
        pfs.seek(0)
        pfs.write(meta_bytes)
        print(f"{filename} removed from supplemental file system.")

def do_mkdir(dirname):
    ensure_pfs()

    if not dirname.startswith("+"):
        print("mkdir: only supplemental directories (prefix '+') are supported.")
        return

    with open(PFS_FILE, "r+b") as pfs:
        pfs.seek(0)
        meta = pfs.read(METADATA_SIZE).decode(errors="ignore").rstrip("\x00")
        entries = meta.strip().splitlines()

        # Check if directory already exists
        for line in entries:
            parts = line.strip().split("|")
            if len(parts) != 5:
                continue
            if parts[0] == dirname and parts[1] == "dir":
                print(f"{dirname} already exists.")
                return

        # Create new metadata entry
        new_entry = f"{dirname}|dir|0|0|{int(time.time())}"
        updated_entries = entries + [new_entry]
        new_meta_block = "\n".join(updated_entries) + "\n"

        meta_bytes = new_meta_block.encode()
        if len(meta_bytes) > METADATA_SIZE:
            print("Error: metadata region full.")
            return
        meta_bytes += b"\x00" * (METADATA_SIZE - len(meta_bytes))

        pfs.seek(0)
        pfs.write(meta_bytes)

        print(f"{dirname} created.")

def do_rmdir(dirname):
    ensure_pfs()

    if not dirname.startswith("+"):
        print("rmdir: only supplemental directories (prefix '+') are supported.")
        return

    with open(PFS_FILE, "r+b") as pfs:
        # Read metadata
        pfs.seek(0)
        meta = pfs.read(METADATA_SIZE).decode(errors="ignore").rstrip("\x00")
        entries = meta.strip().splitlines()

        found = False
        new_entries = []
        
        for line in entries:
            parts = line.strip().split("|")
            if len(parts) != 5:
                continue

            name, ftype, *_ = parts

            # Check for child files
            if name.startswith(dirname + "/"):
                print("Directory not empty.")
                return

            # Mark directory entry for deletion
            if name == dirname and ftype == "dir":
                found = True
                continue

            new_entries.append(line)

        if not found:
            print(f"{dirname} not found or is not a directory.")
            return

        # Write back updated metadata
        new_meta_block = "\n".join(new_entries) + "\n"
        meta_bytes = new_meta_block.encode()
        meta_bytes += b"\x00" * (METADATA_SIZE - len(meta_bytes))

        pfs.seek(0)
        pfs.write(meta_bytes)

        print(f"{dirname} removed.")

def do_merge(src1, src2, dest):
    ensure_pfs()

    if not dest.startswith("+"):
        print("Destination must be a supplemental file (start with '+').")
        return

    def read_content(path, entries, pfs):
        # Read from a normal file
        if not path.startswith("+"):
            try:
                with open(path, "rb") as f:
                    return f.read()
            except FileNotFoundError:
                print(f"{path} not found.")
                return None
        # Read from a supplemental file
        else:
            for line in entries:
                parts = line.strip().split("|")
                if len(parts) != 5:
                    continue
                name, ftype, offset, size, timestamp = parts
                if name == path and ftype == "file":
                    pfs.seek(int(offset))
                    return pfs.read(int(size))
            print(f"{path} not found in supplemental file system.")
            return None

    with open(PFS_FILE, "r+b") as pfs:
        # Load metadata
        pfs.seek(0)
        meta = pfs.read(METADATA_SIZE).decode(errors="ignore").rstrip("\x00")
        entries = meta.strip().splitlines()

        # Check if dest already exists
        for line in entries:
            parts = line.strip().split("|")
            if len(parts) != 5:
                continue
            if parts[0] == dest:
                print(f"{dest} already exists.")
                return

        # Read both inputs
        content1 = read_content(src1, entries, pfs)
        content2 = read_content(src2, entries, pfs)

        if content1 is None or content2 is None:
            return

        merged = content1 + content2

        # Write merged content to end of file
        pfs.seek(0, os.SEEK_END)
        offset = pfs.tell()
        pfs.write(merged)

        # Add metadata
        new_entry = f"{dest}|file|{offset}|{len(merged)}|{int(time.time())}"
        updated_meta = entries + [new_entry]
        new_meta_block = "\n".join(updated_meta) + "\n"
        meta_bytes = new_meta_block.encode()
        meta_bytes += b"\x00" * (METADATA_SIZE - len(meta_bytes))

        pfs.seek(0)
        pfs.write(meta_bytes)

        print(f"{dest} created by merging {src1} and {src2}.")

def do_ls(path):
    ensure_pfs()

    if not path.startswith("+"):
        print("ls: only supplemental files and directories (prefix '+') are supported.")
        return

    with open(PFS_FILE, "rb") as pfs:
        pfs.seek(0)
        meta = pfs.read(METADATA_SIZE).decode(errors="ignore").rstrip("\x00")
        entries = meta.strip().splitlines()

        is_dir = False
        found = False

        for line in entries:
            parts = line.strip().split("|")
            if len(parts) != 5:
                continue

            name, ftype, offset, size, timestamp = parts

            # Case: exact file match
            if name == path and ftype == "file":
                readable_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(timestamp)))
                print(f"{name}\t{readable_time}")
                return

            # Case: matching directory
            if name == path and ftype == "dir":
                is_dir = True

        # If it’s a directory, list its contents
        if is_dir:
            for line in entries:
                parts = line.strip().split("|")
                if len(parts) != 5:
                    continue
                name, ftype, offset, size, timestamp = parts

                # List only immediate children
                if name.startswith(path + "/"):
                    readable_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(timestamp)))
                    print(f"{name}\t{readable_time}")
                    found = True

            if not found:
                print(f"{path} is empty.")
        else:
            print(f"{path} not found.")

#command to split the command but keeps any double quotes 
# Ex.   grep "test" file.txt --> ['grep', '"test"', 'text.txt']
def split_command(command):
    return re.findall(r'".*?"|\S+', command)

def find_path(command):
    # uses the PATH environ variable and creates a list of the path directory
    paths = os.environ["PATH"].split(":") 
    #goes through each directory in the paths list and join them creaitng the entire path. If the file exists and is executable then return it
    for path in paths:
        executable = os.path.join(path, command)
        if os.path.isfile(executable) and os.access(executable, os.X_OK):
            return executable
    return None

#i got this code from google
def expand_variables(command):
    words = command.split()
    for i in range(len(words)):
        #it checks if the first word is a $ meaning that its an enviornment variable
        if words[i].startswith("$"): 
            #splice the list and remove the $ and get the variable name
            var_name = words[i][1:] 
            words[i] = os.environ.get(var_name, words[i])
    # reconstruct the commans into a single string and retunr it
    return " ".join(words)

# checks if < or > 
def redirection(arg):
    input_file = None
    output_file = None
    arg1 = []

    i = 0
    while i < len(arg):
        #check if output redirection and and then that there is a file after the redirection symbol. if there is not 
        #one then print an error statement and return an empty tuple
        if arg[i] == ">":
            if i + 1 < len(arg):
                output_file = arg[i+1]
                i += 1
            else:
                print("Syntax Error: Missing file for output redirection")
                return None, None, None
        #check if input redirection and and then that there is a file after the redirection symbol. if there is not 
        #one then print an error statement and return an empty tuple
        elif arg[i] == "<":
            if i + 1 < len(arg):
                input_file = arg[i + 1]
                i += 1
            else:
                print("Syntax Error: Missing file for input redirection")
                return None, None, None
        #if there is no redirection then just keep the same arg1
        else:
            arg1.append(arg[i])
        i += 1
    return arg1, input_file, output_file

# changing the directory
def change_dir(arg):
    #if the argument has a length of 1 (only "cd") then go tot he home directory
    if len(arg) == 1:
        new_dir = os.environ.get("HOME", "/")
    else:
        # the directory in arg[1] is where we want to go
        new_dir = arg[1]
    # trying to change into the directory and displays error messages if they fail
    try:
        os.chdir(new_dir)
    except FileNotFoundError:
        print(f"cd: {new_dir}: No such file or directory")
    except NotADirectoryError:
        print(f"cd: {new_dir}: Not a directory")

# doing the pipe
def do_pipe(command):
    #split the command into two parts (left of | and right of |). Then check the arguments of each side and remove any double quotes 
    cmd1, cmd2 = [cmd.strip() for cmd in command.split("|")]
    arg1 = [word.strip('"') for word in split_command(cmd1)]
    arg2 = [word.strip('"') for word in split_command(cmd2)]
    
    # find the paths of the left and right of the |
    execute1 = find_path(arg1[0])
    execute2 = find_path(arg2[0])
    
    # if none of the commands is found the just return and print error message 
    if not execute1 or not execute2:
        print("Command not found")
        return
    
    #we create the pipe, and fork the first command and execute the first child process
    pr, pw = os.pipe()
    
    pid1 = os.fork()
    if pid1 == 0:
        #redirect the stdout into the pipe write end
        os.dup2(pw, 1)
        #close the pipe ends
        os.close(pr)
        os.close(pw)
        #execute the first command 
        os.execve(execute1, arg1, os.environ)
        #exit if the execve fails
        sys.exit(1)
    
    #fork the second command and execute the second child process
    pid2 = os.fork()
    if pid2 == 0:
        #redirect the stdin into the pipe read end
        os.dup2(pr, 0)
        #close the pipe ends
        os.close(pr)
        os.close(pw)
        #execute the second command
        os.execve(execute2, arg2, os.environ)
        #exit if the execve fails
        sys.exit(1)
    
    #execute the parent pipe ends and wait for both children processes to finish running
    os.close(pr)
    os.close(pw)
    os.waitpid(pid1, 0)
    os.waitpid(pid2, 0)

def do_command(command):
    command = expand_variables(command)

    #check if pipe 
    if "|" in command:
        do_pipe(command)
        return
    
    #split the commands and then remove any double quotes from each word
    arg = split_command(command)
    arg = [word.strip('"') for word in arg]

    # Check for supplemental commands
    if arg[0] == "cp" and (arg[1].startswith("+") or arg[2].startswith("+")):
        do_cp(arg[1], arg[2])
        return
    elif arg[0] == "show" and arg[1].startswith("+"):
        do_show(arg[1])
        return
    elif arg[0] == "rm" and arg[1].startswith("+"):
        do_rm(arg[1])
        return
    elif arg[0] == "mkdir" and arg[1].startswith("+"):
        do_mkdir(arg[1])
        return
    elif arg[0] == "rmdir" and arg[1].startswith("+"):
        do_rmdir(arg[1])
        return
    elif arg[0] == "ls" and arg[1].startswith("+"):
        do_ls(arg[1])
        return
    elif arg[0] == "merge" and arg[3].startswith("+"):
        do_merge(arg[1], arg[2], arg[3])
        return
    # Add more handlers
    
    #check if the first item in the arg list is the cd command
    if arg[0] == "cd":
        change_dir(arg)
        return
    
    #process the input output redirection
    arg, input_file, output_file = redirection(arg)
    if arg is None:
        return
    
    #checks the last argument in the arg list and if it is & then set the variable to true, run the program and remove the & from the list
    run_in_background = False
    if arg[-1] == '&':
        run_in_background = True
        arg = arg[:-1]
    
    #if empty then return
    if not arg:
        return
    
    #find the path of the command
    executable = find_path(arg[0])
    
    #if the executbale returns empty then print error and return
    if not executable:
        print("Command not found")
        return
    
    #check if the file exists bit is not executable and print error if it is and return
    if os.path.isfile(executable) and not os.access(executable, os.X_OK):
        print(f"{arg[0]}: Not executable")
        return
    
    #fork the process
    pid = os.fork()
    if pid == 0:
        try:
            #if the input_file is not empty then we open the file as a read only file
            if input_file:
                fd_in = os.open(input_file, os.O_RDONLY)
                #redirect the fd_in as the stdin
                os.dup2(fd_in, 0)
                #close the file
                os.close(fd_in)
            if output_file:
                #opent the output file, if the file doesnt exist then we create it, make it a write only file and give it the correct permissions
                fd_out = os.open(output_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
                #make the fd_out as the stdout
                os.dup2(fd_out, 1)
                #close the file
                os.close(fd_out)
                #execute the command and exit if it fails and print error
            os.execve(executable, arg, os.environ)
        except FileNotFoundError:
            print("Command execution failed")
        sys.exit(1)
    else:
        # if we're not supposed to run the command in the background then we wait for the child process to complete
        if not run_in_background:
            os.waitpid(pid, 0)
            
#used to read files 
def process_in(fd):
    with fd as openfile:
        for line in openfile:
            command = line.strip()
            #if the line is empty or starts with a # then we ignore it
            if not command or command.startswith("#"):
                continue
            if command.lower() == "exit": 
                sys.exit(0) 
            do_command(command)

def ensure_pfs():
    if not os.path.exists(PFS_FILE):
        with open(PFS_FILE, "wb") as f:
            f.write(b"\x00" * METADATA_SIZE)  # zero out metadata region


def main():
    #check if the argument provided was a file
    if len(sys.argv) > 1:
        try:
            fd = open(sys.argv[1], "r")
            process_in(fd)
            fd.close()
            return
        except FileNotFoundError:
            print(f"Error: File '{sys.argv[1]}' not found")
            return
        
    ensure_pfs()

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

if __name__ == "__main__":
    main()
