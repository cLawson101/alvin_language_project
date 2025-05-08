import os
import sys
import re
from datetime import datetime

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

    # intercept file system commands
    # if any word in arg starts with '+' then its a supplmental file system command
    if any(word.startswith('+') for word in arg):
        handle_supplementalFS_command(arg)
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

# function to handle any supplemental file system command
def handle_supplementalFS_command(args) :
    # get the command
    cmd = args[0]
    # if the command was cp
    if cmd == 'cp':
        if len(args) == 3:
            copy(args[1], args[2])
        else:
            print('command cp: requires 2 arguments')
    # if the command was show
    elif cmd == 'show':
        if len(args) != 2:
            print('command show: requires 1 argument')
        else:
            show(args[1])
    # if the command was merge
    elif cmd == 'merge':
        if len(args) != 4:
            print('command merge: requires 3 arguments')
        else:
            merge(args[1],args[2], args[3])
    # if the command was rm
    elif cmd == 'rm':
        if len(args) != 2:
            print('command rm: requires 1 argument')
        else:
            remove(args[1])
    # if the command was ls
    elif cmd == 'ls':
        if len(args) != 2:
            print('command ls: requires 1 argument')
        else:
            ls(args[1])
    # if the command was mkdir
    elif cmd == 'mkdir':
        if len(args) != 2:
            print('command mkdir: requires 1 argument')
        else:
            mkdir(args[1])
    # if the command was rmdir
    elif cmd == 'rmdir':
        if len(args) != 2:
            print('command rmdir: requires 1 arguments')
        else:
            rmdir(args[1])
    # otherwise handle any other unsupported command elegantly
    else:
        print(f"\nUnsupported supplemental file system command: {cmd}\n")


# function to cp within the supplemental file system
def copy(src, dest):
    inDir = False
    # open private.pfs for reading
    with open('private.pfs', 'r') as f:
        file_data = f.read()
    # find out if the dest is within a dir
    if '/' in dest:
        dir_name = dest.split('/')[0]
        dir_pattern = rf'DIR_START {re.escape(dir_name)}\s+(.*?)DIR_END'
        dir_block = re.search(dir_pattern, file_data, re.DOTALL)
        if not dir_block: # the directory does not exist
            print(f'Directory: {dir_name} does not exist')
            return
        inDir = True
    
    # if the src is within the supplemental file system
    if src.startswith('+'):
        # get the content of src (capture everything between FILE_START and FILE_END '(.*?)')
        # do it accross multiple lines (re.DOTALL)
        src_match = re.search(rf'FILE_START {re.escape(src)}\s+(.*?)FILE_END', file_data, re.DOTALL)
        if not src_match: # src is not within the supplemental file system
            print(f'File: {src} not found')
            return
        # otherwise extract the files metadata and only capture the content
        content_match = re.search(r'content:\s*(.*?)$', src_match.group(1), re.DOTALL)
        # if there is content
        if content_match:
            # clean the content
            src_content = content_match.group(1).strip()
        else: # there was no content
            src_content = ''
    # otherwise the src is in the OS file system
    else:
        # if the file is in the OS file system
        if not os.path.exists(src):
            print(f'File: {src} not found')
            return
        # otherwise the file exists so open it for reading
        with open(src, 'r') as f_src:
            # get its contents
            src_content = f_src.read().strip()
    # get the content of the dest file
    dest_match = re.search(rf'(FILE_START {re.escape(dest)}\s+.*?content:)(.*?)(FILE_END)', file_data, re.DOTALL)
    if not dest_match: # dest is not within the supplemental file system
        # create the dest supplementary file
        create_new_file(dest)
        # re-read the file
        with open('private.pfs', 'r') as f:
            file_data = f.read()
        # get its content
        dest_match = re.search(rf'(FILE_START {re.escape(dest)}\s+.*?content:)(.*?)(FILE_END)', file_data, re.DOTALL)
    # create the new file block (split into 3 parts:
    # group(1) - everything up to content
    # group(2) - the content section
    # group(3) - the FILE_END tag
    new_block = f'{dest_match.group(1)}{dest_match.group(2)}{dest_match.group(3)}'
    # update the files metadata
    mod_file = update_file_metadata(new_block, src_content)
    # set up content to write into dest:
    # everything before the destination file +
    # the modified destination file
    # everythin after the destination file
    new_data = (file_data[:dest_match.start()] +
                mod_file +
                file_data[dest_match.end():])
    # write content into the supplemental file system
    with open("private.pfs", "w") as f:
        f.write(new_data)
    # update the metadata for the directory (if the file exists within a dir)
    if inDir:
        update_dir_metadata(dir_name)

# function to show within the supplemental file system
def show(src):
    # find out if the file is within the supplemental file system
    file = helper_find_file(src)
    if not file:
        print(f'File: {src} not found')
        return
    # get the metadata
    file_data = file.group(1)
    # extract the content
    match = re.search(r'content:\s*(.*?)$', file_data, re.DOTALL)
    # if there is content
    if match:
        print(match.group(1).strip())
    # if there is no content
    else:
        print("No content found")


