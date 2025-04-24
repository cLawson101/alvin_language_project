import os
import sys
import re

def lookup_command(cmd):
    if '/' in cmd:
        return cmd
    path_dirs = os.environ.get('PATH', '/bin:/usr/bin').split(':')
    for d in path_dirs:
        candidate = d + '/' + cmd
        try:
            fd = os.open(candidate, os.O_RDONLY)
            os.close(fd)
            return candidate
        except OSError:
            pass
    return None


def run_command(cmd_argv, infile, outfile, background):
    path = lookup_command(cmd_argv[0])
    if not path:
        print("command not found")
        return

    pid = os.fork()
    if pid == 0:
        if infile:
            try:
                infd = os.open(infile, os.O_RDONLY)
                os.dup2(infd, 0)
                os.close(infd)
            except OSError as e:
                print(f"Cannot open input file {infile}")
                os._exit(1)

        if outfile:
            try:
                outfd = os.open(outfile, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666)
                os.dup2(outfd, 1)
                os.close(outfd)
            except OSError as e:
                print(f"Cannot open output file {outfile}")
                os._exit(1)

        try:
            os.execv(path, cmd_argv)
        except OSError as e:
            import errno
            if e.errno == errno.EACCES:
                print("not executable")
            else:
                print("command not found")
            os._exit(1)
    else:
        if not background:
            pid_done, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                code = os.WEXITSTATUS(status)
                if code != 0:
                    print(f"Program terminated: exit code {code}")
        else:
            pass


def run_pipe_command(left_argv, right_argv,
                     left_infile, left_outfile,
                     right_infile, right_outfile,
                     background):

    left_path = lookup_command(left_argv[0])
    right_path = lookup_command(right_argv[0])
    if not left_path or not right_path:
        print("command not found")
        return

    rfd, wfd = os.pipe()

    pid_left = os.fork()
    if pid_left == 0:
        if left_infile:
            try:
                infd = os.open(left_infile, os.O_RDONLY)
                os.dup2(infd, 0)
                os.close(infd)
            except OSError:
                print(f"Cannot open input file {left_infile}")
                os._exit(1)
        if left_outfile:
            try:
                outfd = os.open(left_outfile, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o666)
                os.dup2(outfd, 1)
                os.close(outfd)
            except OSError:
                print(f"Cannot open output file {left_outfile}")
                os._exit(1)
        else:
            os.dup2(wfd, 1)

        os.close(rfd)
        os.close(wfd)

        try:
            os.execv(left_path, left_argv)
        except OSError as e:
            import errno
            if e.errno == errno.EACCES:
                print("not executable")
            else:
                print("command not found")
            os._exit(1)

    pid_right = os.fork()
    if pid_right == 0:
        if right_outfile:
            try:
                outfd = os.open(right_outfile, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o666)
                os.dup2(outfd, 1)
                os.close(outfd)
            except OSError:
                print(f"Cannot open output file {right_outfile}")
                os._exit(1)

        if right_infile:
            try:
                infd = os.open(right_infile, os.O_RDONLY)
                os.dup2(infd, 0)
                os.close(infd)
            except OSError:
                print(f"Cannot open input file {right_infile}")
                os._exit(1)
        else:
            os.dup2(rfd, 0)

        os.close(rfd)
        os.close(wfd)

        try:
            os.execv(right_path, right_argv)
        except OSError as e:
            import errno
            if e.errno == errno.EACCES:
                print("not executable")
            else:
                print("command not found")
            os._exit(1)

    os.close(rfd)
    os.close(wfd)

    if not background:
        for pid in (pid_left, pid_right):
            pid_done, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                code = os.WEXITSTATUS(status)
                if code != 0:
                    print(f"Program terminated: exit code {code}")
    else:
        pass

def redirect(cmdline):
    infile = None
    outfile = None

    tokens = re.split(r'\s+', cmdline)
    argv = []
    i = 0
    while i < len(tokens):
        if tokens[i] == '<' and i + 1 < len(tokens):
            infile = tokens[i + 1]
            i += 2
        elif tokens[i] == '>' and i + 1 < len(tokens):
            outfile = tokens[i + 1]
            i += 2
        else:
            argv.append(tokens[i])
            i += 1

    return infile, outfile, argv

def main():
    if len(sys.argv) > 1:
        lines = []
        with open(sys.argv[1], 'r') as f:
            lines = f.readlines()
        input_lines = [ln.strip('\n') for ln in lines]
    else:
        input_lines = None

    idx = 0
    while True:
        if input_lines is None:
            line = input("shell> ")
        else:
            if idx >= len(input_lines):
                break
            line = input_lines[idx]
            idx += 1

        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if line == 'quit':
            break

        background = False
        if line.endswith('&'):
            background = True
            line = line[:-1].strip()

        if '|' in line:
            left_part, right_part = line.split('|', 1)
            left_part = left_part.strip()
            right_part = right_part.strip()

            left_in, left_out, left_argv = redirect(left_part)
            right_in, right_out, right_argv = redirect(right_part)

            run_pipe_command(left_argv, right_argv,
                             left_in, left_out,
                             right_in, right_out,
                             background)
            continue

        infile, outfile, argv = redirect(line)
        if not argv:
            continue

        if argv[0] == 'inspiration':
            msg = os.environ.get('phrase', "Believe in yourself!")
            print(msg)
            continue

        if argv[0] == 'cd':
            target = argv[1] if len(argv) > 1 else os.environ.get('HOME', '/')
            try:
                os.chdir(target)
            except OSError as e:
                print(f"cd: {e}")
            continue

        run_command(argv, infile, outfile, background)


if __name__ == '__main__':
    main()