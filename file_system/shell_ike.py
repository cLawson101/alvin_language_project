import os
import sys
import re
from datetime import datetime

# copy a file from the source to the destination
def cp(source, dest):
    # Check if dest is supplementary
    if not dest.startswith("+"):
        print("ERROR: destination must be supplementary")
        return

    entries = read_pfs_header()  # read the full header once

    # Read source content
    if os.path.exists(source):  # real file
        with open(source, "r") as f: # open in read mode
            content = f.read() # read the file
    else:
        # Source is inside .pfs
        found = False
        for entry in entries:
            if entry[1] == source: # check if the entry is the one to copy
                if entry[0] == "D": # check if the source is a directory
                    print("ERROR: Cannot copy a directory")
                    return
                offset = int(entry[2]) # get the offset
                size = int(entry[3]) # get the size
                with open("private.pfs", "rb") as f: # open in read+binary mode
                    f.seek(offset) # go to the right spot in file
                    content = f.read(size).decode() # read the content
                found = True
                break
        if not found:
            print("ERROR: source file not found")
            return

    # make sure the content ends with a newline
    if not content.endswith("\n"):
        content += "\n"

    # remove any existing file at the destination
    entries = [entry for entry in entries if not (entry[0] == "F" and entry[1] == dest)]

    offset = get_next_offset(entries) # get the next offset
    size = len(content) # get the size of the content
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # get the current timestamp

    entries.append(["F", dest, str(offset), str(size), timestamp]) # add new entry
    write_pfs_header(entries) # write the header
    append_data(offset, content) # write the content to the file
    print(f"Copied {source} to {dest}")


# remove a file from private.pfs
def rm(filename):
    # check if filename is supplementary
    if not filename.startswith("+"):
        print("ERROR: Invalid file")
        return

    entries = read_pfs_header() # read the full header
    new_entries = []
    found = False

    for entry in entries:
        if entry[1] == filename: # check if the entry is the one to remove
            if entry[0] == "D": # check if the entry is a directory
                print("ERROR: Cannot remove a directory with `rm`, use `rmdir`")
                return
            found = True
            offset = int(entry[2]) # get the offset
            size = int(entry[3]) # get the size
        else:
            new_entries.append(entry) # add new entry

    if not found:
        print("ERROR: File not found")
        return

    # overwrite data with filler
    with open("private.pfs", "r+b") as f: # open in read+binary mode
        f.seek(offset) # go to the right spot in file
        f.write(b" " * size)  # overwrite with spaces

    write_pfs_header(new_entries) # write the header
    print(f"Removed {filename}")


# create a new directory in private.pfs
def mkdir(dirname):
    if not dirname.startswith("+"): # check if the directory is supplementary
        print("ERROR: Invalid supplementary directory name")
        return
    if "/" in dirname: # check if the directory is nested
        print("ERROR: Nested directories not supported")
        return

    entries = read_pfs_header() # read the full header
    for entry in entries:
        if entry[1] == dirname: # check if the directory already exists
            print("ERROR: Directory already exists")
            return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # get the current timestamp
    entries.append(["D", dirname, "-", "-", timestamp]) # add new entry
    write_pfs_header(entries) # write the header
    print(f"Created directory {dirname}")


# remove a directory from private.pfs
def rmdir(dirname):
    if not dirname.startswith("+"): # check if the directory is supplementary
        print("ERROR: Invalid supplementary directory name")
        return

    entries = read_pfs_header() # read the full header
    new_entries = []
    found = False

    for entry in entries:
        if entry[1] == dirname: # check if the entry is the one to remove
            if entry[0] != "D": # check if the entry is a directory
                print("ERROR: Not a directory")
                return
            found = True
        elif entry[1].startswith(dirname + "/"): # check if the entry is a subdirectory
            print("ERROR: Directory not empty")
            return
        else:
            new_entries.append(entry) # add entry

    if not found: # check if the directory exists
        print("ERROR: Directory doesn't exist")
        return

    write_pfs_header(new_entries) # write the header
    print(f"Removed directory {dirname}")


# list files/directories in private.pfs
def ls(args=None):
    entries = read_pfs_header() # read the header

    # strip leading/trailing spaces
    def normalize(p):
        return p.strip()

    # no args? list all entries
    if not args or len(args) == 0: 
        for e in entries:
            if '/' not in e[1].lstrip('+'):
                print(e[1], e[4])
        return

    path = normalize(args[0]) # get the path

    for e in entries:
        if normalize(e[1]) == path and e[0] == "F": # check if the entry is a file
            print(e[1], e[4])
            return

    for e in entries:
        if normalize(e[1]) == path and e[0] == "D": # check if the entry is a directory
            found = False
            for sub in entries:
                if normalize(sub[1]).startswith(path + "/"): # check if the entry is a subdirectory
                    print(sub[1], sub[4])
                    found = True
            if not found:
                print(f"{path} is an empty directory")
            return

    print("ERROR: Path not found")


