# modified by Julieta Cano
import os
import sys
import re
import time
import datetime


# command to split the command but keeps any double quotes
# Ex.   grep "test" file.txt --> ['grep', '"test"', 'text.txt']
def split_command(command):
    return re.findall(r'".*?"|\S+', command)


def find_path(command):
    # uses the PATH environ variable and creates a list of the path directory
    paths = os.environ["PATH"].split(":")
    # goes through each directory in the paths list and join them creaitng the entire path. If the file exists and is executable then return it
    for path in paths:
        executable = os.path.join(path, command)
        if os.path.isfile(executable) and os.access(executable, os.X_OK):
            return executable
    return None


# i got this code from google
def expand_variables(command):
    words = command.split()

    for i in range(len(words)):
        # it checks if the first word is a $ meaning that its an enviornment variable
        if words[i].startswith("$"):
            # splice the list and remove the $ and get the variable name
            var_name = words[i][1:]
            words[i] = os.environ.get(var_name, words[i])
    # reconstruct the command into a single string and retunr it
    return " ".join(words)


# checks if < or >
def redirection(arg):
    input_file = None
    output_file = None
    arg1 = []

    i = 0
    while i < len(arg):
        # check if output redirection and and then that there is a file after the redirection symbol. if there is not
        # one then print an error statement and return an empty tuple
        if arg[i] == ">":
            if i + 1 < len(arg):
                output_file = arg[i + 1]
                i += 1
            else:
                print("Syntax Error: Missing file for output redirection")
                return None, None, None
        # check if input redirection and and then that there is a file after the redirection symbol. if there is not
        # one then print an error statement and return an empty tuple
        elif arg[i] == "<":
            if i + 1 < len(arg):
                input_file = arg[i + 1]
                i += 1
            else:
                print("Syntax Error: Missing file for input redirection")
                return None, None, None
        # if there is no redirection then just keep the same arg1
        else:
            arg1.append(arg[i])
        i += 1
    return arg1, input_file, output_file


# changing the directory
def change_dir(arg):
    # if the argument has a length of 1 (only "cd") then go tot he home directory
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
    # split the command into two parts (left of | and right of |). Then check the arguments of each side and remove any double quotes
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

    # we create the pipe, and fork the first command and execute the first child process
    pr, pw = os.pipe()

    pid1 = os.fork()
    if pid1 == 0:
        # redirect the stdout into the pipe write end
        os.dup2(pw, 1)
        # close the pipe ends
        os.close(pr)
        os.close(pw)
        # execute the first command
        os.execve(execute1, arg1, os.environ)
        # exit if the execve fails
        sys.exit(1)

    # fork the second command and execute the second child process
    pid2 = os.fork()
    if pid2 == 0:
        # redirect the stdin into the pipe read end
        os.dup2(pr, 0)
        # close the pipe ends
        os.close(pr)
        os.close(pw)
        # execute the second command
        os.execve(execute2, arg2, os.environ)
        # exit if the execve fails
        sys.exit(1)

    # execute the parent pipe ends and wait for both children processes to finish running
    os.close(pr)
    os.close(pw)
    os.waitpid(pid1, 0)
    os.waitpid(pid2, 0)

def readSupp(name):
    with open('private.pfs', "rb") as f:
        privatecont = f.read()

    parts = privatecont.split(b"--metadata--\n")
    if len(parts) != 2:
        print("Invalid PFS format.")
        return None

    content_bytes = parts[0]
    metadata_lines = parts[1].decode().splitlines()

    for line in metadata_lines:
        if not line.strip():
            continue
        parts = line.strip().split("|")
        if len(parts) != 5:
            continue
        type, filename, offset, timestamp, size = parts
        if type != 'F':
            continue
        if filename.strip() == name.strip():
            offset = int(offset)
            size = int(size)
            filedata = content_bytes[offset:offset+size]
            return filedata.decode()

    print(f"File '{name}' not found in private.pfs.")
    return None

