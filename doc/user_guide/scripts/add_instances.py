import sys
import os
import json

from radical.ensemblemd import Kernel
from radical.ensemblemd import PoE
from radical.ensemblemd import EnsemblemdError
from radical.ensemblemd import ResourceHandle

class MyApp(PoE):

	def __init__(self, stages,instances):
		 PoE.__init__(self, stages,instances)

	def stage_1(self, instance):
		k = Kernel(name="misc.hello")
		k.upload_input_data = ['./input_file.txt > temp.txt']
		k.arguments = ["--file=temp.txt"]
		k.download_output_data = ['./temp.txt > output_file_{0}.txt'.format(instance)]
		return k

if __name__ == "__main__":

	# use the resource specified as argument, fall back to localhost
	if   len(sys.argv)  > 2: 
		print 'Usage:\t%s [resource]\n\n' % sys.argv[0]
		sys.exit(1)
	elif len(sys.argv) == 2: 
		resource = sys.argv[1]
	else: 
		resource = 'local.localhost'

	try:

		# Create a new resource handle with one resource and a fixed
		# number of cores and runtime.
		cluster = ResourceHandle(
				resource=resource,
				cores=1,
				walltime=15,
				#username=None,

				project=config[resource]['project'],
				access_schema = config[resource]['schema'],
				queue = config[resource]['queue'],
				database_url='mongodb://entk_user:entk_user@ds029224.mlab.com:29224/entk_doc',
			)

		os.system('/bin/echo Welcome! > input_file.txt')

		# Allocate the resources.
		cluster.allocate()

		# Set the 'instances' of the BagofTasks to 16. This means that 16 instances
		# of each BagofTasks step are executed.
		app = MyApp(stages=1,instances=16)

		cluster.run(app)

		# Deallocate the resources. 
		cluster.deallocate()

	except EnsemblemdError, er:

		print "Ensemble MD Toolkit Error: {0}".format(str(er))
		raise # Just raise the execption again to get the backtrace
