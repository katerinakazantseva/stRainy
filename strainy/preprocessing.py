import subprocess
import os
import logging

import pysam
import gfapy

from strainy.params import StRainyArgs

logger = logging.getLogger()

def create_bam_file(fasta_file, fastq_file, output_path, index=True):
    """
    Create a .bam file, requires user provided --fastq argument containing reads.
    """
    logger.info(f"Creating bam file from {fasta_file} and {fastq_file}")
    minimap_mode = "map-ont" if StRainyArgs().mode == "nano" else "map-hifi"
    subprocess.check_output(f"minimap2 -ax {minimap_mode} {fasta_file} {fastq_file} | " \
                            f"samtools sort -@4 -t {StRainyArgs().threads} > {output_path}",
                            shell=True)
    if index:
        pysam.samtools.index(f"{output_path}", f"{output_path}.bai")
    logger.info(".bam file created!")


def gfa_to_fasta(gfa_path, output_path):
    """
    Creates a fasta file from the input gfa file. This is needed if the user
    omitted the optional -f argument or if the input graph is modified as a
    result of --split-long-unitigs argument.
    """
    fasta_cmd = f"""awk '/^S/{{print ">"$2"\\n"$3}}' {gfa_path} > {output_path}"""
    try:
        logger.info(f'Creating fasta file from the gfa file {gfa_path}')
        subprocess.check_output(fasta_cmd, shell=True, capture_output=False, stderr=open(os.devnull, "w"))
        StRainyArgs().fa = output_path
        logger.info('Done!')

    except subprocess.CalledProcessError as e:
        logger.error(e)
        raise Exception(f'Error while creating fasta file from the gfa file: {gfa_path} ' \
                        f'Optionally, you can create a fasta file yourself and provide it with "-f file.fasta"')


def add_gfa_line(input_graph, *args):
    """
    Add a gfa line to the input graph. Works for S and L lines.
    """
    line = '\t'.join(args)
    input_graph.add_line(line)

def split_long_unitigs(input_graph, output_path):
    """
    Replaces unitigs with lengths greater than StRainyArgs().splen with multiple
    shorter unitigs for better load balancing accross threads. The number of new
    unitigs will be created is the ceiling of unitig.length / StRainyArgs().splen
    The leftmost newly created unitig inherits the incoming (dovetails_L) edges
    of the original unitig and the rightmost new unitig inherits the outgoing
    (dovetails_R) edges. Other unitigs in between form a chain from one end to
    the other.
    The modified graph is saved to a new file and used for the rest of the
    stRainy pipeline inestead of the original graph. New bam and fasta files 
    need to be generated. 
    """
    # Convert user provided -splen from kb to b
    split_length = int(StRainyArgs().splen * 1000)
    for unitig in input_graph.segments:
        if unitig.length > split_length:
            # number of unitigs that will replace the original unitig
            n_new_unitigs = -(unitig.length // -split_length)
            # length of the each new unitig
            new_unitig_len = unitig.length // n_new_unitigs
            # edges of the original unitig that will be removed 
            to_remove = [] 
            for i in range(n_new_unitigs):
                new_unitig_name = f"{unitig.name}_s{i+1}"
                if i == n_new_unitigs - 1:
                    # the last of the new unitigs gets the remaining bases too
                    new_unitig_seq = unitig.sequence[i*new_unitig_len:]
                else:
                    # all other unitigs get new_unitig_len number of bases
                    new_unitig_seq = unitig.sequence[i*new_unitig_len : (i+1) * new_unitig_len]

                add_gfa_line(input_graph, 'S', new_unitig_name, new_unitig_seq)

                # leftmost new unitigs inherits the L edges
                if i == 0:
                    for edge in unitig.dovetails_L:
                        # new_edge_str[1]: from_name
                        # new_edge_str[3]: to_name
                        new_edge_str = str(edge).split('\t')
                        if edge.from_name == unitig.name:
                            new_edge_str[1] = new_unitig_name
                        else:
                            new_edge_str[3] = new_unitig_name
                        add_gfa_line(input_graph, *new_edge_str)
                        # store the original edge to be removed later on
                        to_remove.append(edge)
                else:
                    # connect the new unitigs to one another
                    add_gfa_line(input_graph,
                                 'L',
                                 prev_unitig, '+',
                                 new_unitig_name, '+',
                                 '0M')
                # The rightmost unitig inherits the R edges
                if i == n_new_unitigs - 1:
                    for edge in unitig.dovetails_R:
                        new_edge_str = str(edge).split('\t')
                        if edge.from_name == unitig.name:
                            new_edge_str[1] = new_unitig_name
                        else:
                            new_edge_str[3] = new_unitig_name
                        add_gfa_line(input_graph, *new_edge_str)
                        to_remove.append(edge)

                prev_unitig = new_unitig_name
            # remove the original unitig and its connections from the graph
            for e in to_remove:
                input_graph.rm(e)
            unitig.disconnect()

    input_graph.to_file(output_path)


def preprocess_cmd_args(args, parser):
    """
    Do preprocessing based on the input cmd arguments before starting phasing
    or transforming
    """
    if bool(StRainyArgs().fq) != StRainyArgs().splu:
        parser.error("To split long unitigs, --fastq should be provided together" \
                    "with the --split-long-unitigs flag. Alternatively, you can omit both" \
                    "to run stRainy without without splitting the long unitigs.")
        
    if StRainyArgs().splu:
        input_graph = gfapy.Gfa.from_file(args.gfa)
        split_long_unitigs(input_graph,
                           os.path.join(args.output, 'long_unitigs_split.gfa'))
        args.gfa = os.path.join(args.output, 'long_unitigs_split.gfa')
        # need to overwrite the following StRainyArgs
        args.graph_edges = input_graph.segment_names
        gfa_to_fasta(os.path.join(args.output, 'long_unitigs_split.gfa'),
                     os.path.join(args.output,'gfa_converted.fasta'))
        args.fasta = os.path.join(args.output,'gfa_converted.fasta')
        create_bam_file(os.path.join(args.output,'gfa_converted.fasta'),
                        StRainyArgs().fq,
                        os.path.join(StRainyArgs().output, 'long_unitigs_split.bam'))
        args.bam = os.path.join(StRainyArgs().output, 'long_unitigs_split.bam')

    if StRainyArgs().fa is None:
        gfa_to_fasta(StRainyArgs().gfa)