#for ls command of supp files
def listSuppEntry(name):
    if not os.path.exists("private.pfs"):
        print("private.pfs does not exist.")
        return

    with open("private.pfs", "rb") as f:
        privatecont = f.read()
        #split metadata and content
    parts = privatecont.split(b"--metadata--\n")
    if len(parts) != 2:
        print("Invalid PFS format.")
        return

    metadata_lines = parts[1].decode().splitlines()
    #if file/director is found
    found = False

    is_directory = False
    dir_prefix = name
    if not dir_prefix.endswith("/"):
        for line in metadata_lines:
            if not line.strip():
                continue
            fields = line.strip().split("|")
            if len(fields) != 5:
                continue
            typecode, entry_name, *_ = fields
            #checks if ls is looking for directory
            if typecode == "D" and entry_name == name:
                dir_prefix = name + "/"
                is_directory = True
                break
    #if its a directory or has a slash at the end then it should look for all the metadata that includes that directory
    if is_directory or name.endswith("/"):
        for line in metadata_lines:
            if not line.strip():
                continue
            fields = line.strip().split("|")
            if len(fields) != 5:
                continue
            typecode, entry_name, _, timestamp, _ = fields
            #check if path is the same as the directory
            if entry_name.startswith(dir_prefix) and "/" not in entry_name[len(dir_prefix):]:
                readable_time = datetime.datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
                print(f"{entry_name}\tLast modified: {readable_time}")
                found = True
        if not found:
            print(f"'{dir_prefix}' empty or does not exist.")
    else:
        #for regular file ls
        for line in metadata_lines:
            if not line.strip():
                continue
            fields = line.strip().split("|")
            if len(fields) != 5:
                continue
            typecode, filename, _, timestamp, _ = fields
            #if the file names match then print the name and modifired day
            if filename == name:
                readable_time = datetime.datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
                print(f"{filename}\tLast modified: {readable_time}")
                return
        print(f"'{name}' not found in PFS.")


# function for writing supp files
def writeSupp(name, content):
    with open("private.pfs", "rb") as f:
        privatecont = f.read()

    parts = privatecont.split(b"--metadata--\n")
    if len(parts) != 2:
        print("Invalid PFS format. Expecting '--metadata--'.")
        return

    content_bytes = parts[0]
    metadata_block = parts[1].decode().splitlines()

    #make sure there isnt any unnecesary metadata
    cleaned_metadata = []
    for line in metadata_block:
        if not line.strip():
            continue
        parts = line.strip().split("|")
        if len(parts) != 5:
            continue
        typecode, filename, *_ = parts
        #check if file already exists
        if filename.strip() == name.strip():
            print(f"File '{name}' already exists in PFS.")
            return
        cleaned_metadata.append(line.strip())

    #compute the new offset for content
    offset = len(content_bytes)
    data = content.encode()
    size = len(data)
    timestamp = int(time.time())
    newmeta = f"F|{name}|{offset}|{timestamp}|{size}"

    #update the private.pfs with the new file metaadata and content
    with open("private.pfs", "wb") as f:
        f.write(content_bytes)
        f.write(data)
        f.write(b"\n--metadata--\n")
        for line in cleaned_metadata:
            f.write((line + "\n").encode())
        f.write((newmeta + "\n").encode())
    #notify the success
    print(f"File '{name}' written to PFS.")

def mergeSuppFiles(file1, file2, result):
    if file1 == result or file2 == result:
        print("Result file name must be different from input files.")
        return

    content1 = readSupp(file1)
    content2 = readSupp(file2)

    if content1 is None or content2 is None:
        print("Some input files dont exist.")
        return

    with open("private.pfs", "rb") as f:
        privatecont = f.read()

    parts = privatecont.split(b"--metadata--\n")
    if len(parts) != 2:
        print("Invalid PFS format.")
        return

    metadata_lines = parts[1].decode().splitlines()
    for line in metadata_lines:
        if not line.strip():
            continue
        fields = line.strip().split("|")
        if len(fields) != 5:
            continue
        _, existing_name, *_ = fields
        if existing_name.strip() == result.strip():
            print(f"File '{result}' already exists.")
            return

    combined = content1 + content2
    writeSupp(result, combined)

