from openpyxl import reader as excel_reader
from openpyxl import writer as excel_writer
import sqlite3
from csv import reader as csv_reader
from csv import DictReader as csv_dict_reader
from csv import writer as csv_writer
import os
import re


class DB:
    def __init__(self):
        self.con = sqlite3.connect('db.db')
        self.cur = self.con.cursor()
        self.schema = {}

    def make_table(self, name, columns):
        query = f"""
                CREATE TABLE IF NOT EXISTS {name} (
                {','.join([column+' TEXT(255)' for column in columns])}
                );
                """
        self.cur.execute(query)
        self.schema[name] = columns

    def insert(self, table: str, columns: list, values: list[tuple]):
        self.table_exists(table)       
        query = f"""
                INSERT INTO {table}
                ({','.join(column for column in columns)})
                VALUES
                ({','.join(['?' for i in range(len(columns))])})
                ;
                """
        self.cur.executemany(query, list(map(tuple, values)))
        self.con.commit()
        print(f'inserted {len(values)} rows')

    def dedup(self, table: str, on: list, keep: str):
        self.table_exists(table)
        query = f"""
        with 
            DUPS AS (
                SELECT 
                        ROWID
                    ,   ROW_NUMBER() OVER (PARTITION BY {','.join(on)}) AS ROWNUM
                FROM {table}
            )
            DELETE FROM {table} WHERE ROWID IN (SELECT ROWID FROM DUPS WHERE ROWNUM <> {keep})
        """

        before = self.cur.execute(f'select count(1) from {table}').fetchone()[0]
        self.cur.execute(query)
        after = self.cur.execute(f'select count(1) from {table}').fetchone()[0]
        print(f'deleted {before-after} rows')
        self.con.rollback()



        
    def table_exists(self, table):
        if not self.schema.get(table):
            raise NameError(f'{table} does not exist')     

class File:
    def __init__(self, file_type: str, file_name: str):
        self.file_type = file_type
        self.file_name = file_name
        self.data = []
        self.columns = []
        self.column_name_regex = r'[^a-zA-Z0-9_]'
        self._get_data_()
    

    def _get_data_(self):
        if self.file_type == 'csv':
            return self.read_csv()
        elif self.file_type == 'xlsx':
            return self.read_excel()
    
    def read_csv(self):
        with open(self.file_name, mode='r', encoding='utf-8') as file:
            self.data = [row for row in csv_reader(file)]
            self.columns = [re.sub(self.column_name_regex, '', str(column).upper().strip().replace('/', ' ').replace(' ','_')) for column in self.data.pop(0)]
        file.close()

    def add_source_column(self):
        self.columns.append('SOURCE')
        for i in range(len(self.data)):
            self.data[i].append(self.file_name.replace('\\','/').split('/')[-1])

    def read_excel(self):
        data = excel_reader(self.file_name)
        return data
    
    def rename(self, columns: dict[str: str]):
        for old, new in columns.items():
            self.columns[self.columns.index(old)] = new

    def drop_column(self, column):
        idx = [idx for idx in range(len(self.columns)) if self.columns[idx] == column]
        idx_to_keep = [i for i in range(len(self.columns)) if i not in idx]
        for i in range(len(self.data)):
            self.data[i] = [self.data[i][j] for j in range(len(self.data[i])) if j in idx_to_keep]

        self.columns = [self.columns[i] for i in range(len(self.columns)) if i in idx_to_keep]
        


class Files:
    def __init__(self, files: list[File]):
        self.files = files

    def add_file(self, file: File):
        self.files.append(file)

    def rename_common_columns(self):
        rename_list = File('csv', 'helper_files/column_names.csv')
        # need lookup columns in same fmt as real ones
        rename_dict = {re.sub(r'[^a-zA-Z0-9_]', '', str(a).upper().strip().replace('/', ' ').replace(' ','_')):b for a,b in rename_list.data}
        self.rename(rename_dict)
        

    def drop_remove(self):
        for file in self.files:
            file.drop_column('REMOVE')

    def connect_to_db(self):
        self.db = DB()

    def get_file(self, file_name: str):
        for file in self.files:
            if file.file_name == file_name:
                return file
        raise FileNotFoundError(f'{file_name} does not exist')
    
    def remove_file(self, file_name: str):
        for i, file in enumerate(self.files):
            if file.file_name == file_name:
                self.files.pop(i)
                return
        
        raise FileNotFoundError(f'{file_name} does not exist')
    
    def get_unique_columns(self):
        columns = {}
        files_with_columns = {}
        for file in self.files:
            for column in file.columns:
                columns[column] = 1 + columns.get(column) if columns.get(column) else 1
                files_with_columns[column] = files_with_columns[column] + [file] if files_with_columns.get(column) else [file]
        
        self.column_counts = columns
        self.file_column_map = files_with_columns

    def add_source_columns(self):
        for file in self.files:
            file.add_source_column()

    def rename(self, columns: dict[str:str]):
        # update column map
        self.get_unique_columns()

        # update name where exists
        for old, new in columns.items():
            if self.file_column_map.get(old):
                for file in self.file_column_map[str(old)]:
                    file.rename({old:new})
        # re index
        self.get_unique_columns()

    
    def stage(self):
        # make sqlite3 db

        # update columns
        self.get_unique_columns()
        # insert
        self.db.make_table('staging', list(self.column_counts.keys()))
        for file in self.files:
            self.db.insert('staging', file.columns, file.data)

    def dedup_staging(self, on: list=None, keep: str='1'):
        cols = list(self.column_counts.keys())
        if on:
            for column in on:
                if column not in cols:
                    raise AttributeError(f'{column} does not exist')
        else:
            on = cols
            
        self.db.dedup(table='staging', on=on, keep=keep)


class Directory:
    def __init__(self, path):
        self.path=path
        self.files = None

    def get_csv_files(self):
        files = Files([File('csv', os.path.join(self.path, file)) for file in os.listdir(self.path) if file.endswith('.csv')])
        if self.files:
            for file in files:
                self.files.add_file(file)
        else:
            self.files = files

        return self.files
