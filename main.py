from models import File, Files, Directory

directory = Directory('data')
files = directory.get_csv_files()

files.add_source_columns()
files.rename_common_columns()
files.drop_remove()

files.connect_to_db()
files.stage()
files.dedup_staging()


