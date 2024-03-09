import os
import re
import math
import pandas as pd
import numpy as np
from datetime import datetime
from selenium.webdriver.common.by import By
from tool import *
from google_api import *
from web_driver import *
from enum import Enum
from threading import Thread, Lock
import glob
import time
from selenium.webdriver.support.ui import WebDriverWait
import json


# パス関連
if os.getenv('GITHUB_ACTIONS') == 'true':
    base_dir = os.getenv('GITHUB_WORKSPACE')
else:
    WORK_DIR_NAME = 'work'
    base_dir = os.path.join(os.path.abspath(os.curdir), WORK_DIR_NAME)
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

#--------------------------------------------------------------------------------
# 並列化
#--------------------------------------------------------------------------------
THREAD_MAX_ORDER = 10
THREAD_MAX_LIST = 10
THREAD_MAX_DETAIL = 20
THREAD_MAX_PRICE = 20
THREAD_MAX_MARKET = 20
THREAD_RETRY_MAX = 5

#--------------------------------------------------------------------------------
# 処理状態
#--------------------------------------------------------------------------------
class GetDataStep(Enum):
    INIT_NONE = '初回データ取得予約'
    INIT_RUN_ORDER = '初回取得中(注文実績)'
    INIT_RUN_LIST = '初回取得中(出品リスト)'
    INIT_RUN_CHECK = '初回取得中(出品リスト確認)'
    INIT_RUN_ITEM = '初回取得中(出品データ)'
    INIT_RUN_MARKET = '初回取得中(市場データ)'
    INIT_DONE = '初回取得済'
    INIT_ERROR = '初回取得エラー'
    UPDATE_RUN_ORDER = '更新中(注文実績)'
    UPDATE_RUN_LIST = '更新中(出品リスト)'
    UPDATE_RUN_ITEM = '更新中(出品データ)'
    UPDATE_RUN_PRICE = '更新中(価格)'
    UPDATE_RUN_MARKET = '更新中(市場データ)'
    UPDATE_DONE = '更新済'
    UPDATE_ERROR = '更新エラー'

#--------------------------------------------------------------------------------
# 外注総合管理ツール
#--------------------------------------------------------------------------------
if os.getenv('GITHUB_ACTIONS') == 'true':
    tmp = os.getenv('MANAGE_SS_URL').replace('\r\n', '\n').replace('\r', '\n')
    MANAGE_SS_URL = tmp.strip().split('\n')
    print(MANAGE_SS_URL)
else:
    with open('config.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    MANAGE_SS_URL = data['manage_ss_url']

MANAGE_SS_NAME = '管理'

MANAGE_ROW_START = 5
MANAGE_COL_STATE = 5
MANAGE_COL_START_DT = 6
MANAGE_COL_END_DT = 7
MANAGE_COL_TIME = 8

MANAGE_COL_INIT_TOTAL = 9
MANAGE_COL_INIT_STEP = 10
MANAGE_COL_UPDATE_TOTAL = 15
MANAGE_COL_UPDATE_STEP = 16
MANAGE_COL_ERROR = 20

MANAGE_COLS = [
        'sheet_url',    # スプレッドURL
        'sheet_name',   # シート名
        'create_date',  # 作成日
        'shop_url',     # ライバルURL
        'order_url',    # 注文実績URL
        'item_url',     # 商品URL
        'state',        # 状態
        'update'        # 更新日時
    ]

#--------------------------------------------------------------------------------
# 分析シート - 操作
#--------------------------------------------------------------------------------
OPE_SHEET_NAME = '操作'
OPE_COL_VALUE = 3
OPE_ROW_STATE = 12
OPE_ROW_START_DT = 13
OPE_ROW_END_DT = 14
OPE_ROW_TIME = 15

#--------------------------------------------------------------------------------
# 出品データリスト(差分比較用)
#--------------------------------------------------------------------------------
LIST_ROW_START = 2              # スプレッドシートの開始行
ITEM_COUNT_PER_PAGE = 80        # 1ページ当たりの商品数

# 出品データCSVファイル
FILE_PATH_LIST = os.path.join(base_dir, 'list.csv')
FILE_PATH_LIST_INC = os.path.join(base_dir, 'list_inc.csv')
FILE_PATH_LIST_DEC = os.path.join(base_dir, 'list_dec.csv')

# スプレッドシートの列
LIST_COLS = ['No.', 'ID', '出品', '取得日時', '商品名', '商品URL', '出品日']

#--------------------------------------------------------------------------------
# 分析シート - 出品データ
#--------------------------------------------------------------------------------
ITEM_SHEET_NAME = '出品データ'
ITEM_ROW_START = 2              # スプレッドシートの開始行

# 出品データCSVファイル
FILE_PATH_ITEM = os.path.join(base_dir, 'item.csv')
FILE_PATH_DETAIL = os.path.join(base_dir, 'item_detail.csv')
FILE_PATH_PRICE = os.path.join(base_dir, 'item_price.csv')

# スプレッドシートの列
ITEM_COLS = ['No.', 'ID', '出品', '取得日時', '商品名', '商品URL', '出品日',
            'ブランド', 'ブランド1', 'ブランド1 URL', 'ブランド2', 'ブランド2 URL', 'ブランド3', 'ブランド3 URL',
            'カテゴリ1', 'カテゴリ2', 'カテゴリ3', 'ブランド x カテゴリ3', '価格', 'タグ1', 'タグ2',
            'お問い合わせ', 'アクセス', 'お気に入りアイテム登録', '買付地', '買付先名', '発送地', '型番']

#--------------------------------------------------------------------------------
# 分析シート - 注文実績データ
#--------------------------------------------------------------------------------
ORDER_SHEET_NAME = '注文実績'
ORDER_MAX_PAGES = 30

# 注文実績データCSVファイル
FILE_PATH_ORDER = os.path.join(base_dir, 'order.csv')
FILE_TMP_NAME = 'order'
FILE_TMP_EXT = 'csv'

# スプレッドシートの列
ORDER_COLS = ['No.', '取得日時', '商品名', '商品URL', '商品ID', '出品日', '成約日']

# ソートキー(成約日=昇順 and No.=昇順)
def sort_key(row):
    sale_date = datetime.strptime(row[6], '%Y/%m/%d')
    no = int(row[0])
    return (sale_date, no)

#--------------------------------------------------------------------------------
# 分析シート - 市場データ
#--------------------------------------------------------------------------------
MARKET_SHEET_NAME = '市場データ'
MARKET_MAX_PAGES = 30
MARKET_MAX_RETRY = 5
MARKET_DAY_SPAN = 7     # 取得頻度(日数)

# 注文実績データCSVファイル
FILE_PATH_MARKET = os.path.join(base_dir, 'market.csv')

# スプレッドシートの列
MARKET_COLS = ['No.', 'ブランド', 'ブランドURL', '出品数']

#--------------------------------------------------------------------------------
# 分析シート - 市場データ
#--------------------------------------------------------------------------------
MODEL_SHEET_NAME = '型番'

# 注文実績データCSVファイル
FILE_PATH_MODEL = os.path.join(base_dir, 'model.csv')

# スプレッドシートの列
MODEL_COLS = ['ID', '型番']

#--------------------------------------------------------------------------------
# ステータス出力
#--------------------------------------------------------------------------------
def update_proc_status(url_manage, url_sheet, index, state):
    # 外注総合管理シート
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_STATE, state)
    # 分析シート
    set_ss_value(url_sheet, OPE_SHEET_NAME, OPE_ROW_STATE, OPE_COL_VALUE, state)

