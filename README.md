[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

# Strainy

Strainy is a graph-based phasing algorithm, that takes a de novo assembly graph (in gfa format) and simplifies it by combining phasing information and graph structure.

<p align="center">
<img width="694" alt="Screenshot 2023-01-30 at 16 47 16" src="https://user-images.githubusercontent.com/82141791/215481164-2b23544f-589d-4cd2-83f9-a6668ecb8ca6.png">
</p>

## Conda Installation

The recommended way of installing is through [conda](https://conda.io/projects/conda/en/latest/user-guide/install/index.html):

```
git clone https://github.com/katerinakazantseva/stRainy
cd stRainy
git submodule update --init
make -C submodules/Flye
conda env create -f environment.yml -n strainy
```

Note that if you use an M1 conda installation, you should run `conda config --add subdirs osx-64` before installation. 
Find details [**here**](https://github.com/conda/conda/issues/11216)

Once installed, you will need to activate the conda environment prior to running:

```
conda activate strainy
./strainy.py -h
```

## Quick usage example

After successful installation, you should be able to run:

```
conda activate strainy
./strainy.py -g test_set/toy.gfa -q test_set/toy.fastq.gz -o out_strainy -m hifi 
```


## Input requirements

Strainy supports PacBio HiFi and Nanopore (Guppy5+) sequencing. 

The two main inputs to Strainy are:
1. **GFA file**: A de novo metagenomic assembly that can be produced with [**metaFlye**](https://github.com/fenderglass/Flye) or minigraph.
For metaFlye parameters, please see **Improving de novo metagenomic assemblies** below.
2. **FASTQ file** containing reads to be aligned to the fasta reference generated from the GFA file).

## Improving de novo metagenomic assemblies

We have developed Strainy using metaFlye metagenomic assembly graphs as input. The recommended
set of parameters is `--meta --keep-haplotypes --no-alt-contigs -i 0`. 

Note that `-i 0` disables metaFlye's polishing procedure, which we found to improve read assignment
to bubble branches during `minimap2` realignment. `--keep-haplotypes` retains structural
variations between strains on the assembly graph. `--no-alt-contigs` disables the output of
"alternative" contigs, which can later confuse the read aligner.

## Usage and outputs
Strainy has 2 stages: **phase** and **transform**. By default, Strainy will perform both. Please see Parameter Description section for the full list of available arguments:

```
./strainy.py -g [gfa_file] -q [fastq_file] -m [mode] -o [output_dir]
```  

 **1. phase** stage performs read clustering, and produces csv files detailing these clusters. A bam file is also produced, which can be used to visualize the clusters.

<p align="center">
<img width="500" alt="Screenshot 2023-01-30 at 17 01 47" src="https://user-images.githubusercontent.com/82141791/215484889-6a032cc0-9c90-4a26-9689-7d5cb41a2ab5.png">
</p>

<br>

**2. transform** stage transforms and simplifies the initial assembly graph, producing the strain resolved gfa file: `strain_unitigs.gfa`

<p align="center">
<img width="500" alt="Screenshot 2023-01-30 at 16 45 20" src="https://user-images.githubusercontent.com/82141791/215480788-3b895736-c43e-43db-a820-6f46c3216a81.png">
</p>

## Parameter description

| Argument  | Description |
| ------------- | ------------- |
|-o, --output	|Output directory|
|-g, --gfa	|Input assembly graph (.gfa) (may be produced with metaFlye or minigraph)|
|-q, --fastq	|FASTQ file containing reads ( PacBio HiFi or  Nanopore sequencing)|
|-m, --mode	|Type of the reads {hifi,nano}|
|-s, --stage (Optional)	| Stage to run: phase, transform or e2e (phase + transform) (default: e2e)|
| --snp (Optional)	| .vcf file, with variants of the desired allele frequency. If not provided, Strainy will use the built-in pileup-based caller|
|-b, --bam (Optional)	| .bam file generated by aligning the input reads to the input graph, minimap2 will be used to generate a .bam file if not provided|
| -a, --allele-frequency (Optional)	| Allele frequency threshold for built-in pileup-based caller. Will only work if --snp is not used (default: None)|
| -d, --cluster-divergence (Optional)|	The maximum number of total mismatches allowed in the cluster per 1 kbp. Should be selected depending on SNP rates and their accuracy. Higher values can reduce high fragmentation at the cost of clustering accuracy (default: None)|
| --unitig-split-length (Optional)	|The length (in kb) which the unitigs that are longer will be split, set 0 to disable (default: 50 kb)|
|--min-unitig-coverage (Optional)	|The minimum coverage threshold for phasing unitigs, unitigs with lower coverage will not be phased (default: 20)|
|--max-unitig-coverage (Optional)	|The maximum coverage threshold for phasing unitigs, unitigs with higher coverage will not be phased (default: 500)|
|-t, --threads (Optional)	| Number of threads to use (default: 4)|
|--debug (Optional) |	Enables debug mode for extra logs and output |

## Output description





**strain_contigs.gfa**

The graph (GFA format) represents the  phased  assembly before simplifying links and merging contigs. In this version, the  graph includes the phasing result of each individual unitig only.

 **strain_unitigs.gfa**
 
The graph (GFA format) represents the  phased  assembly after simplifying links and merging contigs. This is the final version of the graph showing the connections between unitigs and containing extended haplotypes.

**strain_variants.vcf** 

When users don't provide their own VCF file, stRainy utilizes its built-in variant caller to produce a VCF file containing the detected variants. The caller is based on mpileup and includes strand-bias detection. Frequency will be processed according to the specified AF parameter or its default value.

**alignment_phased.bam**	

When users do not provide their own alignments, stRainy conducts the alignment of input reads to the input GFA using mpuleup

**multiplicity_stats.txt** 

The output statistics file provides information regarding the multiplicity and strain divergence info)

**phased_unitig_info_table.csv**

The output statistics file provides key metrics (length, coverage, SNP rate) of the phased unitigs.

**reference_unitig_info_table.csv**

The output statistics file provides key metrics (length, coverage, SNP rate) of the reference unitigs.

## Acknowledgements

Consensus function of Strainy is [**Flye**](https://github.com/fenderglass/Flye)

Community detection algorithm is [**Karate club**](https://github.com/benedekrozemberczki/KarateClub/blob/master/docs/source/notes/introduction.rst)

## Contributers

Strainy was originally developed at at [**Kolmogorov lab at NCI**](https://ccr.cancer.gov/staff-directory/mikhail-kolmogorov)  

Code contributors:
- Ekaterina Kazantseva
- Ataberk Donmez
- Mikhail Kolmogorov

## Citation

Ekaterina Kazantseva, Ataberk Donmez, Mihai Pop, Mikhail Kolmogorov.
"Strainy: assembly-based metagenomic strain phasing using long reads"
bioRxiv 2023, https://doi.org/10.1101/2023.01.31.526521

## License

Shield: [![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg
