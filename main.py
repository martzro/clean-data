from models import Directory

directory = Directory('data')
files = directory.get_csv_files()

files.add_source_columns("DATA KING")
files.rename_common_columns()
files.drop_remove()

files.connect_to_db()
files.stage()
files.clean_staging_person_name('FULL_NAME')




