[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

# stRainy

stRainy is a graph-based phasing algorithm, that takes a de novo assembly graph (in gfa format) and simplifies it by combining phasing information and graph structure.


<img width="694" alt="Screenshot 2023-01-30 at 16 47 16" src="https://user-images.githubusercontent.com/82141791/215481164-2b23544f-589d-4cd2-83f9-a6668ecb8ca6.png">


**metaPhase.py phase** - performs reads clustering according to SNP positions using community detection approach

**metaPhase.py transfom** - transforms assembly graph 
## Conda Installation

Create a new conda envinroment and activate it
```
conda create -n metaphase python=3.8
conda activate metaphase
```

Build and install Flye
```
git clone https://github.com/fenderglass/Flye
cd Flye
python setup.py install
```
Get metaPhase source and install requirements
```
cd ~/
git clone https://github.com/katerinakazantseva/metaPhase.git
cd metaphase
pip install -r requirements.txt
```

Run test code
```
python3 metaphase.py phase  -o test_dir -b test_set/toy.bam -g test_set/toy.gfa -f test_set/toy.fasta -t 1 -m hifi 
```

## Source Installation
### Requirements
```
python3
pip
samtools
```

### Installation

**Ubuntu 20.04:**
```
$ sudo apt update && sudo apt install libbz2-dev liblzma-dev graphviz graphviz-dev bcftools
$ pip install -r requirements.txt
```

**MacOS 12:**
```
$ brew install bcftools
$ pip install -r requirements.txt
```

## Input requirements

metaPhase takes as input gfa graph (can be produced with [**metaFlye**](https://github.com/fenderglass/Flye) or minigraph), 
fasta file and BAM (reads alignned to fasta reference). Also it supports hifi and nanopore modes.

How to get fasta from gfa:
```
awk '/^S/{print ">"$2"\n"$3}’ assembly_graph_.gfa | fold > assembly_graph_sim3.fa 
```

Usage:
```
metaphase.py [-h] [-s SNP] [-t THREADS] -o OUTPUT -b BAM -g GFA -f FA -m {hifi,nano} stage

positional arguments:
  stage                 stage to run: either phase or transform

optional arguments:
  -h, --help            show this help message and exit
  -s SNP, --snp SNP     vcf file
  -t THREADS, --threads THREADS
                        number of threads

required named arguments:
  -o OUTPUT, --output OUTPUT
                        output dir
  -b BAM, --bam BAM     bam file
  -g GFA, --gfa GFA     gfa file
  -f FA, --fa FA        fa file
  -m {hifi,nano}, --mode {hifi,nano}
```

Please specify Flye path in `params.py`:
- `flye` - path to the installed Flye executable

It is not recommended to change other parameters.

## Run and outputs

```
python3 ./metaPhase.py phase -o output_dir -b bam_file -g gfa_graph -f fasta file -m mode -t threads
```
Phasing stage clusters reads and produce csv files with read names and corresponding cluster names and BAM file wich visualise reads clustering

<img width="500" alt="Screenshot 2023-01-30 at 17 01 47" src="https://user-images.githubusercontent.com/82141791/215484889-6a032cc0-9c90-4a26-9689-7d5cb41a2ab5.png">



```
python3 ./metaPhase.py transform -o output_dir -b bam_file -g gfa_graph -f fasta file -m mode -t threads
```
Transform stage transform and simplify initial assembly graph, produce  final gfa file transformed_after_simplification_merged.gfa
<img width="500" alt="Screenshot 2023-01-30 at 16 45 20" src="https://user-images.githubusercontent.com/82141791/215480788-3b895736-c43e-43db-a820-6f46c3216a81.png">

## Asknowledgements

Consesus function of metaphase is [**Flye**](https://github.com/fenderglass/Flye)

Community detection algorithm is [**Karate club**](https://github.com/benedekrozemberczki/KarateClub/blob/master/docs/source/notes/introduction.rst)


## Authors

metaPhase was originally developed at at [**Kolmogorov lab at NCI**](https://ccr.cancer.gov/staff-directory/mikhail-kolmogorov)  

Code contributors:
- Ekaterina Kazantseva
- Ataberk Donmez
- Mikhail Kolmogorov


## Citation

TBD

## License

Shield: [![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg



