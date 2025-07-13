from openpyxl import reader as excel_reader
from datetime import datetime, timedelta
from csv import reader as csv_reader
import os
import re
from .logger import logger
from .db import DB

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
        self.file_tracker = 'helper_files/filetracker.tsv'
        self.file_tracker_data = {}
        self.load_file_tracker()
        self.attempt = 0
    
    def set_date(self, date):
        self.date = date
        self.add_date_column()
    
    def load_file_tracker(self):
        if os.path.isfile(self.file_tracker):
            with open(self.file_tracker, 'r') as f:
                for line in f.read().split('\n'):
                    l=line.split('\t')
                    if len(l) == 2:
                        self.file_tracker_data[l[1]] = l[0]
            f.close()
    
    def set_sub_source(self, sub_source):
        self.sub_source = sub_source
        logger.info(self.file_name+' ==> '+self.sub_source)
        self.add_sub_source_column()

    def parse(self, date_string: str, date_formats: list):
        for date_format in date_formats:

            try:
                parsed = datetime.strptime(date_string, date_format)
                if parsed.year == 1900:
                    parsed = parsed + timedelta(days=365*(datetime.now().year - 1900)) # make it this year

                if parsed > datetime.now() or parsed.year < 2020:
                    #print(parsed,' greater than today or less than 2020')
                    continue
                else:
                    return parsed
            except:
                continue
        return None

    
    def extract_date_from_file_name(self,file=None):
            
        patterns_numeric = [r'[\d]{4,9}',r'(\d{1,2})\s(\d{1,2})\s(\d{4}|\d{2})',r'(\d{1,2})\s(\d{2,4})']
        patterns_months = [r"(\d{1,2})\s([A-Za-z]+)\s(\d{4})", r"([A-Za-z]{3,9})\s(\d{4}|\d{2})", r"\d202\d\b",
                           r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)",
                            r"(JAN|FEB|MAR|APR|MAY|JUNE|JUL|AUG|SEP|OCT|NOV|DEC)",

                           ]
        date_formats_numeric=['%d%m%y','%d%m%Y','%m%d%y','%m%d%Y','%d %m %y','%d %m %Y','%m %d %y','%m %d %Y','%m %y','%Y']
        date_format_months = ['%B %Y','%b %Y', '%d %B %Y', '%d %b %Y', '%d %b %y', '%Y', '%B', '%b']
        output_format = '%Y-%m-%d' # default sqlite date format
        if not file:
            file = self.file_name
        filename = file.upper().replace('.',' ').replace('-',' ').replace('_',' ').replace('(', ' ')

        string_numeric=re.sub('[^\d]{4,9}', ' ',filename)
        logger.info(f'matching dates to: {string_numeric}')
        max_date_numeric = 8
        for pattern in patterns_numeric:
            matches = []
            if len(string_numeric) > max_date_numeric:
                for i in range(len(string_numeric) - max_date_numeric):
                    # sliding window of dates so regex covers full string
                    res = re.findall(pattern=pattern, string=string_numeric[i:i+max_date_numeric])
                    if res:
                        matches += res
            else:
                matches = re.findall(pattern=pattern, string=string_numeric)

            if matches:
                for date_string in matches:
                    if type(date_string) == list or type(date_string) == tuple:
                        date_string = ' '.join([str(int(i)) for i in date_string])
                    else:
                        try:
                            date_string = str(int(date_string)) # remove leading zeros
                        except:
                            continue # skip rest if its not only digits
                    logger.info(f'found match {date_string} parsing date')
                    parsed = self.parse(date_string=date_string, date_formats=date_formats_numeric)
                    if parsed:
                        logger.info(f'matched date {parsed}')
                        self.set_date(parsed.strftime(output_format))
                        return
        logger.info(f'no numeric matches. checking full months, matching dates to: {filename}')
        for pattern in patterns_months:
            matches = re.findall(pattern=pattern, string=filename)
            if matches:
                for match in matches:
                    if type(match) == list or type(match) == tuple:
                        match = ' '.join(match)
                    logger.info(f'found match {match} parsing date')
                    parsed = self.parse(date_string=match, date_formats=date_format_months)
                    if parsed:
                        logger.info(f'matched date {parsed}')
                        self.set_date(parsed.strftime(output_format))
                        return
        
        if self.attempt > 0:
            logger.warning(f'no matches found for {filename}')
            return
        else:
            self.attempt +=1 
            f=self.file_name.replace('\\','/').split('/')[-1]
            folder = self.file_tracker_data.get(f)
            if folder:
                logger.warning(f'no matches found for {f}, trying with parent folder {folder}')
                self.extract_date_from_file_name(folder)
            else:
                logger.warning(f'no matches found for {f}, no parent folder: {folder}')
                return

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
                self.data = [row for row in csv_reader(file)] # if null ''
                self.columns = [re.sub(self.column_name_regex, '', str(column).upper().strip().replace('/', ' ').replace(' ','_')) for column in self.data.pop(0)]
            file.close()
        except Exception as e:
            self.read_attempt += 1
            if  type(e) == IndexError:
                self.data = [['none']]
                self.columns = ['remove']
                logger.error(f'{e} {self.file_name}')
                return
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
        self.person_title_remove_regex = r'^(?:MR|MRS|MS|DR)\.?\s*|[^a-zA-Z\s]'
        self.replace_non_alnum_single_space = r"[^a-zA-Z0-9]+|\s{2,}" 
        self.number_regex = r"[^\d]" 

    def add_file(self, file: File):
        self.files.append(file)

    def rename_common_columns(self):
        rename_list = File('csv', 'helper_files/column_names.csv')
        #print(rename_list.data)
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
        #print(self.column_counts)
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
                                                    reSub(
                                                        '{self.person_title_remove_regex}'
                                                        ,upper({column})
                                                        )
                                                    )
                                                )
                      """,]
        self.db.update(table='staging', 
                       set_values=set_values, 
                       where_values=[f"TRIM({column}) is not null"]
                       )

    def fill_null_with_x(self, column):
        set_values = [f"{column} = 'XxX'",]
        where_values = [f"trim({column}) is null OR {column}=''"]
        try:
            logger.info(f'filling nulls with XxX for staging.{column}')
            self.db.update(table='staging',
                           set_values=set_values,
                           where_values=where_values
                           )
        except Exception as e:
            logger.error(e)
    
    def clean_staging_alphanum_doublespace(self, column: str):
        new_column = f'CLEANED_{column}'
        self.db.add_column_to_table('staging', new_column, 'text')
        set_values = [f"""{new_column} = REPLACE(
                                            UPPER(
                                                TRIM(
                                                    REGEX_REPLACE(
                                                        '{self.replace_non_alnum_single_space}'
                                                        ,{column}
                                                        , ' ' -- WE REMOVE SPACE SO NEED TO ADD BACK
                                                    )
                                                )
                                            )
                                        ,',','')
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
                                                        WHEN '{tgt_column}'='{src_column}' -- CASE SAME COLUMN WE JUST WANT TO KEEP 1
                                                            THEN splitTextGetIndex({src_column}, '{delim}', {idx})
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
        
    def match_state_with_full_record(self):
        logger.info('matching states')
        get_people_null_state = '''select distinct CLEANED_FIRST_NAME,CLEANED_LAST_NAME,CLEANED_COMPANY 
                                    from staging
                                    where trim(state_provence) is null
                                '''
        get_state_match = '''select
                                state_provence
                            from staging
                            where trim(state_provence) is not null
                            and cleaned_first_name = :cleaned_first_name
                            and cleaned_last_name = :cleaned_last_name
                            and cleaned_company = :cleaned_company
                            group by 
                                cleaned_first_name,
                                cleaned_last_name,
                                cleaned_company,
                                state_provence
                            having count(1) = 1
                                '''
        res = self.db.cur.execute(get_people_null_state).fetchall() # need to fetch all bc single thread
        
        for cleaned_first_name,cleaned_last_name,cleaned_company in res:
            resp = self.db.cur.execute(get_state_match,
                                           {'cleaned_first_name':cleaned_first_name,
                                                       'cleaned_last_name': cleaned_last_name,
                                                       'cleaned_company': cleaned_company})
            
            state = resp.fetchall()
            if len(state) == 1:
                self.db.update('staging',
                               [f"state_provence='{state[0][0]}'"],
                               ['trim(state_provence) is null',f"cleaned_first_name='{cleaned_first_name}'",
                                f"cleaned_last_name='{cleaned_last_name}'",f"cleaned_company='{cleaned_company}'"])
                logger.info(f' f:{cleaned_first_name} l:{cleaned_last_name} c:{cleaned_company} added state {state}')
            # else:
            #     logger.warning(f' f:{cleaned_first_name} l:{cleaned_last_name} c:{cleaned_company} no state {state}')
        return
    
    def match_email_with_full_record(self):
        logger.info('matching emails')
        self.db.make_index('staging_phone','staging(CLEANED_FIRST_NAME,CLEANED_LAST_NAME,CLEANED_COMPANY,CLEANED_PHONE)')
        self.db.make_index('staging_email','staging(CLEANED_FIRST_NAME,CLEANED_LAST_NAME,CLEANED_COMPANY,CLEANED_EMAIL)')
        self.db.make_index('staging_record','staging(CLEANED_FIRST_NAME,CLEANED_LAST_NAME,CLEANED_COMPANY,CLEANED_EMAIL,CLEANED_PHONE)')

        get_people_null_email = '''select distinct CLEANED_FIRST_NAME,CLEANED_LAST_NAME,CLEANED_COMPANY,CLEANED_PHONE 
                                    from staging
                                    where trim(CLEANED_EMAIL) is null and CLEANED_PHONE is not null
                                '''
        get_email_match = '''select
                                CLEANED_EMAIL
                            from staging
                            where trim(CLEANED_EMAIL) is not null
                            and cleaned_first_name = :cleaned_first_name
                            and cleaned_last_name = :cleaned_last_name
                            and cleaned_company = :cleaned_company
                            and cleaned_phone = :cleaned_phone
                            group by 
                                cleaned_first_name,
                                cleaned_last_name,
                                cleaned_company,
                                cleaned_email,
                                cleaned_phone
                            having count(1) > 0
                                '''
        logger.info('opening null email cursor')
        res = self.db.cur.execute(get_people_null_email).fetchall() # need to fetch all bc single thread
        update_sql = '''update staging 
                        set cleaned_email=:cleaned_email 
                        where 
                            cleaned_email is null 
                            and cleaned_phone=:cleaned_phone 
                            and cleaned_first_name=:cleaned_first_name 
                            and cleaned_last_name=:cleaned_last_name 
                            and cleaned_company=:cleaned_company
                        '''
        logger.info('iterating null email users')
        for cleaned_first_name,cleaned_last_name,cleaned_company,cleaned_phone in res:
            resp = self.db.cur.execute(get_email_match,
                                       {'cleaned_first_name':cleaned_first_name,
                                        'cleaned_last_name': cleaned_last_name,
                                        'cleaned_company': cleaned_company,
                                        'cleaned_phone':cleaned_phone})
            
            email = resp.fetchall()

            if len(email) > 0:
                try:
                    self.db.cur.execute(update_sql,
                                        {'cleaned_first_name':cleaned_first_name,
                                        'cleaned_last_name': cleaned_last_name,
                                        'cleaned_company': cleaned_company,
                                        'cleaned_phone':cleaned_phone,
                                        'cleaned_email':email[0][0]})
                except Exception as e:
                    logger.warning(f' {e} f:{cleaned_first_name} l:{cleaned_last_name} c:{cleaned_company} failed to add email {email}')
                    continue
                else:
                    logger.info(f' f:{cleaned_first_name} l:{cleaned_last_name} c:{cleaned_company} added email {email}')

        self.db.con.commit()
        return
    
    def match_email_with_full_record(self):
        logger.info('matching emails')
        self.db.make_index('staging_phone','staging(CLEANED_FIRST_NAME,CLEANED_LAST_NAME,CLEANED_COMPANY,CLEANED_PHONE)')
        self.db.make_index('staging_email','staging(CLEANED_FIRST_NAME,CLEANED_LAST_NAME,CLEANED_COMPANY,CLEANED_EMAIL)')
        self.db.make_index('staging_record','staging(CLEANED_FIRST_NAME,CLEANED_LAST_NAME,CLEANED_COMPANY,CLEANED_EMAIL,CLEANED_PHONE)')

        get_people_null_phone = '''select distinct CLEANED_FIRST_NAME,CLEANED_LAST_NAME,CLEANED_COMPANY,cleaned_email 
                                    from staging
                                    where trim(cleaned_phone) is null and cleaned_email is not null
                                '''
        get_phone_match = '''select
                                cleaned_phone
                            from staging
                            where trim(cleaned_phone) is not null
                            and cleaned_first_name = :cleaned_first_name
                            and cleaned_last_name = :cleaned_last_name
                            and cleaned_company = :cleaned_company
                            and cleaned_email = :cleaned_email
                            group by 
                                cleaned_first_name,
                                cleaned_last_name,
                                cleaned_company,
                                cleaned_email,
                                cleaned_phone
                            having count(1) > 0
                                '''
        logger.info('opening null phone cursor')
        res = self.db.cur.execute(get_people_null_phone).fetchall() # need to fetch all bc single thread
        update_sql = '''update staging 
                        set cleaned_phone=:cleaned_phone 
                        where 
                            cleaned_phone is null 
                            and cleaned_email=:cleaned_email 
                            and cleaned_first_name=:cleaned_first_name 
                            and cleaned_last_name=:cleaned_last_name 
                            and cleaned_company=:cleaned_company
                        '''
        logger.info('iterating null phone users')
        for cleaned_first_name,cleaned_last_name,cleaned_company,cleaned_email in res:
            resp = self.db.cur.execute(get_phone_match,
                                       {'cleaned_first_name':cleaned_first_name,
                                        'cleaned_last_name': cleaned_last_name,
                                        'cleaned_company': cleaned_company,
                                        'cleaned_email':cleaned_email})
            
            phone = resp.fetchall()

            if len(phone) > 0:
                try:
                    self.db.cur.execute(update_sql,
                                        {'cleaned_first_name':cleaned_first_name,
                                        'cleaned_last_name': cleaned_last_name,
                                        'cleaned_company': cleaned_company,
                                        'cleaned_phone':phone[0][0],
                                        'cleaned_email':cleaned_email})
                except Exception as e:
                    logger.warning(f' {e} f:{cleaned_first_name} l:{cleaned_last_name} c:{cleaned_company} failed to add phone {phone}')
                    continue
                else:
                    logger.info(f' f:{cleaned_first_name} l:{cleaned_last_name} c:{cleaned_company} added phone {phone}')

        self.db.con.commit()
        return


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

        self.make_lead_table() # make and populate client person table
        
        self.db.make_table('final', list(column_map.keys()))
        insert_statement = f"""INSERT INTO FINAL ({','.join(i for i in column_map.keys())})
                                SELECT DISTINCT {','.join(i for i in column_map.values())} FROM STAGING
                            """
        logger.info(insert_statement)
        self.db.cur.execute(insert_statement)
        self.db.con.commit()

        self.db.make_index('final_company','final(company_name)')
        self.db.make_index('final_lead_id','final(lead_id)')
        self.db.make_index('final_record','final(first_name,last_name,company_name)')

    def aggregate(self):
        self.db.make_table('aggregated',['FIRST_NAME','LAST_NAME','COMPANY_NAME','EMAIL','PHONE',
                                         'PROVIDERS','UCC_DATE','PURCHASE_DATE','STATE']
                            )
        self.db.con.commit()
        query = """
                INSERT INTO AGGREGATED (FIRST_NAME,LAST_NAME,COMPANY_NAME,EMAIL,PHONE,
                PROVIDERS,UCC_DATE,PURCHASE_DATE,STATE)
                    SELECT
                    FIRST_NAME,
                    LAST_NAME,
                    COMPANY_NAME,
                    group_concat( DISTINCT EMAIL) AS EMAIL,
                    group_concat( DISTINCT PHONE) AS PHONE,
                    group_concat( DISTINCT PROVIDER||'-'||LEAD_TYPE) AS PROVIDERS,
                    group_concat( DISTINCT UCC_DATE) AS UCC_DATE,
                    group_concat( DISTINCT PURCHASE_DATE) AS PURCHASE_DATE,
                    group_concat( DISTINCT STATE) AS STATE
                FROM 
                FINAL
                GROUP BY 
                    FIRST_NAME,
                    LAST_NAME,
                    COMPANY_NAME
            """
        self.db.cur.execute(query)
        self.db.con.commit()

    def populate_lead_table(self) -> None:
        logger.info('populating lead table')
        sql_insert = '''insert or ignore into client_person(lead_id,first_name,last_name,company)
        values (?,?,?,?)'''

        sql_get_data = '''
                select 
                    make_lead_id(a.cleaned_first_name,a.cleaned_last_name,a.cleaned_company),
                    a.cleaned_first_name,
                    a.cleaned_last_name,
                    a.cleaned_company
                from (
                    select distinct cleaned_first_name,cleaned_last_name,cleaned_company from staging) a'''
        data = self.db.cur.execute(sql_get_data).fetchall()
        
        self.db.cur.executemany(sql_insert,data)
        self.db.con.commit()

        return
    
    def populate_lead_id_column(self):
        logger.info('populating lead id column in staging')
        self.db.update('staging',
                       ['''lead_id=(select client_person.lead_id from client_person 
                    join staging 
                    on client_person.first_name=staging.cleaned_first_name
                    and client_person.last_name=staging.cleaned_last_name
                    and client_person.company=staging.cleaned_company)'''
                        ],
                    ['lead_id is null'])
        
    
    def make_lead_table(self) -> None:
        logger.info('making lead table')
        self.db.make_table('client_person',['lead_id','first_name','last_name','company_name'])
        self.populate_lead_table()

        self.db.make_index('client_person_company','client_person(company_name)')
        self.db.make_index('client_person_lead_id','client_person(lead_id)')
        self.db.make_index('client_person_record','client_person(first_name,last_name,company_name)',True)

        self.db.add_column_to_table('staging','lead_id','text')
        self.populate_lead_id_column()
        
        return

