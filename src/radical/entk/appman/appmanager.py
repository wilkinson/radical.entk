__copyright__   = "Copyright 2017-2018, http://radical.rutgers.edu"
__author__      = "Vivek Balasubramanian <vivek.balasubramaniana@rutgers.edu>"
__license__     = "MIT"

import radical.utils as ru
from radical.entk.exceptions import *
from radical.entk.pipeline.pipeline import Pipeline
from radical.entk.stage.stage import Stage
from radical.entk.task.task import Task
from radical.entk.execman.resource_manager import ResourceManager
from radical.entk.execman.task_manager import TaskManager
from wfprocessor import WFprocessor
import sys, time, os
import Queue
import pika
import json
from threading import Thread, Event
import traceback
from radical.entk import states

slow_run = os.environ.get('RADICAL_ENTK_SLOW',False)


class AppManager(object):

    """
    An application manager takes the responsibility of setting up the communication infrastructure, instantiates the
    ResourceManager, TaskManager, WFProcessor objects and all their threads and processes. This is the Master object
    running in the main process and is designed to recover from errors from all other objects, threads and processes.

    :Arguments:
        :hostname: host rabbitmq server is running
        :push_threads: number of threads to push tasks on the pending_qs
        :pull_threads: number of threads to pull tasks from the completed_qs
        :sync_threads: number of threads to pull task from the synchronizer_q
        :pending_qs: number of queues to hold pending tasks to be pulled by the task manager
        :completed_qs: number of queues to hold completed tasks pushed by the task manager
    """


    def __init__(self, hostname = 'localhost', push_threads=1, pull_threads=1, 
                sync_threads=1, pending_qs=1, completed_qs=1):

        self._uid       = ru.generate_id('radical.entk.appmanager')
        self._logger    = ru.get_logger('radical.entk.appmanager')
        self._prof      = ru.Profiler(name = self._uid)

        self._prof.prof('create amgr obj', uid=self._uid)

        self._name      = str()

        self._workflow  = None
        self._resubmit_failed = False

        # RabbitMQ Queues
        self._num_pending_qs = pending_qs
        self._num_completed_qs = completed_qs
        self._pending_queue = list()
        self._completed_queue = list()

        # RabbitMQ inits
        self._mq_connection = None
        self._mq_channel = None
        self._mq_hostname = hostname

        # Threads and procs counts
        self._num_push_threads = push_threads
        self._num_pull_threads = pull_threads
        self._num_sync_threads = sync_threads
        self._end_sync = Event()

        # None objects for error handling
        self._wfp = None
        self._task_manager = None
        self._sync_thread = None

        # Resource Manager object
        self._resource_manager = None
        
        # Logger        
        self._logger.info('Application Manager initialized')

        self._prof.prof('amgr obj created', uid=self._uid)

    # ------------------------------------------------------------------------------------------------------------------
    # Getter functions
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def name(self):

        """
        Name for the application manager 

        :getter: Returns the name of the application manager
        :setter: Assigns the name of the application manager
        :type: String
        """

        return self._name

    """
    @property
    def resubmit_failed(self):

        
        Enable resubmission of failed tasks

        :getter: Returns the value of the resubmission flag
        :setter: Assigns a boolean value for the resubmission flag
        
        return self._resubmit_failed
    """

    @property
    def resource_manager(self):

        """
        :getter: Returns the resource manager object being used
        :setter: Assigns a resource manager
        """

        return self._resource_manager

    # ------------------------------------------------------------------------------------------------------------------
    # Setter functions
    # ------------------------------------------------------------------------------------------------------------------

    @name.setter
    def name(self, value):

        if not instantiate(value, str):
            raise TypeError(expected_type=str, actual_type=type(value))

        else:
            self._name = value


    """
    @resubmit_failed.setter
    def resubmit_failed(self, value):
        self._resubmit_failed = value
    """

    @resource_manager.setter
    def resource_manager(self, value):

        if not isinstance(value, ResourceManager):
            raise TypeError(expected_type=ResourceManager, actual_type=type(value))
        else:
            self._resource_manager = value

    # ------------------------------------------------------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------------------------------------------------------

    def assign_workflow(self, workflow):

        """
        **Purpose**: Assign workflow to the application manager to be executed

        :arguments: set of Pipelines
        """


        try:
            
            self._prof.prof('assigning workflow', uid=self._uid)
            self._workflow = self._validate_workflow(workflow)
            self._logger.info('Workflow assigned to Application Manager')

        except KeyboardInterrupt:

            self._logger.error('Execution interrupted by user ' + 
                        '(you probably hit Ctrl+C), tring to exit gracefully...')
            
            raise KeyboardInterrupt

        except Exception, ex:

            self._logger.error('Fatal error while adding workflow to appmanager')
            print traceback.format_exc()
            raise Error(text=ex)

    
    def run(self):

        """
        **Purpose**: Run the application manager. Once the workflow and resource manager have been assigned. Invoking this
        method will start the setting up the communication infrastructure, submitting a resource request and then
        submission of all the tasks.
        """

        try:

            if not self._workflow:
                print 'Please assign workflow before invoking run method - cannot proceed'
                self._logger.error('No workflow assigned currently, please check your script')
                raise MissingError(obj=self._uid, missing_attribute='workflow')


            if not self._resource_manager:
                self._logger.error('No resource manager assigned currently, please create and add a valid resource manager')
                raise MissingError(obj=self._uid, missing_attribute='resource_manager')

            else:

                self._prof.prof('amgr run started', uid=self._uid)

                # Setup rabbitmq stuff
                self._logger.info('Setting up RabbitMQ system')
                setup = self._setup_mqs()

                if not setup:
                    self._logger.error('RabbitMQ system not available')
                    raise Error(text="RabbitMQ setup failed")


                # Submit resource request
                self._logger.info('Starting resource request submission')
                self._prof.prof('init rreq submission', uid=self._uid)
                self._resource_manager._submit_resource_request()


                # Start synchronizer thread
                self._logger.info('Starting synchronizer thread')
                self._sync_thread = Thread(target=self._synchronizer, name='synchronizer-thread')
                self._prof.prof('starting synchronizer thread', uid=self._uid)
                self._sync_thread.start()


                # Create WFProcessor object
                self._prof.prof('creating wfp obj', uid=self._uid)
                self._wfp = WFprocessor(  workflow = self._workflow, 
                                    pending_queue = self._pending_queue, 
                                    completed_queue=self._completed_queue,
                                    mq_hostname=self._mq_hostname)

                self._logger.info('Starting WFProcessor process from AppManager')                
                self._wfp.start_processor()                


                # Create tmgr object
                self._prof.prof('creating tmgr obj', uid=self._uid)
                self._task_manager = TaskManager(   pending_queue = self._pending_queue,
                                                    completed_queue = self._completed_queue,
                                                    mq_hostname = self._mq_hostname,
                                                    rmgr = self._resource_manager
                                                )
                self._logger.info('Starting task manager process from AppManager')
                self._task_manager.start_manager()
                self._task_manager.start_heartbeat()

                
                active_pipe_count = len(self._workflow)   
                finished_pipe_uids = []             


                # We wait till all pipelines of the workflow are marked
                # complete
                while (active_pipe_count > 0)or(self._wfp.workflow_incomplete()):

                    if slow_run:
                        time.sleep(1)

                    if active_pipe_count > 0:

                        for pipe in self._workflow:

                            with pipe._stage_lock:

                                if (pipe.completed) and (pipe.uid not in finished_pipe_uids) :
                                    self._logger.info('Pipe %s completed'%pipe.uid)
                                    finished_pipe_uids.append(pipe.uid)
                                    active_pipe_count -= 1
                                    self._logger.info('Active pipes: %s'%active_pipe_count)


                    if not self._sync_thread.is_alive():
                        self._sync_thread = Thread(   target=self._synchronizer, 
                                                name='synchronizer-thread')
                        self._logger.info('Restarting synchronizer thread')
                        self._prof.prof('restarting synchronizer', uid=self._uid)
                        self._sync_thread.start()

                    
                    if not self._wfp.check_alive():

                        self._prof.prof('recreating wfp obj', uid=self._uid)
                        self._wfp = WFProcessor(  workflow = self._workflow, 
                                            pending_queue = self._pending_queue, 
                                            completed_queue=self._completed_queue,
                                            mq_hostname=self._mq_hostname)

                        self._logger.info('Restarting WFProcessor process from AppManager')                        
                        self._wfp.start_processor()

                    if not self._task_manager.check_alive():

                        self._prof.prof('recreating tmgr obj', uid=self._uid)
                        self._task_manager = TaskManager(   pending_queue = self._pending_queue,
                                                            completed_queue = self._completed_queue,
                                                            mq_hostname = self._mq_hostname,
                                                            rmgr = self._resource_manager
                                                        )
                        self._logger.info('Restarting task manager process from AppManager')
                        self._task_manager.start_manager()

                    
                self._prof.prof('start termination', uid=self._uid)
                    
                # Terminate threads in following order: wfp, helper, synchronizer
                self._logger.info('Terminating WFprocessor')
                self._wfp.end_processor()       
                
                self._logger.info('Terminating task manager process')
                self._task_manager.end_manager()
                self._task_manager.end_heartbeat()
                

                self._logger.info('Terminating synchronizer thread')
                self._end_sync.set()
                self._sync_thread.join()
                self._logger.info('Synchronizer thread terminated')

                self._resource_manager._cancel_resource_request()

                self._prof.prof('termination done', uid=self._uid)


        except KeyboardInterrupt:

            self._prof.prof('start termination', uid=self._uid)

            self._logger.error('Execution interrupted by user (you probably hit Ctrl+C), '+
                                'trying to cancel enqueuer thread gracefully...')

            # Terminate threads in following order: wfp, helper, synchronizer
            if self._wfp:
                self._logger.info('Terminating WFprocessor')
                self._wfp.end_processor()

            if self._task_manager:
                self._logger.info('Terminating task manager process')
                self._task_manager.end_manager()
                self._task_manager.end_heartbeat()
                
            if self._sync_thread:
                self._logger.info('Terminating synchronizer thread')
                self._end_sync.set()
                self._sync_thread.join()
                self._logger.info('Synchronizer thread terminated')

            if self._resource_manager:
                self._resource_manager._cancel_resource_request()

            self._prof.prof('termination done', uid=self._uid)

            raise KeyboardInterrupt

        except Exception, ex:

            self._prof.prof('start termination', uid=self._uid)

            self._logger.error('Error in AppManager')

            print traceback.format_exc()

            ## Terminate threads in following order: wfp, helper, synchronizer
            if self._wfp:
                self._logger.info('Terminating WFprocessor')
                self._wfp.end_processor()

            if self._task_manager:
                self._logger.info('Terminating task manager process')
                self._task_manager.end_manager()
                self._task_manager.end_heartbeat()

            if self._sync_thread:
                self._logger.info('Terminating synchronizer thread')
                self._end_sync.set()
                self._sync_thread.join()
                self._logger.info('Synchronizer thread terminated')

            if self._resource_manager:
                self._resource_manager._cancel_resource_request()

            self._prof.prof('termination done', uid=self._uid)
            
            raise Error(text=ex)

    # ------------------------------------------------------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------------------------------------------------------

    def _validate_workflow(self, workflow):

        """
        **Purpose**: Validate whether the workflow consists of a set of Pipelines and validate each Pipeline. 

        Details: Tasks are validated when being added to Stage. Stages are validated when being added to Pipelines. Only
        Pipelines themselves remain to be validated before execution.
        """

        try:

            self._prof.prof('validating workflow', uid=self._uid)

            if not isinstance(workflow, set):

                if not isinstance(workflow, list):
                    workflow = set([workflow])
                else:
                    workflow = set(workflow)

            for item in workflow:
                if not isinstance(item, Pipeline):
                    self._logger.info('workflow type incorrect')
                    raise TypeError(expected_type=['Pipeline', 'set of Pipeline'], 
                                    actual_type=type(item))

                item._validate()

            self._prof.prof('workflow validated', uid=self._uid)

            return workflow

        except Exception, ex:

            self._logger.error('Fatal error while adding workflow to appmanager: %s'%ex)
            raise


    def _setup_mqs(self):

        """
        **Purpose**: Setup RabbitMQ system on the client side. We instantiate queue(s) 'pendingq-*' for communication 
        between the enqueuer thread and the task manager process. We instantiate queue(s) 'completedq-*' for
        communication between the task manager and dequeuer thread. We instantiate queue 'sync-to-master' for 
        communication from enqueuer/dequeuer/task_manager to the synchronizer thread. We instantiate queue
        'sync-ack' for communication from synchronizer thread to enqueuer/dequeuer/task_manager.

        Details: All queues are durable: Even if the RabbitMQ server goes down, the queues are saved to disk and can
        be retrieved. This also means that after an erroneous run the queues might still have unacknowledged messages
        and will contain messages from that run. Hence, in every new run, we first delete the queue and create a new 
        one.
        """

        try:

            self._prof.prof('init mqs setup', uid=self._uid)

            self._logger.debug('Setting up mq connection and channel')

            self._mq_connection = pika.BlockingConnection(
                                    pika.ConnectionParameters(host=self._mq_hostname)
                                    )
            self._mq_channel = self._mq_connection.channel()

            self._logger.debug('Connection and channel setup successful')

            self._logger.debug('Setting up all exchanges and queues')

            for i in range(1,self._num_pending_qs+1):
                queue_name = 'pendingq-%s'%i
                self._pending_queue.append(queue_name)
                self._mq_channel.queue_delete(queue=queue_name)
                # Durable Qs will not be lost if rabbitmq server crashes
                self._mq_channel.queue_declare(queue=queue_name, durable=True) 
                                                

            for i in range(1,self._num_completed_qs+1):
                queue_name = 'completedq-%s'%i
                self._completed_queue.append(queue_name)
                self._mq_channel.queue_delete(queue=queue_name)
                # Durable Qs will not be lost if rabbitmq server crashes
                self._mq_channel.queue_declare(queue=queue_name, durable=True)
                                                

            self._mq_channel.queue_delete(queue='sync-to-master')
            self._mq_channel.queue_declare(queue='sync-to-master')
            self._mq_channel.queue_delete(queue='sync-ack-tmgr')
            self._mq_channel.queue_declare(queue='sync-ack-tmgr')
            self._mq_channel.queue_delete(queue='sync-ack-enq')
            self._mq_channel.queue_declare(queue='sync-ack-enq')
            self._mq_channel.queue_delete(queue='sync-ack-deq')
            self._mq_channel.queue_declare(queue='sync-ack-deq')
                                                    # Durable Qs will not be lost if rabbitmq server crashes

            self._logger.debug('All exchanges and queues are setup')
            self._prof.prof('mqs setup done', uid=self._uid)

            return True

        except Exception, ex:

            self._logger.error('Error setting RabbitMQ system: %s' %ex)
            raise 


    def _synchronizer(self):

        """
        **Purpose**: Thread in the master process to keep the workflow data 
        structure in appmanager up to date. We receive pipelines, stages and 
        tasks objects directly. The respective object is updated in this master 
        process. 

        Details: Important to note that acknowledgements of the type
        channel.basic_ack() is an acknowledgement to the server that the msg
        was received. This is not to be confused with the Ack sent to the 
        enqueuer/dequeuer/task_manager through the sync-ack queue. 
        """

        try:

            self._prof.prof('synchronizer started', uid=self._uid)

            self._logger.info('synchronizer thread started')


            mq_connection = pika.BlockingConnection(pika.ConnectionParameters(host=self._mq_hostname))
            mq_channel = mq_connection.channel()

            while not self._end_sync.is_set():

                method_frame, props, body = mq_channel.basic_get(queue='sync-to-master')

                """
                The message received is a JSON object with the following structure:

                msg = {
                        'type': 'Pipeline'/'Stage'/'Task',
                        'object': json/dict
                        }
                """                

                if body:

                    msg = json.loads(body)

                    self._prof.prof('received obj with state %s for sync'%msg['object']['state'], uid=msg['object']['uid'])

                    if msg['type'] == 'Task':                        

                        completed_task = Task()
                        completed_task.from_dict(msg['object'])
                        self._logger.info('Received %s with state %s'%(completed_task.uid, completed_task.state))

                        # Traverse the entire workflow to find the correct task
                        for pipe in self._workflow:

                            with pipe._stage_lock:

                                if not pipe.completed:
                                    if completed_task._parent_pipeline == pipe.uid:
                                
                                        for stage in pipe.stages:

                                            if completed_task._parent_stage == stage.uid:

                                                for task in stage.tasks:

                                                    if (completed_task.uid == task.uid)and(completed_task.state != task.state):
                                                        
                                                        task.state = str(completed_task.state)
                                                        self._logger.debug('Found task %s with state %s'%(task.uid, task.state))

                                                        if completed_task.path:
                                                            task.path = str(completed_task.path)

                                                        #print 'Syncing task %s with state %s'%(task.uid, task.state)

                                                        mq_channel.basic_publish(   exchange='',
                                                                                    routing_key=props.reply_to,
                                                                                    properties=pika.BasicProperties(
                                                                                        correlation_id = props.correlation_id),
                                                                                    body='%s-ack'%task.uid)

                                                        self._prof.prof('publishing sync ack for obj with state %s'%
                                                                                            msg['object']['state'], 
                                                                                            uid=msg['object']['uid']
                                                                                        )

                                                        mq_channel.basic_ack(delivery_tag = method_frame.delivery_tag)

                                                        #print 'Synced task %s with state %s'%(task.uid, task.state)


                    elif msg['type'] == 'Stage':

                        completed_stage = Stage()
                        completed_stage.from_dict(msg['object'])
                        self._logger.info('Received %s with state %s'%(completed_stage.uid, completed_stage.state))

                        # Traverse the entire workflow to find the correct stage
                        for pipe in self._workflow:

                            with pipe._stage_lock:

                                if not pipe.completed:
                                    if completed_stage._parent_pipeline == pipe.uid:
                                        self._logger.info('Found parent pipeline: %s'%pipe.uid)
                                
                                        for stage in pipe.stages:

                                            if (completed_stage.uid == stage.uid)and(completed_stage.state != stage.state):              

                                                self._logger.debug('Found stage %s'%stage.uid)

                                                stage.state = str(completed_stage.state)

                                                mq_channel.basic_publish(   exchange='',
                                                                            routing_key=props.reply_to,
                                                                            properties=pika.BasicProperties(
                                                                                correlation_id = props.correlation_id),
                                                                            body='%s-ack'%stage.uid)


                                                self._prof.prof('publishing sync ack for obj with state %s'%
                                                                                        msg['object']['state'], 
                                                                                        uid=msg['object']['uid']
                                                                                    )

                                                mq_channel.basic_ack(delivery_tag = method_frame.delivery_tag)


                    elif msg['type'] == 'Pipeline':

                        completed_pipeline = Pipeline()
                        completed_pipeline.from_dict(msg['object'])

                        self._logger.info('Received %s with state %s'%(completed_pipeline.uid, completed_pipeline.state))

                        # Traverse the entire workflow to find the correct pipeline
                        for pipe in self._workflow:

                            with pipe._stage_lock:

                                if not pipe.completed:

                                    if (completed_pipeline.uid == pipe.uid)and(completed_pipeline.state != pipe.state):

                                        pipe.state = str(completed_pipeline.state)

                                        if completed_pipeline.completed:
                                            pipe._completed_flag.set()

                                        self._logger.info('Found pipeline %s, state %s, completed %s'%( pipe.uid, 
                                                                                                        pipe.state, 
                                                                                                        pipe.completed)
                                                                                                    )

                                        # Reply with ack msg to the sender
                                        mq_channel.basic_publish(   exchange='',
                                                                    routing_key=props.reply_to,
                                                                    properties=pika.BasicProperties(
                                                                                correlation_id = props.correlation_id),
                                                                    body='%s-ack'%pipe.uid)

                                        self._prof.prof('publishing sync ack for obj with state %s'%
                                                                                        msg['object']['state'], 
                                                                                        uid=msg['object']['uid']
                                                                                    )


                                        mq_channel.basic_ack(delivery_tag = method_frame.delivery_tag)


            self._prof.prof('terminating synchronizer', uid=self._uid)

        except KeyboardInterrupt:

            self._logger.error('Execution interrupted by user (you probably hit Ctrl+C), '+
                                'trying to terminate synchronizer thread gracefully...')

            self._end_sync.set()
            raise KeyboardInterrupt



        except Exception, ex:

            self._logger.error('Unknown error in synchronizer: %s. \n Terminating thread'%ex)
            print traceback.format_exc()
            self._end_sync.set()
            raise Error(text=ex)  

    # ------------------------------------------------------------------------------------------------------------------