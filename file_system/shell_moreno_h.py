#!/usr/bin/env python3
import os
import sys
import re
import time

def executable_path(command):
    paths = os.environ.get("PATH", "").split(":")
    for path in paths:
        executable = os.path.join(path, command)
        if os.path.exists(executable):
            if os.access(executable, os.X_OK):  # Check if file is executable
                return executable
            else:
                print(f"{command}: not executable")
                return None
    return None

def execute_command(command, task=False):
    if not command:
        return
    
    # Handle 'inspiration' command
    if command[0] == "inspiration" and len(command) < 2:
        phrase = os.environ.get('phrase', 'Stay positive, work hard, make it happen!')
        print(phrase)
        return
    
    # Handle 'quit' command
    if command[0] == "quit" and len(command) < 2:
        sys.exit(0)

    # Handle change directory (cd)
    if command[0] == "cd":
        if len(command) < 2:
            home = os.environ.get("~", "/")  # Home directory
            os.chdir(home)
        else:
            try:
                os.chdir(command[1])
            except FileNotFoundError:
                print(f"Directory '{command[1]}' not found.")
            except PermissionError:
                print(f"Permission denied, cannot access '{command[1]}'.")
            except NotADirectoryError:
                print(f"Not a directory: '{command[1]}'.")
        return

    input_file = None
    output_file = None

    # Handle output redirection (>)
    if ">" in command:
        idx = command.index(">")
        if idx + 1 >= len(command):
            print("No output file")
            return
        output_file = command[idx + 1]
        command = command[:idx]

    # Handle input redirection (<)
    if "<" in command:
        idx = command.index("<")
        if idx + 1 >= len(command):
            print("No input file")
            return
        input_file = command[idx + 1]
        command = command[:idx]

    # Handle background tasks (&)
    if "&" in command:
        background_commands = [cmd.strip() for cmd in " ".join(command).split('&') if cmd.strip()]
        for cmd in background_commands:
            execute_command(cmd.split(), task=True)
        return

    # Handle supplemental file system
    
    # Handle cp
    if command[0] == "cp":
        if len(command) != 3:
            print("Usage: cp source dest")
            return

        src = command[1]
        dest = command[2]

        # Read content from source
        if is_supplemental(src):
            offset = locate_entry_in_pfs(src)
            if offset is None:
                print(f"{src} does not exist in private.pfs")
                return

            with open("private.pfs", "rb") as pfs:
                pfs.seek(offset)

                # Read header up to 4th pipe
                header_bytes = bytearray()
                pipe_count = 0
                while pipe_count < 4:
                    byte = pfs.read(1)
                    if not byte:
                        break
                    header_bytes.extend(byte)
                    if byte == b'|':
                        pipe_count += 1

                header_str = header_bytes.decode("utf-8")
                if not header_str.startswith("F|"):
                    print("Only files can be copied")
                    return

                parts = header_str.rstrip("|").split("|")
                if len(parts) < 4:
                    print("Malformed file entry")
                    return

                size = int(parts[2])
                content_bytes = pfs.read(size)
                content = content_bytes.decode("utf-8")
        else:
            try:
                with open(src, "r") as f:
                    content = f.read()
            except FileNotFoundError:
                print(f"{src} not found")
                return

        # Ensure destination is supplemental
        if not is_supplemental(dest):
            try:
                with open(dest, "w") as f:
                    f.write(content)
            except Exception as e:
                print(f"Failed to write to {dest}: {e}")
            return
        
        if locate_entry_in_pfs(dest) != None:
            execute_command(['rm', f'{dest}'])

        # Handle directory info
        if "/" in dest:
            dir_name, file_name_only = dest[1:].split("/", 1)
            dir_name = "+" + dir_name
        else:
            dir_name = None
            file_name_only = dest[1:]

        # Validate destination directory exists if specified
        if "/" in dest:
            dir_name, file_name_only = dest[1:].split("/", 1)
            dir_name = "+" + dir_name

            # Check if directory exists
            dir_offset = locate_entry_in_pfs(dir_name)
            if dir_offset is None:
                print(f"Directory {dir_name} does not exist in private.pfs")
                return
        else:
            dir_name = None
            file_name_only = dest[1:]

        # Now safe to write
        new_file_name = dest
        now = get_timestamp()
        size = len(content)
        data_line = f"F|{new_file_name}|{size}|{now}|{content}\n"

        with open("private.pfs", "a+") as pfs:
            pfs.seek(0, os.SEEK_END)
            offset = pfs.tell()
            pfs.write(data_line)

        add_toc_entry(new_file_name, offset)
        rebuild_toc()

        # If part of a directory, update directory entry
        if dir_name:
            with open("private.pfs", "r+") as pfs:
                lines = pfs.readlines()
                try:
                    data_index = lines.index("--DATA--\n")
                except ValueError:
                    print("--DATA-- not found")
                    return

                toc_lines = lines[:data_index]
                data_lines = lines[data_index + 1:]

                updated = False
                new_data_lines = []
                for line in data_lines:
                    if line.startswith("D|") and line.split("|")[1] == dir_name:
                        updated = True
                        parts = line.strip().split("|")
                        files = [f for f in parts[3:] if f.strip()]
                        if file_name_only not in files:
                            files.append(file_name_only)
                        new_line = f"D|{parts[1]}|{parts[2]}|{'|'.join(files)}\n"
                        new_data_lines.append(new_line)
                    else:
                        new_data_lines.append(line)

                if not updated:
                    print(f"Directory {dir_name} does not exist in private.pfs")
                    return

                with open("private.pfs", "w") as pfs:
                    pfs.writelines(toc_lines)
                    pfs.write("--DATA--\n")
                    pfs.writelines(new_data_lines)
        rebuild_toc()
        return


    # Handle rm
    if command[0] == "rm":
        if len(command) < 2:
            print("Usage: rm +filename or rm +dir/filename")
            return

        target = command[1]
        if not is_supplemental(target):
            print("Can only remove supplemental files")
            return

        # Parse path
        if "/" in target:
            dir_path, filename = target[1:].split("/", 1)
            entry_name = f"+{dir_path}/{filename}"
            dir_name = f"+{dir_path}"
        else:
            entry_name = target
            filename = target[1:]
            dir_name = None

        with open("private.pfs", "r") as pfs:
            lines = pfs.readlines()

        try:
            data_index = lines.index("--DATA--\n")
        except ValueError:
            print("--DATA-- marker not found.")
            return

        toc_lines = lines[:data_index]
        data_lines = lines[data_index + 1:]

        # Check if target is a directory (reject it)
        for line in data_lines:
            if line.startswith("D|") and line.split("|")[1] == entry_name:
                print("Cannot remove directory with rm; use rmdir instead.")
                return

        # Remove matching TOC entry
        new_toc = []
        found = False
        for line in toc_lines:
            if line.startswith("T|") and line.split("|")[1] == entry_name:
                found = True
                continue
            new_toc.append(line)

        # Remove matching DATA entry
        new_data = []
        i = 0
        while i < len(data_lines):
            line = data_lines[i]
            if line.startswith("F|") or line.startswith("D|"):
                parts = line.split("|", 4)
                if len(parts) < 4:
                    new_data.append(line)
                    i += 1
                    continue

                entry_type = parts[0]
                name = parts[1]

                if name == entry_name:
                    found = True
                    if entry_type == "F":
                        try:
                            size = int(parts[2])
                            header_len = len(parts[0]) + len(parts[1]) + len(parts[2]) + len(parts[3]) + 4  # plus 4 pipes
                            body = parts[4]

                            remaining_size = size - len(body.encode("utf-8"))
                            current_len = len(body.encode("utf-8"))
                            i += 1

                            while current_len < size and i < len(data_lines):
                                current_len += len(data_lines[i].encode("utf-8"))
                                i += 1
                        except Exception:
                            # If parsing fails, treat it as malformed and skip just this line
                            i += 1
                        continue
                    else:  # Directory (shouldn’t happen if check earlier passed)
                        i += 1
                        continue
                else:
                    new_data.append(line)
                    i += 1
            else:
                new_data.append(line)
                i += 1

        # If in a directory, remove file from directory listing
        if dir_name:
            updated_data = []
            for line in new_data:
                if line.startswith("D|") and line.split("|")[1] == dir_name:
                    parts = line.strip().split("|")
                    files = [f for f in parts[3:] if f != filename]
                    new_line = "|".join(parts[:3] + files) + "\n"
                    updated_data.append(new_line)
                else:
                    updated_data.append(line)
            new_data = updated_data

        # Write updated file and rebuild TOC
        with open("private.pfs", "w") as pfs:
            pfs.writelines(new_toc)
            pfs.write("--DATA--\n")
            pfs.writelines(new_data)
            pfs.truncate()

        rebuild_toc()
        rebuild_toc()
        return

    # Handle mkdir
    if command[0] == "mkdir":
        if not is_supplemental(command[1]):
            print("Must be a supplemental directory")
            return
        
        if locate_entry_in_pfs(command[1]) != None:
            print("directory already exists!")
            return

        timestamp = get_timestamp()
        dir_entry = f"D|{command[1]}|{timestamp}|\n"

        with open("private.pfs", "a+") as pfs:
            pfs.seek(0, os.SEEK_END)
            offset = pfs.tell()
            pfs.write(dir_entry)

        add_toc_entry(command[1], offset + 1)
        rebuild_toc()
        return

    # Hnadle rmdir
    if command[0] == "rmdir":
        if not is_supplemental(command[1]):
            print("Can only remove supplemental directories")
            return

        with open("private.pfs", "r") as pfs:
            lines = pfs.readlines()

        try:
            data_index = lines.index("--DATA--\n")
        except ValueError:
            print("--DATA-- marker not found.")
            return

        name = command[1]
        toc_lines = lines[:data_index]
        data_lines = lines[data_index + 1:]

        # Find and inspect the directory entry
        dir_found = False
        dir_has_files = False
        new_data = []

        for line in data_lines:
            if line.startswith("D|") and line.split("|")[1] == name:
                dir_found = True
                parts = line.strip().split("|")
                if len(parts) > 3 and any(p.strip() for p in parts[3:]):
                    dir_has_files = True
                    break  # no need to continue
            else:
                new_data.append(line)

        if not dir_found:
            print("Directory does not exist in private.pfs")
            return

        if dir_has_files:
            print("Directory is not empty")
            return

        # Remove TOC entry
        new_toc = []
        for line in toc_lines:
            if line.startswith("T|"):
                parts = line.strip().split("|")
                if parts[1] == name:
                    continue
            new_toc.append(line)

        # Rebuild file without the directory
        with open("private.pfs", "w") as pfs:
            pfs.writelines(new_toc)
            pfs.write("--DATA--\n")
            pfs.writelines(new_data)
        rebuild_toc()
        return
    
    # Handle ls
    if command[0] == "ls":
        if len(command) >= 2:
            if is_supplemental(command[1]):
                offset = locate_entry_in_pfs(command[1])
                if offset is None:
                    print(f"{command[1]} File or directory does not exist in private.pfs")
                    return

                with open("private.pfs", "r") as pfs:
                    pfs.seek(offset)
                    line = pfs.readline()

                    if line.startswith("F|"):
                        parts = line.split("|")
                        path = parts[1]  # Full path, like +mydir/file.txt
                        filename = f"{path.split("/")[-1]}"  # Just file.txt
                        print(f"{filename} {parts[3]}")
                    elif line.startswith("D|"):
                        entries = line.split("|")[3:]
                        for entry in entries:
                            entry = entry.strip()
                            if entry == '':
                                return
                            execute_command(['ls', f'{command[1]}/{entry}'])
                    else:
                        print("No file or directories found!")
                return
        else:
            executable = executable_path(command[0])

    # Handle merge
    if command[0] == "merge":
        if len(command) != 4:
            print("Usage: merge file1 file2 destination")
            return

        def read_file_content(path):
            if is_supplemental(path):
                offset = locate_entry_in_pfs(path)
                if offset is None:
                    print(f"{path} does not exist in private.pfs")
                    return None

                with open("private.pfs", "rb") as pfs:
                    pfs.seek(offset)

                    # Read header up to the 4th pipe to get size
                    header_bytes = bytearray()
                    pipe_count = 0
                    while pipe_count < 4:
                        byte = pfs.read(1)
                        if not byte:
                            break
                        header_bytes.extend(byte)
                        if byte == b'|':
                            pipe_count += 1

                    try:
                        header_str = header_bytes.decode("utf-8")
                        parts = header_str.rstrip("|").split("|")
                        if len(parts) < 4:
                            print(f"{path} header malformed")
                            return None
                        size = int(parts[2])
                    except Exception as e:
                        print(f"Failed to parse supplemental file header: {e}")
                        return None

                    content_bytes = pfs.read(size)
                    return content_bytes.decode("utf-8")
            else:
                try:
                    with open(path, "r") as f:
                        return f.read()
                except FileNotFoundError:
                    print(f"{path} not found")
                    return None

        content1 = read_file_content(command[1])
        content2 = read_file_content(command[2])

        if content1 is None or content2 is None:
            return

        # Merge with exactly one newline
        merged = content1.rstrip("\n") + "\n" + content2
        size = len(merged)
        timestamp = get_timestamp()
        dest = command[3]

        if is_supplemental(dest):

            if locate_entry_in_pfs(dest) != None:
                execute_command(['rm', f'{dest}'])

            # Validate supplemental directory if present
            if "/" in dest:
                dir_name, file_name_only = dest[1:].split("/", 1)
                dir_name = "+" + dir_name
                dir_offset = locate_entry_in_pfs(dir_name)
                if dir_offset is None:
                    print(f"Directory {dir_name} does not exist in private.pfs")
                    return
            else:
                file_name_only = dest[1:]
                dir_name = None

            with open("private.pfs", "a+b") as pfs:
                pfs.seek(0, os.SEEK_END)
                data_offset = pfs.tell()
                header = f"F|{dest}|{size}|{timestamp}|".encode("utf-8")
                pfs.write(header + merged.encode("utf-8") + b"\n")

            add_toc_entry(dest, data_offset)
            rebuild_toc()

            # If it's inside a supplemental directory, update that directory
            if dir_name:
                with open("private.pfs", "r+") as pfs:
                    lines = pfs.readlines()
                    try:
                        data_index = lines.index("--DATA--\n")
                    except ValueError:
                        print("--DATA-- not found")
                        return

                    toc_lines = lines[:data_index]
                    data_lines = lines[data_index + 1:]

                    updated = False
                    new_data_lines = []
                    for line in data_lines:
                        if line.startswith("D|") and line.split("|")[1] == dir_name:
                            updated = True
                            parts = line.strip().split("|")
                            files = [f for f in parts[3:] if f.strip()]
                            if file_name_only not in files:
                                files.append(file_name_only)
                            new_line = f"D|{parts[1]}|{parts[2]}|{'|'.join(files)}\n"
                            new_data_lines.append(new_line)
                        else:
                            new_data_lines.append(line)

                    if not updated:
                        print(f"Directory {dir_name} not found")
                        return

                    with open("private.pfs", "w") as pfs:
                        pfs.writelines(toc_lines)
                        pfs.write("--DATA--\n")
                        pfs.writelines(new_data_lines)

            rebuild_toc()
        else:
            try:
                with open(dest, "w") as f:
                    f.write(merged)
            except Exception as e:
                print(f"Failed to write to {dest}: {e}")
        return
    
    # Handle show
    if command[0] == "show":
        if len(command) < 2:
            print("No file given.")
            return

        if is_supplemental(command[1]):
            # new show for supplemental files:
            offset = locate_entry_in_pfs(command[1])
            if offset is None:
                print("File does not exist in private.pfs")
                return

            with open("private.pfs", "rb") as pfs:
                # jump to the start of this record
                pfs.seek(offset)

                # read up to the 4th '|' so we can pull out the size field
                header_bytes = bytearray()
                pipes = 0
                while pipes < 4:
                    b = pfs.read(1)
                    if not b:
                        break
                    header_bytes.extend(b)
                    if b == b'|':
                        pipes += 1

                header = header_bytes.decode("utf-8")
                # header looks like "F|+merged/...|123|2025-05-02 19:00:00|"
                _, name, size_str, timestamp = header.rstrip("|").split("|")
                size = int(size_str)

                # now read exactly size bytes of content (includes internal newlines)
                content_bytes = pfs.read(size)
                content = content_bytes.decode("utf-8")

                print(content)
                return
        else:
            print("No file in supplementary file system given")
            return


        #------ for testing offset with show command -------#
        # if is_supplemental(command[1]):
        #     offset = locate_entry_in_pfs(command[1])
        #     if offset is None:
        #         print("File does not exist in private.pfs")
        #         return

        #     with open("private.pfs", "r") as pfs:
        #         pfs.seek(offset)
        #         content = pfs.read()
        #         print(content)
        #         return

    
    # Otherwise, execute the command normally
    executable = executable_path(command[0])
    if executable is None:
        print(f"command not found: {command[0:]}") 
        return
    
    pid = os.fork()

    if pid == 0:  # Child process
        try:
            # Redirect input
            if input_file:
                fd = os.open(input_file, os.O_RDONLY)
                os.dup2(fd, 0)
                os.close(fd)
            # Redirect output
            if output_file:
                fd = os.open(output_file, os.O_WRONLY | os.O_CREAT)
                os.dup2(fd, 1)  # stdout
                os.dup2(fd, 2)  # stderr
                os.close(fd)

            os.execv(executable, [executable] + command[1:])
        except Exception as e:
            print(f"Execution failed: {e}")
            sys.exit(1)
    else:
        if task:
            print(f'task[]')
        else:
            pid, status = os.wait()  # Parent waits for the child to finish
            exit_code = status >> 8  # to get exit code.
            if status != 0:
                print(f"Program terminated: exit code {exit_code}.")