#--------------------------------------------------------------------------------
# 開始時間出力
#--------------------------------------------------------------------------------
def update_proc_start_time(url_manage, url_sheet, index):
    # 外注総合管理シート
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_START_DT, get_dt_str())    # 開始時間 出力
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_END_DT, '')                # 終了時間 クリア
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_TIME, '')                  # 処理時間 クリア
    # 分析シート
    set_ss_value(url_sheet, OPE_SHEET_NAME, OPE_ROW_START_DT, OPE_COL_VALUE, get_dt_str())                   # 開始時間 出力
    set_ss_value(url_sheet, OPE_SHEET_NAME, OPE_ROW_END_DT, OPE_COL_VALUE, '')                               # 終了時間 クリア
    set_ss_value(url_sheet, OPE_SHEET_NAME, OPE_ROW_TIME, OPE_COL_VALUE, '')                                 # 処理時間 クリア

#--------------------------------------------------------------------------------
# 終了時間出力
#--------------------------------------------------------------------------------
def update_proc_end_time(url_manage, url_sheet, index):
    # 外注総合管理シート
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_END_DT, get_dt_str())
    # 分析シート
    set_ss_value(url_sheet, OPE_SHEET_NAME, OPE_ROW_END_DT, OPE_COL_VALUE, get_dt_str())

#--------------------------------------------------------------------------------
# 処理時間出力
#--------------------------------------------------------------------------------
def update_proc_time(url_manage, url_sheet, index, dt_start, dt_end):
    # 外注総合管理シート
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_TIME, get_dt_diff_str(dt_start, dt_end))
    # 分析シート
    set_ss_value(url_sheet, OPE_SHEET_NAME, OPE_ROW_TIME, OPE_COL_VALUE, get_dt_diff_str(dt_start, dt_end))

#--------------------------------------------------------------------------------
# ステップ処理時間出力
#--------------------------------------------------------------------------------
def update_step_proc_time(url_manage, index, col, dt_start, dt_end):
    # 外注総合管理シート
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, col, get_dt_diff_str(dt_start, dt_end))

#--------------------------------------------------------------------------------
# ステップ処理時間クリア(初回)
#--------------------------------------------------------------------------------
def clear_step_proc_time_init(url_manage, index):
    # 外注総合管理シート
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_INIT_TOTAL, '')
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_INIT_STEP + 0, '')
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_INIT_STEP + 1, '')
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_INIT_STEP + 2, '')
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_INIT_STEP + 3, '')
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_INIT_STEP + 4, '')
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_ERROR, '')

#--------------------------------------------------------------------------------
# ステップ処理時間クリア(更新)
#--------------------------------------------------------------------------------
def clear_step_proc_time_update(url_manage, index):
    # 外注総合管理シート
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_UPDATE_TOTAL, '')
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_UPDATE_STEP + 0, '')
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_UPDATE_STEP + 1, '')
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_UPDATE_STEP + 2, '')
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_UPDATE_STEP + 3, '')
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_ERROR, '')

#--------------------------------------------------------------------------------
# エラー詳細出力
#--------------------------------------------------------------------------------
def set_error_detail(url_manage, index, message):
    # 外注総合管理シート
    set_ss_value(url_manage, MANAGE_SS_NAME, MANAGE_ROW_START + index, MANAGE_COL_ERROR, message)

