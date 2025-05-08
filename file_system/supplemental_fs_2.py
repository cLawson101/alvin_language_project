
import os
import time
import struct
import sys

class SupplementalFileSystem:
    MAGIC_NUMBER = b'SPFS'
    VERSION = 1
    
    
    FILE_TYPE = b'F'
    DIR_TYPE = b'D'
    
    
    ACTIVE = b'A'
    DELETED = b'D'
    
    def __init__(self):
        self.file_path = "private.pfs"
        
        if os.path.exists(self.file_path):
            self.file = open(self.file_path, "r+b")
            
            magic = self.file.read(4)
            if magic != self.MAGIC_NUMBER:
                raise ValueError("Invalid file format: not a valid supplemental file system")
                
            
            version = struct.unpack('B', self.file.read(1))[0]
            if version != self.VERSION:
                raise ValueError(f"Unsupported version: {version}")
                
            
            self.root_dir_offset = struct.unpack('Q', self.file.read(8))[0]
        else:
            
            self.file = open(self.file_path, "w+b")
            
            
            self.file.write(self.MAGIC_NUMBER)  
            self.file.write(struct.pack('B', self.VERSION))  
            
            
            root_offset_pos = self.file.tell()
            self.file.write(struct.pack('Q', 0))  
            
            
            self.root_dir_offset = self.file.tell()
            
            
            self.file.seek(root_offset_pos)
            self.file.write(struct.pack('Q', self.root_dir_offset))
            self.file.seek(self.root_dir_offset)
            
            
            self.file.write(self.DIR_TYPE)  
            self.file.write(self.ACTIVE)    
            self.file.write(struct.pack('B', 1))  
            self.file.write(b'/')           
            self.file.write(struct.pack('Q', int(time.time())))  
            
            
            self.file.write(struct.pack('I', 4))  
            
            
            content_offset = self.file.tell() + 8  
            self.file.write(struct.pack('Q', content_offset))
            
            
            self.file.write(struct.pack('I', 0))  
            
            
            self.file.flush()
    
    def close(self):
        if hasattr(self, 'file') and self.file:
            self.file.close()
    
    def _read_entry(self, offset):
        self.file.seek(offset)
        entry_type = self.file.read(1)
        status = self.file.read(1)
        name_len = struct.unpack('B', self.file.read(1))[0]
        name = self.file.read(name_len).decode('utf-8')
        timestamp = struct.unpack('Q', self.file.read(8))[0]
        size = struct.unpack('I', self.file.read(4))[0]
        content_offset = struct.unpack('Q', self.file.read(8))[0]
        
        return {
            'offset': offset,
            'type': entry_type,
            'status': status,
            'name': name,
            'timestamp': timestamp,
            'size': size,
            'content_offset': content_offset
        }
    
    def _find_entry(self, path):
        if not path or path == '/':
            return self._read_entry(self.root_dir_offset)
        
        
        if path.startswith('+'):
            path = path[1:]
        
        
        if path.startswith('/'):
            path = path[1:]
        
        components = path.split('/')
        current_dir = self._read_entry(self.root_dir_offset)
        
        
        if not components[0]:
            return current_dir
        
        
        for i, component in enumerate(components):
            if current_dir['type'] != self.DIR_TYPE:
                return None  
            
            
            self.file.seek(current_dir['content_offset'])
            entry_count = struct.unpack('I', self.file.read(4))[0]
            
            found = False
            
            for _ in range(entry_count):
                entry_offset = struct.unpack('Q', self.file.read(8))[0]
                entry = self._read_entry(entry_offset)
                
                if entry['status'] == self.ACTIVE and entry['name'] == component:
                    
                    if i == len(components) - 1:
                        
                        return entry
                    else:
                        
                        current_dir = entry
                        found = True
                        break
            
            if not found:
                return None  
        
        return None  
    
    def _get_parent_and_name(self, path):
        if not path or path == '/':
            return None, ''
        
        
        if path.startswith('+'):
            path = path[1:]
        
        
        if path.startswith('/'):
            path = path[1:]
        
        components = path.split('/')
        
        
        if len(components) == 1:
            parent_dir = self._read_entry(self.root_dir_offset)
            return parent_dir, components[0]
        
        
        parent_path = '/'.join(components[:-1])
        parent_dir = self._find_entry(parent_path)
        
        return parent_dir, components[-1]
    
    def _add_to_directory(self, dir_entry, new_entry_offset):
        
        self.file.seek(dir_entry['content_offset'])
        entry_count = struct.unpack('I', self.file.read(4))[0]
        
        
        self.file.seek(dir_entry['content_offset'])
        self.file.write(struct.pack('I', entry_count + 1))
        
        
        self.file.seek(dir_entry['content_offset'] + 4 + (entry_count * 8))
        
        
        self.file.write(struct.pack('Q', new_entry_offset))
        
        
        self.file.seek(dir_entry['offset'] + 3 + struct.unpack('B', self.file.read(1))[0])  
        self.file.write(struct.pack('Q', int(time.time())))
        
        self.file.flush()
    
    def _create_entry(self, entry_type, name, parent_dir, content_size=0):
        
        self.file.seek(0, 2)
        entry_offset = self.file.tell()
        
        
        name_bytes = name.encode('utf-8')
        content_offset = entry_offset + 1 + 1 + 1 + len(name_bytes) + 8 + 4 + 8
        
        
        self.file.write(entry_type)  
        self.file.write(self.ACTIVE)  
        self.file.write(struct.pack('B', len(name_bytes)))  
        self.file.write(name_bytes)  
        self.file.write(struct.pack('Q', int(time.time())))  
        self.file.write(struct.pack('I', content_size))  
        self.file.write(struct.pack('Q', content_offset))  
        
        
        if parent_dir:
            self._add_to_directory(parent_dir, entry_offset)
        
        self.file.flush()
        return entry_offset, content_offset
    
    def _mark_as_deleted(self, entry):
        self.file.seek(entry['offset'] + 1)  
        self.file.write(self.DELETED)
        self.file.flush()
    
    def _is_directory_empty(self, dir_entry):
        self.file.seek(dir_entry['content_offset'])
        entry_count = struct.unpack('I', self.file.read(4))[0]
        
        if entry_count == 0:
            return True
        
        
        active_entries = 0
        for _ in range(entry_count):
            entry_offset = struct.unpack('Q', self.file.read(8))[0]
            entry = self._read_entry(entry_offset)
            if entry['status'] == self.ACTIVE:
                active_entries += 1
        
        return active_entries == 0
    
    def cp(self, source, dest):       
        
        if not dest.startswith('+'):
            print("Error: Destination must be a supplementary file")
            return False
        
        dest = dest[1:]  
        
        
        content = None
        if source.startswith('+'):
            
            source = source[1:]  
            source_entry = self._find_entry(source)
            if not source_entry:
                print(f"Error: Source file '{source}' not found")
                return False
            
            if source_entry['type'] != self.FILE_TYPE:
                print(f"Error: '{source}' is not a file")
                return False
            
            
            self.file.seek(source_entry['content_offset'])
            content = self.file.read(source_entry['size'])
        else:
            
            try:
                with open(source, 'rb') as f:
                    content = f.read()
            except FileNotFoundError:
                print(f"Error: Source file '{source}' not found")
                return False
        
        
        parent_dir, filename = self._get_parent_and_name(dest)
        if not parent_dir:
            print(f"Error: Parent directory for '{dest}' not found")
            return False
        
        if parent_dir['type'] != self.DIR_TYPE:
            print(f"Error: '{parent_dir['name']}' is not a directory")
            return False
        
        
        dest_entry = self._find_entry(dest)
        if dest_entry and dest_entry['status'] == self.ACTIVE:
            
            self._mark_as_deleted(dest_entry)
        
        
        _, content_offset = self._create_entry(self.FILE_TYPE, filename, parent_dir, len(content))
        
        
        self.file.seek(content_offset)
        self.file.write(content)
        self.file.flush()
        
        return True
    
    def rm(self, path):
        if not path.startswith('+'):
            print("Error: Path must be a supplementary file")
            return False
        
        path = path[1:]  
        
        entry = self._find_entry(path)
        if not entry:
            print(f"Error: File '{path}' not found")
            return False
        
        if entry['type'] != self.FILE_TYPE:
            print(f"Error: '{path}' is not a file")
            return False
        
        
        self._mark_as_deleted(entry)
        return True
    
    def mkdir(self, path):
        if not path.startswith('+'):
            print("Error: Path must be a supplementary directory")
            return False
        
        path = path[1:]  
        
        
        existing = self._find_entry(path)
        if existing and existing['status'] == self.ACTIVE:
            print(f"Error: '{path}' already exists")
            return False
        
        
        parent_dir, dirname = self._get_parent_and_name(path)
        if not parent_dir:
            print(f"Error: Parent directory for '{path}' not found")
            return False
        
        
        entry_offset, content_offset = self._create_entry(self.DIR_TYPE, dirname, parent_dir, 4)
        
        
        self.file.seek(content_offset)
        self.file.write(struct.pack('I', 0))  
        self.file.flush()
        
        return True
    
    def rmdir(self, path):
        if not path.startswith('+'):
            print("Error: Path must be a supplementary directory")
            return False
        
        path = path[1:]  
        
        entry = self._find_entry(path)
        if not entry:
            print(f"Error: Directory '{path}' not found")
            return False
        
        if entry['type'] != self.DIR_TYPE:
            print(f"Error: '{path}' is not a directory")
            return False
        
        
        if not self._is_directory_empty(entry):
            print(f"Error: Directory '{path}' is not empty")
            return False
        
        
        self._mark_as_deleted(entry)
        return True
    
    def ls(self, path):
        if not path.startswith('+'):
            print("Error: Path must be a supplementary file or directory")
            return False
        
        path = path[1:]  
        
        entry = self._find_entry(path)
        if not entry:
            print(f"Error: '{path}' not found")
            return False
        
        if entry['type'] == self.FILE_TYPE:
            
            timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
            print(f"{entry['name']} (Last modified: {timestamp_str})")
        elif entry['type'] == self.DIR_TYPE:
            
            self.file.seek(entry['content_offset'])
            entry_count = struct.unpack('I', self.file.read(4))[0]
            
            
            for _ in range(entry_count):
                entry_offset = struct.unpack('Q', self.file.read(8))[0]
                child_entry = self._read_entry(entry_offset)
                
                if child_entry['status'] == self.ACTIVE:
                    
                    entry_type = 'D' if child_entry['type'] == self.DIR_TYPE else 'F'
                    timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(child_entry['timestamp']))
                    print(f"{entry_type} {child_entry['name']} (Last modified: {timestamp_str})")
        
        return True
    
    def merge(self, file1, file2, dest):
        
        if not file1.startswith('+'):
            print("Error: First file must be a supplementary file")
            return False
        
        
        if not dest.startswith('+'):
            print("Error: Destination must be a supplementary file")
            return False
        
        file1 = file1[1:]  
        dest = dest[1:]    
        
        
        file1_entry = self._find_entry(file1)
        if not file1_entry:
            print(f"Error: File '{file1}' not found")
            return False
        
        if file1_entry['type'] != self.FILE_TYPE:
            print(f"Error: '{file1}' is not a file")
            return False
        
        
        self.file.seek(file1_entry['content_offset'])
        content1 = self.file.read(file1_entry['size'])
        
        
        content2 = None
        if file2.startswith('+'):
            
            file2 = file2[1:]  
            file2_entry = self._find_entry(file2)
            if not file2_entry:
                print(f"Error: File '{file2}' not found")
                return False
            
            if file2_entry['type'] != self.FILE_TYPE:
                print(f"Error: '{file2}' is not a file")
                return False
            
            
            self.file.seek(file2_entry['content_offset'])
            content2 = self.file.read(file2_entry['size'])
        else:
            
            try:
                with open(file2, 'rb') as f:
                    content2 = f.read()
            except FileNotFoundError:
                print(f"Error: File '{file2}' not found")
                return False
        
        
        merged_content = content1 + content2
        
        
        parent_dir, filename = self._get_parent_and_name(dest)
        if not parent_dir:
            print(f"Error: Parent directory for '{dest}' not found")
            return False
        
        if parent_dir['type'] != self.DIR_TYPE:
            print(f"Error: '{parent_dir['name']}' is not a directory")
            return False
        
        
        dest_entry = self._find_entry(dest)
        if dest_entry and dest_entry['status'] == self.ACTIVE:
            
            self._mark_as_deleted(dest_entry)
        
        
        _, content_offset = self._create_entry(self.FILE_TYPE, filename, parent_dir, len(merged_content))
        
        
        self.file.seek(content_offset)
        self.file.write(merged_content)
        self.file.flush()
        
        return True
    
    def show(self, path):
        if not path.startswith('+'):
            print("Error: Path must be a supplementary file")
            return False
        
        path = path[1:]  
        
        entry = self._find_entry(path)
        if not entry:
            print(f"Error: File '{path}' not found")
            return False
        
        if entry['type'] != self.FILE_TYPE:
            print(f"Error: '{path}' is not a file")
            return False
        
        
        self.file.seek(entry['content_offset'])
        content = self.file.read(entry['size'])
        
        try:
            
            print(content.decode('utf-8'))
        except UnicodeDecodeError:
            
            print("Binary content (first 100 bytes):", content[:100])
        
        return True


pfs = SupplementalFileSystem()