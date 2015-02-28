# blast_reporting
NCBI BLAST+ searches can output in a range of formats, but in the past only the XML format included fields like sequence description. This tool converts the BLAST XML report into 12, 24, 26 or custom column tabular and HTML reports

The tool allows almost complete control over which fields are displayed, how columns are named, and how the HTML report on each query is sectioned.  Search result records can be filtered out based on values in numeric or textual fields.  Matches (by accession id) to a selection of reference databases can be shown, and this can include a description of the matched sequence.

Currently this tool only takes as input the "Output format: BLAST XML" option of the NCBI Blast+ search tool, triggered by (for example)

blastn -outfmt 5 -query "...."

or via Galaxy by selecting the NCBI Blast+ search tool's option towards bottom of form ...

Online documentation will follow soon.