def use_file(command_file):
    try:
        with open(command_file, "r") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                print(f"\033[34mMyDevice {os.getcwd()}\033[0m")
                print(line)
                commands = line.split()
                if "|" in commands:
                    # handles pipe (|)
                    piped_commands(commands)
                else:
                    execute_command(commands)
    except FileNotFoundError:
        print(f"File '{command_file}' not found.")

def piped_commands(commands):
    commands = [cmd.strip() for cmd in " ".join(commands).split('|')]
    num_commands = len(commands)

    # Create pipes for each pair of consecutive commands
    pipes = []
    for i in range(num_commands - 1):
        r, w = os.pipe()  # Create a pipe
        pipes.append((r, w))

    for i, cmd in enumerate(commands):
        # Split and check for redirection inside each command
        cmd_parts = cmd.split()
        input_file = None
        output_file = None

        # Handle output redirection (>)
        if ">" in cmd_parts:
            idx = cmd_parts.index(">")
            if idx + 1 >= len(cmd_parts):
                print("No output file")
                return
            output_file = cmd_parts[idx + 1]
            cmd_parts = cmd_parts[:idx]

        # Handle input redirection (<)
        if "<" in cmd_parts:
            idx = cmd_parts.index("<")
            if idx + 1 >= len(cmd_parts):
                print("No input file")
                return
            input_file = cmd_parts[idx + 1]
            cmd_parts = cmd_parts[:idx]

        pid = os.fork()

        if pid == 0:  # Child process
            # Setup input redirection if it's not the first command
            if i > 0:
                os.dup2(pipes[i - 1][0], 0)  # Read from the previous pipe's read end

            # Setup output redirection if it's not the last command
            if i < num_commands - 1:
                os.dup2(pipes[i][1], 1)  # Write to the current pipe's write end

            # Apply input redirection if specified
            if input_file:
                fd = os.open(input_file, os.O_RDONLY)
                os.dup2(fd, 0)
                os.close(fd)

            # Apply output redirection if specified
            if output_file:
                fd = os.open(output_file, os.O_WRONLY | os.O_CREAT)
                os.dup2(fd, 1)  # stdout
                os.dup2(fd, 2)  # stderr
                os.close(fd)

            # Close all pipes in the child process
            for r, w in pipes:
                os.close(r)
                os.close(w)

            executable = executable_path(cmd_parts[0])
            if executable is None:
                print(f"command not found: {cmd_parts[0]}")
                sys.exit(1)

            os.execv(executable, [executable] + cmd_parts[1:])
        else:
            continue

    # Parent process: Close all pipes and wait for the last child
    for r, w in pipes:
        os.close(r)
        os.close(w)

    os.wait()  # Wait for the last command to finish


