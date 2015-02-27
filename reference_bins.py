import os.path
import common

class ReferenceBins:

	def __init__(self, db_spec_path = None):
		"""
	 	@param db_spec_path string path to fasta databases specification file.  This file has format:
		 #value	id	type	active	name	path
		 16S_euzby	16S	1	Euzby	/usr/local/galaxy/shared/ngs_data/
		 ...
		"""
		self.reference_bins = []

		if db_spec_path == None: # Default to the command-line lookup table in code's folder: 
			db_spec_path = os.path.join(os.path.dirname(__file__), 'fasta_reference_dbs.tab') 	
		self.fieldSpec = common.FieldSpec(db_spec_path)

	def __main__(self): pass
	
	# Could double check to see if it exists?
	def build_bins(self, bins, columns):
				
		if bins == None: 
			self.reference_bins = []		
			return False
			
		for myfield in bins.strip().strip(';').split(';'):
			field_spec = myfield.strip().split(':')
			field_name = field_spec[0].strip()

			if field_name != '':
				if not field_name.replace('_','').isalnum():
					common.stop_err("Invalid bin name: " + field_name + ':' + myfield)
				
				if len(field_spec) < 2: field_spec.append('column') # default grouping = column
				if len(field_spec) < 3: field_spec.append('') # default filtering = none
				if len(field_spec) < 4: field_spec.append('') # default no description

				grouping = field_spec[1].strip()
				if not grouping in ['table', 'column', 'hidden']:
					common.stop_err("Invalid bin layout: " + grouping)

				bin_filter = field_spec[2].strip()
				if not bin_filter in ['', 'include', 'exclude']:
					common.stop_err("Invalid bin sort: " + bin_filter)

				newbin = self.buildBin(field_name, bin_filter)
				self.reference_bins.append(newbin)				
				
				field = { # any time we have a bin we want sort descending
					'field': field_name,
					'group': grouping,
					'sort': 'desc',
					'label': newbin.name,
					'type': 'bin'
				} 
				columns.append(field)
				if (field_spec[3] == 'true'): # description field requested
					field = {
						'field': field_name + '_desc',
						'group': 'column',
						'sort': '',							# Allow other sorts????
						'label': newbin.name + ' Description',
						'type': 'text'
					} 
					columns.append(field)


	def buildBin(self, bin_folder_name, bin_filter):
		""" 
		 Create a lookup table consisting of a dictionary entry for each accession id held in dictionary's file.
		 @param bin_folder_name string name of requested db, e.g 16S_ncbi 
		 @param bin_filter string '' or 'include' or 'exclude'
	
		"""
		bin = ReferenceBin(self.fieldSpec, bin_folder_name, bin_filter)
		
		try:
			with open(bin.file_path) as file_in:
				for line in file_in: # Should always contains succession id
					#FUTURE: Preprocess so accession ID ready to go.
					keyValue = line.rstrip().split("\t",1)
 					# keep only first term minus integer portion of id
					accGeneralId = keyValue[0].split('.')[0]
					if len(keyValue) >1: description = keyValue[1]
					else: description = ''
					bin.lookup[accGeneralId] = description
				
				file_in.close()
			
		except IOError:
		   stop_err("Reference bin could not be found or opened: " + self.path + bin_folder_name + '/accession_ids.tab')
		
		return bin

	def setStatus(self, record):

		if len(self.reference_bins) == 0: return #no bins

		# Use of "extended slices" http://docs.python.org/2.3/whatsnew/section-slices.html
		# Example sallseqid is 'gi|194753780|ref|XR_046072.1|;gi|195119578|ref|XR_047594.1|;gi|195154052|ref|XR_047967.1|'
 		# Example accs is ['XR_046072.1', 'XR_047594.1', 'XR_047967.1']
		# Original code was "[1::2][1::2]" (select every 2nd item, then every 2nd item of that)
		accs = record.sallseqid.split('|')

		if common.re_default_ncbi_id.match(record.sseqid):
			accs = accs[3::4] #Select every 4th item starting offset 4
			
		elif common.re_default_ref_id.match(record.sseqid):
			accs = accs[1::2]
		

		# Check each accession # against each bin.  
		for ptr, bin in enumerate(self.reference_bins):		
				setattr(record, bin.field, '') #Using '','1' not FALSE/TRUE because of tab delim output
				setattr(record, bin.field + '_desc', '')			
				for acc in accs:
					accGeneralId = acc.split('.')[0]
					if accGeneralId in bin.lookup:
						if bin.exclude: return False
						setattr(record, bin.field, str(ptr+1))
						# Include any bin notes for this item
						setattr(record, bin.field + '_desc', bin.lookup[accGeneralId])
						break # This result has been binned to this bin so break.




	def __str__(self):
		return "name: %s    dict: %s" % (self.name, str(self.lookup))

class ReferenceBin: 
	def __init__(self, fieldSpec, bin_folder_name, bin_filter):
		self.lookup = {}
		self.folder = bin_folder_name
		self.name = fieldSpec.getAttribute(bin_folder_name, 'name')
		self.field = bin_folder_name
		self.path = fieldSpec.getAttribute(bin_folder_name, 'path')
		self.exclude = bin_filter
		#absolute path to reference bins folder: /usr/local/galaxy/shared/ngs_data/
		self.file_path = os.path.join(self.path + self.folder + '/accession_ids.tab')
		
if __name__ == '__main__':

        binManager = ReferenceBins()
        binManager.__main__()