# merge two files in private.pfs
def merge(file1, file2, output):
    if not output.startswith("+"): # check if the output is supplementary
        print("ERROR: destination must be supplementary")
        return

    # get the content of the files
    def get_file_content(name):
        entries = read_pfs_header() # read the header
        for entry in entries:
            if entry[1] == name and entry[0] == "F": # check if the entry is a file
                offset = int(entry[2]) # get the offset
                size = int(entry[3]) # get the size
                with open("private.pfs", "rb") as f: # open in read+binary mode
                    f.seek(offset) # go to the right spot in file
                    return f.read(size).decode()
        raise Exception(f"File {name} not found")

    try:
        content1 = get_file_content(file1) # get the content of file1
        content2 = get_file_content(file2) # get the content of file2
    except Exception as e:
        print("ERROR:", e)
        return

    merged = content1 + content2 # merge the content
    entries = read_pfs_header() # read the header
    offset = get_next_offset(entries) # get the next offset
    size = len(merged) # get the size of the merged content
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # get the current timestamp
    entries.append(["F", output, str(offset), str(size), timestamp]) # add new entry
    write_pfs_header(entries) # write the header
    append_data(offset, merged) # write the content to the file
    print(f"Merged {file1} and {file2} into {output}")


# show the content of a file in private.pfs
def show(filename):
    if not filename.startswith("+"): # check if the filename is supplementary
        print("ERROR: destination must be supplementary")
        return

    entries = read_pfs_header() # read the header
    for entry in entries:
        if entry[1] == filename: # check if the entry is the one to show
            if entry[0] == "D": # check if the entry is a directory
                print("ERROR: Cannot show a directory")
                return
            offset = int(entry[2]) # get the offset
            size = int(entry[3]) # get the size
            with open("private.pfs", "rb") as f: # open in read+binary mode
                f.seek(offset) # go to the right spot in file
                content = f.read(size).decode() # read the content
                print(content)
                return
    print("ERROR: File not found")


# write data to private.pfs
def append_data(offset, content):
    with open("private.pfs", "r+b") as f: # open in read+binary mode
        f.seek(offset) # go to the right spot
        f.write(content.encode()) # write the content


# get the next offset of private.pfs
def get_next_offset(entries):
    max_offset = 1024  # data starts at byte 1024
    for entry in entries:
        if entry[0] == "F": # check if the entry is a file
            offset = int(entry[2]) # get the offset
            size = int(entry[3]) # get the size
            end = offset + size 
            if end > max_offset: # check if the end of the file goes past max offset
                max_offset = end # update max offset
    return max_offset


# write header entry of private.pfs
def write_pfs_header(entries):
    header_data = ""
    for entry in entries:
        header_data += "|".join(entry) + "\n" # join the entry with "|"
    header_bytes = header_data.encode() # convert header to bytes

    if len(header_bytes) > 1024: # check if the header is too large
        raise ValueError("Header too large!")

    with open("private.pfs", "r+b") as f: # open in read+binary mode
        f.seek(0) # go to the start of the file
        f.write(header_bytes) # write the header
        f.write(b"\n" * (1024 - len(header_bytes))) # pad the rest with spaces


# read header entries and return a list of entries
def read_pfs_header():
    with open("private.pfs", "rb") as f: # open in read+binary mode
        return [line.strip().split("|") for line in f.read().decode().splitlines() if line.strip().count("|") >= 4] # read the header and split it into entries


# check if the private.pfs file exists and if not create it
def initialize_pfs():
    if not os.path.exists("private.pfs"): # check if the file exists
        with open("private.pfs", "w") as f: # create the file
            f.write("")  # write an empty string


# run the private.pfs commands
def run_pfs_command(arg):
    cmd = arg[0]
    args = arg[1:]

    # handle each command
    if cmd == "cp":
        if len(args) != 2:
            print("Usage: cp <source> <destination>")
        else:
            cp(args[0], args[1])
    elif cmd == "rm":
        if len(args) != 1:
            print("Usage: rm <path>")
        else:
            rm(args[0])
    elif cmd == "mkdir":
        if len(args) != 1:
            print("Usage: mkdir <dir>")
        else:
            mkdir(args[0])
    elif cmd == "rmdir":
        if len(args) != 1:
            print("Usage: rmdir <dir>")
        else:
            rmdir(args[0])
    elif cmd == "ls":
        ls(args)  # optional args
    elif cmd == "merge":
        if len(args) != 3:
            print("Usage: merge <file1> <file2>")
        else:
            merge(args[0], args[1], args[2])
    elif cmd == "show":
        if len(args) != 1:
            print("Usage: show <file>")
        else:
            show(args[0])




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
    
    # check for built-in private.pfs commands
    pfs_commands = ["cp", "rm", "mkdir", "rmdir", "ls", "merge", "show"]
    if arg[0] in pfs_commands:
        run_pfs_command(arg)
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

def main():
    #initialize the private file system
    initialize_pfs()
    
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
