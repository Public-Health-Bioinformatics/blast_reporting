#!/usr/bin/python
"""Convert a BLAST XML file to 12 column tabular output

This tool can be used both via command line and via a local Galaxy install.  
Galaxy uses .loc files as indicated by the tool_data_table_conf.xml.sample.
The command line version uses .tab versions of the above files: 
	blast_reporting_fields.loc
	fasta_reference_dbs.loc
So for command-line use, ensure the .tab files are updated to their .loc counterparts.
 
Takes three command line options, input BLAST XML filename, output tabular
BLAST filename, output format (std for standard 12 columns, or ext for the
extended 25 columns offered in the BLAST+ wrappers).

The 12 columns output are 'qseqid sseqid pident length mismatch gapopen qstart
qend sstart send evalue bitscore' or 'std' at the BLAST+ command line, which
mean:
   
====== ========= ============================================
Column NCBI name Description
------ --------- --------------------------------------------
     1 qseqid    Query Seq-id (ID of your sequence)
     2 sseqid    Subject Seq-id (ID of the database hit)
     3 pident    Percentage of identical matches
     4 length    Alignment length
     5 mismatch  Number of mismatches
     6 gapopen   Number of gap openings
     7 qstart    Start of alignment in query
     8 qend      End of alignment in query
     9 sstart    Start of alignment in subject (database hit)
    10 send      End of alignment in subject (database hit)
    11 evalue    Expectation value (E-value)
    12 bitscore  Bit score
====== ========= ============================================

The additional columns offered in the Galaxy BLAST+ wrappers are:

====== ============= ===========================================
Column NCBI name     Description
------ ------------- -------------------------------------------
    13 sallseqid     All subject Seq-id(s), separated by a ';'
    14 score         Raw score
    15 nident        Number of identical matches
    16 positive      Number of positive-scoring matches
    17 gaps          Total number of gaps
    18 ppos          Percentage of positive-scoring matches
    19 qframe        Query frame
    20 sframe        Subject frame
    21 qseq          Aligned part of query sequence
    22 sseq          Aligned part of subject sequence
    23 qlen          Query sequence length
    24 slen          Subject sequence length
====== ============= ===========================================

Very slight modifications were made to the "BLAST XML to tabular" tool that
ships with Galaxy to output two more column columns:

====== ============= ===========================================
Column NCBI name     Description
------ ------------- -------------------------------------------
    25 salltitles  All Subject Title(s), separated by a '<>'
    26 pcov          Percentage coverage
====== ============= ===========================================

Most of these fields are given explicitly in the XML file, others some like
the percentage identity and the number of gap openings must be calculated.

In addition an option exists to select particular columns for the output 
report.  Reference bin columns will be added if they have been included in
search.

A command line version can be used.  Type blast_reporting.py -h for help.

Be aware that the sequence in the extended tabular output or XML direct from
BLAST+ may or may not use XXXX masking on regions of low complexity. This
can throw the off the calculation of percentage identity and gap openings.
[In fact, both BLAST 2.2.24+ and 2.2.25+ have a subtle bug in this regard,
with these numbers changing depending on whether or not the low complexity
filter is used.]

This script attempts to produce identical output to what BLAST+ would have done.
However, check this with "diff -b ..." since BLAST+ sometimes includes an extra
space character (probably a bug).

python blast_reporting.py in_file out_tabular_file out_html_file out_format
"""
import sys
import re
import os.path
import common
import reference_bins
#import templates.html_report

if __name__ == '__main__' and __package__ is None:
	from os import path
	sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

if sys.version_info[:2] >= ( 2, 5 ):
    import xml.etree.cElementTree as ElementTree
else:
    from galaxy import eggs
    import pkg_resources; pkg_resources.require( "elementtree" )
    from elementtree import ElementTree

class GenericRecord(object): pass