#--------------------------------------------------------------------------------
# 外注管理情報取得
#--------------------------------------------------------------------------------
def get_management_info(url):

    try:
        print_ex('get_management_info 外注管理情報取得 開始')

        # 管理情報シート取得
        data_all = get_ss_all_values(url, MANAGE_SS_NAME)

        url_list = []

        for i, row in enumerate(data_all):
            if i < MANAGE_ROW_START - 1:
                continue

            data = {}
            for col in MANAGE_COLS:
                data[col] = ''

            # データ取得
            data['sheet_url'] = row[0]      # スプレッドシートURL
            data['sheet_name'] = row[1]     # シート名
            data['create_date'] = row[2]    # 作成日
            data['shop_url'] = row[3]       # ライバルURL
            data['state'] = row[4]          # 状態
            data['update'] = row[5]         # 更新日時

            # 注文実績URL
            shop_id = data['shop_url'].split('/')[-1].split('.html')[0]
            data['order_url'] = f'https://www.buyma.com/buyer/{shop_id}/sales_<% page %>.html'

            # 商品リストURL
            shop_id = data['shop_url'].split('/')[-1].split('.html')[0]
            data['item_url'] = f'https://www.buyma.com/r/-B{shop_id}O2/'

            url_list.append(data)

        print_ex('get_management_info 外注管理情報取得 終了')

    except Exception as e:
        print_ex("エラー発生: " + str(e))
        return None

    return url_list

#--------------------------------------------------------------------------------
# 注文実績取得
#--------------------------------------------------------------------------------
def get_order_data_multi(dt, url):

    try:
        thread_max = THREAD_MAX_ORDER

        base = ORDER_MAX_PAGES // thread_max
        remainder = ORDER_MAX_PAGES % thread_max
        page_nums = [base + (1 if i < remainder else 0) for i in range(thread_max)]

        start_pages = [1]
        for i in range(1, len(page_nums)):
            start_pages.append(start_pages[i-1] + page_nums[i-1])

        # テンポラリファイルを削除
        file_pattern = f'{FILE_TMP_NAME}*.{FILE_TMP_EXT}'
        file_pattern = os.path.join(base_dir, file_pattern)
        delete_files = glob.glob(file_pattern)
        for file in delete_files:
            try:
                os.remove(file)
            except OSError as e:
                print_ex(f'ファイル "{file}" の削除中にエラーが発生しました: {e}')

        threads = []
        errors = []
        lock = Lock()
        for i in range(thread_max):
            thread = Thread(target=get_order_data, args=(dt, url, i, start_pages[i], page_nums[i], errors, lock))
            threads.append(thread)
            thread.start()    

        # すべてのスレッドが終了するまで待機
        for thread in threads:
            thread.join()

        # エラー確認
        if errors:
            for error in errors:
                print_ex(f'[Th.{error[0]+1}]エラー発生')
            raise

        # 収集したファイルを連結
        df_concat = pd.DataFrame()
        for i in range(thread_max):
            file_name = f'{FILE_TMP_NAME}_{i + 1}.{FILE_TMP_EXT}'
            file_path = os.path.join(base_dir, file_name)
            if os.path.exists(file_path):
                df = pd.read_csv(file_path,
                    dtype={'No.': int, '商品ID': str},
                    parse_dates=['取得日時', '出品日', '成約日'])
                df_concat = pd.concat([df_concat, df], ignore_index=True)

        df_concat['No.'] = range(1, 1 + len(df_concat))
        df_concat.to_csv(FILE_PATH_ORDER, index=False)

    except Exception as e:
        print_ex(f'get_order_data_multi エラー発生: {e}')

    return


# 注文実績取得処理
def get_order_data(dt, url, index, page_start, page_num, errors, lock):

    for i in range(THREAD_RETRY_MAX):

        result = get_order_data_worker(dt, url, index, page_start, page_num, lock)

        if result:
            print_ex(f'[Th.{index+1}] 試行 {i+1} 回目成功')
            return
        else:
            print_ex(f'[Th.{index+1}] 試行 {i+1} 回目失敗')

    print_ex(f'[Th.{index+1}] リトライオーバー')

    with lock:
        errors.append(index)
    
    return


# 注文実績取得タスク
def get_order_data_worker(dt, url, index, page_start, page_num, lock):

    print_ex(f'[Th.{index+1}] 注文実績データ取得処理 開始')

    try:
        # ChromeDriver
        driver = get_web_driver(lock)

        df_data = pd.DataFrame(columns=ORDER_COLS)
        data_list = []
        count = 0

        for i in range(page_start, page_start + page_num):
            target_url = url.replace('<% page %>', str(i))

            # URLアクセス
            driver.get(target_url)

            # ページが完全にロードされるまで待機
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')

            path = '.buyeritemtable_body'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                elems = driver.find_elements(By.CSS_SELECTOR, path)
            else:
                # 30ページ固定でアクセスしているので実績件数によりページアクセスに失敗する
                continue

            for elem in elems:

                data = {}
                for col in ORDER_COLS:
                    data[col] = ''

                # No.
                count += 1
                data['No.'] = str(count)

                # 取得日時
                data['取得日時'] = str(dt)

                # 商品名
                # 商品URL
                path = '.buyeritem_name a'
                if len(elem.find_elements(By.CSS_SELECTOR, path)) > 0:
                    tmp = elem.find_element(By.CSS_SELECTOR, path).text.strip()
                    data['商品名'] = str(tmp)

                    tmp = elem.find_element(By.CSS_SELECTOR, path).get_attribute('href').strip()
                    data['商品URL'] = str(tmp)
                else:
                    path = '.buyeritem_name'
                    tmp = elem.find_element(By.CSS_SELECTOR, path).text.strip()
                    data['商品名'] = str(tmp)
                    data['商品URL'] = ''

                # 商品ID
                if data['商品URL'] != '':
                    parts = data['商品URL'].split('/')
                    tmp = parts[-2].strip()
                    data['商品ID'] = str(tmp)

                # 画像URL
                # 出品日
                path = '.buyeritemtable_img__wrap img'
                if len(elem.find_elements(By.CSS_SELECTOR, path)) > 0:
                    img_url = elem.find_element(By.CSS_SELECTOR, path).get_attribute('src').strip()

                    if 'nopub' in img_url:
                        data['出品日'] = ''
                    else:
                        parts = img_url.split('/')
                        date_str = parts[5]
                        yy = "20" + date_str[:2]
                        mm = date_str[2:4]
                        dd = date_str[4:6]
                        tmp2 = f"{yy}/{mm}/{dd}"
                        data['出品日'] = str(tmp2)

                # 成約日
                path = '.buyeritemtable_info > p'
                if len(elem.find_elements(By.CSS_SELECTOR, path)) > 0:
                    elems2 = elem.find_elements(By.CSS_SELECTOR, path)
                    for elem2 in elems2:
                        tmp1 = elem2.text
                        if '成約日' in tmp1:
                            tmp2 = re.search(r'\d{4}/\d{2}/\d{2}', tmp1).group()
                            data['成約日'] = str(tmp2)
                
                data_list.append(data)

            df_data = pd.DataFrame(data_list)

            # テンポラリファイルへ出力
            file_name = f'{FILE_TMP_NAME}_{index+1}.{FILE_TMP_EXT}'
            file_path = os.path.join(base_dir, file_name)
            df_data.to_csv(file_path, index=False)

    except Exception as e:
        driver.quit()
        return False

    driver.quit()
    print_ex(f'[Th.{index+1}] 注文実績データ取得処理 終了')
    return True