#returns the contents of the file whether it is in the supplementaty system or regular file
def helper_get_file_content(file):
    #supplementary file system
    if file.startswith('+'):
        file_data = helper_find_file(file)
        if not file_data:
            return None
        return re.search(r'content:\s*(.*?)$', file_data.group(1), re.DOTALL).group(1).strip() #contents of the file in string format
    #regular file
    else:
        if not os.path.exists(file): #file not found
            return None 
        with open(file, 'r') as f_src:
            return f_src.read().strip()

# function to merge within the supplemental file system
def merge(src1, src2, dest):
    inDir = False
    # open private.pfs for reading
    with open('private.pfs', 'r') as f:
        file_data = f.read()
    # find out if the dest is within a dir
    if '/' in dest:
        dir_name = dest.split('/')[0]
        dir_pattern = rf'DIR_START {re.escape(dir_name)}\s+(.*?)DIR_END'
        dir_block = re.search(dir_pattern, file_data, re.DOTALL)
        if not dir_block: # the directory does not exist
            print(f'Directory: {dir_name} does not exist')
            return
        inDir = False
    src1_content = helper_get_file_content(src1)
    src2_content = helper_get_file_content(src2)

    if not src1_content:
        print(f'File: {src1} not found')
        return
    if not src2_content:
        print(f'File: {src2} not found')
        return
        
    dest_content = str(src1_content)  + str(src2_content) #contents concat

    if dest.startswith("+"): #if dest in supplementary file system
        dest_file = helper_find_file(dest)
        if not dest_file: #if dest not found, create it
            print(f"File: {dest} not found")
            print(f"Creating new {dest} file")
            create_new_file(dest)
            dest_file = helper_find_file(dest)
                
        with open('private.pfs', 'r') as f:
            file_data = f.read()

        #getting and updating the metadata
        dest_match = re.search(rf'(FILE_START {re.escape(dest)}\s+.*?content:)(.*?)(FILE_END)', file_data, re.DOTALL)
        new_block = f'{dest_match.group(1)}{dest_match.group(2)}{dest_match.group(3)}'
        new_dest = update_file_metadata(new_block, dest_content)

        new_data = (file_data[:dest_match.start()] +
                new_dest +
                file_data[dest_match.end():])
        
        #writing updated info to supplementary file system
        with open("private.pfs", "w") as f:
            f.write(new_data)

        #if the dest is in a dir, update the dir as well
        dir_name = helper_in_directory(dest)
        if (dir_name):
            update_dir_metadata(dir_name)
        return
    
    #if it is a regular file
    with open(dest, "w") as f:
            f.write(dest_content)
    # if the destination file is in a dir, update dir metadata
    if inDir:
        update_dir_metadata(dir_name)

# function to rm within the supplemental file system
def remove(src):

    src_file = helper_find_file(src)
    if not src_file: #verify file exists
        print(f"File {src} not found")
        return
    
    #read fle system and ignore the file we wish to remove
    with open('private.pfs', 'r') as f:
        file_data = f.read()
    new_data = (file_data[:src_file.start()].strip() + "\n\n" +
            file_data[src_file.end():].strip() + "\n\n")
    
    #rewrite the file systme
    with open("private.pfs", "w") as f:
        f.write(new_data)

    #update the directory if it was in one
    dir_name = helper_in_directory(src)
    if (dir_name):
        update_dir_metadata(dir_name)
    
    return

# function to ls within the supplemental file system
def ls(src):
    # find out if it is a file and is within the supplemental file system
    file = helper_find_file(src)
    if not file:
        file = helper_find_dir(src)
        if not file:
            print(f'File: {src} not found')
            return
    # get the metadata
    file_data = file.group(1)
    # extract size and last_modified
    size = re.search(r'^size:\s*(.*)', file_data, re.MULTILINE)
    last_modified = re.search(r'^last_modified:\s*(.*)', file_data, re.MULTILINE)
    # if there is metadata
    if size and last_modified:
        print(f'Name: {src}\nSize: {size.group(1).strip()}\nLast Modified: {last_modified.group(1).strip()}')
    # if there is no content
    else:
        print("No content found")

# function to mkdir within the supplemental file system
def mkdir(src):
    new_dir = f'DIR_START {src}\nsize:??\nlast_modified:??\nDIR_END\n'
    # open private.pfs for reading and writing
    try:
        with open('private.pfs', '+r') as f:
            # seek to the end of the file
            f.seek(0, os.SEEK_END)
            f.write(new_dir)
    except FileNotFoundError:
        print('private.pfs not found')

# function to rmdir within the supplemental file system
def rmdir(src):

    dir_info = helper_find_dir(src)
    if not dir_info: #verify dir exists
        print(f"Dir {src} not found")
        return
    
    #remove every file that exists in the dir
    for file_name in get_files_in_dir(src):
        print(f"Removing {file_name} file")
        remove(file_name)
    
    print(f"Removing {src} directory")

    dir_info = helper_find_dir(src)
    #read the file system and ignore the dir metadata
    with open('private.pfs', 'r') as f:
        file_data = f.read()

    new_data = (file_data[:dir_info.start()].strip() + "\n" +
            file_data[dir_info.end():].strip() + "\n")
    
    #rewrite the file system
    with open("private.pfs", "w") as f:
        f.write(new_data)

    return

