# The Galaxy Blast Reporting tool for NCBI Blast+ Search Results

Produced by [@Public-Health-Bioinformatics](https://github.com/Public-Health-Bioinformatics)

The Blast Reporting (`blast_reporting.py`) command-line app and Galaxy tool tool generates HTML and tab-delimited tabular reports based on the XML format results of an NCBI Blast+ (`blastn` / `blastp` / `tblastn` etc.) search.

- The tool allows almost complete control over which fields are displayed, how columns are named, and how the HTML report on each query is sectioned.
- Search result records can be filtered out based on values in numeric or textual fields.
- Matches (by accession id) to a selection of reference databases can be shown, and this can include a description of the matched sequence.

Currently this tool only takes as input the "Output format: BLAST XML" option of the NCBI Blast+ search tool, triggered by (for example)

```
blastn -outfmt 5 -query "...."
```

...or via Galaxy by selecting the NCBI Blast+ search tool's option as shown below:

![Output XML Option](images/output_blast_xml.png)

Example of the HTML data report:

![Example HTML Report](images/example_html_report.png)

Example of the tabular data report:

![Example Tabular Report](images/example_tabular_report.png)

## Usage in Galaxy

The tool's form is shown below.  (Note that this custom visual appearance requires an extra installation step in the Installation section below).

![Galaxy Form](images/galaxy_form.png)

## Inputs

- **BLAST results as XML**: This list only shows files of galaxy type "blastxml". if your Blast+ search result file isn't in this list, then you need to go back and select the XML format for the blast search output.

- **Add new Numeric Filter**: Filters out rows by numeric field value conditions. Click here to add one or moreconditions (=, >=,< etc.) to a field to filter out search results. The example below shows a "greater than 97%" filter on the percentage identity (pident) field:

![Numeric Filter](images/numeric_filter.png)

- Add new Text Filter: If you want to accept or reject search result records based on one or more textual terms, put them in a comma-delimited list. Select "excludes text" to reject any records that have one or more of those terms; or "has text" to keep only those that have one or more of the terms.

![Text Filter](images/text_filter.png)

- Throw out redundant hits: If a query matches more than one location in a long sequence, this will only show the hit with the best match. Otherwise each locale hit will be reported on a separate line.

- Row limit (per query): Only the first N results will be shown for a query. 0 = no filtering.

## Basic Report Field Output
This section allows one to select the number of fields to output by selecting from a number of pre-defined formats, and/or by selecting individual fields. By default, results aresorted by Blast+ search score in descending order.

![Basic Report Field Output](images/basic_report_field_output.png)

The following fields can be included or added to an existing report format:

| Column | NCBI name    | Description                                  |
|--------|--------------|----------------------------------------------|
| 1      | qseqid       | Query Seq-id (ID of your sequence)           |
| 2      | sseqid       | Subject Seq-id (ID of the database hit)      |
| 3      | pident       | Percentage of identical matches              |
| 4      | length       | Alignment length                             |
| 5      | mismatch     | Number of mismatches                         |
| 6      | gapopen      | Number of gap openings                       |
| 7      | qstart       | Start of alignment in query                  |
| 8      | qend         | End of alignment in query                    |
| 9      | sstart       | Start of alignment in subject (database hit) |
| 10     | send         | End of alignment in subject (database hit)   |
| 11     | evalue       | Expectation value (E-value)                  |
| 12     | bitscore     | Bit score                                    |
| 13     | sallseqid    | All subject Seq-id(s), separated by a ';'    |
| 14     | score        | Raw score                                    |
| 15     | nident       | Number of identical matches                  |
| 16     | positive     | Number of positive-scoring matches           |
| 17     | gaps         | Total number of gaps                         |
| 18     | ppos         | Percentage of positive-scoring matches       |
| 19     | qframe       | Query frame                                  |
| 20     | sframe       | Subject frame                                |
| 21     | qseq         | Aligned part of query sequence               |
| 22     | sseq         | Aligned part of subject sequence             |
| 23     | qlen         | Query sequence length                        |
| 24     | slen         | Subject sequence length                      |
| 25     | pcov         | Percentage coverage                          |
| 26     | sallseqdescr | All subject Seq-descr(s), separated by a ',' |

The "**Add new Field**" function enables one to add a field from the list above to the report. Adding a field that already exists in a 12/24/26 column report allows one to change the label or sorting of that column. Within a query result, added fields can be the primary, secondary, tertiary etc. sort (ascending or descending, or with the "no sort" option which does not affect the overall sort). The field can be included as:

- a column in both tabular and HTML report.
- a hidden column in the HTML report (so it can be used in calculations but not appear). It is not shown on the tabular report either.
- a table section in the HTML report. These table sections are separated by a bold line.
- a report section (within a query result area, each report section gets its own table of data).

![Add A New Field](images/add_new_field.png)

The empty text input field above allows one to change the default label of a column.

In the tabular report, fields marked as table or report sections remain as columns but sorting is still carried out according to those fields' settings.

Note that after running the Galaxy tool version of this command, you can access the "view details" ("i" information icon) link of a job to see the "Job Command-Line:" that was executed. Running this almost verbatim via the command line should generate the same results.