import multiprocessing
import pysam
import pickle
import os
import subprocess
from multiprocessing.managers import BaseManager
import logging
import shutil

from metaphase.clustering.cluster import cluster
from metaphase.color_bam import color
from metaphase.flye_consensus import FlyeConsensus
from metaphase.params import *
from metaphase.logging import set_thread_logging


logger = logging.getLogger()


class CustomManager(BaseManager):
    pass


def _thread_fun(args):
    set_thread_logging(MetaPhaseArgs.log_phase, "phase", multiprocessing.current_process().pid)
    logger.info("\n\n\t==== Processing uniting " + str(MetaPhaseArgs.edges[args[0]]) + " ====")
    cluster(args)


def phase(edges):
    if os.path.isdir(MetaPhaseArgs.log_phase):
        shutil.rmtree(MetaPhaseArgs.log_phase)
    os.mkdir(MetaPhaseArgs.log_phase)

    CustomManager.register('FlyeConsensus', FlyeConsensus)

    with CustomManager() as manager:
        default_manager = multiprocessing.Manager()
        lock = default_manager.Lock()
        empty_consensus_dict = {}
        num_processes = multiprocessing.cpu_count() if MetaPhaseArgs.threads == -1 else MetaPhaseArgs.threads
        shared_flye_consensus = manager.FlyeConsensus(MetaPhaseArgs.bam, MetaPhaseArgs.gfa, num_processes, empty_consensus_dict, lock)
        pool = multiprocessing.Pool(num_processes)
        #with multiprocessing.get_context("spawn").Pool() as pool:
        init_args = [(i, shared_flye_consensus) for i in range(len(edges))]
        pool.map(_thread_fun, init_args)
        pool.close()
        shared_flye_consensus.print_cache_statistics()
        return shared_flye_consensus.get_consensus_dict()


def color_bam(edges):
    pool = multiprocessing.Pool(3)
    pool.map(color, range(0, len(edges)))
    pool.close()
    subprocess.check_output('samtools merge %s/bam/coloredBAM.bam -f `find %s/bam -name "*unitig*.bam"`' % (MetaPhaseArgs.output, MetaPhaseArgs.output), 
                            shell=True, capture_output=False)
    subprocess.check_output('rm `find %s/bam -name "*unitig*.bam"`' % MetaPhaseArgs.output, shell=True, capture_output=False)
    pysam.samtools.index("%s/bam/coloredBAM.bam" % MetaPhaseArgs.output, "%s/bam/coloredBAM.bai" % MetaPhaseArgs.output)


def phase_main():
    #logging.info(MetaPhaseArgs)
    logger.info("Starting phasing")
    dirs = ("%s/vcf/" % MetaPhaseArgs.output,
            "%s/adj_M/" % MetaPhaseArgs.output,
            "%s/clusters/" % MetaPhaseArgs.output,
            "%s/graphs/" % MetaPhaseArgs.output,
            "%s/bam/" % MetaPhaseArgs.output,
            "%s/bam/clusters" % MetaPhaseArgs.output,
            "%s/flye_inputs" % MetaPhaseArgs.output,
            "%s/flye_outputs" % MetaPhaseArgs.output)

    for dir in dirs:
        try:
            os.stat(dir)
        except:
            os.makedirs(dir)

    consensus_dict = phase(MetaPhaseArgs.edges)
    if write_consensus_cache:
        with open(os.path.join(MetaPhaseArgs.output, consensus_cache_path), 'wb') as f:
            pickle.dump(consensus_dict, f)
    color_bam(MetaPhaseArgs.edges)


if __name__ == "__main__":
    phase_main()
