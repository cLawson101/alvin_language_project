
import os
import sys
import re
from pfs_commands import pfs_cp, pfs_show, init_pfs, pfs_ls, pfs_merge

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

    #cmds
    if arg[0] == "cp" and (arg[1].startswith("+") or arg[2].startswith("+")):
        pfs_cp(arg[1], arg[2])
        return
    elif arg[0] == "show" and arg[1].startswith("+"):
        pfs_show(arg[1])
        return

    if arg[0] == "ls" and len(arg) == 2 and arg[1].startswith("+"):
        pfs_ls(arg[1])
        return

    if arg[0] == 'merge' and arg[3].startswith('+'):
        pfs_merge(arg[1], arg[2], arg[3])
        return

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

def main():
    print('Shell start!\n')
    init_pfs()
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
