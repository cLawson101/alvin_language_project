import os
import sys
import re
import time

private_fs = "private.pfs"

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
    arg = split_command(command)
    arg = [w.strip('"') for w in arg]
    if not arg:
        return

    # private.fps commands
    # cp
    if arg[0] == "cp" and len(arg) == 3 and arg[2].startswith("+"):
        sup_cp(arg[1], arg[2])
        return
    # rm 
    if arg[0] == "rm" and len(arg) == 2 and arg[1].startswith("+"):
        sup_rm(arg[1])
        return
    # mkdir
    if arg[0] == "mkdir" and len(arg) == 2 and arg[1].startswith("+"):
        sup_mkdir(arg[1])
        return
    # rmdir 
    if arg[0] == "rmdir" and len(arg) == 2 and arg[1].startswith("+"):
        sup_rmdir(arg[1])
        return
    # ls 
    if arg[0] == "ls" and (len(arg) == 1 or arg[1].startswith("+")):
        sup_ls(arg[1] if len(arg) > 1 else None)
        return
    # show 
    if arg[0] == "show" and len(arg) == 2 and arg[1].startswith("+"):
        sup_show(arg[1])
        return
    # merge
    if arg[0] == "merge" and len(arg) == 4 and arg[3].startswith("+"):
        sup_merge(arg[1], arg[2], arg[3])
        return

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

def load_private_fs():
    dirs = []
    files = {}
    data = ""
    if not os.path.exists(private_fs):
        # initialize with an empty metadata block
        with open(private_fs, 'w') as f:
            f.write("END\n")
        return dirs, files, data
    with open(private_fs, 'r') as f:
        meta_lines = []
        # read metadata lines until END
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                break
            if line.strip() == "END":
                break
            meta_lines.append(line.rstrip('\n'))
        # remaining is data block
        data = f.read() or ""
    # parse metadata
    for line in meta_lines:
        if line.startswith("DIR:"):
            dirname = line[len("DIR:"):].strip()
            if dirname:
                dirs.append(dirname)
        elif line.startswith("FILE:"):
            parts = line[len("FILE:"):].split(":")
            if len(parts) == 4:
                path, offset, length, timestamp = parts
                files[path] = [int(offset), int(length), int(timestamp)]
    return dirs, files, data


def save_private_fs(dirs, files, data):
    with open(private_fs, 'w') as f:
        for d in dirs:
            f.write(f"DIR:{d}\n")
        for path, (offset, length, timestamp) in files.items():
            f.write(f"FILE:{path}:{offset}:{length}:{timestamp}\n")
        f.write("END\n")
        f.write(data)


def sup_cp(src, dest):
    if not dest.startswith("+"):
        print("cp: destination must start with +")
        return
    dest_path = dest[1:]
    dirs, files, data = load_private_fs()
    if src.startswith("+"):
        src_path = src[1:]
        if src_path not in files:
            print(f"cp: {src}: No such file")
            return
        off, length, _ = files[src_path]
        content = data[off:off+length]
    else:
        try:
            with open(src, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"cp: {src}: No such file or directory")
            return
    if '/' in dest_path:
        dir_name, _ = dest_path.split('/', 1)
        if dir_name not in dirs:
            print(f"cp: cannot create regular file '{dest}': No such directory")
            return
    if dest_path in files:
        sup_rm(dest)
        dirs, files, data = load_private_fs()
    timestamp = int(time.time())
    offset = len(data)
    length = len(content)
    files[dest_path] = [offset, length, timestamp]
    data += content
    save_private_fs(dirs, files, data)


