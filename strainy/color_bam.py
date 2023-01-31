import csv
import pysam
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mt
import gfapy
import os

from metaphase.params import *


def write_bam(edge, I, AF):
    infile = pysam.AlignmentFile(MetaPhaseArgs.bam, "rb")
    outfile = pysam.AlignmentFile("%s/bam/coloredBAM_unitig_%s.bam" % (MetaPhaseArgs.output, edge), "wb", template=infile)
    cl = pd.read_csv("%s/clusters/clusters_%s_%s_%s.csv" % (MetaPhaseArgs.output, edge, I, AF),keep_default_na=False)
    iter = infile.fetch(edge,until_eof=True)
    cmap = plt.get_cmap('viridis')
    cl.loc[cl['Cluster'] == 'NA', 'Cluster'] = 0
    clusters=sorted(set(cl['Cluster'].astype(int)))
    cmap = cmap(np.linspace(0, 1, len(clusters)))
    colors={}
    i=0
    colors[0] = "#505050"
    try:
        clusters.remove('0')
    except: KeyError
    for cluster in clusters:
        colors[cluster]=mt.colors.to_hex(cmap[i])
        i=i+1
    cl_dict = dict(zip(cl.ReadName, cl.Cluster))
    for read in iter:
        try:
            clN=int(cl_dict[str(read).split()[0]])
            tag=colors[clN]
            read.set_tag('YC', tag, replace=False)
            outfile.write(read)
        except (KeyError):
            continue
    outfile.close()


def color(i):
    edge=MetaPhaseArgs.edges[i]

    try:
        write_bam(edge, I, AF)
        #print("color")
    except (FileNotFoundError):
        pass

#I=1000
#AF=0.1
#bam="/Users/ekaterina.kazantseva/MT/5strain_hifi_sim/minigraph2/mg2.bam"
#output="minigraph_2"
#edges=['s365']

#color(0)