#----Supplemental file system helper functions below----#

# Helper function to check if a file is supplemental
def is_supplemental(path):
    return path.startswith('+')

# Function to split a path into directory and filename
def split_path(path):
    parts = path.split('/')
    dirname = '/'.join(parts[:-1]) if len(parts) > 1 else ''
    filename = parts[-1]
    return (dirname, filename)

# Function to locate an entry in the private.pfs by name (returns offset or None)
def locate_entry_in_pfs(name):
    with open("private.pfs", "r") as pfs:
        pfs.seek(0)
        while True:
            line = pfs.readline()
            if not line:
                break
            line = line.strip()
            if line == '--DATA--':
                break
            parts = line.split('|')
            if len(parts) >= 3 and parts[0] == 'T':
                entry_name = parts[1].strip()
                entry_offset = int(parts[2].strip(';'))
                if entry_name == name:
                    return entry_offset
    return None

# Function to add an entry to the TOC (Table of Contents) in private.pfs
def add_toc_entry(full_path, offset):
    with open("private.pfs", "r+") as pfs:
        lines = pfs.readlines()
        data_index = None

        for i, line in enumerate(lines):
            if line.strip() == "--DATA--":
                data_index = i
                break

        if data_index is None:
            print("Error: --DATA-- marker not found in private.pfs.")
            return

        new_entry = f"T|{full_path}|{offset};\n"
        lines.insert(data_index, new_entry)

        pfs.seek(0)
        pfs.writelines(lines)
        pfs.truncate()


