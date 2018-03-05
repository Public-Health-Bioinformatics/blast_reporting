import os.path
import sys
import re
import optparse
import subprocess
from shutil import move
import csv

re_default_query_id = re.compile("^Query_\d+$")
	#assert re_default_query_id.match("Query_101")
	#assert not re_default_query_id.match("Query_101a")
	#assert not re_default_query_id.match("MyQuery_101")
re_default_subject_id = re.compile("^(Subject_|gnl\|BL_ORD_ID\|)\d+$") #requires some kind of numeric id
	#assert self.re_default_subject_id.match("gnl|BL_ORD_ID|221")
	#assert re_default_subject_id.match("Subject_1")
	#assert not re_default_subject_id.match("Subject_")
	#assert not re_default_subject_id.match("Subject_12a")
	#assert not re_default_subject_id.match("TheSubject_1")  
	# Spot sequence ids that have accession ids in them
re_default_ncbi_id = re.compile("^gi\|\d+\|[a-z]+\|[a-zA-Z0-9_]+(\.\d+)?\|")
re_default_ref_id = re.compile("^ref\|[a-zA-Z0-9_]+\|[a-zA-Z0-9_]+(\.\d+)?\|")


def stop_err( msg ):
    sys.stderr.write("%s\n" % msg)
    sys.exit(1)

class MyParser(optparse.OptionParser):
	"""
	 From http://stackoverflow.com/questions/1857346/python-optparse-how-to-include-additional-info-in-usage-output
	 Provides a better class for displaying formatted help info in epilog() portion of optParse; allows for carriage returns.
	"""
	def format_epilog(self, formatter):
		return self.epilog



## *********************************** FieldFilter ****************************
class FieldFilter(object):
	
	def __init__(self, tagGroup, options):	
		""" Creates dicitionary of fields that are to be filtered, and array of comparators and their values.
		Numeric filters have a single numeric value
		Each text filter is a string of phrases separated by "|"

		 e.g. filters = "pident: > 97,score: > 37,salltitles includes what | have|you"
		
		 @param filters string	e.g. "[ [field name]: [comparator] [value],[[comparator] [value],]* ]* 
		 @result .dict dictionary contains field name keys and arrays of [comparator, filterValue]
		
		"""
		self.dict = {}
		self.comparators = {
			'==': lambda x,y: float(x) == float(y), 
			'!=': lambda x,y: float(x) != float(y), 
			'gt': lambda x,y: float(x) > float(y), 
			'gte': lambda x,y: float(x) >= float(y), 
			'lt': lambda x,y: float(x) < float(y), 
			'lte': lambda x,y: float(x) <= float(y),
			'includes': self.includesPhrase, 
			'excludes': self.excludesPhrase
		}
		self.matches = {}
		self.drop_redundant_hits = options.drop_redundant_hits
		

		
		if options.filters != None:
			cleaned_filters = []
			for colPtr, filterParam in enumerate(options.filters.strip().strip(';').split(';')):
				filterSpec = filterParam.strip().split(":")
				filterField = filterSpec[0].strip()
				if len(filterField) > 0:
					if filterField in self.dict:
						stop_err("Filter field listed twice: \"" + filterField + "\". Please move constraints up to first use of field!")
					field_name = cleanField(tagGroup.columns_in, filterField, 'Invalid field for filtering eh')
					if len(filterSpec) > 1: #we have start of filter field defn. "[field]:[crit]+,"
							
						self.dict[field_name] = [] #new entry for filter field
					
						for filterParam in filterSpec[1].strip().strip(',').split(','):
							filterSpec2 = filterParam.strip().split(' ')
							comparator = filterSpec2[0]
							if not comparator in self.comparators:
								stop_err("Invalid comparator for field filter: \"" + comparator + "\"")
							if len(filterSpec2) < 2:
								stop_err("Missing value for field comparator: \"" + comparator + "\"")
					
							#For text search, values are trimmed array of phrases 
							if comparator in ['includes','excludes']:
								filterValue = list(map(str.strip, ' '.join(filterSpec2[1:]).split('|')))
								filterValue = filter(None, filterValue)
							else:	
								filterValue = filterSpec2[1] 
						
							self.dict[field_name].append([comparator, filterValue])

						cleaned_filters.append(field_name + ':' + filterSpec[1])
			
			options.filters = ';'.join(cleaned_filters)
			# Adjust filter expression fieldnames.
			words = {'gt':'&gt;', 'gte':'&gt;=', 'lt':'&lt;', 'lte':'&lt;=',',':'',':':' '} 
			options.filters_HTML = word_replace_all(options.filters, words)
			words = {'gt':'>', 'gte':'>=', 'lt':'<', 'lte':'<=',',':'',':':' '}
			options.filters = word_replace_all(options.filters, words)
		
		else:
			options.filters = None
			options.filters_HTML = ''
		
	def __str__(self):
		return "label: %s    dict: %s" % (self.label, str(self.dict))

	def includesPhrase(self, source, filter_phrases):
		""" Search for any words/phrases (separated by commas) in commastring in source string
		 @param source string	Words separated by whitespace
		 @param filter_phrases array of phrases
		
		"""
		return any(x in source for x in filter_phrases)
		
	def excludesPhrase(self, source, commastring):	
		return not self.includesPhrase(source, commastring)
		
	def process(self, record):
		""" For given record (an object) cycle through filters to see if any of record's attributes fail filter conditions.

		 FUTURE: MAKE GENERIC SO PASSED record field function for unique test.???
		
		 @uses self.dict
		 @uses self.drop_redundant_hits
		 @uses self.matches
		 @param record object	An object containing field & values read from a <hit> line.
		 @return boolean	True if all filter criteria succeed, false otherwise
		
		"""
		
		# Block out repeated hits
		# THIS ASSUMES BLASTn XML file is listing BEST HIT FIRST.  Only appropriate for searching for single hits within a reference sequence.
		if self.drop_redundant_hits == True:
			# parsing succession id from e.g. gi|57163783|ref|NP_001009242.1| rhodopsin [Felis catus]
			#acc = str(record.sseqid.split('|')[3:4]).strip()
			key = record.qseqid + '-' + record.accessionid #acc
			if key in self.matches:
				return False
			self.matches[key] = True
		
		for key, constraints in self.dict.items():
			try:	# The .loc table of fields has fieldnames without leading _ underscore. 
				# Such fields are assumed to be added by code;
				# Leading underscore fields are raw values read from XML file directly.
				# Our filter names don't have underscore, but we see if underscore field exists if normal attr check fails
				value = getattr(record, key)
				for ptr, constraint in enumerate(constraints):
					comparator = constraint[0]
					userValue = constraint[1]
					# print "constraint " + str(value) + comparator + str(userValue) + " -> " + \
					# str (self.comparators[comparator](value, userValue) )
					if not self.comparators[comparator](value, userValue): 
						return False #failed a constraint
			except AttributeError: 
				print 'A filter on field [' + key + '] was requested, but this field does not exist.'
				raise KeyError
		
		return True