#--------------------------------------------------------------------------------
# 出品データ取得（リスト）
#--------------------------------------------------------------------------------
def get_item_list_multi(url, cols):

    try:
        thread_max = THREAD_MAX_LIST

        lock = Lock()
        driver = get_web_driver(lock)

        # ページ数取得のためにアクセス
        driver.get(url)

        # ページが完全にロードされるまで待機
        WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')

        # ページ数算出
        path = '#totalitem_num'     # 該当件数
        if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
            tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
            total_num = int(tmp.replace(',',''))
            total_page = math.ceil(total_num / ITEM_COUNT_PER_PAGE)

        base = total_page // thread_max
        remainder = total_page % thread_max
        page_nums = [base + (1 if i < remainder else 0) for i in range(thread_max)]

        start_pages = [1]
        for i in range(1, len(page_nums)):
            start_pages.append(start_pages[i-1] + page_nums[i-1])

        # テンポラリファイルを削除
        FILE_TMP_NAME = 'item_list'
        FILE_TMP_EXT = 'csv'

        file_pattern = f'{FILE_TMP_NAME}*.{FILE_TMP_EXT}'
        file_pattern = os.path.join(base_dir, file_pattern)
        delete_files = glob.glob(file_pattern)
        for file in delete_files:
            try:
                os.remove(file)
            except OSError as e:
                print_ex(f'ファイル "{file}" の削除中にエラーが発生しました: {e}')

        # スレッド開始
        threads = []
        errors = []
        for i in range(thread_max):
            if page_nums[i] > 0:
                thread = Thread(target=get_item_list, args=(url, cols, i, start_pages[i], page_nums[i], errors, lock))
                threads.append(thread)
                thread.start()    

        # すべてのスレッドが終了するまで待機
        for thread in threads:
            thread.join()

        # エラー確認
        if errors:
            for error in errors:
                print_ex(f'[Th.{error[0]+1}]エラー発生')
            raise

        # 収集したファイルを連結
        df_concat = pd.DataFrame()
        for i in range(thread_max):
            file_name = f'{FILE_TMP_NAME}_{i + 1}.{FILE_TMP_EXT}'
            file_path = os.path.join(base_dir, file_name)
            if os.path.exists(file_path):
                df = pd.read_csv(file_path,
                    dtype={'No.': int, 'ID': str}, parse_dates=['取得日時', '出品日'])
                df_concat = pd.concat([df_concat, df], ignore_index=True)

        df_concat['No.'] = range(1, 1 + len(df_concat))
        df_concat.to_csv(FILE_PATH_ITEM, index=False)

    except Exception as e:
        print_ex(f'エラー発生: {e}')

    return                

# 出品データ取得（リスト）
def get_item_list(dt, url, index, page_start, page_num, errors, lock):

    for i in range(THREAD_RETRY_MAX):
        result = get_item_list_worker(dt, url, index, page_start, page_num, lock)

        if result:
            print_ex(f'[Th.{index+1}] 試行 {i+1}回目成功')
            return
        else:
            print_ex(f'[Th.{index+1}] 試行 {i+1}回目失敗')

    print_ex(f'[Th.{index+1}] リトライオーバー')

    with lock:
        errors.append(index)
    
    return


# 出品データ取得（リスト）タスク
def get_item_list_worker(url, cols, index, page_start, page_num, lock):

    print_ex(f'[Th.{index+1}] 出品データ(リスト)取得処理 開始')

    try:
        driver = get_web_driver(lock)

        df_data = pd.DataFrame(columns=cols)
        data_list = []
        count = 0

        for i in range(page_start, page_start + page_num):

            tmp = url[:-3]
            target_url = tmp + "_" + str(i) + '/'

            # URLアクセス
            driver.get(target_url)

            # ページが完全にロードされるまで待機
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')

            path = '.product_lists li'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                elems = driver.find_elements(By.CSS_SELECTOR, path)
            else:
                continue

            for elem in elems:

                data = {}
                for col in cols:
                    data[col] = ''

                # No.
                count += 1
                data['No.'] = str(count)

                #ID
                tmp = elem.get_attribute('item-id')
                data['ID'] = str(tmp)

                # 取得日時
                data['取得日時'] = get_dt_str()

                #商品名
                #ブランド
                #商品URL
                #カテゴリ1
                #カテゴリ2
                #カテゴリ3
                path = '.product_name a'
                if len(elem.find_elements(By.CSS_SELECTOR, path)) > 0:
                    tmp = elem.find_element(By.CSS_SELECTOR, path).text.strip()
                    data['商品名'] = str(tmp)

                    tmp = elem.find_element(By.CSS_SELECTOR, path).get_attribute('href')
                    data['商品URL'] = str(tmp)

                #画像URL
                #出品日
                path = '.product_img img'
                if len(elem.find_elements(By.CSS_SELECTOR, path)) > 0:
                    img_url = elem.find_element(By.CSS_SELECTOR, path).get_attribute('src').strip()

                    if 'nopub' in img_url:
                        data['出品日'] = ''
                    else:
                        parts = img_url.split('/')
                        date_str = parts[5]
                        yy = "20" + date_str[:2]
                        mm = date_str[2:4]
                        dd = date_str[4:6]
                        tmp2 = f"{yy}/{mm}/{dd}"
                        data['出品日'] = str(tmp2)

                data_list.append(data)

            df_data = pd.DataFrame(data_list)

            # テンポラリファイルへ出力
            FILE_TMP_NAME = 'item_list'
            FILE_TMP_EXT = 'csv'            
            file_name = f'{FILE_TMP_NAME}_{index+1}.{FILE_TMP_EXT}'
            file_path = os.path.join(base_dir, file_name)
            df_data.to_csv(file_path, index=False)

    except Exception as e:
        driver.quit()
        print_ex(f'[Th.{index+1}] エラー発生: {str(e)}')
        return False

    driver.quit()
    print_ex(f'[Th.{index+1}] 出品データ(リスト)取得処理 終了')
    return True