def sup_rm(arg):
    if not arg.startswith("+"):
        print("rm: argument must start with +")
        return
    file_name = arg[1:]
    dirs, files, data = load_private_fs()
    if file_name not in files:
        print(f"rm: cannot remove '{arg}': No such file")
        return
    entries = []
    for path, (off, length, ts) in files.items():
        if path == file_name:
            continue
        entries.append((off, path, data[off:off+length], ts))
    entries.sort(key=lambda x: x[0])
    new_data = ""
    new_files = {}
    curr = 0
    for _, path, content, ts in entries:
        new_files[path] = [curr, len(content), ts]
        new_data += content
        curr += len(content)
    save_private_fs(dirs, new_files, new_data)


def sup_mkdir(arg):
    if not arg.startswith("+"):
        print("mkdir: argument must start with +")
        return
    dir_name = arg[1:]
    dirs, files, data = load_private_fs()
    if dir_name in dirs:
        print(f"mkdir: cannot create directory '{arg}': File exists")
        return
    if '/' in dir_name:
        print(f"mkdir: cannot create directory '{arg}': Nested directories not supported")
        return
    dirs.append(dir_name)
    save_private_fs(dirs, files, data)


def sup_rmdir(arg):
    if not arg.startswith("+"):
        print("rmdir: argument must start with +")
        return
    dir_name = arg[1:]
    dirs, files, data = load_private_fs()
    if dir_name not in dirs:
        print(f"rmdir: failed to remove '{arg}': No such directory")
        return
    for path in files:
        if path.startswith(dir_name + "/"):
            print(f"rmdir: failed to remove '{arg}': Directory not empty")
            return
    dirs.remove(dir_name)
    save_private_fs(dirs, files, data)


def sup_ls(arg=None):
    dirs, files, data = load_private_fs()
    if arg is None:
        for d in dirs:
            print(f"{d}/")
        for path, (_, _, ts) in files.items():
            if '/' not in path:
                print(f"{path}\t{ts}")
        return
    if arg.startswith("+"):
        path = arg[1:]
    else:
        path = arg
    if path in dirs:
        for fpath, (_, _, ts) in files.items():
            if fpath.startswith(path + "/"):
                name = fpath.split('/',1)[1]
                print(f"{name}\t{ts}")
    elif path in files:
        _, _, ts = files[path]
        print(f"{path}\t{ts}")
    else:
        print(f"ls: cannot access '{arg}': No such file or directory")


def sup_show(arg):
    if not arg.startswith("+"):
        print("show: argument must start with +")
        return
    file_name = arg[1:]
    dirs, files, data = load_private_fs()
    if file_name not in files:
        print(f"show: cannot show '{arg}': No such file")
        return
    off, length, _ = files[file_name]
    sys.stdout.write(data[off:off+length])


def sup_merge(src1, src2, dest):
    if not dest.startswith("+"):
        print("merge: destination must start with +")
        return
    dest_path = dest[1:]
    dirs, files, data = load_private_fs()
    # first source
    if src1.startswith("+"):
        s1 = src1[1:]
        if s1 not in files:
            print(f"merge: {src1}: No such file")
            return
        off, length, _ = files[s1]
        c1 = data[off:off+length]
    else:
        try:
            with open(src1,'r') as f:
                c1 = f.read()
        except FileNotFoundError:
            print(f"merge: {src1}: No such file or directory")
            return
    # second source
    if src2.startswith("+"):
        s2 = src2[1:]
        if s2 not in files:
            print(f"merge: {src2}: No such file")
            return
        off, length, _ = files[s2]
        c2 = data[off:off+length]
    else:
        try:
            with open(src2,'r') as f:
                c2 = f.read()
        except FileNotFoundError:
            print(f"merge: {src2}: No such file or directory")
            return
    merged = c1 + c2
    if dest_path in files:
        sup_rm(dest)
        dirs, files, data = load_private_fs()
    if '/' in dest_path:
        dn, fn = dest_path.split('/',1)
        if dn not in dirs:
            print(f"merge: cannot create file '{dest}': No such directory")
            return
    ts = int(time.time())
    off = len(data)
    ln = len(merged)
    files[dest_path] = [off, ln, ts]
    data += merged
    save_private_fs(dirs, files, data)

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