class FieldSpec(object):

	def __init__(self, file_path, columns_in = []):
		""" READ FIELD SPECIFICATIONS of a particular galaxy tool form/process from a .loc 'tabular data' file

		Example blast_reporting_fields.tab file
		
			#value	type	subtype	sort	filter	default	min	max	choose	name
			# Remember to edit tool_data_table_conf.xml for column spec!
			qseqid	numeric	int	1	1				1	Query Seq-id
			sseqid	numeric	int	1	1				1	Subject Seq-id
			pident	numeric	float	1	1	97	90	100	1	Percentage of identical matches

		 - value is name of field: alphanumeric strings only.
		 - type is 'text' or 'numeric' or 'bin'
		 - subtype where applicable, indicates further validation function
		 - sort indicates if field should be provided in sort menu
		 - filter indicates if field should be in menu of fields that can be filtered
		 - default is default value field should have if drawn on form
		 - min is minimum range of field
		 - max is maximum range of field
		 - choose indicates if field can be chosen for an output column (some are mandatory / some are to be avoided?)
		 - name is textual name of field as it should appear on pulldown menus

		 @param file_path string	full name and path of .loc file containing pertinent field names and their specifications.
		 @result .dict dictionary
		
		"""
		self.dict = {}
		self.columns_in = columns_in

		with open(file_path, 'rb') as f:
			reader = csv.DictReader(f, delimiter='\t') #1st row read as field name header by default
			try:
				for row in reader:
					myKey = row['#value']
					# Some lines begin with '#' for value.  Ignore them
					# Also, reader has read column names from first row; "#value" is name of first column
					if not myKey[0] == '#': # 1st character is not a hash
						row.pop("#value", None)
						self.dict[myKey] = row
						# self.dict[myKey]['value']=row['#value'] # If we need this ever?
						
				
			except csv.Error as e:
				stop_err('file %s, line %d: %s' % (filename, reader.line_num, e))


	def initColumns(self, columns_out, custom_columns):
		"""
		# Augment columns with fieldSpec label and some sorting defaults.
		# Default sorts: qseqid is marked as sorted asc; score as sorted desc.
		# No need to move sorted fields around.
		# This basically creates spec to generate tab-delimited file.  
		# The only other calculation done for that is the row_limit cut, if any.
		"""		
		column_spec = list(columns_out)
		for (i, spec) in enumerate(column_spec):
			spec_field = spec.lstrip("_")

			if spec_field == 'qseqid': 
				sort = 'asc'
				group = 'section'
			elif spec_field == 'score': 
				sort = 'desc'
				group = 'column'			
			else:
				sort = ''
				group = 'column'			

			field = {
				'field': spec,
				'group': group,
				'sort': sort,
				'label': self.getAttribute(spec_field, 'short_name'),
				'type': self.getAttribute(spec_field, 'type')
			} 
			column_spec[i] = field
		
		"""
		# For the HTML (OR XML) report we allow users to specify columns of data to represent sections of the report or table sections.
		# Selected columns either enhance an existing column's info, or add a new column. 
		# If a selected column is sorted, it is inserted/moved to after last SORTED column in data. 
		# In other words, primary/secondary etc sorting is preserved.
		"""
		if custom_columns != None:


			custom_spec = [x.strip() for x in custom_columns.split(';')]
			for spec in custom_spec:	
				params = [i.strip() for i in spec.rstrip(":").split(":")]
				parlen = len(params)
				if parlen > 0 and params[0] != '':
					field_name = cleanField(self.columns_in, params[0]) # Halts if it finds a field mismatch
	
					group = 'column'
					sort = ''
					if parlen > 1 and params[1] in ['column','hidden','table','section']: group = params[1] 
					if parlen > 2 and params[2] in ['asc','desc']: sort = params[2] 

					# Enforce sort on section and table items....

					# All self.column_spec have a fieldspec entry.  Get default label from there.
					# HOW TO HANDLE CALCULATED FIELD LABELS?  ENSURE THEY HAVE ENTRIES? 			
					spec_field = field_name.lstrip("_")
					label = self.getAttribute(spec_field, 'short_name')
					if parlen > 3: label = params[3] 

					field = {
						'field': field_name,
						'group': group,
						'sort': sort,
						'label': label,
						'type': self.getAttribute(spec_field, 'type')
					} 

					#	If field is a 'section' move it right after last existing 'section' (if not matched)
					#	if its a 'table' move it after last existing 'table' (if not matched)
					#	otherwise append to column list.(if not matched)
				
					found = False # if found== true, rest of loop looks for existing mention of field, and removes it.
					for (ptr, target) in enumerate(column_spec):

						found_name = spec_field == target['field'].lstrip("_")
						if (found == True):
							if (found_name): # Found duplicate name
								del column_spec[ptr]
								break
						elif (found_name):
							found = True
							column_spec[ptr] = field # Overwrite spec.
							break

						elif (field['group'] == 'section'):
							if (target['group'] != 'section'): # time to insert section
								found = True
								column_spec.insert(ptr, field)

						elif (field['group'] == 'table'):
							if (target['group'] == 'column' or target['group'] == 'hidden'):
								found = True
								column_spec.insert(ptr, field)

					if found == False: # didn't find place for field above.
						column_spec.append(field)
		# print ("col spec: " + str(column_spec))

		return column_spec



	def getAttribute(self, fieldName, attribute):
		""" Retrieve attribute of a given field
		
		 @param fieldName string
		 @param attribute string
		 @return string value of attribute
		
		"""
		return self.dict[fieldName][attribute]


