#!/usr/bin/env python3

import sys
import os
import re
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, RawDescriptionHelpFormatter
import gfapy
import multiprocessing
import logging
import shutil

# Setting executable paths
metaphase_root = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, metaphase_root)

# needed for importing directly calling the Flye polisher
flye_root = os.path.join(metaphase_root, "submodules", "Flye")
sys.path.insert(0, flye_root)


from metaphase.phase import phase_main
from metaphase.transform import transform_main
from metaphase.params import MetaPhaseArgs
from metaphase.logging import set_thread_logging


logger = logging.getLogger()


def main():
    BIN_TOOLS = ["samtools", "bcftools"]
    for tool in BIN_TOOLS:
        if not shutil.which(tool):
            print("{} not installed".format(tool), file=sys.stderr)
            return 1

    parser = ArgumentParser(formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument("stage", help="stage to run: either phase or transform")
    parser.add_argument("-s", "--snp", help="vcf file", default=None)
    parser.add_argument("-t", "--threads", help="number of threads", type=int, default=4)

    requiredNamed = parser.add_argument_group('required named arguments')
    requiredNamed.add_argument("-o", "--output", help="output dir",required=True)
    requiredNamed.add_argument("-b", "--bam", help="bam file",required=True)
    requiredNamed.add_argument("-g", "--gfa", help="gfa file",required=True)
    requiredNamed.add_argument("-f", "--fa", help="fa file",required=True)
    requiredNamed.add_argument("-m", "--mode", help="", choices=["hifi", "nano"], required=True)

    args = parser.parse_args()

    bam_index = re.sub(".bam", ".bam.bai", args.bam)
    bam_index_exist = os.path.exists(bam_index)
    if bam_index_exist == False:
        raise Exception("No index file found (%s) Please create index using \"samtools index\"." % bam_index)

    #important so that global variables are inherited
    multiprocessing.set_start_method("fork")

    #global arguments storage
    MetaPhaseArgs.output = args.output
    MetaPhaseArgs.bam = args.bam
    MetaPhaseArgs.gfa = args.gfa
    MetaPhaseArgs.fa = args.fa
    MetaPhaseArgs.mode = args.mode
    MetaPhaseArgs.snp = args.snp
    MetaPhaseArgs.threads = args.threads
    MetaPhaseArgs.flye = os.path.join(metaphase_root, "submodules", "Flye", "bin", "flye")
    MetaPhaseArgs.gfa_transformed = "%s/transformed_before_simplification.gfa" % args.output
    MetaPhaseArgs.gfa_transformed1 = "%s/transformed_after_simplification.gfa" % args.output
    MetaPhaseArgs.gfa_transformed2 = "%s/transformed_after_simplification_merged.gfa" % args.output
    MetaPhaseArgs.log_phase = os.path.join(args.output, "log_phase")
    MetaPhaseArgs.log_transform = os.path.join(args.output, "log_transform")

    if not os.path.isdir(MetaPhaseArgs.output):
        os.mkdir(MetaPhaseArgs.output)

    input_graph = gfapy.Gfa.from_file(args.gfa)
    MetaPhaseArgs.edges = input_graph.segment_names
    ###

    set_thread_logging(MetaPhaseArgs.output, "root", None)

    if args.stage == "phase":
        sys.exit(phase_main())
    elif args.stage == "transform":
        sys.exit(transform_main())
    else:
        raise Exception("Stage should be aither phase or transform!")


if __name__ == "__main__":
    main()

