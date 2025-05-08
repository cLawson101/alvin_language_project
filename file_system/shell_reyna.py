import os
import sys
import re
import time

fileName = "privatePFS.txt"

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

def checkPFS():
        #Checks if privatePFS file already exists
    try:
        privatePFS = open("privatePFS.txt", "x")
        privatePFS.write("+root/#END#")
    except FileExistsError:
        print("File Already Exists")

def do_sp_command(command):

    #Split command by spaces
    arg = split_command(command)
    arg = [word.strip('"') for word in arg]

    try:

        #Switch Case for finding right command
        match arg[0]:

            case "show":

                if checkFileExists(arg[1]) and ".txt" in arg[1]:
                    show(arg[1])
                else:
                    print("Must be a path to a FILE")

            case "rm":
                if checkFileExists(arg[1]):
                    rm(arg[1])
                else:
                    print("File does not exist")

            case "mkdir":

                mkdir(arg[1])

            case "rmdir":

                rmdir(arg[1])

            case "ls":

                ls(arg[1])

            case "cp":

                spCopy(arg[1], arg[2])

            case "merge":
                if not checkFileExists(arg[2]) or not checkFileExists(arg[1]):
                    print("At least one of the files does not exist")
                    return
                merge(arg[1], arg[2], arg[3])

            case _:
                print("Invalid Command")

        #After command is process/failed return.
        return
    
    except IndexError:

        print("Not enough arguments")

    return

def show(path):

    # Get content based on formatting and prints content
    if path[0] == "+":
        content = getSPContent(path)
    else:
        content = getContent(path)

    print(path + ": " + content)

def merge(arg, arg2, arg3):
    global fileName
    
    try:
        # Gets content of file from real/fake file system
        if arg[0] == "+":
            content1 = getSPContent(arg)
        else:
            content1 = getContent(arg)

        if arg2[0] == "+":
            content2 = getSPContent(arg2)
        else:
            content2 = getContent(arg2)

        #Formate check
        if arg3[0] == "+":
            #Cheks if file already exists, if not creat one and merge
            if not checkFileExists(arg3):
                addToPFS(arg3, True, content1 + content2)
            else:
                addToPFS("dummy", True, content1 + content2)
                spCopy("dummy", arg3)
                rm("dummy")
        else:
            print("Third argument path must start with +")
            return

    except FileNotFoundError as e:
        print(f"File not found: {e}")
        return

def ls(path):
    global fileName
    try:
        with open(fileName, 'r') as f:
            content = f.read()

        entries = content.split('#END#')
        results = []

        # Format check
        if not path.startswith('+'):
            path = '+' + path

        #For the single file ls
        if ".txt" in path:
            # Checks for path + |FILE| and displays the name and last mod time
            for entry in entries:
                if entry.strip().startswith(path) and '|FILE|' in entry:
                    parts = entry.split('|')
                    if len(parts) >= 4:
                        filename = path.split('/')[-1]
                        modified = parts[3]
                        print([(filename, modified)])
                        return

        # Format Check
        if not path.endswith('/'):
            path += '/'

        #Lists all files underneath this directory
        for entry in entries:
            if entry.strip().startswith(path) and '|FILE|' in entry:
                parts = entry.split('|')
                if len(parts) >= 4:
                    # Extract file name from path
                    fileName = parts[0]
                    filename = fileName.split('/')[-1]
                    modified = parts[3]
                    results.append((filename, modified))

        if not results:
            print("No files found at the given path.")
            return

        print(results)
        return

    except FileNotFoundError:
        print(f"The file '{fileName}' does not exist.")
        return

def rmdir(dir_path):
    global fileName
    try:
        with open(fileName, 'r+') as f:
            content = f.read()

        # Make sure path is formatted is in format
        if not dir_path.endswith('/'):
            dir_path += '/'
        if not dir_path.startswith('+'):
            dir_path = '+' + dir_path

        entries = content.split('#END#')
        new_entries = []
        found = False

        for entry in entries:
            entry = entry.strip()
            if entry == "":
                continue

            # Removes the directory and everything under it
            if entry.startswith(dir_path):
                found = True
                continue

            new_entries.append(entry)

        if not found:
            print("Directory not found.")
            return False

        # Update and put back
        new_content = '#END#'.join(new_entries).strip() + '#END#'

        with open(fileName, 'w') as f:
            f.write(new_content)

        return True

    except FileNotFoundError:
        print(f"The file '{fileName}' does not exist.")
        return False

def mkdir(path):
    global fileName
    try:
        with open(fileName, 'r+') as f:
            content = f.read()

        #  Makes sure it ends with a slash and starts with '+'
        if not path.endswith('/'):
            path += '/'
        if not path.startswith('+'):
            path = '+' + path

        # Check if directory already exists
        if path in content:
            print("Directory already exists.")
            return False

        # Format directory entry
        new_entry = f"{path}#END#"

        # Add the new directory
        with open(fileName, 'a') as f:
            f.write(new_entry)

        return True

    except FileNotFoundError:
        print(f"The file '{fileName}' does not exist.")
        return False