#--------------------------------------------------------------------------------
# 出品データ取得（詳細）
#--------------------------------------------------------------------------------
def get_item_detail_multi(ss_url):

    try:
        thread_max = THREAD_MAX_DETAIL

        # スプレッドシートから出品データ取得
        data = get_ss_all_values(ss_url, ITEM_SHEET_NAME)
        data_cols = data[0]
        data_rows = data[1:]
        df_data = pd.DataFrame(data_rows, columns=data_cols)

        split_size = int(np.ceil(len(df_data) / thread_max))
        split_dfs = {}

        for i in range(0, len(df_data), split_size):
            start_row = i
            split_df  = df_data.iloc[i:i + split_size].reset_index(drop=True)
            split_dfs[start_row] = split_df

        # テンポラリファイルを削除
        FILE_TMP_NAME = 'item_detail'
        FILE_TMP_EXT = 'csv'          
        file_pattern = f'{FILE_TMP_NAME}*.{FILE_TMP_EXT}'
        file_pattern = os.path.join(base_dir, file_pattern)
        delete_files = glob.glob(file_pattern)
        for file in delete_files:
            try:
                os.remove(file)
            except OSError as e:
                print_ex(f'ファイル "{file}" の削除中にエラーが発生しました: {e}')

        # スレッド開始
        threads = []
        errors = []
        lock = Lock()
        for index, (start_row, split_df) in enumerate(split_dfs.items()):
            thread = Thread(target=get_item_detail, args=(ss_url, index, start_row, split_df, errors, lock))
            threads.append(thread)
            thread.start()    

        # すべてのスレッドが終了するまで待機
        for thread in threads:
            thread.join()

        # エラー確認
        if errors:
            for error in errors:
                print_ex(f'[Th.{error[0]+1}]エラー発生')
            raise

        # 収集したファイルを連結
        df_concat = pd.DataFrame()
        for i in range(thread_max):
            file_name = f'{FILE_TMP_NAME}_{i + 1}.{FILE_TMP_EXT}'
            file_path = os.path.join(base_dir, file_name)
            if os.path.exists(file_path):
                df = pd.read_csv(file_path,
                    dtype={'No.': int, 'ID': str}, parse_dates=['取得日時', '出品日'])
                df_concat = pd.concat([df_concat, df], ignore_index=True)

        df_concat['No.'] = range(1, 1 + len(df_concat))
        df_concat.to_csv(FILE_PATH_DETAIL, index=False)

        # 型番のみファイル出力
        df_model = df_concat[['ID', '商品名', 'ブランド', '型番']]
        df_model['型番'] = df_model['型番'].str.split('<br>')
        df_exploded = df_model.explode('型番')
        df_exploded = df_exploded[df_exploded['型番'].notna()]
        df_unique = df_exploded.drop_duplicates(subset=['ID', '型番'])
        df_unique.to_csv(FILE_PATH_MODEL, index=False)

    except Exception as e:
        print_ex(f'エラー発生: {e}')

    return


# 出品データ取得（詳細）
def get_item_detail(ss_url, index, start_row, split_df, errors, lock):

    for i in range(THREAD_RETRY_MAX):
        result = get_item_detail_worker(ss_url, index, start_row, split_df, lock)

        if result:
            print_ex(f'[Th.{index+1}] 試行 {i+1}回目成功')
            return
        else:
            print_ex(f'[Th.{index+1}] 試行 {i+1}回目失敗')

    print_ex(f'[Th.{index+1}] リトライオーバー')

    with lock:
        errors.append(index)
    
    return

