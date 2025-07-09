from models import Directory
import os
from sys import argv

outname = argv[1]
outrows=argv[2]

base_dir = 'data'

sources = [
  'PROLEADS',
  'DATAKING',
  'SALESPROSPECTS',
  'VIPER',
  'MERIDIAN'
]
for source in sources:
  print(source)
  d = os.path.join(base_dir, source)
  directory = Directory(d)
  files = directory.get_csv_files()
  files.add_source_columns(source)
  files.add_file_column()
  files.extract_date_from_file_name()
  files.extract_sub_source_from_file_name()
  files.rename_common_columns()
  files.drop_remove()

  files.connect_to_db()  
  files.stage()

# Remove titles from names, get only letters
files.clean_staging_person_name('FULL_NAME')
files.clean_staging_person_name('FIRST_NAME')
files.clean_staging_person_name('LAST_NAME')
files.clean_staging_alphanum_doublespace('COMPANY')
files.clean_staging_phone()
files.clean_staging_email()
files.upper_trim_column('ADDRESS')
files.make_number_value('ZIP')
files.get_date_from_staging()

# If name null take from full name
files.split_and_choose(src_column='CLEANED_FULL_NAME', tgt_column='CLEANED_FIRST_NAME', delim=' ', idx=0)
files.split_and_choose(src_column='CLEANED_FULL_NAME', tgt_column='CLEANED_LAST_NAME', delim=' ', idx=-1)
files.split_and_choose(src_column='CLEANED_FIRST_NAME', tgt_column='CLEANED_LAST_NAME', delim=' ', idx=1) # if last name null and first name has 2 use second
files.split_and_choose(src_column='CLEANED_FIRST_NAME', tgt_column='CLEANED_FIRST_NAME', delim=' ', idx=0) # if name has spaces remove second
files.fill_null_with_x('CLEANED_FIRST_NAME')
files.fill_null_with_x('CLEANED_LAST_NAME')
files.fill_null_with_x('CLEANED_COMPANY')
#finalize column selection
column_map = {'FIRST_NAME':'CLEANED_FIRST_NAME',
              'LAST_NAME':'CLEANED_LAST_NAME',
              'COMPANY_NAME':'CLEANED_COMPANY', # CHANGED TO COMPANY_NAME
              'EMAIL':'CLEANED_EMAIL',
              'PHONE':'CLEANED_PHONE',
              'PROVIDER':'SOURCE', # CHANGED TO PROVIDER
              'LEAD_TYPE': 'SUB_SOURCE', # CHANGED TO LEAD_TYPE
              'UCC_DATE': 'DATE_FROM_DATA',
              'PURCHASE_DATE': 'DATE_FROM_FILE_NAME', # CHANGED TO PURCHASE DATE
              'STATE': 'STATE_PROVENCE',
            }

files.final(column_map=column_map)
files.aggregate()
directory.export_table_to_file('aggregated', rows_per_file=int(outrows), fname=outname, fmt='csv',delimiter=',')
files.db.con.close()




