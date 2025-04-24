import re
import os
import sys

programs = [["/bin/cat", "/proc/cpuinfo"], ["/bin/echo", "Hello World"], ["/home/seed/Desktop/Pre-shell", "spinner.py 1000000"], ["/bin/uname","-a"]]

def executeCommand(command):
		run_in_background = False # This will set a variable to check if the command should run in the background or not
		if command[-1] == "&": # Checks if the last character in the command is "&", if so it will set the run background to true and remove that character.
			run_in_background = True
			command = command[:-1]
		
		# This will handle the output redirection
		if ">" in command:
			redirection_index = command.index(">")
			if redirection_index == len(command) - 1 or redirection_index == 0:
				print("Error: Missing file name for output redirection.")
				return
			
			output_file = command[redirection_index + 1] # This will get the file name from the command list
			command = command[:redirection_index] # This is to remove the ">"" from the command list

			try:
				fd = os.open(output_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644) # This will open the file in write only mode and create it if it does not exist
				os.dup2(fd, 1) # This will duplicate the file descriptor to standard output
				os.close(fd) # This will close the file descriptor
			except Exception as e:
				print(f"Error redirceting output: {e}")
				return

		# This segment is to execute the "cd" command
		if command[0] == "cd":
			try:
				if len(command) > 1:
					os.chdir(command[1]) # Changes directory to the specified path
				else:
					os.chdir(os.path.expanduser("~")) # This actually changes the directory to the home directory
			# These exceptions are to catch errors that can occus such as file not found or permissions denied
			except FileNotFoundError:
				print(f"cd: {command[1]}: No such file or directory")
			except Exception as e:
				print(f"cd: {e}")
			return


		# Used for inspirational command
		if command[0] == "inspiration":
			quote = os.getenv("phrase", "One Step at a Time")
			print(quote)
			return
		
		# This is to search for executable files in the path
		ePath = None
		for path_dir in os.environ["PATH"].split(os.pathsep):
			potential_path = os.path.join(path_dir, command[0])
			# This will try to open the file in read only mode, if it fails it will continue to the next path
			# If it succeeds, it will set the executable_path to the potential_path and break out of the loop
			try:
				fd = os.open(potential_path, os.O_RDONLY)
				os.close(fd)
				ePath = potential_path
				break
			except FileNotFoundError:
				continue

		# if the executable_path is None, it means that the command was not found in any of the paths and will print an error message
		if not ePath:
			print(f"Command {command[0]} not found.")
			return
		
		# Execute user command using os.execv
		pid = os.fork()
		if pid == 0:
			try:
				os.execv(ePath, command) # was originally hardcoded but now it is dynamic
			except FileNotFoundError:
				print(f"Command {command[0]} not found.")
				os.exit(1)
		else:
			if not run_in_background:
				os.waitpid(pid, 0)

def getUserInput():
	userInput = ""

	while True:
		userInput = input("> ")
		command = userInput.split(" ")

		# This is to check if the user input is empty or not
		if not command or command[0] == "":
			continue

		# This is to stop the program if the user types "quit"
		if command[0].lower() == "quit":
			break
		
		executeCommand(command)

if __name__ == "__main__":

    getUserInput()