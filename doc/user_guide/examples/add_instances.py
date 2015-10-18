from radical.ensemblemd import Kernel
from radical.ensemblemd import Pipeline
from radical.ensemblemd import EnsemblemdError
from radical.ensemblemd import SingleClusterEnvironment

class MyApp(Pipeline):

      def __init__(self, steps,instances):
             Pipeline.__init__(self, steps,instances)

      def step_1(self, instance):
             k = Kernel(name="misc.hello")
             k.upload_input_data = ['./input_file.txt > temp.txt']
             k.arguments = ["--file=temp.txt"]
             k.download_output_data = ['./temp.txt > output_file_{0}.txt'.format(instance)]
             return k

if __name__ == "__main__":

      try:

            # Create a new static execution context with one resource and a fixed
            # number of cores and runtime.
            cluster = SingleClusterEnvironment(
                         resource="localhost",
                         cores=1,
                         walltime=15,
                         username=None,
                         allocation=None,
                         database_name="mongod:mymongodburl"
                  )

            os.system('Welcome! > input_file.txt')

            # Allocate the resources. 
            cluster.allocate()

            # Set the 'instances' of the pipeline to 16. This means that 16 instances
            # of each pipeline step are executed.
            app = MyApp(steps=1,instances=16)

            cluster.run(app)

            # Deallocate the resources. 
            cluster.deallocate()

       except EnsemblemdError, er:

             print "Ensemble MD Toolkit Error: {0}".format(str(er))
             raise # Just raise the execption again to get the backtrace