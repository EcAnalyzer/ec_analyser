import csv
import pytz
from datetime import datetime, timedelta
import threading

lock = threading.Lock()

#--------------------------------------------------------------------------------
# 現在日時文字列
# us: μ秒の出力可否
#--------------------------------------------------------------------------------
def get_dt_str(us=False):

    tz = pytz.timezone('Asia/Tokyo')
    if us:
        return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S.%f")
    else:
        return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

#--------------------------------------------------------------------------------
# 経過時間を表す文字列
#--------------------------------------------------------------------------------
def get_dt_diff_str(start, end):
    time_diff = end - start
    hours, remainder = divmod(time_diff.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return '{:02}:{:02}:{:02}'.format(hours, minutes, seconds)

#--------------------------------------------------------------------------------
# 現在日時付きprint出力
#--------------------------------------------------------------------------------
def print_ex(message):
    with lock:    
        print(get_dt_str(us=True) + ',' + message)

#--------------------------------------------------------------------------------
# CSVファイル→二次元配列
#--------------------------------------------------------------------------------
def csv_to_array(filepath):

    try:
        with open(filepath, mode='r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)

            data = []
            for i, row in enumerate(reader):
                if i > 0:
                    data.append(row)

    except Exception as e:
        print_ex(f'エラー発生: {e}')
        return None
    
    return data

#--------------------------------------------------------------------------------
# 二次元配列の日付文字列の区切りをスラッシュに置換
#--------------------------------------------------------------------------------
def replace_date_separator(data, col_indexs):
    
    for row in data:
        for index in col_indexs:
            if index < len(row):
                data_str = row[index]
                if '-' in data_str:
                    row[index] = data_str.replace('-', '/')

    return data