# 出品データ取得（詳細）タスク
def get_item_detail_worker(ss_url, index, start_row, df_data, lock):

    print_ex(f'[Th.{index+1}] 出品データ(詳細)取得処理 開始')

    try:
        driver = get_web_driver(lock)
        print_ex(f'[Th.{index+1}] Webドライバ初期化 完了')

        for i in range(df_data.shape[0]):

            if df_data['出品'][i] == '削除' or df_data['出品'][i] == '出品中':
                print_ex(f'[Th.{index+1}] 出品データ(詳細) 取得スキップ: {i + 1} / {df_data.shape[0]}')
                continue

            # URLアクセス
            target_url = df_data.loc[i, '商品URL']
            driver.get(target_url)

            # ページが完全にロードされるまで待機
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')

            no_item = False
            path = '.notfoundSection_txt'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()

                if '申し訳ございません' in tmp:

                    path = '#detail_ttl'
                    if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                        tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                        df_data.loc[i, '商品名'] = str(tmp)

                    path = '.n_item_grid li:nth-child(1) a'
                    if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                        driver.find_element(By.CSS_SELECTOR, path).click()
                        no_item = True

            # ブランド
            path = '#s_brand .brand-link'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                df_data.loc[i, 'ブランド'] = str(tmp)

            # ブランド1
            path = '#s_brand .detail_txt_list li:nth-child(1)'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                df_data.loc[i, 'ブランド1'] = str(tmp)

            # ブランド1 URL
            path = '#s_brand .detail_txt_list li:nth-child(1) a'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).get_attribute('href')
                df_data.loc[i, 'ブランド1 URL'] = str(tmp)

            # ブランド2
            path = '#s_brand .detail_txt_list li:nth-child(2)'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                df_data.loc[i, 'ブランド2'] = str(tmp)

            # ブランド2 URL
            path = '#s_brand .detail_txt_list li:nth-child(2) a'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).get_attribute('href')
                df_data.loc[i, 'ブランド2 URL'] = str(tmp)

            # ブランド3
            path = '#s_brand .detail_txt_list li:nth-child(3)'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                df_data.loc[i, 'ブランド3'] = str(tmp)

            # ブランド3 URL
            path = '#s_brand .detail_txt_list li:nth-child(3) a'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).get_attribute('href')
                df_data.loc[i, 'ブランド3 URL'] = str(tmp)

            # カテゴリ1
            path = '#s_cate .detail_txt_list li:nth-child(1)'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                df_data.loc[i, 'カテゴリ1'] = str(tmp)

            # カテゴリ2
            path = '#s_cate .detail_txt_list li:nth-child(2)'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                tmp = tmp.replace('>', '').strip()
                df_data.loc[i, 'カテゴリ2'] = str(tmp)

            # カテゴリ3
            path = '#s_cate .detail_txt_list li:nth-child(3)'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                tmp = tmp.replace('>', '').strip()
                df_data.loc[i, 'カテゴリ3'] = str(tmp)

            # ブランド x カテゴリ3
            tmp = df_data.loc[i, 'ブランド'] + ' x ' + df_data.loc[i, 'カテゴリ3']
            df_data.loc[i, 'ブランド x カテゴリ3'] = tmp

            # 出品中の未取得
            if no_item == False:

                # お問い合わせ
                path = '#tabmenu_inqcnt'
                if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                    tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                    df_data.loc[i, 'お問い合わせ'] = str(tmp)

                # アクセス
                path = '.ac_count'
                if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                    tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                    df_data.loc[i, 'アクセス'] = str(tmp)

                # お気に入りアイテム登録
                path = '.fav_count'
                if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                    tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                    tmp = tmp.replace('人', '')
                    df_data.loc[i, 'お気に入りアイテム登録'] = str(tmp)

                # 価格
                tmp = ''
                path = '#abtest_display_pc'
                if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                    tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                else:
                    path = '#priceWrap .price_dd .fab-typo-midium'
                    if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                        tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                tmp = tmp.replace('¥', '')
                tmp = tmp.replace(',', '')
                df_data.loc[i, '価格'] = str(tmp)

                # タグ1
                # タグ2
                path = '.itemcomment-disc__detail a'
                if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                    elems = driver.find_elements(By.CSS_SELECTOR, path)
                    for elem in elems:
                        tmp = elem.text.strip()
                        if '手元に在庫あり' in tmp:
                            df_data.loc[i, 'タグ1'] = '手元に在庫あり(即発送可能)'
                        elif 'アウトレット' in tmp:
                            df_data.loc[i, 'タグ2'] = 'アウトレット'

                # 買付地
                path = '#s_buying_area a'
                if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                    tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                    df_data.loc[i, '買付地'] = str(tmp)

                # 買付先名
                path = '#s_buying_area span'
                if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                    tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                    df_data.loc[i, '買付先名'] = str(tmp)

                # 発送地
                path = '#s_shipment_area dd'
                if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                    tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                    df_data.loc[i, '発送地'] = str(tmp)

                # 型番
                path = '#s_season'
                if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                    tmp_dt = driver.find_element(By.CSS_SELECTOR, '#s_season dt').text.strip()
                    if tmp_dt == 'ブランド型番':
                        elems = driver.find_elements(By.CSS_SELECTOR, '#s_season dd a')
                        tmp = ''
                        for elem in elems:
                            if tmp != '':
                                tmp += '<br>'
                            tmp += elem.text.strip()
                        df_data.loc[i, '型番'] = str(tmp)

            if no_item:
                # 出品が削除されてカテゴリだけ取得
                df_data.loc[i, '出品'] = '削除'
            else:
                # 出品
                df_data.loc[i, '出品'] = '出品中'

            # 取得日時
            df_data.loc[i, '取得日時'] = get_dt_str()

            print_ex(f'[Th.{index+1}] 出品データ(詳細) 取得完了: {i + 1} / {df_data.shape[0]}')

        # テンポラリファイルへ出力
        FILE_TMP_NAME = 'item_detail'
        FILE_TMP_EXT = 'csv'            
        file_name = f'{FILE_TMP_NAME}_{index+1}.{FILE_TMP_EXT}'
        file_path = os.path.join(base_dir, file_name)
        df_data.to_csv(file_path, index=False)

    except Exception as e:
        driver.quit()
        print_ex(f'[Th.{index+1}] エラー発生: {str(e)}')
        return False

    driver.quit()
    print_ex(f'[Th.{index+1}] 出品データ(詳細)取得処理 終了')
    return True

