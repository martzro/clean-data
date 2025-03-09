from openpyxl import reader as excel_reader
from openpyxl import writer as excel_writer
import sqlite3
from csv import reader as csv_reader
from csv import DictReader as csv_dict_reader
from csv import writer as csv_writer
import os
import re
from sqlite_regex import loadable_path
import logging
from itertools import count
from pathlib import Path
from time import time

logging.basicConfig(
    filename='logs.log',
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

logger = logging.getLogger(__name__)

# sqlite functions
def _function_split_text_get_index(text, delim, index):
    if index >= 0:
        try:
            return text.split(delim)[index].title()
        except:
            return None
    else:
        return text.split(delim)[index].title() if len(text.split(delim)) > 1 else None
    
def _function_extract_numbers_format_phone(phone):
    
    phonevals = re.sub(pattern=r'[^\d]', repl='', string=str(phone))
    if phonevals:
        phonevals = str(phonevals)
        if len(phone) < 10:
            return None
        return "("+phonevals[-10:-7]+") "+phonevals[-7:-4]+"-"+phonevals[-4:]
    
def _function_clean_email_address(email):
    if '@' and '.' in email:
        return email.upper().strip()
    else:
        return None
    
def _function_title_string(text):
    if not text:
        return None
    return str(text).title()

class DB:
    def __init__(self):
        self.con = sqlite3.connect('db.db')
        self.cur = self.con.cursor()
        self.con.enable_load_extension(True)
        self.con.load_extension(loadable_path()) # https://github.com/asg017/sqlite-regex?tab=readme-ov-file
        self.con.enable_load_extension(False)
        self.schema = {}

        # define functions
        self.con.create_function("splitTextGetIndex", 3, _function_split_text_get_index)
        self.con.create_function("parsePhone", 1, _function_extract_numbers_format_phone)
        self.con.create_function("parseEmail", 1, _function_clean_email_address)
        self.con.create_function("title", 1, _function_title_string)


    def make_table(self, name, columns):
        query = f"""
                CREATE TABLE IF NOT EXISTS {name} (
                {','.join([column+' TEXT(255)' for column in columns])}
                );
                """
        self.cur.execute(query)
        self.schema[name] = columns

    def add_column_to_table(self, table, column, dtype):
        query = f"""ALTER TABLE {table}
                    ADD COLUMN {column} {dtype}
                """
        self.cur.execute(query)
        self.con.commit()

    def insert(self, table: str, columns: list, values: list[tuple]):
        self.table_exists(table)       
        query = f"""
                INSERT INTO {table}
                ({','.join(column for column in columns)})
                VALUES
                ({','.join(['?' for i in range(len(columns))])})
                ;
                """
        try:
            self.cur.executemany(query, list(map(tuple, values)))
        except Exception as e:
            logger.error(e, list(filter(lambda x: len(x) < len(columns), list(map(tuple, values))))[0],columns)
        self.con.commit()
        logger.info(f'inserted {len(values)} rows')

    def update(self, table: str, set_values: list, where_values: list=[]):
        self.table_exists(table)
        query = f"""UPDATE {table}
                SET {','.join(set_values)}
                WHERE 1=1 AND {' AND '.join(where_values)}
                ;
                """
        logger.info(query)
        self.cur.execute(query)
        self.con.commit()

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
        logger.info(f'deleted {before-after} rows')
        self.con.rollback()



        
    def table_exists(self, table):
        if not self.schema.get(table):
            raise NameError(f'{table} does not exist')     

class File:
    def __init__(self, file_type: str, file_name: str):
        self.file_type = file_type
        self.file_name = file_name
        self.date = None
        self.data = []
        self.columns = []
        self.column_name_regex = r'[^a-zA-Z0-9_]'
        self.encoding_retrys = ['utf-8', 'cp1252', 'latin-1']
        self.read_attempt = 0
        self._get_data_()
    
    def set_date(self, date):
        self.date = date
        self.add_date_column()
    
    def set_sub_source(self, sub_source):
        self.sub_source = sub_source
        logger.info(self.file_name+' ==> '+self.sub_source)
        self.add_sub_source_column()

    def extract_date_from_file_name(self):
        pattern = r'[\d]{5,9}'
        matches = re.findall(pattern=pattern, string=self.file_name)
        if matches:
            match = matches[0]
            if len(match) == 6:
                self.set_date(f'{match[0:2]}-{match[2:4]}-{match[4:6]}')

    def _sliceby(self, string:str, delim: str, before: bool):
        idx = 0 if before else -1
        return string.split(delim)[idx]
    
    def extract_sub_source_from_file_name(self):
        def add_to_file(base, add):
            return add + ' ' + base
        
        patterns = [r'\dK',r'[^a-zA-Z ]', r' +']
        file = self.file_name.upper().replace('\\','/').split('/')[-1]
        val = self._sliceby(self._sliceby(self._sliceby(file, '_', False), '.', True), 'DAYS', True)
        val = val.replace('PARK BUSINESS CAPITAL','')
        for pattern in patterns:
            val = re.sub(pattern=pattern,repl=' ',string=val).strip()
        if 'UCC' in file:
            add_to_file(val, 'UCC')
        if 'FIRE' in file:
            add_to_file(val, 'FIRE')
        
        self.set_sub_source(val)
        
    
    def _get_data_(self):
        if self.file_type == 'csv':
            return self.read_csv()
        elif self.file_type == 'xlsx':
            return self.read_excel()
    
    def read_csv(self):
        try:
            with open(self.file_name, mode='r', encoding=self.encoding_retrys[self.read_attempt]) as file:
                self.data = [row for row in csv_reader(file)]
                self.columns = [re.sub(self.column_name_regex, '', str(column).upper().strip().replace('/', ' ').replace(' ','_')) for column in self.data.pop(0)]
            file.close()
        except:
            self.read_attempt += 1
            logger.warning(f'Retrying: read_csv with encoding {self.encoding_retrys[self.read_attempt - 1]} failed trying with {self.encoding_retrys[self.read_attempt]}, file: {self.file_name}')
            self.read_csv() # try again

    def add_source_column(self, source: str= None):
        self.columns.append('SOURCE')
        if not source:
            for i in range(len(self.data)):
                self.data[i].append(self.file_name.replace('\\','/').split('/')[-1])
        else:
            for i in range(len(self.data)):
                self.data[i].append(source) # custom souce override
    
    def add_date_column(self):
        if self.date:
            self.columns.append('DATE_FROM_FILE_NAME')
            for i in range(len(self.data)):
                self.data[i].append(self.date)
    
    def add_file_column(self):
        self.columns.append('FILE')
        for i in range(len(self.data)):
                self.data[i].append(self.file_name.replace('\\','/').split('/')[-1])

    def add_sub_source_column(self):
        if self.sub_source:
            self.columns.append('SUB_SOURCE')
            for i in range(len(self.data)):
                self.data[i].append(self.sub_source)

    def read_excel(self):
        data = excel_reader(self.file_name)
        return data
    
    def rename(self, columns: dict[str: str]):
        for old, new in columns.items():
            logger.warning(self.file_name+': Renaming '+old+' to: '+new)
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
        self.person_title_remove_regex = r'^(MR|MRS|MS|DR)\.?\s*|[^a-zA-Z\s]'
        self.replace_non_alnum_single_space = r"[^a-zA-Z0-9]+|\s{2,}" 
        self.number_regex = r"[^\d]" 

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

    def add_source_columns(self, source: str=None):
        for file in self.files:
            file.add_source_column(source)

    def extract_date_from_file_name(self):
        for file in self.files:
            file.extract_date_from_file_name()

    def extract_sub_source_from_file_name(self):
        for file in self.files:
            file.extract_sub_source_from_file_name()
    
    def add_file_column(self):
        for file in self.files:
            file.add_file_column()

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
        
        try:
            self.db.make_table('staging', list(self.column_counts.keys()))

        except Exception as e:
            logger.error(e, self.column_counts, list(self.column_counts.keys()), stack_info=True)
            raise e
        for file in self.files:
            try:
                self.db.insert('staging', file.columns, file.data)
            except Exception as e:
                 logger.error(e, file.columns, file.file_name)

    def dedup_staging(self, on: list=None, keep: str='1'):
        cols = list(self.column_counts.keys())
        if on:
            for column in on:
                if column not in cols:
                    raise AttributeError(f'{column} does not exist')
        else:
            on = cols
            
        self.db.dedup(table='staging', on=on, keep=keep)

    def clean_staging_person_name(self, column: str):
        new_column = f'CLEANED_{column}'
        self.db.add_column_to_table('staging', new_column, 'text')
        set_values = [f"""{new_column} = TITLE(
                                                TRIM(
                                                    REGEX_REPLACE(
                                                        '{self.person_title_remove_regex}'
                                                        ,{column}
                                                        , ''
                                                    )
                                                )
                                            )
                      """,]
        self.db.update(table='staging', 
                       set_values=set_values, 
                       where_values=[f"TRIM({column}) is not null"]
                       )
        
    def clean_staging_alphanum_doublespace(self, column: str):
        set_values = [f"""{column} = UPPER(
                                            TRIM(
                                                REGEX_REPLACE(
                                                    '{self.replace_non_alnum_single_space}'
                                                    ,{column}
                                                    , ' ' -- WE REMOVE SPACE SO NEED TO ADD BACK
                                                )
                                            )
                                        )
                      """,]
        self.db.update(table='staging', 
                       set_values=set_values, 
                       where_values=[f"TRIM({column}) is not null"]
                       )

    def split_and_choose(self, src_column: str, tgt_column: str,delim: str, idx: int):
        set_values = [f"""{tgt_column} = CASE
                                            WHEN {tgt_column} IS NULL AND {src_column} IS NOT NULL
                                                THEN splitTextGetIndex({src_column}, '{delim}', {idx})
                                            WHEN {src_column} IS NULL THEN {tgt_column}
                                            WHEN {tgt_column} <> splitTextGetIndex({src_column}, '{delim}', {idx})
                                                THEN   -- NAMES ARE DIFFERENT AND NOT NULL
                                                    CASE 
                                                        WHEN LENGTH(splitTextGetIndex({src_column}, '{delim}', {idx})) >= {tgt_column}
                                                            THEN splitTextGetIndex({src_column}, '{delim}', {idx})
                                                        ELSE {tgt_column}
                                                    END
                                            ELSE {tgt_column} -- THEYRE THE SAME, CHOOSE ONE
                                        END
                      """,
                      ]
                
        self.db.update(table='staging',
                       set_values=set_values,
                       where_values=[f"TRIM({src_column}) is not null OR TRIM({tgt_column}) is not null"]
                       )
        
    
    def get_date_from_staging(self):
        self.db.add_column_to_table('staging', 'DATE_FROM_DATA', 'date')

        set_values = [f"""DATE_FROM_DATA = FILLING_MONTH||"-"||FILLING_DAY||"-"||FILLING_YEAR
                      """,]
        where_values = ['FILLING_DAY IS NOT NULL','FILLING_MONTH IS NOT NULL','FILLING_YEAR IS NOT NULL']

        self.db.update(table='staging',
                       set_values=set_values,
                       where_values=where_values
                       )
        
    def clean_staging_phone(self):
        self.db.add_column_to_table('staging', 'CLEANED_PHONE', 'text')
        set_values = [f"""CLEANED_PHONE = parsePhone(PHONE)
                      """,]
                
        self.db.update(table='staging',
                       set_values=set_values,
                       where_values=["LENGTH(TRIM(PHONE)) >= 10"]
                       )
        
    def clean_staging_email(self):
        self.db.add_column_to_table('staging', 'CLEANED_EMAIL', 'text')
        set_values = [f"""CLEANED_EMAIL = parseEmail(EMAIL)
                      """,]
                
        self.db.update(table='staging',
                       set_values=set_values,
                       where_values=["TRIM(EMAIL) IS NOT NULL"]
                       )
        
    def upper_trim_column(self, column):
        set_values = [f"""{column} = UPPER(TRIM({column}))
                      """,]
                
        self.db.update(table='staging',
                       set_values=set_values,
                       where_values=[f"TRIM({column}) IS NOT NULL"]
                       )
    def make_number_value(self, column):
        set_values = [f"""{column} = TRIM(
                                            REGEX_REPLACE(
                                                '{self.number_regex}'
                                                ,{column}
                                                , ''
                                            )
                                        )
                        """,
                        ]
                
        self.db.update(table='staging',
                       set_values=set_values,
                       where_values=[f"TRIM({column}) IS NOT NULL"]
                       )
    
    def final(self, column_map: dict):
        logger.info(f'moving data to final table: {column_map}')
        self.db.make_table('final', list(column_map.keys()))
        insert_statement = f"""INSERT INTO FINAL ({','.join(i for i in column_map.keys())})
                                SELECT {','.join(i for i in column_map.values())} FROM STAGING
                            """
        logger.info(insert_statement)
        self.db.cur.execute(insert_statement)
        self.db.con.commit()
class Directory:
    def __init__(self, path):
        self.start_time = time()
        logger.info('*'*50+'STARTING'+'*'*50)
        self.path=path
        self.files = None
        self.output_dir = 'output'
        Path(self.output_dir).mkdir(exist_ok=True, parents=True)
    
    def get_csv_files(self):
        files = Files([File('csv', os.path.join(self.path, file)) for file in os.listdir(self.path) if file.endswith('.csv')])
        if self.files:
            for file in files:
                self.files.add_file(file)
        else:
            self.files = files

        return self.files
    
    def export_table_to_csv(self, rows_per_file: int = 500_000, fname: str = 'output'):
        logger.info(f'Exporting final table to {fname} in {rows_per_file} rows per file')
        query = "select * from final"
        res = self.files.db.cur.execute(query)
        done = False
        c = count()
        next(c) # start at 1
        columns = [i[0] for i in self.files.db.cur.description]
        while not done:
            data = res.fetchmany(rows_per_file)
            if data:
                outfile = os.path.join(self.output_dir, f'{fname}_{next(c)}.csv')
                with open(outfile, 'w', newline="") as file:
                    writer = csv_writer(file)
                    writer.writerow(columns)
                    writer.writerows(data)
                file.close()
                logger.info(f'Wrote {rows_per_file} rows to {outfile}')
            else:
                done = True
        self.done()

    def done(self):
        self.end_time = time()
        self.duration = str(round(self.end_time - self.start_time, 0))
        logger.info('*'*50+'FINISHED'+'*'*50)
        logger.info(f'* Duration: {self.duration} seconds'+'*'*108 - len(f'* Duration: {self.duration} seconds'))
        logger.info('*'*108)
    


