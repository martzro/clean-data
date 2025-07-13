import sqlite3
import re
from sqlite_regex import loadable_path
from .logger import logger

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

def _function_re_sub(pattern,string):
    return re.sub(pattern=pattern,string=string,repl='')

def _function_make_lead_id(first_name,last_name,company) -> int:
    lead_id = abs(hash((first_name,last_name,company)))
    return lead_id

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
        self.con.create_function("reSub", 2, _function_re_sub)
        self.con.create_function("make_lead_id",3,_function_make_lead_id)


    def make_table(self, name: str, columns: list, auto_increment_key: str|None=None):
        col_str = ','.join([f'{column}'+' TEXT(255)' for column in columns])
        if auto_increment_key:
            col_str = f'{auto_increment_key} integer primary key AUTOINCREMENT,' + col_str
        query = f"""
                CREATE TABLE IF NOT EXISTS {name} (
                {col_str}
                )
                """
        logger.info(query)
        self.cur.execute(query)
        self.schema[name] = columns


    def make_index(self, name: str, index: str, unique: bool=False):
        if unique:
            create = 'CREATE unique index'
        else:
            create = 'CREATE index'

        query = f"""{create} IF NOT EXISTS {name} on {index}"""
        logger.info(query)
        try:
            self.cur.execute(query)
        except Exception as e:
            logger.error(f'{e} {query}')
    

    def add_column_to_table(self, table, column, dtype):
        query = f"""ALTER TABLE {table}
                    ADD COLUMN {column} {dtype}
                """
        try:
            self.cur.execute(query)
        except Exception as e:
            logger.error(f'{e} {query}')
        else:
            self.con.commit()

    def insert(self, table: str, columns: list, values: list[tuple]):
        self.table_exists(table)       
        query = f"""
                INSERT OR IGNORE INTO {table}
                ({','.join(column for column in columns)})
                VALUES
                ({','.join(['?' for i in range(len(columns))])})
                ;
                """
        try:
            self.cur.executemany(query, list(map(tuple, values)))
        except Exception as e:
            logger.error(e)
        self.con.commit()
        logger.info(f'inserted {len(values)} rows')

    def update(self, table: str, set_values: list, where_values: list=[]):
        #self.table_exists(table)
        if len(where_values) == 0:
            where_values.append('2=2')
        query = f"""UPDATE {table}
                SET {','.join(set_values)}
                WHERE 1=1 AND {' AND '.join(where_values)}
                ;
                """
        # logger.info(query)
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
            logger.error(f'{table} does not exist')
            raise NameError(f'{table} does not exist')