#--------------------------------------------------------------------------------
# 出品データ取得(価格更新)
#--------------------------------------------------------------------------------
def get_item_price_multi(ss_url):

    try:
        thread_max = THREAD_MAX_PRICE

        # スプレッドシートから出品データ取得
        data = get_ss_all_values(ss_url, ITEM_SHEET_NAME)
        data_cols = data[0]
        data_rows = data[1:]
        df_data = pd.DataFrame(data_rows, columns=data_cols)

        split_size = int(np.ceil(len(df_data) / thread_max))
        split_dfs = {}

        for i in range(0, len(df_data), split_size):
            start_row = i
            split_df  = df_data.iloc[i:i + split_size].reset_index(drop=True)
            split_dfs[start_row] = split_df

        # テンポラリファイルを削除
        FILE_TMP_NAME = 'item_price'
        FILE_TMP_EXT = 'csv'          
        file_pattern = f'{FILE_TMP_NAME}*.{FILE_TMP_EXT}'
        file_pattern = os.path.join(base_dir, file_pattern)
        delete_files = glob.glob(file_pattern)
        for file in delete_files:
            try:
                os.remove(file)
            except OSError as e:
                print_ex(f'ファイル "{file}" の削除中にエラーが発生しました: {e}')

        # スレッド開始
        threads = []
        errors = []
        lock = Lock()
        for index, (start_row, split_df) in enumerate(split_dfs.items()):
            thread = Thread(target=get_item_price, args=(ss_url, index, start_row, split_df, errors, lock))
            threads.append(thread)
            thread.start()    

        # すべてのスレッドが終了するまで待機
        for thread in threads:
            thread.join()

        # エラー確認
        if errors:
            for error in errors:
                print_ex(f'[Th.{error[0]+1}]エラー発生')
            raise

        # 収集したファイルを連結
        df_concat = pd.DataFrame()
        for i in range(thread_max):
            file_name = f'{FILE_TMP_NAME}_{i + 1}.{FILE_TMP_EXT}'
            file_path = os.path.join(base_dir, file_name)
            if os.path.exists(file_path):
                df = pd.read_csv(file_path,
                    dtype={'No.': int, 'ID': str}, parse_dates=['取得日時', '出品日'])
                df_concat = pd.concat([df_concat, df], ignore_index=True)

        df_concat['No.'] = range(1, 1 + len(df_concat))
        df_concat.to_csv(FILE_PATH_PRICE, index=False)

    except Exception as e:
        print_ex(f'エラー発生: {e}')

    return

# 出品データ取得(価格更新)
def get_item_price(ss_url, index, start_row, split_df, errors, lock):

    for i in range(THREAD_RETRY_MAX):
        result = get_item_price_worker(ss_url, index, start_row, split_df, lock)

        if result:
            print_ex(f'[Th.{index+1}] 試行 {i+1}回目成功')
            return
        else:
            print_ex(f'[Th.{index+1}] 試行 {i+1}回目失敗')

    print_ex(f'[Th.{index+1}] リトライオーバー')

    with lock:
        errors.append(index)
    
    return

# 出品データ取得(価格更新) タスク
def get_item_price_worker(ss_url, index, start_row, df_data, lock):

    print_ex(f'[Th.{index+1}] 出品データ(価格更新)取得処理 開始')

    try:
        driver = get_web_driver(lock)
        print_ex(f'[Th.{index+1}] Webドライバ初期化 完了')

        for i in range(df_data.shape[0]):

            if df_data['出品'][i] != '出品中':
                print_ex(f'[Th.{index+1}] 出品データ(価格更新) 取得スキップ: {i + 1} / {df_data.shape[0]}')
                continue

            # URLアクセス
            target_url = df_data.loc[i, '商品URL']
            driver.get(target_url)

            # ページが完全にロードされるまで待機
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')

            no_item = False
            path = '.notfoundSection_txt'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()

                if '申し訳ございません' in tmp:

                    path = '#detail_ttl'
                    if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                        tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                        df_data.loc[i, '商品名'] = str(tmp)

                    path = '.n_item_grid li:nth-child(1) a'
                    if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                        driver.find_element(By.CSS_SELECTOR, path).click()
                        no_item = True

            # 出品中の未取得
            if no_item == False:
                # 価格
                path = '.js-item-price p'
                if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                    elems = driver.find_elements(By.CSS_SELECTOR, path)

                    next_hit = False
                    for elem in elems:
                        if next_hit:
                            tmp_dd = elem.text.strip()
                            tmp = tmp_dd.replace('¥', '')
                            tmp = tmp.replace(',', '')
                            df_data.loc[i, '価格'] = str(tmp)
                            break

                        tmp_dt = elem.text.strip()
                        if tmp_dt == '価格':
                            next_hit = True

            if no_item:
                # 出品が削除されてカテゴリだけ取得
                df_data.loc[i, '出品'] = '削除'

            print_ex(f'[Th.{index+1}] 出品データ(価格更新) 取得完了: {i + 1} / {df_data.shape[0]}')

        # テンポラリファイルへ出力
        FILE_TMP_NAME = 'item_price'
        FILE_TMP_EXT = 'csv'            
        file_name = f'{FILE_TMP_NAME}_{index+1}.{FILE_TMP_EXT}'
        file_path = os.path.join(base_dir, file_name)
        df_data.to_csv(file_path, index=False)

    except Exception as e:
        driver.quit()
        print_ex(f'[Th.{index+1}] エラー発生: {str(e)}')
        return False

    driver.quit()
    print_ex(f'[Th.{index+1}] 出品データ(価格更新)取得処理 終了')
    return True

