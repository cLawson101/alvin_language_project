import os
import sys
import re
import pfs  

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

    
    if any(word.startswith('+') or '+' in word for word in arg):
        try:
            if arg[0] == "cp":
                pfs.cp_pfs(arg[1], arg[2])
            elif arg[0] == "rm":
                pfs.rm_pfs(arg[1])
            elif arg[0] == "mkdir":
                pfs.mkdir_pfs(arg[1])
            elif arg[0] == "rmdir":
                pfs.rmdir_pfs(arg[1])
            elif arg[0] == "ls":
                pfs.ls_pfs(arg[1] if len(arg) > 1 else None)
            elif arg[0] == "merge":
                pfs.merge_pfs(arg[1], arg[2], arg[3])
            elif arg[0] == "show":
                pfs.show_pfs(arg[1])
            else:
                print(f"{arg[0]}: Not implemented for supplemental files")
        except IndexError:
            print(f"{arg[0]}: Missing argument")
        return

    
    run_in_background = False
    if arg[-1] == '&':
        run_in_background = True
        arg = arg[:-1]
    
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
    
    while True:
        try:
            command = input("$ ").strip()
        except EOFError:
            break
        
        if command.lower() == "exit":
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