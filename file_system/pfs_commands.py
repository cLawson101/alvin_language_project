
import os
import time

PFS_FILENAME = 'private.pfs'

#initialize pfs file if not present
def init_pfs():
    if not os.path.exists(PFS_FILENAME):
        with open(PFS_FILENAME, 'w') as f:
            f.write("FILES:\n")
            f.write("DIRS:\n")
            f.write("DATA:\n")

#finds where sections begin
def get_section_offsets():
    with open(PFS_FILENAME, 'r') as f:
        content = f.read()
        files_index = content.find("FILES:\n") + len("FILES:\n")
        dirs_index = content.find("DIRS:\n")
        data_index = content.find("DATA:\n")
        return files_index, dirs_index, data_index

#return data, actual content
def read_data_section():
    with open(PFS_FILENAME, 'r') as f:
        content = f.read()
        data_index = content.find("DATA:\n") + len("DATA:\n")
        return content[data_index:]

#merges 2 files
def pfs_merge(src1, src2, dest):
    init_pfs()

    def read_regfile(path):
        if path.startswith('+'):
            return read_file_from_pfs(path)
        else:
            try:
                with open(path, 'r') as f:
                    return f.read()
            except:
                print(f"Couldn't read: {path}")
                return None
    
    data1 = read_regfile(src1)
    data2 = read_regfile(src2)

    if data1 is None or data2 is None:
        print("Marge fails: Missing data")
        return

    mergedData = data1 + data2

    with open(PFS_FILENAME, 'r+') as f:
        data = f.read()
        data_index = data.find("DATA:\n") + len("DATA:\n")
        f.seek(0)
        head = data[:data_index]
        tail = data[data_index:]
        offset = len(tail)
        timestamp = str(int(time.time()))
        new_entry = f"{dest:<32}:{'root':<16}:{offset}:{len(mergedData)}:{timestamp}\n"
        insert_point = data.find("DIRS:\n")
        f.seek(insert_point)
        f.write(new_entry + data[insert_point:])
        f.seek(0, 2)
        f.write(mergedData)

#shows target's time of last change
def pfs_ls(target):
    init_pfs()
    with open(PFS_FILENAME, 'r') as f:
        lines = f.readlines()

        for line in lines:
            if line.startswith(target):
                data = line.strip().split(':')
                if len(data) >= 5:
                    name = data[0].strip()
                    tTime = int(data[4])
                    print(f"{name} Time Modified: {time.ctime(tTime)}")
                    return

#copies a file into the PFS
def pfs_cp(src, dest):
    init_pfs()
    is_src_pfs = src.startswith('+')
    is_dest_pfs = dest.startswith('+')

    if not is_dest_pfs:
        print("Destination must be a +file")
        return

    if is_src_pfs:
        content = read_file_from_pfs(src)
    else:
        print(f"Trying to read file: {src}")
        try:
            #print("File read success.")
            with open(src, 'r') as f:
                content = f.read()
            print("File read success.")
        except:
            print(f"Could not read source file: {src}")
            return

    with open(PFS_FILENAME, 'r+') as f:
        data = f.read()
        data_index = data.find("DATA:\n") + len("DATA:\n")
        f.seek(0)
        head = data[:data_index]
        tail = data[data_index:]
        offset = len(tail)
        timestamp = str(int(time.time()))
        new_entry = f"{dest:<32}:{'root':<16}:{offset}:{len(content)}:{timestamp}\n"
        insert_point = data.find("DIRS:\n")
        f.seek(insert_point)
        f.write(new_entry + data[insert_point:])
        f.seek(0, 2)
        f.write(content)

#reading from pfs
def read_file_from_pfs(filename):
    with open(PFS_FILENAME, 'r') as f:
        lines = f.readlines()

    data_index = None
    for i, line in enumerate(lines):
        if line.strip() == "DATA:":
            data_index = i
            break

    for line in lines:
        if line.startswith(filename):
            parts = line.strip().split(":")
            offset = int(parts[2])
            length = int(parts[3])
            break
    else:
        print(f"{filename} not found")
        return ""

    content = "".join(lines[data_index + 1:])
    return content[offset:offset + length]

#shows +files content
def pfs_show(filename):
    content = read_file_from_pfs(filename)
    print(content.strip())
