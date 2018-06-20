__copyright__ = "Copyright 2017-2018, http://radical.rutgers.edu"
__author__ = "Vivek Balasubramanian <vivek.balasubramaniana@rutgers.edu>"
__license__ = "MIT"

import radical.utils as ru
from radical.entk.exceptions import *
import radical.pilot as rp
import os


class Base_ResourceManager(object):

    """
    A resource manager takes the responsibility of placing resource requests on 
    different, possibly multiple, DCIs. 

    :arguments: 
        :resource_desc: dictionary with details of the resource request + access credentials of the user 
        :example: resource_desc = { 'resource'      : 'xsede.stampede', 
                                    'walltime'      : 120, 
                                    'cores'         : 64, 
                                    'project'       : 'TG-abcxyz',
                                    'queue'         : 'abc',    # optional
                                    'access_schema' : 'ssh'  # optional
                                }
    """

    def __init__(self, resource_desc, sid, rts):

        if not isinstance(resource_desc, dict):
            raise TypeError(expected_type=dict, actual_type=type(resource_desc))

        self._resource_desc = resource_desc
        self._sid = sid
        self._rts = rts
        
        # Resource reservation related parameters
        self._resource = None
        self._walltime = None
        self._cores = None
        self._project = None
        self._access_schema = None
        self._queue = None
        self._validated = False

        # Utility parameters
        self._uid = ru.generate_id( 'resource_manager.%(item_counter)04d', 
                                    ru.ID_CUSTOM, 
                                    namespace=self._sid)
        self._path = os.getcwd() + '/' + self._sid
        self._logger = ru.Logger('radical.entk.%s'%self._uid, path=self._path)
        self._prof = ru.Profiler(name='radical.entk.%s'%self._uid, path=self._path)

        # Shared data list
        self._shared_data = list()

    @property
    def resource(self):
        """
        :getter: Return user specified resource name
        """
        return self._resource

    @property
    def walltime(self):
        """
        :getter: Return user specified walltime
        """
        return self._walltime

    @property
    def cores(self):
        """
        :getter: Return user specified number of cpus
        """
        return self._cores

    @property
    def project(self):
        """
        :getter: Return user specified project ID
        """
        return self._project

    @property
    def access_schema(self):
        """
        :getter:    Return user specified access schema -- 'ssh' or 'gsissh' or 
                    None
        """
        return self._access_schema

    @property
    def queue(self):
        """
        :getter: Return user specified resource queue to be used
        """
        return self._queue

    @property
    def shared_data(self):
        """
        :getter:    list of files to be staged to remote and that are common to 
                    multiple tasks
        """
        return self._shared_data

    @shared_data.setter
    def shared_data(self, data_list):

        if not isinstance(data_list, list):
            data_list = [data_list]

        for val in data_list:
            if not isinstance(val, str):
                raise TypeError(expected_type=str, actual_type=type(val))

        self._shared_data = data_list

    # ------------------------------------------------------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------------------------------------------------------

    def get_resource_allocation_state(self):
        """
        **Purpose**: Get the state of the resource allocation
        """
        raise NotImplementedError(msg='get_resource_allocation_state() method ' +
                                  'not implemented in ResourceManager for %s' % self._rts_type)

    def completed_states(self):
        """
        **Purpose**: Test if a resource allocation was submitted
        """

        raise NotImplementedError(msg='completed_states() method ' +
                                  'not implemented in ResourceManager for %s' % self._rts_type)

    # ------------------------------------------------------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------------------------------------------------------

    def _validate_resource_desc(self):
        """
        **Purpose**: Validate the resource description provided to the ResourceManager
        """

        self._prof.prof('validating rdesc', uid=self._uid)
        self._logger.debug('Validating resource description')

        expected_keys = ['resource',
                         'walltime',
                         'cores']

        for key in expected_keys:
            if key not in self._resource_desc:
                raise Error(text='Mandatory key %s does not exist in the resource description' % key)

        if not isinstance(self._resource_desc['resource'], str):
            raise TypeError(expected_type=str, actual_type=type(self._resource_desc['resource']))

        if not isinstance(self._resource_desc['walltime'], int):
            raise TypeError(expected_type=int, actual_type=type(self._resource_desc['walltime']))

        if not isinstance(self._resource_desc['cores'], int):
            raise TypeError(expected_type=int, actual_type=type(self._resource_desc['cores']))

        if 'project' in self._resource_desc:
            if (not isinstance(self._resource_desc['project'], str)) and (not self._resource_desc['project']):
                raise TypeError(expected_type=str, actual_type=type(self._resource_desc['project']))

        if 'access_schema' in self._resource_desc:
            if not isinstance(self._resource_desc['access_schema'], str):
                raise TypeError(expected_type=str, actual_type=type(self._resource_desc['access_schema']))

        if 'queue' in self._resource_desc:
            if not isinstance(self._resource_desc['queue'], str):
                raise TypeError(expected_type=str, actual_type=type(self._resource_desc['queue']))

        self._validated = True

        self._logger.info('Resource description validated')
        self._prof.prof('rdesc validated', uid=self._uid)

        return self._validated

    def _populate(self):
        """
        **Purpose**:    Populate the ResourceManager class with the validated
                        resource description
        """

        if self._validated:

            self._prof.prof('populating rmgr', uid=self._uid)
            self._logger.debug('Populating resource manager object')

            self._resource = self._resource_desc['resource']
            self._walltime = self._resource_desc['walltime']
            self._cores = self._resource_desc['cores']

            if 'project' in self._resource_desc:
                self._project = self._resource_desc['project']

            if 'access_schema' in self._resource_desc:
                self._access_schema = self._resource_desc['access_schema']

            if 'queue' in self._resource_desc:
                self._queue = self._resource_desc['queue']

            self._logger.debug('Resource manager population successful')
            self._prof.prof('rmgr populated', uid=self._uid)
        
        else:
            raise EnTKError('Resource description not validated')
            

    def _submit_resource_request(self):
        """
        **Purpose**:    Submit resource request as per the description provided by the user
        """

        raise NotImplementedError(msg='_submit_resource_request() method ' +
                                  'not implemented in ResourceManager for %s' % self._rts_type)

    def _cancel_resource_request(self):
        """
        **Purpose**:    Cancel resource request by terminating any reservation on any acquired
                        resources or resources pending acquisition
        """

        raise NotImplementedError(msg='_cancel_resource_request() method ' +
                                  'not implemented in ResourceManager for %s' % self._rts_type)
