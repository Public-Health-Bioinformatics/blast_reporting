import os.path
import time
import csv
import collections
import re
import common

HTML_REPORT_HEADER_FILE = 'html_report_header.html'

class HTMLReport(object):
	
	""" This receives and sets up the general meta-data fields available to the html rendering engine 

	"""
	def __init__(self, tagGroup, options, query_stats = []):

		self.columns = tagGroup.columns
		self.display_columns = [field for field in self.columns if field['group']=='column']
		self.row_limit = options.row_limit
		self.section_bins = {}
		self.todo = collections.deque([]) # stack of things to do
		self.query_stats = query_stats
		self.empty_queries = [query['id'] for query in query_stats if query['filtered_rows'] == 0]
		self.initialized = False

		# These items are available for display in html generation via dictionary string replacement: [string ... %(filters)s ...] % self.lookup
		self.lookup = {
			'depth': 0,
			'filters': 'Filters: ' + options.filters_HTML if len(options.filters_HTML) else '',
			'timestamp': time.strftime('%Y/%m/%d'),
			'visible_limit': 20,
			'column_count': str(len([field for field in self.columns if field['group']=='column'])),
			'table_rows':0,
			'select_row':0,
			'row_limit': self.row_limit,
			'label':'',
			'value':'',
			'link':'',
			'cssClass':'',
			'table_header': self._tableHeader(),
			'section_bins':'',
			'section_counter':1,
			'target_form':'select_subsets'
		}
		
		if options.dataset_selection_id != False:
			self.lookup['dataset_selection_id'] = options.dataset_selection_id
			self.initialized = True
		
		else:
			self.lookup['dataset_selection_id'] = 0
			self.errorNotice = '<div style="width:400px;margin:auto"><h3>This Selectable HTML Report needs the "Basic Report Field Output" to include the qseq and sseq sequence fields (aligned part of query sequence and subject sequence) as well as their identifiers qseqid and sseqid.  Add these fields or try a selection that has more than 12 columns.</h3></div>'

	"""		
	_processTagStack()
	In the production of html, start tags and template bits are added to the outgoing html when 
	designated section columns of data change value.  the self.todo stack keeps track of all the 
	tag closings that have to occur when a section or table section comes to an end (and new one 
	begins or end of document occurs).

	This dynamically executes any functions listed in stack that are greater than given tag depth.
	Generally the functions return html closing content.
	
	@param depth integer >= 0
	@uses self.todo stack of [depth, function_name] items	
	"""
	def _processTagStack(self, depth = 0):
		html = ''
		while len(self.todo) and self.todo[0][0] >= depth: 
			html += getattr(self, self.todo.popleft()[1] )()
		return html 



	############################### HTML REPORT RENDERING ############################## 
	""" render() produces the html.  Takes in tabular data + metainformation about that file,
	 and iterates through rows.  This approach depends on detecting changes in stated report 
	section columns and table section columns, and triggers appropriate section start and end, 
	and table / table section start and end tags.

	@param in_file string	Full file path
	@param out_html_file string	Full output html data file path to write to.
	"""
	def render (self, in_file, out_html_file):

		try:
			
			fp_in = open(in_file, "rb")
			fp_out = open(out_html_file, 'w')

			fp_out.write( self._header(HTML_REPORT_HEADER_FILE) )
				
			if self.initialized:

				fp_out.write( self._bodyStart() )
				self.todo.appendleft([0,'_bodyEnd'])
				
				reader = csv.reader(fp_in, delimiter="\t")

				for row in reader:

					html = ''
					self.rowdata = []
					row_bins = []
					section_reset = False
					
					for (idx, field) in enumerate(self.columns):

						value = field['value'] = row[idx]
						depth = idx + 1

						# If a bin is mentioned on this row, its put into self.selection_bins.
						if field['type'] == 'bin' and value != '': 
							row_bins.append(value)
							if not value in self.section_bins:
								self.section_bins[value] = field['label']

						grouping = field['group']
						# Section or table grouping here: 
						if grouping == 'section' or grouping == 'table':	

							# Check to see if a new section or table section is triggered by change in field's value:
							if section_reset or (not 'valueOld' in field) or value != field['valueOld']:
								
								self.lookup['value'] = value
								self.lookup['label'] = field['label']

								html += self._processTagStack(depth)

								if grouping == 'section':
									section_reset = True 
									self.lookup['section_depth'] = depth
									self.lookup['section_counter'] += 1
									self.lookup['table_rows'] = 0
									self.section_bins = {}

									html += self._sectionStart()

									html += self._sectionFormStart()
									self.todo.appendleft([depth,'_sectionFormEnd'])

									self.todo.appendleft([depth,'_sectionEnd'])

								elif grouping == 'table': 
									
									lastToDo = self.todo[0]
									if lastToDo[1] == '_sectionEnd': #Just started a section
										html += self._tableStart()
										self.todo.appendleft([lastToDo[0]+1,'_tableEnd'])

									html += self._tbodyHeader() + self._tbodyStart()
									self.todo.appendleft([lastToDo[0]+2,'_tbodyEnd'])

							field['valueOld'] = value

						else:
							
							if grouping == 'column': self.rowdata.append(row[idx])

					lastToDo = self.todo[0]
					# No table level, instead going right from section to column field:
					if lastToDo[1] == '_sectionEnd': 
						html += self._tableStart() + self._tbodyStart()
						self.todo.appendleft([lastToDo[0]+1,'_tableEnd'])
						self.todo.appendleft([lastToDo[0]+2,'_tbodyEnd'])

					self.lookup['row_bins'] = ",".join(row_bins)

					fp_out.write(html)

					self.lookup['table_rows'] += 1

					# Now output table row of data:
					fp_out.write( self._tableRow() )

		
			#Not initialized here, so just write created error notice.
			else:

				fp_out.write('<h3>' + self.errorNotice + '</body></html>')
				
			fp_out.write( self._processTagStack() )
				
		except IOError as e:
			print 'Operation failed: %s' % e.strerror

		fp_in.close()
		fp_out.close()


	############################### HTML REPORT PART TEMPLATES ############################## 
	def _header(self, filename):

		with open(os.path.join(os.path.dirname(__file__), filename), "r") as fphtml:
			data = fphtml.read()
		
		return data
		
		
	def _bodyStart(self):
		# The form enables the creation of a dataset from selected entries.  It passes selections (based on a certain column's value) to the "Select tabular rows" tool, which then creates a dataset from the selected rows. 
		with open(os.path.join(os.path.dirname(__file__), "html_selectable_report_tool_state.txt"), "r") as form_code_file:
			self.lookup['form_state'] = form_code_file.readline().strip()
		
		html = """
				<script>
					// Toggle checkbox inputs of given table according to state of checkbox
					function toggleInputs(mycheckbox, table) {
						var checkboxes = table.getElementsByTagName('INPUT');
						// Loop skips first toggler checkbox
						for (var ptr = 1; ptr < checkboxes.length; ptr ++ ) {
							checkboxes[ptr].checked = mycheckbox.checked;
						}
						return true; // prevents click processing
					}
					
					//Drops hidden section id from form submission when no section items were selected
					function formCheck() {
						var tables = document.getElementsByTagName('TABLE');
						for (var ptr = 0; ptr < tables.length; ptr ++) {
							var inputs = tables[ptr].getElementsByTagName('INPUT');
							var selected = 0;
							// 1st item in table is select-all toggle
							for (var ptr2 = 1; ptr2 < inputs.length; ptr2 ++) { 
								if (inputs[ptr2].getAttribute('name') == 'select' && inputs[ptr2].checked) selected ++;
							}
							if (selected==0) {	
								id = tables[ptr].getAttribute("id");
								secInput = document.getElementById(id + '_start');
								secInput.disabled = true;	
								secInput.setAttribute('disabled','disabled');								
								secInput.value='';								
							}

						}
						return true;
					}
				</script>

				<form id="tool_form" name="tool_form" action="../../../tool_runner"  target="galaxy_main" method="post" enctype="application/x-www-form-urlencoded">
   				<input type="hidden" name="refresh" value="refresh"/>
            	<input type="hidden" name="tool_id" value="%(target_form)s"/>
               <input type="hidden" name="tool_state" value="%(form_state)s">
					<input type="hidden" name="input" value="%(dataset_selection_id)s"/>			
					<input type="hidden" name="incl_excl" value="1"/>
		""" % self.lookup

		if len(self.empty_queries):
			qnames = ''
			for name in self.empty_queries:	qnames += '<li>' + name + '</li>\n'
			html += """
			<div class="headerMessage">The following %s queries yielded 0 results (check filters): 
				<ul>
				%s
				</ul>
			</div>""" % (len(self.empty_queries), qnames)

		return html % self.lookup

	# Repeated for each grouped section table display
	def _sectionStart(self):
		self.lookup['select_row'] +=1
		return """
			<div class="section section_depth%(section_depth)s">
				<div class="section_title">%(label)s: %(value)s</div>
		""" % self.lookup 



	def _sectionFormStart (self):
		# This sets up the selection form with the minimal necessary parameters  # 
		return """
					<input type="checkbox" name="select" value="%(select_row)s" id="secId_%(select_row)s_start" checked="checked" style="display:none">
					<input type="submit" class="btn btn-primary nonprintable" name="runtool_btn" value="Submit" onclick="formCheck()">
			""" % self.lookup 


	def _tableStart (self):

		return """
			<div class="checkUncheckAllPlaceholder"></div>
			<table class="report" id="secId_%(select_row)s">
				%(table_header)s
		"""  % self.lookup


	def _tableHeader(self):

		colTags = ''
		thTags = ''
		firstColumnFlag = True
		# Style numeric fields
		for field in self.columns: 
			if field['group'] == 'column': 
				colTags += ('<col />' if field['type'] == 'text' else '<col class="numeric" />')
				if firstColumnFlag == True:
					thTags += '''<th>
						<input type="checkbox" class="sectionCheckbox nonprintable" value="1"/>
						''' + field['label'] + '</th>'
					firstColumnFlag = False
				else:
					thTags += '<th>' + field['label'] + '</th>'

		return """
				<colgroup>
					%s
				</colgroup>
				<thead class="top">
					<tr>%s</tr>
				</thead>""" % (colTags, thTags)

	def _tbodyHeader (self):
		if self.lookup['value'] == '': self.lookup['value'] = '(no match)'
		return """	
				<thead class="inside">
					<tr>
						<th colspan="%(column_count)s">%(label)s: %(value)s</th>
					</tr>
				</thead>""" % self.lookup

	def _tbodyStart (self):
		return """
				<tbody>""" % self.lookup


	def _tableRow(self):
		self.lookup['select_row'] +=1

		tdTags = ''
		for (col, field) in enumerate(self.display_columns):
			value =  self.rowdata[col]
			self.lookup['value'] = value
			self.lookup['cssClass'] = ' class="numeric"' if field['type'] == 'numeric' else ''
			#See http://www.ncbi.nlm.nih.gov/books/NBK21091/table/ch18.T.refseq_accession_numbers_and_mole/?report=objectonly
			#See http://www.ncbi.nlm.nih.gov/Sequin/acc.html
			accessionID = re.search(r'[a-z]+[_]?[0-9]+(.[0-9]+)*' ,value, re.I)
			if (accessionID) :
				self.lookup['link'] = '<a href="https://google.com/#q=%s+gene" target="search">%s</a>' % (accessionID.group(), value)
			else:
				self.lookup['link'] = value
			# First column optionally gets bin indicator as well as row checkbox selector 
			if (col == 0):
				tdTags += '<td%(cssClass)s><input type="checkbox" name="select" value="%(select_row)s" />%(link)s<span class="super">%(row_bins)s</span></td>' % self.lookup
			else:
				tdTags += '<td%(cssClass)s>%(value)s</td>' % self.lookup

		return """\n\t\t\t<tr>%s</tr>""" % tdTags


	def _tbodyEnd (self):
		return """
				</tbody>"""

	def _tableEnd (self):
		if len(self.section_bins):
			bins = []
			for key in sorted(self.section_bins):
				bins.append( '<span class="super">(%s)</span>%s' % (key, self.section_bins[key]) )
			self.lookup['section_bins'] = 'Bins: ' + ', '.join(bins)
		else:
			self.lookup['section_bins'] = ''

		return """
				<tfoot>
					<tr>
						<td colspan="%(column_count)s">
							<div class="footerCenter">
								%(filters)s. 
							</div>
							<div class="footerLeft">
								<span class="rowViewer0"></span> %(table_rows)s results. 
								<span class="rowViewer1 nonprintable"></span>
								%(section_bins)s
							</div> 
							<div class="footerRight">
								Report produced on %(timestamp)s
							</div>

						</td>
					</tr>
				</tfoot>
			</table>""" % self.lookup

	def _sectionFormEnd (self):
		return """
			
		""" 

	def _sectionEnd (self):
		return """
	
		</div>"""


	def _bodyEnd (self):

		return """
			</form>\n\t</body>\n</html>"""