#--------------------------------------------------------------------------------
# 市場データ取得
#--------------------------------------------------------------------------------
def get_market_data_multi():

    THREAD_MAX = THREAD_MAX_MARKET

    # スプレッドシートから出品データ取得
    df_data = pd.read_csv(FILE_PATH_MARKET)

    split_size = int(np.ceil(len(df_data) / THREAD_MAX))
    split_dfs = {}

    for i in range(0, len(df_data), split_size):
        start_row = i
        split_df  = df_data.iloc[i:i + split_size].reset_index(drop=True)
        split_dfs[start_row] = split_df

    # テンポラリファイルを削除
    FILE_TMP_NAME = 'market'
    FILE_TMP_EXT = 'csv'          
    file_pattern = f'{FILE_TMP_NAME}*.{FILE_TMP_EXT}'
    file_pattern = os.path.join(base_dir, file_pattern)
    delete_files = glob.glob(file_pattern)
    for file in delete_files:
        try:
            os.remove(file)
        except OSError as e:
            print_ex(f'ファイル "{file}" の削除中にエラーが発生しました: {e}')

    # スレッド開始
    threads = []
    errors = []
    lock = Lock()    
    for index, (start_row, split_df) in enumerate(split_dfs.items()):
        thread = Thread(target=get_market_data, args=(index, split_df, errors, lock))
        threads.append(thread)
        thread.start()    

    # すべてのスレッドが終了するまで待機
    for thread in threads:
        thread.join()

    # エラー確認
    if errors:
        for error in errors:
            print_ex(f'[Th.{error[0]+1}]エラー発生')
        raise

    # 収集したファイルを連結
    df_concat = pd.DataFrame()
    for i in range(THREAD_MAX):
        file_name = f'{FILE_TMP_NAME}_{i + 1}.{FILE_TMP_EXT}'
        file_path = os.path.join(base_dir, file_name)
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, dtype={'No.': int, '出品数': int})
            df_concat = pd.concat([df_concat, df], ignore_index=True)

    df_concat['No.'] = range(1, 1 + len(df_concat))
    df_concat.to_csv(FILE_PATH_MARKET, index=False)
    return

# 市場データ取得
def get_market_data(index, split_df, errors, lock):

    for i in range(THREAD_RETRY_MAX):
        result = get_market_data_worker(index, split_df, lock)

        if result:
            print_ex(f'[Th.{index+1}] 試行 {i+1}回目成功')
            return
        else:
            print_ex(f'[Th.{index+1}] 試行 {i+1}回目失敗')

    print_ex(f'[Th.{index+1}] リトライオーバー')

    with lock:
        errors.append(index)
    
    return

# 市場データ取得タスク
def get_market_data_worker(index, df_data, lock):

    print_ex(f'[Th.{index+1}] 市場データ取得処理 開始')

    try:
        driver = get_web_driver(lock)

        for i in range(df_data.shape[0]):

            # URLアクセス
            target_url = df_data.loc[i, 'ブランド3 URL']

            driver.get(target_url)

            # ページが完全にロードされるまで待機
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')

            # 該当件数
            path = '#totalitem_num'
            if len(driver.find_elements(By.CSS_SELECTOR, path)) > 0:
                tmp = driver.find_element(By.CSS_SELECTOR, path).text.strip()
                tmp = tmp.replace(',', '')
                df_data.loc[i, '出品数'] = tmp
            
            df_data.to_csv(FILE_PATH_MARKET, index=False)

        # テンポラリファイルへ出力
        FILE_TMP_NAME = 'market'
        FILE_TMP_EXT = 'csv'          
        file_name = f'{FILE_TMP_NAME}_{index+1}.{FILE_TMP_EXT}'
        file_path = os.path.join(base_dir, file_name)
        df_data.to_csv(file_path, index=False)

    except Exception as e:
        driver.quit()
        print_ex(f'[Th.{index+1}] エラー発生: {str(e)}')
        return False

    driver.quit()
    print_ex(f'[Th.{index+1}] 市場データ取得処理 終了')
    return True

#--------------------------------------------------------------------------------
# 出品データ→市場データ用リスト
#--------------------------------------------------------------------------------
def item_to_market(ss_url):

    # スプレッドシートから出品データ取得
    data = get_ss_all_values(ss_url, ITEM_SHEET_NAME)
    data_cols = data[0]
    data_rows = data[1:]
    df_data = pd.DataFrame(data_rows, columns=data_cols)

    # ブランド3で重複除去
    df_data = df_data.drop_duplicates(subset='ブランド3')           # 重複除去
    df_data = df_data[df_data['ブランド3'] != '']                   # 欠損行を削除
    df_data = df_data[['No.', 'ブランド', 'カテゴリ3', 'ブランド x カテゴリ3', 'ブランド3', 'ブランド3 URL']]        # 列抽出
    df_data = df_data.reset_index(drop=True)
    df_data['No.'] = df_data.index + 1                              # 連番振り直し
    df_data['出品数'] = -1                                          # 列追加
    df_data.to_csv(FILE_PATH_MARKET, index=False)                   # ファイル出力

#--------------------------------------------------------------------------------
# 注文実績にあるが未出品の商品IDリスト取得
#--------------------------------------------------------------------------------
def get_compare_order_of_item(ss_url):

    # 出品データ取得
    data_item = get_ss_all_values(ss_url, ITEM_SHEET_NAME)
    ids_item = [row[1] for row in data_item[1:]]

    # 注文実績取得
    data_order = get_ss_all_values(ss_url, ORDER_SHEET_NAME)
    ids_order = [row[4] for row in data_order[1:]]

    # 追加するIDリスト
    ids_new = set(ids_order) - set(ids_item)

    count = len(ids_item) + 1
    for id in ids_new:
        if id == '':
            continue

        new_row = [f'{count}'] + [id] + ['未取得'] +  [''] + [''] + [f'https://www.buyma.com/item/{id}/'] + [''] * (len(data_item[0]) - 6)
        data_item.append(new_row)
        count += 1

    set_ss_all_values(ss_url, '出品データ', data_item[1:])


def main():
    print('テスト実行')


if __name__ == "__main__":
    main()