def rebuild_toc():
    with open("private.pfs", "r+") as pfs:
        lines = pfs.readlines()

        # Find where --DATA-- is
        try:
            data_index = lines.index("--DATA--\n")
        except ValueError:
            raise ValueError("--DATA-- not found")

        # Slice file into parts
        toc_lines = lines[:data_index]
        data_lines = lines[data_index + 1:]

        # Build a map of name -> data line index in data_lines
        data_offsets = {}
        byte_offset = sum(len(line.encode('utf-8')) for line in toc_lines) + len("--DATA--\n")

        for line in data_lines:
            if line.startswith("F|") or line.startswith("D|"):
                parts = line.split("|")
                name = parts[1]
                data_offsets[name] = byte_offset
            byte_offset += len(line.encode('utf-8'))

        # Rebuild TOC with correct offsets
        new_toc = []
        for line in toc_lines:
            if line.startswith("T|"):
                parts = line.strip().split("|")
                name = parts[1]
                offset = data_offsets.get(name, 0)
                new_toc.append(f"T|{name}|{offset};\n")
            else:
                new_toc.append(line)  # Preserve any non-TOC lines

        # Rewrite file
        with open("private.pfs", "w") as out:
            out.writelines(new_toc)
            out.write("--DATA--\n")
            out.writelines(data_lines)




# Function to get the current timestamp
def get_timestamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def main():

    # Ensure private.pfs exists
    if not os.path.exists("private.pfs"):
        with open("private.pfs", "w") as f:
            f.write("--DATA--\n")  # Initialize with TOC marker

    if len(sys.argv) > 1:
        use_file(sys.argv[1])
        return

    while True:
        try:
            print(f"\033[34mMyDevice {os.getcwd()}\033[0m")  # changed color to blue for simplicity in terminal.
            user_command = input("$ ").strip()
            if user_command:
                # Split command based on whitespace
                commands = re.split(r'\s+', user_command)

                if "|" in commands:
                    # handles pipe (|)
                    piped_commands(commands)
                else:
                    execute_command(commands)  # Just pass the parsed command to execute_command
        except Exception as e:
            print('Error while executing command(s)')

            
if __name__ == "__main__":
    main()