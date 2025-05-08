import os
import struct

PFS_FILE = "private.pfs"
ENTRY_SIZE = 256
MAX_ENTRIES = 1024

def ensure_pfs_exists(): #this makes sure that the pfs exists or make it
    if not os.path.exists(PFS_FILE):
        with open(PFS_FILE, "wb") as f:
            f.write(b"\x00" * ENTRY_SIZE * MAX_ENTRIES)

def find_pfs_entry(name): #find a file or directory using its name
    with open(PFS_FILE, "rb") as f:
        for i in range(MAX_ENTRIES):
            entry = f.read(ENTRY_SIZE)
            if entry.strip(b"\x00") == b"":
                continue
            entry_name = entry[:128].rstrip(b"\x00").decode()
            if entry_name == name:
                is_dir = struct.unpack("B", entry[128:129])[0]
                size = struct.unpack("I", entry[129:133])[0]
                offset = struct.unpack("Q", entry[133:141])[0]
                return {"index": i, "name": entry_name, "is_dir": is_dir, "size": size, "offset": offset} #return its data
    return None

def write_pfs_entry(name, is_dir, size, offset): #make new file or dir
    name_bytes = name.encode().ljust(128, b"\x00")
    entry = name_bytes + struct.pack("B", is_dir) + struct.pack("I", size) + struct.pack("Q", offset)
    entry = entry.ljust(ENTRY_SIZE, b"\x00")
    with open(PFS_FILE, "rb+") as f:
        for i in range(MAX_ENTRIES): 
            f.seek(i * ENTRY_SIZE)
            e = f.read(ENTRY_SIZE)
            if e.strip(b"\x00") == b"":
                f.seek(i * ENTRY_SIZE)
                f.write(entry)
                return
        print("PFS directory full.")

def delete_pfs_entry(name): #zeros to delete
    with open(PFS_FILE, "rb+") as f:
        for i in range(MAX_ENTRIES):
            f.seek(i * ENTRY_SIZE)
            entry = f.read(ENTRY_SIZE)
            entry_name = entry[:128].rstrip(b"\x00").decode() #here
            if entry_name == name:
                f.seek(i * ENTRY_SIZE)
                f.write(b"\x00" * ENTRY_SIZE)
                return True
    return False

def list_pfs_entries(): #show everything
    with open(PFS_FILE, "rb") as f:
        for i in range(MAX_ENTRIES):
            entry = f.read(ENTRY_SIZE)
            if entry.strip(b"\x00") == b"":
                continue
            name = entry[:128].rstrip(b"\x00").decode()
            is_dir = struct.unpack("B", entry[128:129])[0]
            size = struct.unpack("I", entry[129:133])[0]
            print(f"{name} ({'DIR' if is_dir else f'{size} bytes'})")

def show_pfs_file(name): #Show 
    entry = find_pfs_entry(name)
    if not entry or entry["is_dir"]:
        print("File not found or is a directory.")
        return
    with open(PFS_FILE, "rb") as f:
        f.seek(entry["offset"])
        content = f.read(entry["size"])
        print(content.decode(errors="ignore"))

def pfs_cp(args): #copy
    if len(args) != 3:
        print("Usage: +cp <host_file> <+file>")
        return
    src, dest = args[1], args[2]
    if not os.path.isfile(src):
        print("Source file not found.")
        return
    with open(src, "rb") as f_src, open(PFS_FILE, "ab+") as f_pfs:
        content = f_src.read()
        f_pfs.seek(0, os.SEEK_END)
        offset = f_pfs.tell()
        f_pfs.write(content)
        write_pfs_entry(dest, is_dir=0, size=len(content), offset=offset)
        print(f"Copied '{src}' to PFS as '{dest}'.")

def pfs_rm(args): #remove
    if len(args) != 2:
        print("Usage: +rm <+file>")
        return
    name = args[1]
    entry = find_pfs_entry(name)
    if not entry or entry["is_dir"]:
        print("File not found or is a directory.")
        return
    delete_pfs_entry(name)
    print(f"Removed '{name}' from PFS.")

def pfs_mkdir(args): #new dir
    if len(args) != 2:
        print("Usage: +mkdir <+dir>")
        return
    name = args[1]
    if find_pfs_entry(name):
        print("Directory already exists.")
        return
    write_pfs_entry(name, is_dir=1, size=0, offset=0)
    print(f"Directory '{name}' created in PFS.")

def pfs_rmdir(args): #remove dir
    if len(args) != 2:
        print("Usage: +rmdir <+dir>")
        return
    name = args[1]
    entry = find_pfs_entry(name)
    if not entry or not entry["is_dir"]:
        print("Directory not found.")
        return
    # Make sure no files are inside the directory
    with open(PFS_FILE, "rb") as f:
        for i in range(MAX_ENTRIES):
            entry_raw = f.read(ENTRY_SIZE)
            if entry_raw.strip(b"\x00") == b"":
                continue
            ename = entry_raw[:128].rstrip(b"\x00").decode()
            if ename.startswith(name + "/"):
                print("Directory is not empty.")
                return
    delete_pfs_entry(name)
    print(f"Removed directory '{name}' from PFS.")

def pfs_merge(args): #combine
    if len(args) != 4:
        print("Usage: +merge <+file1> <+file2> <+destination>")
        return

    file1_name, file2_name, dest_name = args[1], args[2], args[3]
    entry1 = find_pfs_entry(file1_name)
    entry2 = find_pfs_entry(file2_name)
    if not entry1 or not entry2:
        print("One or both source files not found in PFS.")
        return
    if find_pfs_entry(dest_name):
        print("Destination file already exists in PFS.")
        return

    with open(PFS_FILE, "rb") as f:
        f.seek(entry1["offset"])
        content1 = f.read(entry1["size"])

        f.seek(entry2["offset"])
        content2 = f.read(entry2["size"])

    merged_content = content1 + content2

    with open(PFS_FILE, "ab") as f:
        offset = f.tell()
        f.write(merged_content)
        write_pfs_entry(dest_name, is_dir=0, size=len(merged_content), offset=offset)
    
    print(f"Merged '{file1_name}' and '{file2_name}' into '{dest_name}'")

def main():
    ensure_pfs_exists()
    while True:
        try:
            cmd = input("micro> ").strip()
            if not cmd:
                continue
            args = cmd.split()
            command = args[0].lower()

            if command == "+cp":
                pfs_cp(args)
            elif command == "+rm":
                pfs_rm(args)
            elif command == "+mkdir":
                pfs_mkdir(args)
            elif command == "+rmdir":
                pfs_rmdir(args)
            elif command == "+ls":
                list_pfs_entries()
            elif command == "+show":
                if len(args) != 2:
                    print("Usage: +show <+file>")
                else:
                    show_pfs_file(args[1])
            elif command == "+merge":
                pfs_merge(args)
            elif command == "exit":
                break
            else:
                print(f"Unknown command: {args[0]}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