# helper function to find a file within the supplemental file system
def helper_find_file(file):
    # open private.pfs for reading
    try:
        with open('private.pfs', 'r') as f:
            content = f.read()
            # get the files metadata
            pattern = rf'FILE_START {re.escape(file)}\s+(.*?)FILE_END'
            return re.search(pattern, content, re.DOTALL)
    except FileNotFoundError:
        print('private.pfs not found')
        return None

# helper function to find a directory within the supplemental file system
def helper_find_dir(dir):
    # open private.pfs for reading
    try:
        with open('private.pfs', 'r') as f:
            content = f.read()
            # get the dir metadata
            pattern = rf'DIR_START {re.escape(dir)}\s+(.*?)DIR_END'
            return re.search(pattern, content, re.DOTALL)
    except FileNotFoundError:
        print('private.pfs not found')
        return None
    
#helper that returns the dir_name if it is in a dir, false otherwise
def helper_in_directory(file_name):
    if '/' in file_name: #path contains dir
        dir_name = file_name.split('/')[0]
        dir_data = helper_find_dir(dir_name)
        if not dir_data: #dir doesnt exist in file system
            return False
        return dir_name
    return False


# helper function to create a new file within the supplemental file system
def create_new_file(file):
    new_file = f'\nFILE_START {file}\nsize:??\nlast_modified:??\ncontent:??\nFILE_END\n'
    # open private.pfs for reading and writing
    try:
        with open('private.pfs', '+r') as f:
            # seek to the end of the file
            f.seek(0, os.SEEK_END)
            f.write(new_file)
    except FileNotFoundError:
        print('private.pfs not found')

# helper function to update the file metadata
def update_file_metadata(data, content):
    # get the size of the content in bytes
    size = len(content.encode('utf-8'))
    # get the timestamp
    last_modified = datetime.now().strftime('%m/%d/%Y %I:%M %p')
    # replace the size, last modified, and content
    data = re.sub(r'size:\s*.*', f'size: {size}', data)
    data = re.sub(r'last_modified:\s*.*', f'last_modified: {last_modified}', data)
    data = re.sub(r'content:\s*.*', f'content: {content}', data)
    return data

# helper function to update the dir metadata
def update_dir_metadata(dir):
    # get all the files within the directory
    files = get_files_in_dir(dir)
    # keep track of the size and timestamp
    total_size = 0
    latest_timestamp = None
    # open private.pfs for reading
    try:
        with open('private.pfs', 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print('private.pfs not found')
        return
    # loop through the files within the directory
    for filename in files:
        # get the files metadata
        data = re.search(rf'FILE_START {re.escape(filename)}\s+(.*?)FILE_END', content, re.DOTALL)
        if data:
            block = data.group(1)
            # get the size and update total size if applicable
            size = re.search(r'size:\s*(\d+)', block)
            if size:
                total_size += int(size.group(1))
            # get the time and update latest timestamp if applicable
            time = re.search(r'last_modified:\s*(.*)', block)
            if time:
                timestamp = datetime.strptime(time.group(1).strip(), "%m/%d/%Y %I:%M %p")
                if not latest_timestamp or timestamp > latest_timestamp:
                    latest_timestamp = timestamp
    # set up the metadata for writing
    new_size = f'size: {total_size}'
    if latest_timestamp:
        new_time = f'last_modified: {latest_timestamp.strftime("%m/%d/%Y %I:%M %p")}'
    else:
        new_time = 'last_modified: ??'
    # update the metadata
    dir_block = re.search(rf'(DIR_START {re.escape(dir)}\s+)size:\s*.*\nlast_modified:\s*.*(\s+DIR_END)', content)
    if dir_block:
        new_dir_block = f"{dir_block.group(1)}{new_size}\n{new_time}{dir_block.group(2)}"
        content = content[:dir_block.start()] + new_dir_block + content[dir_block.end():]
        with open("private.pfs", "w") as f:
            f.write(content)

# helper function to get all the files within the directory
def get_files_in_dir(dir):
    # open private.pfs for reading
    try:
        with open('private.pfs', 'r') as f:
            content = f.read()
        # Match all file blocks
        pattern = r'FILE_START\s+(\+\S+)\s+.*?FILE_END'
        files = re.findall(pattern, content, re.DOTALL)
        # Filter those that start with +dirname/
        files_in_dir = [f for f in files if f.startswith(dir + '/')]
        return files_in_dir
    except FileNotFoundError:
        print("private.pfs not found")
        return []

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

        if command.lower() == 'inspiration':
            phrase = os.environ.get("phrase")
            if phrase:
                print(phrase)
            else:
                print("There is no current 'inspirational' quote, but\nYou Got This!")
            continue

        do_command(command)

if __name__ == "__main__":
    main()
