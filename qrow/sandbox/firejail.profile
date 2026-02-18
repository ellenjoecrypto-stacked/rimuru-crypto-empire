# Firejail security profile for Qrow bot sandboxing
# Restricts network, filesystem, and process capabilities

include /etc/firejail/default.profile

# Deny network access by default — bots must explicitly request it
net none

# Restrict filesystem
whitelist ${HOME}/qrow/sandbox
read-only ${HOME}/qrow/core
read-only ${HOME}/qrow/apis

# No root escalation
noroot

# Disable sound, dbus, 3d
nosound
nodbus
no3d

# Seccomp filtering
seccomp

# Private /tmp per sandbox
private-tmp
