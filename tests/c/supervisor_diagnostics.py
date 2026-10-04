"""Deterministic supervisor failures, without spawning or signalling children."""
import subprocess
import sys

cases = [(name, name, "EINVAL") for name in (
    "actions_init", "attributes_init", "addchdir", "dup_stdin", "close_stdin",
    "setsigmask", "setpgroup", "setflags", "posix_spawn")]
cases += [("socketpair", "socketpair", "EACCES"), ("pipe", "pipe_stdout", "EACCES"),
          ("fcntl_cloexec", "fcntl_cloexec", "EACCES"),
          ("fcntl_nonblock", "nonblock_stdin", "EACCES"),
          ("clock", "clock_gettime", "EACCES"), ("clock-value", "clock_value", "zero"),
          ("send", "send", "EACCES"), ("read", "read_stdout", "EACCES"),
          ("waitid", "waitid", "EACCES"), ("poll", "poll", "EACCES"),
          ("kill", "kill_group", "EACCES"), ("waitpid", "waitpid", "ECHILD"),
          ("poll-kill", "poll", "EACCES"), ("spawn-cleanup", "posix_spawn", "EINVAL"),
          ("cleanup-success", "close", "EIO"), ("success", "none", "zero"),
          ("actions_destroy", "actions_destroy", "EINVAL"),
          ("attributes_destroy", "attributes_destroy", "EINVAL"),
          ("read-eintr", "none", "zero")]
if sys.platform == "darwin":
    cases.append(("setsockopt", "setsockopt", "EACCES"))
for case in cases:
    subprocess.run([sys.argv[1], *case], check=True)
print(f"{len(cases)} supervisor diagnostic scenarios passed")
