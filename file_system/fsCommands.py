import os
import time

PFS_FILENAME = "private.pfs"

#generates current timestamp
def get_timestamp():
    return time.strftime("%Y%m%dT%H%M")

#mark a record as deleted
def mark_as_deleted(offset):
    with open(PFS_FILENAME, "r+b") as f:
        f.seek(offset)
        f.write(b"X")

# read all valid records (ignoring deleted entries marked 'X')
def read_all_records():
    records = []
    with open(PFS_FILENAME, "r") as f:
        for offset, line in enumerate(f):
            if not line.startswith("X"):
                records.append((offset, line.strip()))
    return records

# cp command 
def fs_cp(source, destination):
    """
    Copy from a normal or supplemental file to supplemental FS stored in private.pfs 
    """
    content = ''
    if source.startswith("+"): #find in private.pfs
        source = source[1:] #skip +
        found = False 
        with open(PFS_FILENAME, "r") as fs:
            for line in fs:
                if line.startswith("F|") and not line.startswith("X|"): #file is not deleted 
                    parts = line.strip().split("|") #strip removes \n,\r,\t split splits string into a list after '|'
                    if parts[1] == source: #file name match
                        content = parts[-1] #update content 
                        found = True
                        break 
        #error message 
        if not found:
            print(f"cp error: supplemental file '{source}' not found.")
            return 
    else: #not a supplemental file 
        try:
            with open(source, "r") as normalFile:
                content = normalFile.read().strip() #grab every word or char or symbol that is not \n,\r,\t
        except FileNotFoundError:
            print(f"cp error: Normal file '{source}' not found.")
            return

    #create new supplemental file record if it doesnt exist as a supplement file or normal file 
    record = f"F|{destination[1:]}|{get_timestamp()}|{len(content)}|{content}\n" 

    #open private.psf in append mode 
    with open(PFS_FILENAME, "a") as fs:
        #adds record line to the end of the file 
        fs.write(record)
        
    #success message 
    print(f"cp: copied to {destination}")
 
# Command: show
def fs_show(file):
    """
    Display the content of a supplemental file
    """
    #skip + if it starts with +, else keep file name as is 
    file = file[1:] if file.startswith("+") else file 
    with open(PFS_FILENAME, "r") as fs:
        for line in fs: 
            if line.startswith("F|") and not line.startswith("X|"):
                parts = line.strip().split("|")
                if parts[1] ==  file: #file name match 
                    print(parts[-1]) #display content 
                    return 
    #error message 
    print(f"show error: File '{file}' not found.")

# Command: merge
def fs_merge(file1, file2, destination):
    """
    Merges the content of two files (supplemental or normal) into a new supplemental file.
    Adds a newline between the two contents only if the first does not end with one.
    """
    def read_file(name):
        # Strip '+' and check source
        if name.startswith("+"):
            name = name[1:]
            with open(PFS_FILENAME, "r") as f:
                for line in f:
                    if line.startswith("F|") and not line.startswith("X|"):
                        parts = line.strip().split("|")
                        if parts[1] == name:
                            return parts[-1]
            return None
        else:
            try:
                with open(name, "r") as f:
                    return f.read().strip()
            except FileNotFoundError:
                return None

    content1 = read_file(file1)
    content2 = read_file(file2)

    if not content1 or not content2:
        print("merge error: one or both files not found.")
        return
    
    merged = content1.rstrip() + "\n" + content2
    record = f"F|{destination[1:]}|{get_timestamp()}|{len(merged)}|{merged}\n"
    with open(PFS_FILENAME, "a") as f:
        f.write(record)
    print(f"merge: created {destination} with merged content")


# Command: rm
def fs_rm(file):
    """
    Soft deletes a supplemental file by marking its record with X (instead of F).
    """
    name = file[1:] if file.startswith("+") else file

    with open(PFS_FILENAME, "r") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if line.startswith("X|"):
            continue
        parts = line.strip().split("|")
        if parts[0] == "F" and parts[1] == name:
            offset = sum(len(l.encode()) for l in lines[:i])
            mark_as_deleted(offset)
            print(f"rm: deleted {name}")
            return

    print(f"rm error: File '{file}' not found.")


def fs_mkdir(directory_name):
    """
    Creates a directory record in private.pfs (D|dirname|...).
    """
    dirname = directory_name[1:] if directory_name.startswith("+") else directory_name
    with open(PFS_FILENAME, "r") as fs:
        for line in fs:
            if line.startswith("D|") and not line.startswith("X|"):
                parts = line.strip().split("|")
                if parts[1] == dirname:
                    print(f"mkdir error: directory '{dirname}' already exists.")
                    return
    record = f"D|{dirname}|{get_timestamp()}|\n"
    with open(PFS_FILENAME, "a") as fs:
        fs.write(record)
    print(f"mkdir: created directory {directory_name}")

def fs_rmdir(directory_name):
    """
    Deletes a directory only if it's empty (no files prefixed with dirname/).
    """
    name = directory_name[1:] if directory_name.startswith("+") else directory_name

    with open(PFS_FILENAME, "r") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if line.startswith("X|"):
            continue
        parts = line.strip().split("|")
        if parts[0] == "D" and parts[1] == name:
            for l in lines:
                if l.startswith("X|"):
                    continue
                p = l.strip().split("|")
                if p[0] == "F" and p[1].startswith(name + "/"):
                    print(f"rmdir error: Directory '{name}' is not empty.")
                    return
            offset = sum(len(l.encode()) for l in lines[:i])
            mark_as_deleted(offset)
            print(f"rmdir: removed directory {directory_name}")
            return

    print(f"rmdir error: Directory '{directory_name}' not found.")

def fs_ls(target):
    """
    Lists metadata if the target is a file, or child entries if the target is a directory.
    Uses prefix matching to discover directory contents.
    """
    name = target[1:] if target.startswith("+") else target
    output = []

    with open(PFS_FILENAME, "r") as f:
        lines = f.readlines()

    found = False
    is_dir = False

    for line in lines:
        if line.startswith("X|"):
            continue
        parts = line.strip().split("|")
        if parts[0] == "D" and parts[1] == name:
            found = True
            is_dir = True
            break
        elif parts[0] == "F" and parts[1] == name:
            found = True
            output.append(f"{parts[1]} - Last Modified: {parts[2]}")
            break

    if is_dir:
        # now find all files in that directory
        for line in lines:
            if line.startswith("X|"):
                continue
            parts = line.strip().split("|")
            if parts[0] == "F" and parts[1].startswith(name + "/"):
                output.append(parts[1])

    if output:
        print("\n".join(output))
    elif found:
        # empty directory
        return
    else:
        print(f"ls error: target '{target}' not found.")
