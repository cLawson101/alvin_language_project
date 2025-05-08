"""
Aitiana L. Mondragon & Giovanna P. Carballido
CS 4375 - CRN: 23426
Dr. Ward
May 5, 2025
Assignment: Supplementary File System - File System
"""

import time
import os

PFS_FILE = "private.pfs"
DELIMITER = "|"

# Load metadata into memory from private.pfs
def load_metadata():
    if not os.path.exists(PFS_FILE):
        return []

    metadata = []
    with open(PFS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        parts = line.split(DELIMITER)

        # Only process valid metadata lines
        if len(parts) == 6 and parts[0] in ("f", "d"):
            try:
                entry = {
                    "type": parts[0].strip(),
                    "name": parts[1].strip(),
                    "folder": parts[2].strip(),
                    "offset": int(parts[3]),
                    "size": int(parts[4]),
                    "timestamp": float(parts[5])
                }
                metadata.append(entry)
                # Skip content line only for files
                if entry["type"] == "f":
                    i += 2
                else:  # entry["type"] == "d"
                    i += 1
            except ValueError:
                i += 1  # corrupted metadata, skip
        else:
            i += 1  # skip content or corrupted lines

    return metadata

# Write new metadata + content to private.pfs (FIXED OFFSET)
def write_entry(entry_type, name, folder, content=""):
    with open(PFS_FILE, "a+", encoding="utf-8") as f:
        f.seek(0, os.SEEK_END)
        content_start = f.tell() + 101  # metadata (100) + newline
        size = len(content.encode("utf-8"))
        timestamp = time.time()
        metadata_line = f"{entry_type}|{name}|{folder}|{content_start}|{size}|{timestamp}"
        metadata_line = metadata_line.ljust(100)

        # Write metadata + newline
        f.write(metadata_line + "\n")
        # Write content
        if entry_type == 'f':
            f.write(content + "\n")
    
# function to update offsets after rm or rmdir
def update_offset():
    # Load the metadata
    metadata = load_metadata()

    # Open the file for reading and writing (without rewriting everything)
    with open(PFS_FILE, "r+", encoding="utf-8") as f:
        # Read all lines into memory
        lines = f.readlines()

        # Starting point for the offset
        new_offset = 101  # After metadata header (100 bytes)

        # Iterate through the lines that contain metadata
        i = 0
        while i < len(lines):
            metadata_line = lines[i]
            parts = metadata_line.split(DELIMITER)

            if len(parts) >= 6:
                entry_type = parts[0].strip()
                name = parts[1].strip()
                folder = parts[2].strip()
                size = int(parts[4].strip())
                timestamp = float(parts[5].strip())

                # Update the offset in the metadata (modify it directly)
                new_metadata_line = f"{entry_type}|{name}|{folder}|{new_offset}|{size}|{timestamp}"
                new_metadata_line = new_metadata_line.ljust(100)

                # Replace the old metadata line with the new one
                lines[i] = new_metadata_line + "\n"

                # Move the offset forward (content size + newline)
                new_offset += size + 100  # 100 for each new line
                if entry_type =='f':
                    new_offset +=2 #considering content
                    
                elif entry_type == 'd':
                    new_offset +=1 #not considering content

                # Skip the content line for files (only files have content)
                if entry_type == "f":
                    i += 1  # Skip the content line for files

            # Move to the next entry
            i += 1

        # Go back to the beginning of the file and update the modified lines
        f.seek(0)
        f.writelines(lines)






# cp: Copy file into supplemental FS
def cp(src, dest):
    # Load metadata into memory
    metadata = load_metadata()
    new_content = ""

    # Handle the case where src is a supplemental file
    if src.startswith("+"):
        src_name = src[1:]
        found = False
        for entry in metadata:
            if entry["name"] == src_name:
                # Read the content of the existing supplemental file
                with open(PFS_FILE, "r", encoding="utf-8") as f:
                    f.seek(entry["offset"])
                    new_content = f.read(entry["size"])
                found = True
                break
        
        if not found:
            print(f"Supplemental source file {src} not found.")
            return

    # Handle the case where src is a regular file (not supplemental)
    else:
        try:
            with open(src, "r", encoding="utf-8") as s:
                new_content = s.read().strip()
        except Exception as e:
            print(f"Error reading source file: {e}")
            return

    # Handle the case where the destination is a supplemental file
    if dest.startswith("+"):
        dest_name = dest[1:]
        folder = "/"
        
        if "/" in dest_name:
            folder, dest_name = dest_name.rsplit("/", 1)
            folder = "/" + folder.split("+")[-1]
        
        # Search for the file in metadata to check if it already exists
        for entry in metadata:
            if entry["name"] == dest_name and entry["folder"] == folder:
                # Remove the existing file by skipping its metadata and content

                # Find and remove its old content from the file
                new_lines = []
                with open(PFS_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                i = 0
                while i < len(lines):
                    parts = lines[i].split(DELIMITER)
                    if len(parts) >= 6:
                        entry_name = parts[1].strip()
                        entry_folder = parts[2].strip()
                        if entry_name == dest_name and entry_folder == folder:
                            # Skip over the metadata line
                            i += 1
                            entry_size = int(parts[4].strip())
                            char_count = 0
                            while i < len(lines) and char_count < entry_size: #skpping over lines with content larger than one line
                                char_count += len(lines[i])
                                i += 1
                            continue
                    new_lines.append(lines[i])
                    i += 1

                # Rewrite the file without the old content
                with open(PFS_FILE, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                
                # Recalculate offsets after removal
                update_offset()

                # Now write the new content at the same location
                write_entry("f", dest_name, folder, new_content)
                return
        
        # If the file doesn't exist, create a new one
        write_entry("f", dest_name, folder, new_content)
    
    else:
        print("Destination must be a supplemental file (start with '+')")


# show: Display content of a supplemental file
def show(file):
    metadata = load_metadata()
    path = file[1:]

    if "/" in path:
        folder, name = path.rsplit("/", 1)
        folder = "/" + folder
    else:
        name = path
        folder = "/"

    for entry in metadata:
        if entry["name"] == name and entry["folder"] == folder:
            with open(PFS_FILE, "rb") as f:  # OPEN IN BINARY
                f.seek(entry["offset"])
                raw = f.read(entry["size"])
                try:
                    content = raw.decode("utf-8")
                    print(content.strip())
                except UnicodeDecodeError as e:
                    print(f"(Decode error: {e})")
                return
    print("File not found.")



# rm: Remove a supplemental file entry
def rm(file):
    path = file[1:]
    if "/" in path:
        folder, name = path.rsplit("/", 1)
        folder = "/" + folder
    else:
        name = path
        folder = "/"

    metadata = load_metadata()
    new_lines = []
    found = False
    with open(PFS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        if DELIMITER in lines[i]:
            parts = lines[i].split(DELIMITER)
            if len(parts) >= 3:
                entry_name = parts[1].strip()
                entry_folder = parts[2].strip()
                if entry_name == name and entry_folder == folder:
                    found = True
                    i +=1 #skipping metadata line
                    
                    #figuring out the lines to skip of the content section
                    entry_size = int(parts[4].strip())
                    char_count = 0
                    while i < len(lines) and char_count < entry_size:
                        char_count += len(lines[i])
                        i+=1
                        
                                            
                    continue
        new_lines.append(lines[i])
        i += 1

    with open(PFS_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    if found == True:
        update_offset()
        print(f"{file} removed.")
    else:
        print(f"{file} does not exist and was not removed. Check notation.")


# mkdir: Create a new directory
def mkdir(dir):
    dir_name = dir[1:]
    write_entry("d", dir_name, "/", "")

# rmdir: Remove directory if empty
def rmdir(dir):
    dir_name = dir[1:]
    metadata = load_metadata()
    for entry in metadata:
        if entry["folder"] == "/" + dir_name:
            print("Directory not empty.")
            return
    new_lines = []
    found = False
    with open(PFS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        if DELIMITER in lines[i]:
            name = lines[i].split(DELIMITER)[1].strip()
            t = lines[i].split(DELIMITER)[0].strip()
            if t == "d" and name == dir_name:
                found = True
                i += 2
                continue
        new_lines.append(lines[i])
        i += 1
    with open(PFS_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    if found == True:
        update_offset()
        print(f"{dir_name} removed.")
    else:
        print(f"{dir_name} does not exist and was not removed. Check notation.")

# ls: List a file or directory contents
def ls(path):
    path = path[1:]
    metadata = load_metadata()

    if "/" in path:
        folder, name = path.rsplit("/", 1)
        folder = "/" + folder
    else:
        name = path
        folder = "/"

    for entry in metadata:
        if entry["name"] == name and entry["folder"] == folder and entry["type"] == "f":
            print(f"{entry['name']} (Last modified: {time.ctime(entry['timestamp'])})")
            return
        elif entry["type"] == "d" and entry["name"] == name:
            print(f"Contents of /{entry['name']}:")
            for e in metadata:
                if e["folder"] == "/" + entry["name"]:
                    print(f"- {e['name']} (Last modified: {time.ctime(e['timestamp'])})")
            return
    print("Path not found.")


# merge: Combine two files and save as a third
def merge(file1, file2, newfile):
    metadata = load_metadata()

    def get_content(path, is_supplementary):
        """Get content from either regular or supplementary file."""
        if is_supplementary:
            # Handle supplementary file (starts with '+')
            path = path[1:]  # Remove leading '+' for supplementary files
            if "/" in path:
                folder, name = path.rsplit("/", 1)
                folder = "/" + folder
            else:
                name = path
                folder = "/"

            # Find the file in the metadata
            for entry in metadata:
                if entry["name"] == name and entry["folder"] == folder:
                    with open(PFS_FILE, "rb") as f:
                        f.seek(entry["offset"])  # Seek to the content position
                        data = f.read(entry["size"])  # Read the content
                        return data.decode("utf-8")  # Return as string
            return ""  # Return empty if supplementary file not found
        else:
            # Handle regular file (does not start with '+')
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()  # Read from regular file
            except FileNotFoundError:
                print(f"Error reading regular file: {path}")
                return ""  # Return empty if file not found

    # Determine whether each file is supplementary or regular
    is_file1_supplementary = file1.startswith("+")
    is_file2_supplementary = file2.startswith("+")
    
    # Handle the different cases
    if is_file1_supplementary and is_file2_supplementary:
        # Both files are supplementary
        content1 = get_content(file1, True)
        content2 = get_content(file2, True)
        merged_content = content1 + content2
    elif is_file1_supplementary or is_file2_supplementary:
        # One file is supplementary, the other is regular
        content1 = get_content(file1, is_file1_supplementary)
        content2 = get_content(file2, is_file2_supplementary)
        merged_content = content1 + content2
    else:
        print("Error: At least one file must be a supplementary file (start with '+').")
        return

    # Write the merged content to the new supplementary file
    if newfile.startswith("+"):
        new_path = newfile[1:]  # Remove leading '+' for new file
        if "/" in new_path:
            folder, name = new_path.rsplit("/", 1)
            folder = "/" + folder  # Ensure folder structure starts with "/"
        else:
            name = new_path
            folder = "/"

        # Call your function to write the merged content into the new file
        write_entry("f", name, folder, merged_content)
        print(f"File {newfile} created with merged content.")
    else:
        print("Destination must be a supplemental file (start with '+').")

