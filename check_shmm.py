import sys
import matplotlib
matplotlib.use('agg')

import shmm
status = shmm.test(*sys.argv[1:])
sys.exit(status)