class XMLRecordScan(object): 
	"""
	XML Input file usually looks like:

		<BlastOutput>
			<BlastOutput_program>blastn</BlastOutput_program>
			<BlastOutput_param>
				<Parameters>
					<Parameters_expect>0.001</Parameters_expect>
					<Parameters_sc-match>1</Parameters_sc-match>
					<Parameters_sc-mismatch>-2</Parameters_sc-mismatch>
					<Parameters_gap-open>0</Parameters_gap-open>
					<Parameters_gap-extend>0</Parameters_gap-extend>
					<Parameters_filter>L;m;</Parameters_filter>
				</Parameters>
			</BlastOutput_param>
			<Iteration>
				<Iteration_iter-num>1</Iteration_iter-num>
				<Iteration_query-ID>Query_1</Iteration_query-ID>
				<Iteration_query-def>ENA|EF604038|EF604038.1 Uncultured bacterium clone 16saw43-2g09.q1k 16S ribosomal RNA gene, partial sequence</Iteration_query-def>
				<Iteration_query-len>1364</Iteration_query-len>
				<Iteration_hits>

				<Hit>
					<Hit_num>1</Hit_num>
					<Hit_id>gi|444439670|ref|NR_074985.1|</Hit_id>
					<Hit_hsps>...
						<Hsp>...
	"""
	def __init__(self, options, output_format):
		""" Creates a record object that holds field data for each <hit> iteration in Blastn XML data
		
		 .record object: holds values read in from <XML> <hit> record mainly.
		 .tags dictionary: XML tags and the record.[x] fields/attributes that should be set to tag values.
		 .column_format dictionary: Name to field count dictionary used for selecting # of output fields
		 .fieldSpec dictionary: Specification of each possible field's type (for validation), full name, and suitability for sorting, filtering, etc.
		 .custom_columns array takes list of custom columns to output. (If sorting by a column it must be in this list)
		 .reference_bins dictionary
		
		"""
		self.record = GenericRecord() # Set up so we can use object attributes.
		
		#This is a list of all incomming blast generated XML fields that we want to capture
		# self.record gets all underscored variables values as well as new derived ones in process() below
		self.tags = {
			"BlastOutput_program":  '_blast_program', 
			"Iteration_query-ID":   '_qseqid',
			"Iteration_query-def":  '_qdef',
			"Iteration_query-len":  '_qlen',	#extended+ calc
			
			"Hit_id":               '_hit_id',
			"Hit_def":              '_hit_def',	#extended+ calc
			"Hit_accession":        '_hit_acc',
			"Hit_len":              '_hit_len',
			
			"Hsp_bit-score":        '_bitscore',	#basic
			"Hsp_score":            '_score',	#extended
			"Hsp_evalue":           '_evalue',	#basic
			"Hsp_query-from":       '_qstart',	#basic, extended+ calc
			"Hsp_query-to":         '_qend',	#basic, extended+ calc
			"Hsp_hit-from":         '_sstart',	#basic
			"Hsp_hit-to":           '_send',	#basic
			"Hsp_query-frame":      '_qframe',	#extended only
			"Hsp_hit-frame":        '_sframe',	#extended only
			"Hsp_identity":         '_nident',	#extended
			"Hsp_positive":         '_positive',	#extended
			"Hsp_gaps":             '_gaps',	#extended
			"Hsp_align-len":        '_length',	#basic
			"Hsp_qseq":             '_qseq',	#extended
			"Hsp_hseq":             '_sseq',	#extended
			"Hsp_midline":          '_mseq'	#basic
		}
		
		self.column_format = {
			'std':12,
			'std+seqs':12,
			'ext':25,
			'ext+':26,
			'custom':1
		}
		
		if not output_format in self.column_format:
			common.stop_err("Format argument should be std (12 column) or ext (extended 25 columns) or ext+ (extended 26+ columns) or custom (you choose fields). Format argument x22 has been replaced with ext (extended 25 columns)")
		
		# Array of columns destined for tab-delimited output - This defines default ORDER of fields too.
		# Raw data fields that never get output: _bitscore, _evalue, _qframe, _sframe, 
		# and this that has no m_frame equivalent: _mseq 
		self.columns_in = 'qseqid sseqid pident _length mismatch gapopen _qstart _qend _sstart _send evalue bitscore \
			sallseqid _score _nident _positive _gaps ppos qframe sframe _qseq _sseq qlen slen \
			salltitles pcov accessionid stitle _mseq'.split()
		
		fieldSpecFile = os.path.join(os.path.dirname(__file__), 'blast_reporting_fields.tab')
		self.field_spec = common.FieldSpec(fieldSpecFile, self.columns_in)

		# Include first N fields from .columns according to format. 
		# In all cases qseqid is included.
		# Default everything to "column".
		columns_out = self.columns_in[0:self.column_format[output_format]]

		# This column list is designed for creating phylogeny reports.
		if output_format == 'std+seqs': columns_out.extend(['_qseq','_sseq'])

		self.columns = self.field_spec.initColumns(columns_out, options.custom_fields)

		# We're making these columns hidden for this particular HTML report format 
		# UNLESS they are mentioned in options.custom_fields
		if output_format == 'std+seqs': 
			for (ptr, target) in enumerate(self.columns):
				if target['field'] in ['_qseq','_sseq'] and options.custom_fields and not target['field'] in options.custom_fields :
					target['group'] = 'hidden' 

		# ADD SELECTED BINS TO COLUMN LIST;
		self.binManager = reference_bins.ReferenceBins()
		self.binManager.build_bins(options.reference_bins, self.columns)

	def setRecordAttr(self, tag, text):
		#self.record is a class object (not a dictionary) so using setattr()
		setattr(self.record, self.tags[tag], text) 

	# Called after set() has processed a bunch of <hit> ...</hit> tags
	def processRecord(self) :

		bline = self.record
		
		# NCBI notes: Expecting either this,
		# <Hit_id>gi|3024260|sp|P56514.1|OPSD_BUFBU</Hit_id>
		# <Hit_def>RecName: Full=Rhodopsin</Hit_def>
		# <Hit_accession>P56514</Hit_accession>
		#or,
		# <Hit_id>Subject_1</Hit_id>
		# <Hit_def>gi|57163783|ref|NP_001009242.1| rhodopsin [Felis catus]</Hit_def>
		# <Hit_accession>Subject_1</Hit_accession>
		#or,
		# <Hit_id>Subject_1</Hit_id>
		# <Hit_def>gi|57163783|ref|NP_001009242.1| rhodopsin [Felis catus]</Hit_def>
		# <Hit_accession>Subject_1</Hit_accession>
		#apparently depending on the parse_deflines switch            

		sseqid = self.record._hit_id.split(None,1)[0]

		# If Hit_id == Hit_accession AND it is a default "Subject_1" ...   
		# OR Hit_accession IN Hit_id and BL_ORD_ID|XXXX contains hit_accession
		if common.re_default_subject_id.match(sseqid) and sseqid.find(bline._hit_acc):
		# and sseqid == bline._hit_acc:
		#Place holder ID, take the first word of the subject definition
			hit_def = bline._hit_def
			sseqid = hit_def.split(None,1)[0]
		else:
			hit_def = sseqid + " " + bline._hit_def
		
		self.record.sseqid = sseqid
		
		if common.re_default_ncbi_id.match(sseqid):
			self.record.accessionid = sseqid.split('|')[3] 
		elif common.re_default_ref_id.match(sseqid):
			self.record.accessionid = sseqid.split('|')[1] 
		else: 
			# Have to use the whole string.
			self.record.accessionid = sseqid
			
		
		# NCBI notes: Expecting either this, from BLAST 2.2.25+ using FASTA vs FASTA
		# <Iteration_query-ID>sp|Q9BS26|ERP44_HUMAN</Iteration_query-ID>
		# <Iteration_query-def>Endoplasmic reticulum resident protein 44 OS=Homo sapiens GN=ERP44 PE=1 SV=1</Iteration_query-def>
		# <Iteration_query-len>406</Iteration_query-len>
		# <Iteration_hits></Iteration_hits>
		#
		#Or, from BLAST 2.2.24+ run online
		# <Iteration_query-ID>Query_1</Iteration_query-ID>
		# <Iteration_query-def>Sample</Iteration_query-def>
		# <Iteration_query-len>516</Iteration_query-len>
		# <Iteration_hits>...

		# Note BioPython's approach http://biopython.org/DIST/docs/api/Bio.SearchIO.BlastIO.blast_xml-pysrc.html
		# ... if hit_id.startswith('gnl|BL_ORD_ID|'): ...
		
		if common.re_default_query_id.match(bline._qseqid): 
		#Place holder ID, take the first word of the query definition
			qseqid = bline._qdef.split(None,1)[0]
		else:
			qseqid = bline._qseqid

		self.record.qseqid = qseqid
		
		self.record.evalue = "0.0" if bline._evalue == "0" else "%0.0e" % float(bline._evalue)

		# NCBI notes:
		#   if bline._bitscore < 100:
		#       #Seems to show one decimal place for lower scores
		#       bitscore = "%0.1f" % bline._bitscore
		#   else:
		#       #Note BLAST does not round to nearest int, it truncates
		#       bitscore = "%i" % bline._bitscore
		bitscore = float(bline._bitscore)
		self.record.bitscore = "%0.1f" % bitscore if bitscore < 100 else "%i" % bitscore

		self.record.pident = "%0.2f" % (100*float(bline._nident)/float(bline._length))

		self.record.gapopen = str(len(bline._qseq.replace('-', ' ').split())-1 + \
			len(bline._sseq.replace('-', ' ').split())-1)

		mismatch = bline._mseq.count(' ') + bline._mseq.count('+') \
		     - bline._qseq.count('-') - bline._sseq.count('-')
		#assert len(bline._qseq) == len(bline._sseq) == len(bline._mseq) == int(bline._length)
		self.record.mismatch = str(mismatch)

		# Extended fields
		#sallseqid gets ";" delimited list of first words in each hit_def "x>y>z" expression. 
		#Nov 7 2013 fix: https://github.com/peterjc/galaxy_blast/blob/master/tools/ncbi_blast_plus/blastxml_to_tabular.py
		hit_def_array = hit_def.split(" >") #Note: elem.text below converts escaped "&gt;" back to ">"
		try: 
			self.record.sallseqid = ";".join(name.split(None,1)[0] for name in hit_def_array)
		except IndexError as e:
			common.stop_err("Problem splitting multiple hit ids?\n%r\n--> %s" % (hit_def, e))

		# Calculate accession ids, and check bin(s) for them, update record accordingly.
		self.binManager.setStatus(self.record)

		self.record.ppos = "%0.2f" % (100*float(bline._positive)/float(bline._length))
		qframe = bline._qframe
		sframe = bline._sframe 
		if bline._blast_program == "blastp":
			#Probably a bug in BLASTP that they use 0 or 1 depending on format
			if qframe == "0": qframe = "1" 
			if sframe == "0": sframe = "1" 
		
		self.record.qframe = qframe
		self.record.sframe = sframe
		self.record.slen = str(int(bline._hit_len))
		self.record.qlen = str(int(bline._qlen))

		#NCBI DOCUMENTATION ON qcovs == pcov == pct_coverage == http://www.ncbi.nlm.nih.gov/IEB/ToolBox/CPP_DOC/lxr/source/include/objects/seqalign/Seq_align.hpp#L54
		#extended+
		self.record.pcov = "%0.2f" % (float(int(bline._qend) - int(bline._qstart) + 1)/int(bline._qlen) * 100)
		
		titlesArray = self.getSalltitles(hit_def_array)
		self.record.salltitles = "<>".join(titlesArray)
		self.record.stitle = titlesArray[0]

		return True # One may return false anywhere above to filter out current <Hsp> record.


	def getSalltitles(self, hit_def_array):
		""" Example salltitles is "Mus musculus ribosomal protein S8 (Rps8), mRNA <>Mus musculus ES cells cDNA, RIKEN full-length enriched library, clone:2410041L12 product:ribosomal protein S8, full insert sequence"
		"""
		salltitles = []
		try: 
			for name in hit_def_array:
				id_desc = name.split(None,1)
				if len(id_desc) == 1: salltitles.append('missing title - database issue') 
				else: salltitles.append(id_desc[1]) 
		except IndexError as e:
			common.stop_err("Problem splitting multiple hits?\n%r\n--> %s" % (hit_def, e))

		return salltitles
		
				
	# Tab-delimited order is important, so we can't just cycle through (unordered) self.record attributes.
	#
	# @uses .record object with field attributes
	# @uses .prelim_columns (used before final column selection)
	def outputTabDelimited(self):
		values = []
		
		for col in self.columns:
			values.append(getattr(self.record, col['field']))

		return '\t'.join(values) + '\n'