def word_replace_all(text, dictionary):
	textArray = re.split('(\W+)', text)   #Workaround: split() function is not allowing words next to punctuation.
	for ptr,w in enumerate(textArray):
		if w in dictionary: textArray[ptr] = dictionary[w]
	return ''.join(textArray)


def cleanField(columns_in, field_name, msg = 'Not a valid field name'):

	if not field_name.replace('_','').isalnum():
		stop_err(msg + ': [' + field_name+']')
	if field_name in columns_in: 
		clean = field_name
	elif '_' + field_name in columns_in: #passed from source file
		clean = '_' + field_name
	else: #column not found here
		stop_err(msg + ':'+ field_name + '- no such field')
	return clean


def fileSort (out_file, fields):
	"""
	 fileSort() uses linux "sort" to handle possibility of giant file sizes. 
	 List of fields to sort on delivered in options.sorting string as:
	
		[{name:[field_name],order:[asc|desc],label:[label]},{name ... }] etc.

	 Match "sorts" fields to columns to produce -k[col],[col] parameters that start and end sorting
	 Note that sort takes in columns with primary listed first, then secondary etc.
	 Note that file to be sorted can't have 1st line column headers.

	 sort attributes:
	
		-f ignore case;
		-r reverse (i.e. descending)Good.
		-n numeric
		-k[start col],[end col] range of text that sort will be performed on
		-s stabilize sort : "If checked, this will stabilize sort by disabling its last-resort comparison so that lines in which all fields compare equal are left in their original relative order." Note, this might not be available on all linux flavours?
		-V sorts numbers within text - if number is leading then field essentially treated as numeric.  This means we don't have to specify -n for numeric fields in particular

	 Note: some attention may need to be given to locale settings for command line sort
	 May need to set export LC_ALL=C or export LANG=C to ensure same results on all systems 
	
	 @param out_file string File path of file to resort
	 @param sorts string	Comma-separated list of fields to sort, includes ascending/descending 2nd term;each field validated as an alphanumeric word + underscores.
	 @param prelim_columns dictionary of files column header names
	"""

	sortparam = []
	for colPtr, field in enumerate(fields):
		if field['sort']:
			field_name = field['field']
			if not field_name.replace('_','').isalnum():
				stop_err("Invalid field to sort on: " + field)
		
			#print "sort term:" + field + ":" + str(prelim_columns)
			ordering = '' if field['sort'] == "asc" else 'r'
			column = str(colPtr+1)
			# V sorts numbers AND text (check server's version of sort
			sortparam.append('-k' + column + 'V' + ordering + ',' + column)

	if len(sortparam) > 0:
		args = ['sort','-s','-f','-V','-t\t'] + sortparam + ['-o' + out_file, out_file]
		sort_a = subprocess.call(args)