def makeSuppDir(name):
    with open("private.pfs", "rb") as f:
        privatecont = f.read()
    #separate metadata from content
    parts = privatecont.split(b"--metadata--\n")
    if len(parts) != 2:
        print("Invalid PFS format.")
        return

    content_bytes = parts[0]
    metadata_lines = parts[1].decode().splitlines()

    #checks if directory already exists
    for line in metadata_lines:
        if not line.strip():
            continue
        parts = line.strip().split("|")
        if len(parts) != 5:
            continue
        _, existing_name, *_ = parts
        if existing_name == name:
            print(f"Directory '{name}' already exists.")
            return

    timestamp = int(time.time())
    newmeta = f"D|{name}|0|{timestamp}|0"

    #update all the metadata
    with open("private.pfs", "wb") as f:
        f.write(content_bytes)
        f.write(b"--metadata--\n")
        for line in metadata_lines:
            f.write((line + "\n").encode())
        f.write((newmeta + "\n").encode())

    print(f"Directory '{name}' created in PFS.")

#for removing a directory
def removeSuppDir(name):
    if not os.path.exists("private.pfs"):
        print("private.pfs does not exist.")
        return

    with open("private.pfs", "rb") as f:
        privatecont = f.read()
    #split metadata and content
    parts = privatecont.split(b"--metadata--\n")
    if len(parts) != 2:
        print("Invalid PFS format.")
        return

    content_bytes = parts[0]
    metadata = parts[1].decode().splitlines()

    newMetadata = []
    dir_found = False
    not_empty = False
    #go through the metadata
    for line in metadata:
        if not line.strip():
            continue

        fields = line.strip().split("|")
        if len(fields) != 5:
            newMetadata.append(line)
            continue
        ##get the metadata for the line
        typecode, dirname, *_ = fields
        #if its a directory and name matches
        if typecode == "D" and dirname == name:
            #mark directory as found
            dir_found = True
            continue

        #if any file is inside the directory, it's not empty
        if dirname.startswith(name + "/"):
            not_empty = True
            break
        newMetadata.append(line)
    #error code if directory isnt found/doesnt exist
    if not dir_found:
        print(f"Directory '{name}' not found.")
        return
    #can only delete if the directory is empty
    if not_empty:
        print(f"Directory '{name}' is not empty.")
        return
    #update/remove the metadata for directory
    with open("private.pfs", "wb") as f:
        f.write(content_bytes)
        f.write(b"--metadata--\n")
        for line in newMetadata:
            f.write((line + "\n").encode())

    print(f"Directory '{name}' removed.")


def removeSuppFile(name):
    with open("private.pfs", "rb") as f:
        privatecont = f.read()
    #separate metadata and content
    parts = privatecont.split(b"--metadata--\n")
    if len(parts) != 2:
        print("Invalid PFS format.")
        return

    content_bytes = parts[0]
    metadata_lines = parts[1].decode().splitlines()

    updated_metadata = []
    #checking that the file is found
    found = False

    for line in metadata_lines:
        if not line.strip():
            continue
        fields = line.strip().split("|")
        if len(fields) != 5:
            updated_metadata.append(line)
            continue
        typecode, entry_name, *_ = fields
        #if the file being removed matches metadata then dont include it in the new metadata
        if typecode == "F" and entry_name == name:
            found = True
            continue
        updated_metadata.append(line)
    #alert that file is not found or doesnt exist
    if not found:
        print(f"File '{name}' not found.")
        return

    #update/remove metadata
    with open("private.pfs", "wb") as f:
        f.write(content_bytes)
        f.write(b"--metadata--\n")
        for line in updated_metadata:
            f.write((line + "\n").encode())
    #for succesful removing
    print(f"File '{name}' removed from PFS.")