def rm(entry_path):
    global fileName
    try:
        with open(fileName, 'r+') as f:
            content = f.read()

        entries = content.split('#END#')
        new_entries = []
        found = False

        for entry in entries:
            if entry.strip() == "":
                continue
            if entry_path in entry:
                # Checks if it's an exact match
                if entry.strip().startswith(entry_path):
                    found = True
                    continue  # Skip this entry (i.e., remove it)
            new_entries.append(entry.strip())

        if not found:
            print("Entry not found.")
            return False

        # Update and put it back to PFS
        new_content = '#END#'.join(new_entries).strip() + '#END#'
        with open(fileName, 'w') as f:
            f.write(new_content)

        return True

    except FileNotFoundError:
        print(f"The file '{fileName}' does not exist.")
        return False

def spCopy(arg, arg2):

    # Checks if source file exists or not, and checks if destination file is formatted correctly
    if not checkFileExists(arg):

        print("Argument 1 file does not exist")
        return
    
    elif arg2[0] != "+":

        print("Destination path must start with +")
        return
    
    #Checks if the destination file already exists, if not, create a new entry
    if not checkFileExists(arg2):

        addToPFS(arg2, True, getSPContent(arg))

    # get content from real/fake file system
    if arg[0] == '+':

        content = getSPContent(arg)

    else:

        content = getContent(arg)

    overWrite(arg2, content)

    return

def addToPFS(entry_path, is_file=False, file_content=""):
    global fileName

    try:
        with open(fileName, 'r+') as f:
            content = f.read()

        # Check if entry already exists
        if entry_path in content:
            print("Entry already exists.")
            return False

        # Build new entry
        new_entry = ""
        if is_file:
            now = time.strftime('%B-%d-%Y:%H:%M:%S')
            size = str(len(file_content))
            new_entry = f"{entry_path}|FILE|{now}|{now}|{size}|{file_content}#END#"
        else:
            if not entry_path.endswith('/'):
                entry_path += '/'
            new_entry = f"{entry_path}#END#"

        # Add new entry to PFS
        with open(fileName, 'a') as f:
            f.write(new_entry)

        return True

    except FileNotFoundError:
        print(f"The file '{fileName}' does not exist.")
        return False

def overWrite(file_path, new_content):

    global fileName
    
    try:
        with open(fileName, 'r+') as f:
            content = f.read()

        #Split content of the PFS file by #END#
        entries = content.split('#END#')
        new_entries = []
        found = False

        for entry in entries:
            if file_path in entry and '|FILE|' in entry:
                parts = entry.split('|')
                if len(parts) >= 6:
                    found = True
                    # Update time for modification section
                    modified_time = time.strftime('%B-%d-%Y:%H:%M:%S')

                    # Update the file entry
                    updated_entry = '|'.join([
                        parts[0],                 # +path
                        parts[1],                 # FILE
                        parts[2],                 # Created date + time (unchanged)
                        modified_time,            # New modified date + time
                        str(len(new_content)),    # New size
                        new_content               # New content
                    ])
                    new_entries.append(updated_entry)
                else:
                    new_entries.append(entry)
            else:
                new_entries.append(entry)

        if not found:
            print("File not found.")
            return False

        # Rejoin and put it back to the PFS file
        new_content_full = '#END#'.join(new_entries).strip()

        with open(fileName, 'w') as f:
            f.write(new_content_full)

        return True

    except FileNotFoundError:
        print(f"The file '{fileName}' does not exist.")
        return False

def checkFileExists(path):
    global fileName

    try:
        # Try to open the private file system file
        with open(fileName, "r") as privatePFS:
            # Read the entire content of the file
            content = privatePFS.read()

        # Split entries using #END#
        entries = content.split('#END#')

        # Loop through each entry to check if the given path exists in the private system
        for entry in entries:
            if path in entry:
                return True 

        # If not found in private system, try checking the real file system
        with open(path, "r") as file:
            return True

        # If neither found in private system nor real file system, return False
        return False

    except FileNotFoundError:
        # This handles the case where either privatePFS or the real file doesn't exist
        print(f"The file '{fileName}' does not exist.")
        return False

def getSPContent(file_path):

    global fileName

    try:
        with open(fileName, 'r+') as f:
            content = f.read()
        
        # Split the content by the #END# to process each entry.
        entries = content.split('#END#')

        for entry in entries:
            # Check if the entry matches to a file and matches the file path
            if file_path in entry and '|FILE|' in entry:
                # get the part after |FILE|, which has the content
                parts = entry.split('|')
                if len(parts) >= 6:
                    return parts[5]

        # If file not found
        return None
    except FileNotFoundError:
        print(f"The file '{fileName}' does not exist.")
        return None

def getContent(file):

    try:
        #Opens file, if success, return the entire text
        file = open(file, "r")
        content = file.read()
        file.close()
        return content

    except FileNotFoundError:

        print("File does not exist")

    return None

def main():

    checkPFS()

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

        args = command.split(" ")
        if len(args) < 2: args.append(" ")
        if "+" in args[1] or "+" in args[2]:

            do_sp_command(command)

        else:

            do_command(command)

if __name__ == "__main__":
    main()