def fileTabular (in_file, tagGroup, options):
	"""Produces tabular report format.  Takes in tabular data + metainformation about that file, and iterates through rows.  Not a query-based approach.
	It trims off the sort-only columns (prelim - final), 
	It optionally adds column label header. (not done in fileSort() because it gets mixed into sort there.)
	NOTE: RUN THIS AFTER fileHTML() BECAUSE IT MAY TRIM FIELDS THAT HTML REPORT NEEDS

	@param in_file string	Full file path
	@param tagGroup	object Includes prelim_columns, final_columns
	@param options object Includes label_flag and row_limit

	"""
	fp_in = open(in_file, "rb")
	fp_out = open(in_file + '.tmp', 'wb')

	try:

		reader = csv.reader(fp_in, delimiter="\t")
		writer = csv.writer(fp_out, delimiter="\t")

		# WRITE TABULAR HEADER
		if options.column_labels: # options.column_labels in ['name','field']:
			if options.column_labels == 'label':
				tabHeader = [field['label'] for field in tagGroup.columns]
			else:
				# Tabular data header: strip leading underscores off of any labels...
				tabHeader = [field['field'].lstrip('_') for field in tagGroup.columns]

			writer.writerow(tabHeader)

		for row in reader:

			rowdata=[]
			for (idx, field) in enumerate(tagGroup.columns): # Exclude hidden columns here?
				rowdata.append(row[idx])
			writer.writerow(rowdata)

		move(in_file + '.tmp', in_file) # Overwrites in_file
	
	except IOError as e:
		print 'Operation failed: %s' % e.strerror

	fp_in.close()
	fp_out.close()



def fileSelections (in_file, selection_file, tagGroup, options):
	""" Produces selection report format.  
	For selection file we need: qseqid, qseq, sseqid, sseq, and #

	@param in_file string	Full file path
	@param tagGroup	object Includes prelim_columns, final_columns
	@param options object Includes label_flag and row_limit

	"""

	fp_in = open(in_file, "rb")
	fp_out = open(selection_file, 'w')
	
	try:

		reader = csv.reader(fp_in, delimiter="\t")
		writer = csv.writer(fp_out, delimiter="\t")

		for (idx, field) in enumerate(tagGroup.columns): 
			fieldname = field['field']
			if fieldname == 'qseqid': qseqid_col = idx
			elif fieldname == '_qseq': 	qseq_col = idx
			elif fieldname == 'sseqid': sseqid_col = idx
			elif fieldname == '_sseq': 	sseq_col = idx

		selectrow_count = 0
		grouping = -1
		old_section = ''
		for row in reader:

			selectrow_count +=1
			if row[qseqid_col] != old_section:
				old_section = row[qseqid_col]
				grouping +=1
				writer.writerow([row[qseqid_col], row[qseq_col], grouping, selectrow_count])
				selectrow_count +=1

			writer.writerow([row[sseqid_col], row[sseq_col], grouping, selectrow_count])

	
	except IOError as e:
		print 'Operation failed: %s' % e.strerror

	fp_in.close()
	fp_out.close()

