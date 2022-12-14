import csv
import ftplib
import os
from collections import defaultdict
from datetime import datetime
from django.utils import timezone
import pandas as pd
from celery.utils.log import get_task_logger

from albo.celery import app

from user_app import models
logger_celery = get_task_logger(__name__)


def function_with_try_int(x):
    try:
        data = int(x)
    except ValueError:
        data = int(''.join(x.split()))
    return data


def transform_filename_to_dt(i):
    return datetime.strptime(i.split("_")[-1].split(".")[0], '%Y-%m-%dT%H:%M:%S')


def get_last_filename(ftp):
    logger_celery.debug('get func get_last_filename')
    list_data_ftp = [i for i in ftp.nlst() if i.endswith('.csv')]
    sort_list_file = sorted(list_data_ftp, key=transform_filename_to_dt)
    filename_last = sort_list_file[-1]
    logger_celery.debug('out func get_last_filename - %s' % filename_last)
    return filename_last


def get_file_ftp(import_ftp_data):
    import_ftp_data_list = import_ftp_data.split(':')
    logger_celery.debug('get func get_file_ftp')
    ftp = ftplib.FTP(*import_ftp_data_list)

    file = get_last_filename(ftp)

    with open(file, 'wb') as f:
        ftp.retrbinary('RETR ' + file, f.write)

    ftp.quit()
    logger_celery.debug('out func get_file_ftp')
    return file


def read_csv(file):
    df = pd.read_csv(file, delimiter=';')
    my_df = df.copy()

    my_df[my_df.columns[1]] = my_df[my_df.columns[1]].apply(function_with_try_int)
    dict_code_1C = my_df.set_index(my_df.columns[0])[my_df.columns[1]].to_dict()

    tuple_code_for_map = models.OneCCodeModel.objects.filter(uniq_code_one_c__in=dict_code_1C.keys()).values_list(
        'uniq_code_one_c', 'map_code__uniq_code')
    my_dict = defaultdict(int)

    for key, value in tuple_code_for_map:
        my_dict[value] += dict_code_1C[key]

    os.remove(file)
    return my_dict


def write_result_in_base(data):
    list_model = models.AlboProductModel.objects.filter(uniq_code__in=data.keys())
    
    for obj_model in list_model:
        obj_model.quantity = data.get(obj_model.uniq_code)
    if list_model.exists():
        models.AlboProductModel.objects.bulk_update(list_model, ['quantity'])


def dict_writer(data, filename):
    write_result_in_base(data)
    with open(filename, "w", encoding="utf-8") as f_obj:
        writer = csv.writer(f_obj, delimiter=';')

        for key, value in data.items():
            writer.writerow([key, value])


def get_filename(filename, _type):
    pattern_date = "%Y-%m-%dT%H:%M:%S"
    dt_now = timezone.now()
    name_file = filename.split("_")[0]
    return f'{name_file}_{dt_now:{pattern_date}}' + _type, dt_now


def export_file_ftp(file_csv: str, export_ftp_data, _type: str = None, filename_for_export=None):
    logger_celery.debug('get func import_file-%s' % file_csv)

    export_ftp_data_list = export_ftp_data.split(':')
    ftp = ftplib.FTP(*export_ftp_data_list)

    file = open(filename_for_export, 'rb')
    filename, dt_now = get_filename(file_csv, _type)  # file to send

    logger_celery.debug('-- filename-%s' % filename)
    ftpResponseMessage = ftp.storbinary(f'STOR {filename}', file)  # send the file
    logger_celery.debug('-- STOR filename-%s' % f'STOR {filename}')

    ftp_list_files = ftp.nlst()
    logger_celery.debug(f'{len(ftp_list_files)}')
    logger_celery.debug(f'ftpResponseMessage - {ftpResponseMessage}')
    logger_celery.debug(f'{filename} in nlst ------ {filename in ftp_list_files}')
    file.close()
    ftp.quit()

    models.PeriodicTimeModel.objects.update(**{'last_time': dt_now})


@app.task(bind=True)
def task_export(*args, import_ftp_address: str = '', export_ftp_address: str = '', filename_for_export: str = '',
                _type='csv', **kwargs):
    file_last = get_file_ftp(import_ftp_address)
    dict_to_write = read_csv(file_last)
    dict_writer(dict_to_write, filename_for_export)
    # export_file_ftp(import_ftp_address, export_ftp_address, filename_for_export)

