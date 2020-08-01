# UT Clara
This repository is a fork from https://github.com/iradicek/clara

UT Clara is command line tool, you can download binaries form release page or the following links
* [Linux Binaries](https://github.com/amirs7/UT-Synthesis-Project/releases/download/v1.1/ut_clara_linux.zip)
* [Mac OSX Binaries](https://github.com/amirs7/UT-Synthesis-Project/releases/download/v1.1/ut_clara_macosx.zip)

## Usage 

### Evaluation
Evaluates a program on the given input and prints the program model and trace:
```
 ut_clara eval --src ./examples/sum.correct.cpp --inputs "[1,2]"
```
### Matching
Finds a matching between two programs, if there exists any, and prints whether they match or not:
```
 ut_clara match --src ./examples/sum.correct.cpp --match-src ./examples/sum.wrong.cpp --inputs "[1,2]"
```
### Clustering
Clusters the programs in the given directory and save each cluster's representative in `clusters` directory:
```
 ut_clara  cluster --src-dir ./examples/ --inputs "[1,2]"
```
> This command ignores files that are not in the provided language

### Repair
Generates a repair for the given program regarding the correct programs in the directory specified by `--src-dir`:
```
 ut_clara  repair --src ./examples/sum.wrong.cpp --src-dir ./resources/utap/1001/accepted/  --inputs "[1,2]"

```
## Matching Programs with Different Structure

For generating repair for programs with different structure, currently a simple command is implemented which generates a repair for a given program with regard to another program. 
The different is that the repair is generated even if the correct does not have any loops and the wrong program contains a simple loop.

> Due to some conflicts with master branch, to use this command you must use the code or binaries fro`two-phase-repair`branch:
> 

```
 ut_clara  repair --src ./examples/sum.wrong.cpp --src-dir ./resources/utap/1001/accepted/  --inputs "[1,2]"

```