class ReportEngine(object):

	def __init__(self): pass

	def __main__(self):


		## *************************** Parse Command Line *****************************
		parser = common.MyParser(
			description = 'Generates tab-delimited table report based on BLAST XML results.',
			usage = 'python blast_reporting.py [blastxml_input_file] [out_format] [tabular_output_file] [option: html_output_file] [option: selection_output_file:id_1:id_2:id_3] [options]',
			epilog="""Details:

			This tool can be used both via command line and via a local Galaxy install.  
			Galaxy uses .loc files (blast_reporting_fields.loc, fasta_reference_dbs.loc)
			as indicated by the tool's tool_data_table_conf.xml.sample.  The command line script 
			uses .tab versions (located in the script's folder) which need to reflect any changes
			made in the .loc versions.
			
			Note: the selection file option is used mainly by the galaxy blast reporting tool.
			
		   [out_format] is one of:
			 "std" : standard 12 column
			 "std+seqs" : standard 12 column plus search (qseq) and matched (sseq) sequences
			 "ext" : extended 25 column
			 "ext+": 26+ column
			 "custom": Use only given field selections.
	
		   Use -i to see possible field (column) selections as defined by blast_reporting_fields.tab.

		   REFERENCE_BINS: Selected bins have their columns shown in output table for clarity, even when custom fields are selected, unless selecting the bin "exclude" option.

		   FILTERS: 
			Format: ([field_name]:[comparator] [value];)*
			e.g. "pident: gt 97; salltitles: excludes bovine|clone|environmental|swine|uncultivated|uncultured|unidentified"
			[comparator] =
				==	numeric equal
				!=	numeric not equal
				gt	numeric greater than 
				gte	numeric greater than or equal to 
				lt	numeric less than
				lte	numeric less than or equal to
				includes (search text fields for included words/phrases)
				excludes (same as above but exclude result if text found)
	
			Textual comparisons may have a value consisting of phrases to search for separated by "|" (disjunction).
		
	
		""")

		parser.set_defaults(row_limit=0)
		# Don't use "-h" , it is reserved for --help!
		
		parser.add_option('-b', '--bins', type='string', dest='reference_bins', 
			help='Provide a comma-delimited list of reference databases to check, along with their sort order, and a flag to exclude them if desired, e.g. "16Sncbi desc,euzby desc,16Srdp exclude".  See -i option for a list of available databases.')

		parser.add_option('-c', '--columns', type='string', dest='custom_fields', 
			help='To modify sorting and formatting, specify a comma-delimited list of field specifications of the form: "[field_name]:[column|table|section]:[asc|desc|none]:[new label text];..." .')

		parser.add_option('-f', '--filter', type='string', dest='filters', 
			help='Provide a semicolon-delimited list of fields and their criteria to filter by.')

		parser.add_option('-i', '--info', dest='info', default=False, action='store_true', 
			help='Provides list of columns and their descriptions, for use in filter, sort and custom column lists. Shows a list of available sequence type reference bins as well')
	
		parser.add_option('-l', '--label', type='string', dest='column_labels', 
			help='Include field labels in first row of tab-delimited result table as short names or data field names (or none)') 

		parser.add_option('-n', '--number', type='int', dest='row_limit', 
			help='Provide a limit to the number of rows of returned data. The default 0=unlimited.')

		#TESTING Galaxy library dataset files for reference bins.
		parser.add_option('-B', '--refbins', type='string', dest='refbins', 
			help='Testing library_data form input.')

		parser.add_option('-r', '--redundant', dest='drop_redundant_hits', default=False, action='store_true', 
			help='Return only first match to a gene bank id result.')

		options, args = parser.parse_args()

		import time
		time_start = time.time()

		# "info" command provides a dump of all the fields that can be displayed from the Blast search.
		if options.info:
			# Future: Can stand-alone command line program access Galaxy's version of the field spec file?  Right now it is a separate copy.
			print 'FIELDS:\n'
			field_spec_path = os.path.join(os.path.dirname(__file__), 'blast_reporting_fields.tab')
			fields = common.FieldSpec(field_spec_path)				
			for field in sorted(fields.dict.keys()):
				print field + "\t" + fields.getAttribute(field,'type') + "\t" + fields.getAttribute(field,'name')

			print '\nREFERENCE BINS:\n'
			field_spec_path = os.path.join(os.path.dirname(__file__), 'fasta_reference_dbs.tab')
			fields = common.FieldSpec(field_spec_path)				
			for field in sorted(fields.dict.keys()):
				print field + "\t" + fields.getAttribute(field, 'path') + field + '/accession_ids.tab' + '\t' + fields.getAttribute(field, 'name')

			sys.exit(1)	

		try:
			in_file, output_format, out_tabular_file = args[0:3]
		
		except:
			common.stop_err("Expecting 3 arguments: input BLAST XML file, out format (std | std+seqs | ext | ext+ | custom), and output tabular file")

		try: 
			# Get an iterable, see http://effbot.org/zone/element-iterparse.htm
			context = ElementTree.iterparse(in_file, events=("start","end")) # By default only does end events. 
			context = iter(context)
			event, root = context.next() # Creates reference to root element on 'start' event, for housecleaning below.
		except:
			common.stop_err("Invalid data format. !!")

		tagGroup = XMLRecordScan(options, output_format)
		fieldFilter = common.FieldFilter(tagGroup, options) # .filter list field names are changed above.

		if options.reference_bins: 		print 'Database bins: %s' % str([bin.name for (ptr, bin) in enumerate(tagGroup.binManager.reference_bins) ]).translate(None, "[']")
		if options.custom_fields:		print 'Customized Fields: %s' % options.custom_fields
		if options.filters:				print 'Filters: ' + options.filters
		if options.drop_redundant_hits:	print 'Throwing out redundant hits...'

		# ************************ FILE OUTPUT *****************************
		# IT IS CRITICAL THAT EVERY <HIT>/<HSP> RETURN A COMPLETE XML SET OF TAGS OTHERWISE PREV. RECORD VALUES PERSIST
		# NOTE: GALAXY 2012 has bug in html data display - it will show duplicate records OCCASIONALLY (at least on some browsers).  You have to download data file to verify there are no duplicates
		
		row_count = 0
		row_count_filtered = 0
		outfile = open(out_tabular_file, 'w')
		query_stats = []

		for event, elem in context:

			# Alternative is to wipe Hit/Hsp fields on event == "start".		
			tag = elem.tag
			if event == 'end':
				if tag in tagGroup.tags : #Content of these tags fills a tabular line with column info.
					tagGroup.setRecordAttr(tag, elem.text)
					if tag == 'Iteration_query-def':
						row_count = 0
						row_count_filtered = 0
						query_stats.append({'id':elem.text, 'rows' : 0, 'filtered_rows' : 0})

				# Process each </hsp> record
				elif tag == 'Hsp':	
					row_count += 1
					query_stats[-1]['rows'] = row_count # real rows, not clipped
					if options.row_limit == 0 or row_count_filtered < options.row_limit: 
					
						# Transform <Hsp> record & add field info.
						if tagGroup.processRecord(): 

							#if tagGroup.processFilters():
							if fieldFilter.process(tagGroup.record):
								row_count_filtered +=1
								query_stats[-1]['filtered_rows'] = row_count_filtered 
								outfile.write(tagGroup.outputTabDelimited())
								
						root.clear() # Clears references from root to (now unused) children to keep iterated datastructure small ???

				elem.clear() # I think root.clear() cover this case.

		root.clear() 
		outfile.close()


		# Use fast Linux "sort" after filtering & file write
		common.fileSort(out_tabular_file, tagGroup.columns)

		"""
		The "Selection file" option is meant for galaxy UI use in conjunction 
		with the "Select Subsets on data" tool.  If a selection_file is called 
		for, then we need to extract its id as well.  For that we have to test 
		for somewhat odd expression from xml-generated command line, the 
		[$selection_file:$selection_file.hid:$selection_file.dataset_id:$selection_file.id]
		Selection list doesn't necessarily need the HTML selectable report template, 
		but that template was designed to feed the galaxy "Select subsets" tool with its data.
		
		From galaxy, incoming format is $selection_file:$selection_file.hid:$selection_file.dataset_id:$selection_file.id
		"""
		
		if len(args) > 4 and args[4] != 'None:None:None:None': 
			
			sel_file_fields = args[4].split(':')
			selection_file = sel_file_fields[0]

			# From command line, user won't have specified any of this, so ignore.
			options.dataset_selection_id = None
			if len(sel_file_fields) > 3 and selection_file != 'None':
				# Unfortunately we can't tell galaxy not to set up selection_file handle on xml form if input fields haven't been selected.  
				# Have to test for needed input fields here
				sel_requisites = 0
				for (idx, field) in enumerate(tagGroup.columns): 
					if field['field'] in 'qseqid _qseq sseqid _sseq': sel_requisites += 1
					
				if sel_requisites == 4:	
					options.dataset_selection_id = sel_file_fields[3]
					common.fileSelections(out_tabular_file, selection_file, tagGroup, options)
				
		
		"""
		We must have a template in order to write anything to above html output file.
		All report templates need to be listed in the module's tabular data "blast_reporting_templates" folder.
		# There are two possible HTML Report template locations: 
		# 1) The stock reports included in the module in the "templates/" subfolder, e.g. html_report.py
		# 2) User customized templates.  To set this up:
			- add a custom template folder in a location of your choice.
			- Copy this module's templates folder into it.  
			- The new folder must be in python's sys.path, which is achieved by adding a .pth file to python's site-packages folder..  E.g. set up /usr/lib/python2.6/site-packages/galaxy-custom-modules.pth to contain "/usr/local/galaxy/shared/python2.6_galaxy_custom_modules" 
		, and place 'templates_custom/html_report.py' in there.
		"""
		if len(args) > 3:
			out_html_file = args[3] #Galaxy-generated	
			# args[5] = html_template, default from galaxy xml is 'templates.html_report', but testing can receive 'None' value
			if len(args) > 5 and len(args[5].strip()) > 0 and not args[5].strip() == 'None': 
					
				html_template = args[5] #User-selected
				if not html_template.translate(None, "._-" ).isalnum():
					common.stop_err("The HTML Report template name is not correct.  It should be a python class path like templates.html_report)! : " + html_template)
				
			else:
				html_template = 'templates.html_report'
			
			try:
				# See http://stackoverflow.com/questions/769534/dynamic-loading-of-python-modules
				HTMLReportModule = __import__(html_template, fromlist=['does not in fact matter what goes here!'])
				# Now create final tabular, html (or future: xml) data
				htmlManager = HTMLReportModule.HTMLReport(tagGroup, options, query_stats)	
				# htmlManager might not be initialized if the caller couldn't provide all the data the particular template needed.
				htmlManager.render(out_tabular_file, out_html_file)
				
			except ImportError:
				common.stop_err("Unable to locate HTML Report template! : " + html_template)
		
		
		common.fileTabular(out_tabular_file, tagGroup, options)
		
		print('Execution time (seconds): ' + str(int(time.time()-time_start)))
		
     
if __name__ == '__main__':
	# Command line access
    reportEngine = ReportEngine()
    reportEngine.__main__()
