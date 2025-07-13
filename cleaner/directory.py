from time import time
from pathlib import Path
import csv
from itertools import count
import os
from .logger import logger
from .file import File,Files


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
    
    def export_table_to_file(self,table: str='final',rows_per_file: int = 500_000, fname: str = 'output',fmt: str='csv',delimiter:str=','):
        logger.info(f'Exporting final table to {fname} in {rows_per_file} rows per file')
        query = f"select * from {table} order by company_name asc"
        res = self.files.db.cur.execute(query)
        done = False
        c = count()
        next(c) # start at 1
        columns = [i[0] for i in self.files.db.cur.description]
        while not done:
            data = res.fetchmany(rows_per_file)
            if data:
                outfile = os.path.join(self.output_dir, f'{fname}_{next(c)}.{fmt}')
                with open(outfile, 'w', newline="",encoding='utf-8') as file:
                    writer = csv.writer(file, delimiter=delimiter)
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
        logger.info(f'* Duration: {self.duration} seconds'+'*'*(108 - len(f'* Duration: {self.duration} seconds')))
        logger.info('*'*108)