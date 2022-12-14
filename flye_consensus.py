import multiprocessing
import subprocess
import os
import shutil
import random
import re

import pysam
from Bio import SeqIO, Align
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from params import *


def calculate_coverage(position, read_limits):
    """
    Calculates and returns the coverage for a given position that is relative to the reference seq, not the aligment
    string
    """
    coverage = 0
    for read in read_limits:
        if read[0] < position < read[1]:
            coverage += 1
    return coverage


class FlyeConsensus:
    def __init__(self, bam_file_name, gfa_file_name, num_processes=1, consensus_dict={}, lock=None,
                 indel_block_length_leniency = 5):
        self._bam_file = pysam.AlignmentFile(bam_file_name, "rb")

        self._name_indexed_list = []
        for i in range(num_processes):
            self._name_indexed_list.append(pysam.IndexedReads(pysam.AlignmentFile(bam_file_name, "rb")))
            self._name_indexed_list[i].build()

        self._num_processes = num_processes
        self._bam_header = self._bam_file.header.copy()
        self._gfa_file = gfapy.Gfa.from_file(gfa_file_name)
        self._consensus_dict = consensus_dict
        self._lock = multiprocessing.Lock() if lock is None else lock
        self._indel_block_length_leniency = indel_block_length_leniency
        self._coverage_limit = 3

        self._key_hit = 0
        self._key_miss = 0

        self._debug_count = 0
        self._call_count = 0

    def get_consensus_dict(self):
        return self._consensus_dict.copy()

    def print_cache_statistics(self):
        print(f"Total number of key hits and misses for consensus computation:")
        print(f" H:{self._key_hit}, M:{self._key_miss}")


    def extract_reads(self, read_names, output_file, edge=""):
        """
        based on the code by Tim Stuart https://timoast.github.io/blog/2015-10-12-extractreads/
        Extract the reads given query names to a new bam file
        """
        cluster_start = -1
        cluster_end = -1
        read_limits = []
        if self._num_processes == 1:
            pid = 0
        else:
            pid = int(re.split('\'|-', str(multiprocessing.current_process()))[2]) - 1

        read_list = []  # stores the reads to be written after the cluster start/end is calculated
        for name in read_names:
            try:
                self._name_indexed_list[pid].find(name)
            except KeyError:
                pass
            else:
                iterator = self._name_indexed_list[pid].find(name)
                with self._lock:
                    for x in iterator:
                        if x.reference_name == edge:
                            if x.reference_start < cluster_start or cluster_start == -1:
                                cluster_start = x.reference_start
                            if x.reference_end > cluster_end or cluster_end == -1:
                                cluster_end = x.reference_end
                            read_list.append(x)
                            read_limits.append((x.reference_start, x.reference_end))

        out = pysam.Samfile(output_file, "wb", header=self._bam_header)
        for x in read_list:
            temp_dict = x.to_dict()
            temp_dict["ref_pos"] = str(int(temp_dict["ref_pos"]) - cluster_start)
            y = x.from_dict(temp_dict, x.header)  # create a new read from the modified dictionary
            out.write(y)

        out.close()
        return cluster_start, cluster_end, read_limits

    def flye_consensus(self, cluster, edge, cl, debug=False):
        """
        Computes the Flye based consensus of a cluster of reads for a specific edge.
        cluster: id (int)
        cl: dataframe with columns read_name and cluster(id)
        edge: edge name (str)
        """

        # check if the output for this cluster-edge pair exists in the cache
        consensus_dict_key = f"{cluster}-{edge}"
        with self._lock:
            if consensus_dict_key in self._consensus_dict:
                self._key_hit += 1
                return self._consensus_dict[consensus_dict_key]
            self._key_miss += 1

        # fetch the read names in this cluster and extract those reads to a new bam file to be used by the
        # Flye polisher
        reads_from_curr_cluster = cl.loc[cl["Cluster"] == cluster]["ReadName"].to_numpy()  # store read names
        salt = random.randint(1000, 10000)
        fprefix = "%s/flye_inputs/" % output
        cluster_start, cluster_end, read_limits = self.extract_reads(reads_from_curr_cluster,
                                                        f"{fprefix}cluster_{cluster}_reads_{salt}.bam", edge)

        print((f"CLUSTER:{cluster}, CLUSTER_START:{cluster_start}, CLUSTER_END:{cluster_end}, EDGE:{edge},"
               f"# OF READS:{len(reads_from_curr_cluster)}"))

        # access the edge in the graph and cut its sequence according to the cluster start and end positions
        # this sequence is written to a fasta file to be used by the Flye polisher
        edge_seq_cut = (self._gfa_file.line(edge)).sequence[cluster_start:cluster_end]
        fname = f"{fprefix}{edge}-cluster{cluster}-{salt}"
        record = SeqRecord(
            Seq(edge_seq_cut),
            id=f"{edge}",
            name=f"{edge} sequence cut for cluster {cluster}",
            description=""
        )
        SeqIO.write([record], f"{fname}.fa", "fasta")

        # sort the bam file
        pysam.sort("-o", f"{fprefix}cluster_{cluster}_reads_sorted_{salt}.bam",
                   f"{fprefix}cluster_{cluster}_reads_{salt}.bam")
        # index the bam file
        pysam.index(f"{fprefix}cluster_{cluster}_reads_sorted_{salt}.bam")
        polish_cmd = f"{flye} --polish-target {fname}.fa " \
                     f"--pacbio-hifi {fprefix}cluster_{cluster}_reads_sorted_{salt}.bam " \
                     f"-o {output}/flye_outputs/flye_consensus_{edge}_{cluster}_{salt}"
        try:
            subprocess.check_output(polish_cmd, shell=True, capture_output=False)
        except subprocess.CalledProcessError as e:
            print("Error running the Flye polisher. Make sure the fasta file contains only the primary alignments")
            print(e)
            with self._lock:
                self._consensus_dict[consensus_dict_key] = {
                    'consensus': Seq(''),
                    'start': cluster_start,
                    'end': cluster_end
                }
            return self._consensus_dict[consensus_dict_key]

        try:
            # read back the output of the Flye polisher
            consensus = SeqIO.read(f"{output}/flye_outputs/flye_consensus_{edge}_{cluster}_{salt}/polished_1.fasta",
                                   "fasta")
        except (ImportError, ValueError) as e:
            # If there is an error, the sequence string is set to empty by default
            print("WARNING: error reading back the flye output, defaulting to empty sequence for consensus")
            if type(e).__name__ == 'ImportError':
                print('found ImportError')
            consensus = SeqRecord(
                seq=''
            )
        # delete the created input files to Flye
        if delete_files:
            os.remove(f"{fname}.fa")
            os.remove(f"{fprefix}cluster_{cluster}_reads_{salt}.bam")
            os.remove(f"{fprefix}cluster_{cluster}_reads_sorted_{salt}.bam")
            os.remove(f"{fprefix}cluster_{cluster}_reads_sorted_{salt}.bam.bai")
            shutil.rmtree(f"{output}/flye_outputs/flye_consensus_{edge}_{cluster}_{salt}")

        with self._lock:
            self._consensus_dict[consensus_dict_key] = {
                'consensus': consensus.seq,
                'start': cluster_start,
                'end': cluster_end,
                'read_limits': read_limits,
                'bam_path': f"{fprefix}cluster_{cluster}_reads_{salt}.bam",
                'reference_path': f"{fname}.fa"
            }
        return self._consensus_dict[consensus_dict_key]

    def _custom_scoring_function(self, alignment_string, intersection_start, cl1_reads, cl2_reads):
        """
        A custom distance scoring function for two sequences taking into account the artifacts of Flye consensus.
        alignment_string: a string consisting of '-', '.', '|' characters which correspond to indel, mismatch, match,
        respectively.
        Mismatches are worth 1 point, indels are 1 point each if there are more than 5 of them in a contiguous block.
        Except for the indel blocks start at at the beginning or finish at the end, those indels are ignored.
        Moreover, variants that are covered by less than self._coverage_limits are ignored (assumed match)
        """
        score = 0
        indel_length = 0
        aligment_list = list(alignment_string)
        for i in range(len(aligment_list)):
            reference_position = i + intersection_start

            # ignore variants with coverage less than 3
            if ((aligment_list[i] == '-' or aligment_list[i] == '.')
                    and (calculate_coverage(reference_position, cl1_reads) < 3
                    or calculate_coverage(reference_position, cl2_reads) < 3)):
                aligment_list[i] = '|'

            if aligment_list[i] == '-':
                # igonre the indels at the first or last position
                if (i == 0) or (i == len(aligment_list) - 1):
                    continue
                else:
                    # start of an indel block
                    if aligment_list[i-1] != '-':
                        # an indel block can't start from position 0.
                        indel_length = 1
                    # continuing indel block
                    else:
                        indel_length += 1

            # a contiguous block ends
            elif aligment_list[i-1] == '-':
                if indel_length >= self._indel_block_length_leniency:
                    score += indel_length
                indel_length = 0

            # mismatch
            if aligment_list[i] == '.':
                score += 1
        return score

    def _log_alignment_info(self, alignment_string, first_cl_dict, second_cl_dict,
                            score, intersection_start, intersection_end):
        if self._num_processes == 1:
            pid = 0
        else:
            pid = int(re.split('\'|-', str(multiprocessing.current_process()))[2]) - 1
        fname = f"{output}/distance_inconsistency-{pid}.log"
        with open(fname, 'a+') as f:
            """
            Things to write to the file:
            A different file for each process (filename{pid}.log)
            Alignment string,
            calculated score
            for each cluster:
                consensuses
                read start and end positions 
            """
            # TODO: thread IDs are incorrect
            f.write("ALIGNMENT:\n")
            f.write(alignment_string + '\n')
            mismatch_positions = [i for i in range(len(alignment_string)) if alignment_string.startswith('.', i)]
            f.write(f"# OF MISMATCHES: {len(mismatch_positions)}\n")
            f.write(f"MISMATCH POSITIONS: {mismatch_positions}\n")
            f.write(f"SCORE:{score}\n")
            length = intersection_end - intersection_start
            f.write(f"INTERSECTION AREA:({intersection_start}, {intersection_end}),"
                    f"LENGTH:{length}\n")

            # Calculate coverages of mismatches for both clusters
            first_cl_mismatch_coverages = []
            second_cl_mismatch_coverages = []
            for i in mismatch_positions:
                # i is relative to the alignment string
                first_cl_mismatch_coverages.append(
                    calculate_coverage(i + intersection_start, first_cl_dict['read_limits'])
                )
                second_cl_mismatch_coverages.append(
                    calculate_coverage(i + intersection_start, second_cl_dict['read_limits'])
                )

            f.write("FIRST CLUSTER:\n")
            f.write("\tREADS:\n")
            f.write(f"\t{first_cl_dict['read_limits']}\n")
            f.write(f"\tMISMATCH COVERAGES: {first_cl_mismatch_coverages}\n")
            avg_coverage = 0
            for read in first_cl_dict['read_limits']:
                avg_coverage += read[1] - read[0]
            avg_coverage = "{:.2f}".format(avg_coverage / len(first_cl_dict['consensus']))
            f.write(f"\tAVERAGE COVERAGE:{avg_coverage}\n")
            f.write(f"\tBAM FILE PATH:{first_cl_dict['bam_path']}\n")
            f.write(f"\tREFERENCE FILE PATH:{first_cl_dict['reference_path']}\n")

            f.write("SECOND CLUSTER:\n")
            f.write("\tREADS:\n")
            f.write(f"\t{second_cl_dict['read_limits']}\n")
            f.write(f"\tMISMATCH COVERAGES: {second_cl_mismatch_coverages}\n")
            avg_coverage = 0
            for read in second_cl_dict['read_limits']:
                avg_coverage += read[1] - read[0]
            avg_coverage = "{:.2f}".format(avg_coverage / len(second_cl_dict['consensus']))
            f.write(f"\tAVERAGE COVERAGE:{avg_coverage}\n")
            f.write(f"\tBAM FILE PATH:{second_cl_dict['bam_path']}\n")
            f.write(f"\tREFERENCE FILE PATH:{second_cl_dict['reference_path']}\n")

            f.write("**********-------************\n\n")

    def cluster_distance_via_alignment(self, first_cl, second_cl, cl, edge, debug=False):
        """
        Computes the distance between two clusters consensus'. The distance is based on the global alignment between the
        intersecting parts of the consensus'.
        first_cl: id (int)
        second_cl: id (int)
        cl: dataframe with columns read_name and cluster(id)
        edge: edge name (str)
        """
        self._call_count += 1
        if debug:
            self._debug_count += 1
        print(f"{self._debug_count}/{self._call_count} disagreements")
        first_cl_dict = self.flye_consensus(first_cl, edge, cl, debug)
        second_cl_dict = self.flye_consensus(second_cl, edge, cl, debug)

        intersection_start = max(first_cl_dict['start'], second_cl_dict['start'])
        intersection_end = min(first_cl_dict['end'], second_cl_dict['end'])

        # clip the intersecting parts of both consensus'
        first_consensus_clipped = first_cl_dict['consensus'][
                                  intersection_start - first_cl_dict['start']:intersection_end - first_cl_dict['start']]
        second_consensus_clipped = second_cl_dict['consensus'][
                                   intersection_start - second_cl_dict['start']:intersection_end - second_cl_dict['start']]

        if (intersection_end - intersection_start < 1
                or len(first_consensus_clipped) == 0
                or len(second_consensus_clipped) == 0):
            print(f'Intersection length for clusters is less than 1 for clusters {first_cl}, {second_cl} in {edge}')
            return 1

        aligner = Align.PairwiseAligner()
        aligner.mode = 'global'
        aligner.match_score = 1
        aligner.mismatch_score = -1
        aligner.gap_score = -1
        alignments = aligner.align(first_consensus_clipped, second_consensus_clipped)
        # get the alignment string consisting of (- . |)
        alignment_string = alignments[0].format().split('\n')[1]
        score = self._custom_scoring_function(alignment_string, intersection_start,
                                              first_cl_dict['read_limits'], second_cl_dict['read_limits'])

        if debug:
            self._log_alignment_info(alignment_string, first_cl_dict, second_cl_dict,score,
                                     intersection_start, intersection_end)

        # score is not normalized!
        return score
