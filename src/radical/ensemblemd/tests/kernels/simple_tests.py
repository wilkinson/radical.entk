""" Tests cases
"""
import os
import sys
import glob
import unittest

import radical.ensemblemd

#-----------------------------------------------------------------------------
#
class SimpleKernelTests(unittest.TestCase):

    def setUp(self):
        # clean up fragments from previous tests
        pass

    def tearDown(self):
        # clean up after ourselves
        pass

    #-------------------------------------------------------------------------
    #
    def test__amber_kernel(self):
        """Basic test of the AMBER kernel.
        """
        k = radical.ensemblemd.Kernel(name="md.amber")
        _kernel = k._bind_to_resource("*")
        assert type(_kernel) == radical.ensemblemd.kernel_plugins.md.amber.Kernel, _kernel

        # Test kernel specifics here:
        k = radical.ensemblemd.Kernel(name="md.amber")
        k.arguments = ["--mininfile=abc", "--mdinfile=def", "--topfile=ghi","--cycle=1"]

        k._bind_to_resource("*")
        assert k._cu_def_executable == "/bin/bash", k._cu_def_executable
        assert k.arguments == ["--mininfile=abc", "--mdinfile=def", "--topfile=ghi","--cycle=1"], k.arguments
        assert k._cu_def_pre_exec == [], k._cu_def_pre_exec
        assert k._cu_def_post_exec == [], k._cu_def_post_exec

        k._bind_to_resource("stampede.tacc.utexas.edu")
        assert k._cu_def_executable == "/bin/bash", k._cu_def_executable
        assert k.arguments == ["--mininfile=abc", "--mdinfile=def", "--topfile=ghi","--cycle=1"], k.arguments
        assert k._cu_def_pre_exec == ["module load TACC", "module load amber"], k._cu_def_pre_exec
        assert k._cu_def_post_exec == [], k._cu_def_post_exec

        #k._bind_to_resource("archer")
        #assert k._cu_def_executable == "pmemd.MPI", k._cu_def_executable
        #assert k.arguments == ["-1", "-2", "-3"], k.arguments
        #assert k._cu_def_pre_exec == ["module load packages-archer","module load amber"], k._cu_def_pre_exec
        #assert k._cu_def_post_exec == [], k._cu_def_post_exec


    #-------------------------------------------------------------------------
    #
    def test__coco_kernel(self):
        """Basic test of the CoCo kernel.
        """
        k = radical.ensemblemd.Kernel(name="md.coco")
        _kernel = k._bind_to_resource("*")
        assert type(_kernel) == radical.ensemblemd.kernel_plugins.md.coco.Kernel, _kernel

        # Test kernel specifics here:
        k = radical.ensemblemd.Kernel(name="md.coco")
        k.arguments = ["--mininfile=abc", "--mdinfile=def", "--topfile=ghi","--cycle=1"]

        k._bind_to_resource("*")
        assert k._cu_def_executable == "/bin/bash", k._cu_def_executable
        assert k.arguments == ["--mininfile=abc", "--mdinfile=def", "--topfile=ghi","--cycle=1"], k.arguments
        assert k._cu_def_pre_exec == [], k._cu_def_pre_exec
        assert k._cu_def_post_exec == [], k._cu_def_post_exec

        k._bind_to_resource("stampede.tacc.utexas.edu")
        assert k._cu_def_executable == "/bin/bash", k._cu_def_executable
        assert k.arguments == ["--mininfile=abc", "--mdinfile=def", "--topfile=ghi","--cycle=1"], k.arguments
        assert k._cu_def_pre_exec == ["module load TACC", "module load amber"], k._cu_def_pre_exec
        assert k._cu_def_post_exec == [], k._cu_def_post_exec
        pass

    #-------------------------------------------------------------------------
    #
    def test__gromacs_kernel(self):
        """Basic test of the GROMACS kernel.
        """
        k = radical.ensemblemd.Kernel(name="md.gromacs")
        _kernel = k._bind_to_resource("*")
        assert type(_kernel) == radical.ensemblemd.kernel_plugins.md.gromacs.Kernel, _kernel

        # Test kernel specifics here:
        pass

    #-------------------------------------------------------------------------
    #
    def test__lsdmap_kernel(self):
        """Basic test of the LSDMAP kernel.
        """
        k = radical.ensemblemd.Kernel(name="md.lsdmap")
        _kernel = k._bind_to_resource("*")
        assert type(_kernel) == radical.ensemblemd.kernel_plugins.md.lsdmap.Kernel, _kernel

        # Test kernel specifics here:
        pass
