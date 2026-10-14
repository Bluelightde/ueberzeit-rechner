import time, sys, os, subprocess
t0 = time.perf_counter()
# Launch the packaged binary and time how long until the window appears
# Use xdotool or just time the process startup via a quick exit
proc = subprocess.Popen([sys.executable, '--version'], stdout=subprocess.PIPE)
# Not relevant; instead time binary