def supplimentaryCommands(args):
    if args[0] == 'cp':
        # error if not enough arguments for cp
        if len(args) != 3:
            print("cp requires source and destination")
            return
        # sets the source and destination from the args
        src, dest = args[1], args[2]
        # if source is a supplimentary file and destination is a normal file
        if src.startswith('+') and not dest.startswith('+'):
            #read contents from the private.pfs
            suppContent = readSupp(src[1:])
            with open(dest, 'w') as f:
                #write whatever is in the supplimentary file into the destination
                f.write(suppContent)

        # if source is a normal file and destination is a supplimentary file
        elif not src.startswith('+') and dest.startswith('+'):
            if os.path.exists(src):
                with open(src, 'r') as f:
                    content = f.read()
                path = dest[1:]
            else:
                print(f"Source '{src}' does not exist.")
                return
            writeSupp(path, content)
        elif src.startswith('+') and dest.startswith('+'):
            # read contents from the private.pfs
            suppContent = readSupp(src[1:])
            path = dest[1:]
            writeSupp(path, suppContent)

    if args[0] == 'show':
        filename = args[1][1:]  # strip +
        content = readSupp(filename)
        if content is not None:
            print(content)

    elif args[0] == 'mkdir':
        if len(args) != 2 or not args[1].startswith('+'):
            print("Usage: mkdir +directory")
            return
        dirname = args[1][1:]
        makeSuppDir(dirname)

    elif args[0] == 'rmdir':
        if len(args) != 2 or not args[1].startswith('+'):
            print("Usage: rmdir +directory")
            return
        dirname = args[1][1:]
        removeSuppDir(dirname)
    elif args[0] == 'ls':
        if len(args) != 2 or not args[1].startswith('+'):
            print("for use in +filename or +dirname/")
            return
        path = args[1][1:]
        listSuppEntry(path)

    #for removing regular files
    elif args[0] == 'rm':
        if len(args) != 2 or not args[1].startswith('+'):
            print("Usage: rm +filename")
            return
        filename = args[1][1:]
        removeSuppFile(filename)

    elif args[0] == 'merge':
        if len(args) != 4 or not all(arg.startswith('+') for arg in args[1:]):
            print("make sure files are supplimentary")
            return
        file1 = args[1][1:]
        file2 = args[2][1:]
        result = args[3][1:]
        mergeSuppFiles(file1, file2, result)



def do_command(command):
    # creates the full string of command
    command = expand_variables(command)

    # split the commands and then remove any double quotes from each word
    arg = split_command(command)
    arg = [word.strip('"') for word in arg]

    # chech for supplimentary files first
    supplementary_args = [arg for arg in arg[1:] if arg.startswith('+')]
    if supplementary_args:
        supplimentaryCommands(arg)
        return

    # check if pipe
    if "|" in command:
        do_pipe(command)
        return

    # check if the first item in the arg list is the cd command
    if arg[0] == "cd":
        change_dir(arg)
        return

    # process the input output redirection
    arg, input_file, output_file = redirection(arg)
    if arg is None:
        return

    # checks the last argument in the arg list and if it is & then set the variable to true, run the program and remove the & from the list
    run_in_background = False
    if arg[-1] == '&':
        run_in_background = True
        arg = arg[:-1]

    # if empty then return
    if not arg:
        return

    # find the path of the command
    executable = find_path(arg[0])

    # if the executbale returns empty then print error and return
    if not executable:
        print("Command not found")
        return

    # check if the file exists bit is not executable and print error if it is and return
    if os.path.isfile(executable) and not os.access(executable, os.X_OK):
        print(f"{arg[0]}: Not executable")
        return

    # fork the process
    pid = os.fork()
    if pid == 0:
        try:
            # if the input_file is not empty then we open the file as a read only file
            if input_file:
                fd_in = os.open(input_file, os.O_RDONLY)
                # redirect the fd_in as the stdin
                os.dup2(fd_in, 0)
                # close the file
                os.close(fd_in)
            if output_file:
                # opent the output file, if the file doesnt exist then we create it, make it a write only file and give it the correct permissions
                fd_out = os.open(output_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
                # make the fd_out as the stdout
                os.dup2(fd_out, 1)
                # close the file
                os.close(fd_out)
                # execute the command and exit if it fails and print error
            os.execve(executable, arg, os.environ)
        except FileNotFoundError:
            print("Command execution failed")
        sys.exit(1)
    else:
        # if we're not supposed to run the command in the background then we wait for the child process to complete
        if not run_in_background:
            os.waitpid(pid, 0)


# used to read files
def process_in(fd):
    with fd as openfile:
        for line in openfile:
            command = line.strip()
            # if the line is empty or starts with a # then we ignore it
            if not command or command.startswith("#"):
                continue
            if command.lower() == "exit":
                sys.exit(0)
            do_command(command)


def main():
    # creates the private.pfs if it doesnt exist already
    if not os.path.exists("private.pfs"):
        with open("private.pfs", 'w') as f:
            f.write("--content--\n")
            f.write("--metadata--\n")

    # check if the argument provided was a file
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
