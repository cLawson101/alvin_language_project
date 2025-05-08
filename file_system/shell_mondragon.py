# -*- coding: utf-8 -*-
"""
Aitiana L. Mondragon & Giovanna P. Carballido
CS 4375 - CRN: 23426
Dr. Ward
May 5, 2025
Assignment: Supplementary File System - Microshell
"""

import os
import sys
import re

# Import supplemental FS commands

from supplemental_fs import cp, rm, mkdir, rmdir, ls, show, merge

# cd method
def cdCommand(command):
    # change directory to respective path
    if len(command) >= 2:
        try:
            os.chdir(command[1])
        except FileNotFoundError:
            # if file or directory does not exist
            os.write(2, f"cd {command[1]}: No such file or directory\n".encode())
    else: # default to home directory
        os.chdir(os.environ['HOME'])
    
# run method
def run(command):
    try:
        os.execv(command[0], command)# Try executing directly
    except FileNotFoundError:
        pass

    for directory in re.split(':', os.environ['PATH']):
        program = f"{directory}/{command[0]}"
            
        try:
            os.execv(program, command)
            return # move on to next command 
        except FileNotFoundError:

            pass
        except PermissionError:
            os.write(2, f"{program}: Not executable\n".encode())
            sys.exit(1)
            
    os.write(2, f"{command[0]}: Error - Command not found\n".encode())
    sys.exit(1)
    
# redirection method
def redirect(command):
    inputfile = None
    outputfile = None

    # Redirection of input (<)
    if '<' in command:
        index = command.index('<')
        inputfile = command[index + 1]  # Get the input file
        command.pop(index)
        command.pop(index)  

    # Redirection of output (>)
    if '>' in command:
        index = command.index('>')
        outputfile = command[index + 1]  # Get the output file
        command.pop(index)
        command.pop(index)  
    
    # input redirection if there is an input file
    if inputfile:
        try:
            fd_in = os.open(inputfile, os.O_RDONLY)  # Open input file
            os.dup2(fd_in, 0)
            os.close(fd_in)  
            return True
        except Exception as e:
            os.write(2, f"Error opening input file: {e}\n".encode())
            return False

    # output redirection if there is an output file
    if outputfile:
        try:
            fd_out = os.open(outputfile, os.O_WRONLY | os.O_CREAT)  # Open output file
            os.dup2(fd_out, 1)
            os.close(fd_out)
            return True
        except Exception as e:
            os.write(2, f"Error opening output file: {e}\n".encode())
            return False
      
# pipes method
def pipe(command):
    # pipes referred to forkPipeDemo.c from Dr. Freudenthal
    reader, writer = os.pipe()
    index = command.index('|')
    
    pid = os.fork()
    
    if pid < 0: # if failed
        sys.exit(1) 

    elif pid == 0: # child
        os.close(1) # close out 
        os.dup(writer) # duplicate writer to out
        os.set_inheritable(1, True)
        os.close(reader)
        os.close(writer)
        
        run(command[:index])
        
    else: # parent
       os.close(0) #close in 
       os.dup(reader) # duplicate reader to in
       os.set_inheritable(0, True)
       os.close(reader)
       os.close(writer)
       run(command[index+1:])
       run(command[index + 1:])       
    
# inspiration method
def inspirationCommand():
    phrase = os.environ.get('phrase')
    if phrase:
        print(phrase)
    else:
        print('Always be yourself. Unless you can be a dragon... then always be a dragon.')

# banner at the start of the shell        
def welcomeBanner():
    print(' ____                      _____ _       _ _ ')
    print('|    \\ ___ ___ ___ ___ ___|   __| |_ ___| | |')
    print('|  |  |  _| .\'| . | . |   |__   |   | -_| | |')
    print('|____/|_| |__,|_  |___|_|_|_____|_|_|___|_|_|') 
    print('              |___|                          ')
    print()
    print()
    print('Strength is not seen in the loudest roar, but in the quiet, focused actions...')
    print()
    print()
    
# Detect supplemental file
def is_supplemental_file(arg):
    return arg.startswith("+")

# Shell method to handle input and file reading          
def process_line(line):
    command = list(filter(None, line.split(' ')))
    if len(command) == 0:
        return

    if command[0] == 'quit':
        sys.exit(0)

    if command[0] == 'cd':
        cdCommand(command)
        return

    if command[0] == 'inspiration':
        inspirationCommand()
        return
    
    # Handle supplemental FS commands with checks for supplementary files
    if command[0] == "cp":
        if any(is_supplemental_file(arg) for arg in command[1:]):
            cp(command[1], command[2])
        else:
            # if working with regular cp (unix command)
            pass
        return
    
    elif command[0] == "rm" and is_supplemental_file(command[1]):
        rm(command[1])
        return
    
    elif command[0] == "mkdir" and is_supplemental_file(command[1]):
        mkdir(command[1])
        return
    
    elif command[0] == "rmdir" and is_supplemental_file(command[1]):
        rmdir(command[1])
        return
    
    elif command[0] == "ls" and len(command) >= 2 and is_supplemental_file(command[1]):
        ls(command[1])
        return
    
    elif command[0] == "show" and len(command) >= 2 and is_supplemental_file(command[1]):
        show(command[1])
        return
    
    elif command[0] == "merge" and len(command) >= 4 and any(is_supplemental_file(arg) for arg in command[1:]):
        merge(command[1], command[2], command[3])
        return

    # Handle regular file operations (non-supplementary) -- JUST IN CASE
    if command[0] == "cp" and len(command) >= 3:
        # Handle regular file copy logic here
        pass
    elif command[0] == "ls" and len(command) >= 1:
        # Handle regular ls command (list files in the current directory) - JUST IN CASE
        pass

    # Continue to typical Unix command execution (normal shell functionality)
    
    pid = os.fork()  # create child process
    wait = True # wait boolean

    if command[-1] == '&':  # run in the background
        wait = False
        command.pop()

    if pid == -1:  # no child process was created
        os.write(2, "Process creation failed\n".encode())
        sys.exit(1)  # exit

    elif pid == 0:  # is child
        if '<' in command or '>' in command:
            redirection = redirect(command)
            if not redirection:
                return
        if '|' in command:  # pipe needed
            pipe(command)
        else:
            run(command)

    else:  # is parent
        if wait:
            pid, status_code = os.waitpid(pid, 0)
            
            if status_code != 0:
                print("Error has occurred. View line above for specifics.")
            
            if not os.WIFEXITED(status_code):
                print(f"Program terminated: exit code {status_code}.")
                sys.exit(1)

      
def shell():
    
    welcomeBanner()
    
    # Check if a filename is provided, batch mode
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        try:
            with open(filename, 'r') as file:
                for line in file:
                    line = line.strip()
                    # Skip comment lines
                    if line.startswith('#'):
                        continue
                    process_line(line)
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found.")
            sys.exit(1)
    else:
        # Otherwise, proceed with console mode
        while True:
            command = input('$ ')
            process_line(command)
                
            
if __name__ == "__main__":
    shell() #runs shell