import os
import time

PFS_FILENAME = "private.pfs"

# Ensure private.pfs exists
if not os.path.exists(PFS_FILENAME):
    with open(PFS_FILENAME, 'w') as f:
        pass

def write_file(filename, content):
    """Write a file to the supplementary file system."""
    timestamp = int(time.time())
    record = f"F|{filename}|{len(content)}|{timestamp}|{content}\n"
    with open(PFS_FILENAME, 'a') as f:
        f.write(record)

def read_file(filename):
    """Read a file from the supplementary file system."""
    with open(PFS_FILENAME, 'r') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) < 5:
                continue
            if parts[0] == 'F' and parts[1] == filename:
                return {
                    'filename': parts[1],
                    'size': int(parts[2]),
                    'timestamp': int(parts[3]),
                    'content': parts[4]
                }
    return None

def show_file(filename):
    """Display the contents of a supplementary file."""
    file_data = read_file(filename)
    if file_data:
        print(file_data['content'])
    else:
        print(f"Error: File '{filename}' not found.")

def list_files_in_dir(directory):
    """List files in a directory with timestamps."""
    found = False
    with open(PFS_FILENAME, 'r') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) < 5:
                continue
            if parts[0] == 'F' and (parts[1].startswith(directory + '/') or parts[1] == directory):  # Match files inside or matching the filename
                found = True
                print(f"{parts[1]} - Last modified: {time.ctime(int(parts[3]))}")
    if not found:
        print(f"Error: No files found in directory or matching filename '{directory}'.")


def merge_files(src1, src2, dest):
    """Merge two supplementary files into a new file."""

    # Check if src1 and src2 are PFS files, and handle accordingly
    if src1.startswith('+'):
        file1 = read_file(src1[1:])  # Remove the '+' prefix for PFS file lookup
    else:
        file1 = None

    if src2.startswith('+'):
        file2 = read_file(src2[1:])  # Remove the '+' prefix for PFS file lookup
    else:
        file2 = None

    # If both are PFS files
    if file1 and file2:
        merged_content = file1['content'] + file2['content']
        write_file(dest, merged_content)
        print(f"Merged {src1} and {src2} into {dest}.")
    # If one is a real file
    elif file1 and not file2:
        with open(src2, 'r') as f:  # src2 is a real file
            content2 = f.read()
        merged_content = file1['content'] + content2
        write_file(dest, merged_content)
        print(f"Merged {src1} and {src2} into {dest}.")
    elif not file1 and file2:
        with open(src1, 'r') as f:  # src1 is a real file
            content1 = f.read()
        merged_content = content1 + file2['content']
        write_file(dest, merged_content)
        print(f"Merged {src1} and {src2} into {dest}.")
    else:
        print("Error: One or both source files not found.")


def remove_file(filename):
    """Remove a supplementary file from the system."""
    lines = []
    file_found = False

    with open(PFS_FILENAME, 'r') as f:
        lines = f.readlines()

    with open(PFS_FILENAME, 'w') as f:
        for line in lines:
            parts = line.strip().split('|')
            if len(parts) < 5:
                continue
            if parts[0] == 'F' and parts[1] == filename:
                file_found = True
            else:
                f.write(line)

    if file_found:
        print(f"File {filename} removed.")
    else:
        print(f"Error: File '{filename}' not found.")

def create_directory(directory):
    """Create a supplementary directory."""
    timestamp = int(time.time())
    record = f"D|{directory}|0|{timestamp}|\n"
    with open(PFS_FILENAME, 'a') as f:
        f.write(record)
    print(f"Directory {directory} created.")

def remove_directory(directory):
    """Remove a supplementary directory."""
    lines = []
    dir_found = False

    with open(PFS_FILENAME, 'r') as f:
        lines = f.readlines()

    with open(PFS_FILENAME, 'w') as f:
        for line in lines:
            parts = line.strip().split('|')
            if len(parts) < 5:
                continue
            if parts[0] == 'D' and parts[1] == directory:
                dir_found = True
            else:
                f.write(line)

    if dir_found:
        print(f"Directory {directory} removed.")
    else:
        print(f"Error: Directory '{directory}' not found.")

def shell_loop():
    """Main shell loop for interacting with the PFS."""
    while True:
        try:
            cmd = input("pfs> ").strip()
            if not cmd:
                continue
            if cmd == 'exit':
                break
            tokens = cmd.split()
            if tokens[0] == 'cp':
                src, dest = tokens[1], tokens[2]

                # Case 1: Real file to PFS
                if not src.startswith('+') and dest.startswith('+'):
                    dest = dest[1:]  # strip +
                    if not os.path.exists(src):
                        print(f"Error: Source file '{src}' not found.")
                        continue
                    with open(src, 'r') as f:
                        content = f.read()
                    write_file(dest, content)
                    print(f"Copied real file '{src}' to '+{dest}'.")

                # Case 2: PFS to PFS
                elif src.startswith('+') and dest.startswith('+'):
                    src = src[1:]
                    dest = dest[1:]
                    file_data = read_file(src)
                    if file_data:
                        write_file(dest, file_data['content'])
                        print(f"Copied '+{src}' to '+{dest}'.")
                    else:
                        print(f"Error: Source file '+{src}' not found.")

                # Case 3: PFS to real file
                elif src.startswith('+') and not dest.startswith('+'):
                    src = src[1:]
                    file_data = read_file(src)
                    if file_data:
                        with open(dest, 'w') as f:
                            f.write(file_data['content'])
                        print(f"Copied '+{src}' to '{dest}' (real file).")
                    else:
                        print(f"Error: Source file '+{src}' not found.")

                else:
                    print("Error: At least one of the files must be a PFS file (prefixed with '+').")

            elif tokens[0] == 'rm':
                filename = tokens[1][1:]  # strip +
                remove_file(filename)

            elif tokens[0] == 'mkdir':
                directory = tokens[1][1:]  # strip +
                create_directory(directory)

            elif tokens[0] == 'rmdir':
                directory = tokens[1][1:]  # strip +
                remove_directory(directory)

            elif tokens[0] == 'ls':
                if tokens[1].startswith('+'):
                    list_files_in_dir(tokens[1][1:])
                else:
                    print("Error: Only supplementary directories/files can be listed.")

            elif tokens[0] == 'merge':
                src1, src2, dest = tokens[1], tokens[2], tokens[3][1:]
                merge_files(src1, src2, dest)

            elif tokens[0] == 'show':
                if tokens[1].startswith('+'):
                    show_file(tokens[1][1:])
                else:
                    print("Error: Only supplementary files can be shown.")

            else:
                print("Error: Unknown command:", tokens[0])
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    shell_loop()
