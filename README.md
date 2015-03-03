# blast_reporting
NCBI BLAST+ searches can output in a range of formats, but in the past only the XML format included fields like sequence description. This tool converts the NCBI BLAST XML report into 12, 24, 26 or custom column tabular and HTML reports.  It is used as a command-line tool or via a Galaxy bioinformatics platform tool.

The tool allows almost complete control over which fields are displayed and filtered, how columns are named, and how the HTML report on each query is sectioned.  Search result records can be filtered out based on values in numeric or textual fields.  Matches (by accession id) to a selection of reference databases can be shown, and this can include a description of the matched sequence.

Currently this tool only takes as input the "Output format: BLAST XML" option of the NCBI Blast+ search tool, triggered by (for example)

blastn -outfmt 5 -query "...."

or via Galaxy by selecting the NCBI Blast+ search tool's option towards bottom of form ...

## Documentation
A fairly comprehensive user guide is available in the doc/ folder.

## Installation
The tool can be installed from https://toolshed.g2.bx.psu.edu/ .  It draws upon the XML reports generated by the NCBI Blast+ tools.

The setup of Reference Bins and the Selectable HTML Report are optional as described below.

### Using ''Reference Bins''
A reference bin file is simply a text file having line records each containing an accession id and a description.  The accession id is cross-referenced with the accession id returned with each search hit.  However we have to tell the Blast reporting tool where these tables are.  Their names and paths are listed in the fasta_reference_dbs.loc.sample, which ends up in the Galaxy install's tool-data/fasta_reference_dbs.loc file.
Example:

```
AADS00000000.1 Phanerochaete chrysosporium RP-78
AAEW02000014.2 Desulfuromonas acetoxidans DSM 684
AAEY01000007.0 Cryptococcus neoformans var. neoformans B-3501A
AAFI01000166 Dictyostelium discoideum AX4
AAFW02000169.3 Saccharomyces cerevisiae YJM789
```

Both the search result hit and the reference file accession ids are stripped of any fractional component before being compared. 

### Using the ''Selectable HTML Report'':
 - This is EXPERIMENTAL because it currently requires the "select subsets" galaxy tool with a bit of extra setup that might have to be redone as Galaxy evolves:
 - In Galaxy install and run the "Select subsets" tool from https://toolshed.g2.bx.psu.edu/.
 - Use your browser's "View frame source" option while mouse is over the "Select subsets" form.
 - Scroll down to the <input type="hidden" name="tool_state" value="..."> and copy the numeric value string into a new text file.
 - save the text file with the name "html_selectable_report_tool_state" to the tool's templates/ subfolder.  It should be alongside the html_selectable_report.py script which reads it.

## Development notes
A few changes are in the works: A galaxy form tool fix sheduled in the next month will enable setup of reference databases to be much easier.  One will only have to load each reference bin file into a Galaxy data library you can set up.
