from models import Directory

directory = Directory('data')
files = directory.get_csv_files()

files.add_source_columns("DATA KING")
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
files.split_and_choose('CLEANED_FULL_NAME', 'CLEANED_FIRST_NAME', ' ', 0)
files.split_and_choose('CLEANED_FULL_NAME', 'CLEANED_LAST_NAME', ' ', -1)

#finalize column selection
column_map = {'FIRST_NAME':'CLEANED_FIRST_NAME',
              'LAST_NAME':'CLEANED_LAST_NAME',
              'COMPANY':'COMPANY',
              'EMAIL':'CLEANED_EMAIL',
              'PHONE':'CLEANED_PHONE',
              'SOURCE':'SOURCE',
              'SUB_SOURCE': 'SUB_SOURCE',
              'UCC_DATE': 'DATE_FROM_DATA',
              'PURCHASE': 'DATE_FROM_FILE_NAME',
              'STATE_PROVENCE': 'STATE_PROVENCE',
            }

files.final(column_map=column_map)
directory.export_table_to_csv(rows_per_file=500_000, fname='Dataking-3-9-2025')





