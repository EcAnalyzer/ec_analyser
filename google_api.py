import os
import time
import gspread
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from tool import print_ex
from functools import wraps

# Google API スコープ
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',             # Google スプレッドシートのすべてのスプレッドシートの参照、編集、作成、削除
]

# パス関連
if os.getenv('GITHUB_ACTIONS') == 'true':
    base_dir = os.getenv('GITHUB_WORKSPACE')
else:
    base_dir = os.path.abspath(os.curdir)

# ファイルパス
FILE_NAME_SECRET = 'client_secret.json'
FILE_NAME_TOKEN = 'token.json'
FILE_PATH_CREDENTIAL = os.path.join(base_dir, FILE_NAME_SECRET) # クライアントシークレットファイル
FILE_PATH_TOKEN = os.path.join(base_dir, FILE_NAME_TOKEN)       # リフレッシュトークンファイル

# Google Sheet API 呼出し関連
credentials = None

class GoogleApiError(Exception):
    def __init__(self, message, status_code=None, response_text=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text

#--------------------------------------------------------------------------------
# リトライデコレータ
#--------------------------------------------------------------------------------
def retry(retry_max=10, retry_wait=10):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < retry_max:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    print(f'リトライ {attempts}/{retry_max}... エラー: {e}')
                    time.sleep(retry_wait)
                    if attempts == retry_max:
                        raise
        return wrapper
    return decorator

#--------------------------------------------------------------------------------
# スプレッドシートにデータを格納
#--------------------------------------------------------------------------------
def set_ss_all_values(url, sheet, data, start_row=2, start_col=1):

    try:
        # OAuth認証
        global credentials
        if credentials == None:
            credentials = get_credentials()     

        # Google API 認証
        ss = get_spreadsheet(credentials, url)
        ws = ss.worksheet(sheet)

        # スプレッドシートを一旦消去
        last_row = len(ws.get_all_values())
        last_column = len(ws.get_all_values()[0])

        start_a1 = gspread.utils.rowcol_to_a1(start_row, start_col)

        if last_row > 1:
            end_a1 = gspread.utils.rowcol_to_a1(last_row, last_column)
            ws.batch_clear([f"{start_a1}:{end_a1}"])

        # スプレッドシートを更新
        ws.update(start_a1, data, value_input_option="USER_ENTERED")
        
    except Exception as e:
        print_ex(f'エラー発生: {str(e)}')
        raise

    #print_ex(f'スプレッドシート更新 終了')
    return True

#--------------------------------------------------------------------------------
# スプレッドシートからデータ取得
#--------------------------------------------------------------------------------
def get_ss_all_values(url, sheet):

    try:
        # OAuth認証
        global credentials
        if credentials == None:
            credentials = get_credentials()     

        # Google API 認証
        spreadsheet = get_spreadsheet(credentials, url)
        ws = spreadsheet.worksheet(sheet)

        # スプレッドシートから読込み
        values = ws.get_all_values()

    except Exception as e:
        print_ex(f'エラー発生: {str(e)}')
        raise

    return values

#--------------------------------------------------------------------------------
# スプレッドシートにデータを格納(セル)
#--------------------------------------------------------------------------------
def set_ss_value(url, sheet, row, col, data):

    #print_ex(f'スプレッドシート更新 開始')

    
    try:
        # OAuth認証
        global credentials
        if credentials == None:
            credentials = get_credentials()     

        # Google API 認証
        ss = get_spreadsheet(credentials, url)
        ws = ss.worksheet(sheet)

        # スプレッドシートを更新
        cell_label = gspread.utils.rowcol_to_a1(row, col)
        ws.update(cell_label, [[data]], value_input_option="USER_ENTERED")
        print_ex(f'set_ss_value sheet={sheet}, cell_label={cell_label}, data={[[data]]}')
        
    except Exception as e:
        print_ex(f'エラー発生: {str(e)}')
        raise

    #print_ex(f'スプレッドシート更新 終了')
    return True


#--------------------------------------------------------------------------------
# スプレッドシートにデータを格納(セル)
#--------------------------------------------------------------------------------
def num_to_col_letter(n):
    string = ''
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        string = chr(65 + remainder) + string
    return string

def del_ss_value(url, sheet, row_start, col_start, row_count, col_count):

    end_row = row_start + row_count - 1
    end_col = col_start + col_count - 1

    start_col_letter = num_to_col_letter(col_start)
    end_col_letter = num_to_col_letter(end_col)
    cell_range = f'{start_col_letter}{row_start}:{end_col_letter}{end_row}'
    
    try:
        # OAuth認証
        global credentials
        if credentials == None:
            credentials = get_credentials()     

        # Google API 認証
        ss = get_spreadsheet(credentials, url)
        ws = ss.worksheet(sheet)

        # スプレッドシートを更新
        empty_data = [['' for _ in range(col_count)] for _ in range(row_count)]
        ws.update(cell_range, empty_data, value_input_option="USER_ENTERED")
        print_ex(f'set_ss_value sheet={sheet}, cell_label={cell_range}, data={empty_data}')
        
    except Exception as e:
        print_ex(f'エラー発生: {str(e)}')
        raise

    #print_ex(f'スプレッドシート更新 終了')
    return True


#--------------------------------------------------------------------------------
# スプレッドシートからデータを取得(セル)
#--------------------------------------------------------------------------------
def get_ss_value(url, sheet, row, col):

    #print_ex(f'スプレッドシート更新 開始')

    try:
        # OAuth認証
        global credentials
        if credentials == None:
            credentials = get_credentials()     

        # Google API 認証
        ss = get_spreadsheet(credentials, url)
        ws = ss.worksheet(sheet)

        # スプレッドシートを更新
        data = ws.cell(row, col).value
        
    except Exception as e:
        print_ex(f'エラー発生: {str(e)}')
        raise

    #print_ex(f'スプレッドシート更新 終了')
    return data

#--------------------------------------------------------------------------------
# スプレッドシート取得
#--------------------------------------------------------------------------------
@retry()
def get_spreadsheet(credentials, url):

    #print_ex(f'get_spreadsheet 開始')

    try:
        # スプレッドシート取得
        gc = gspread.authorize(credentials)
        ss = gc.open_by_url(url)

    except PermissionError as e:
        message = 'スプレッドシートにアクセスする権限がありません。'
        print_ex(f'エラー発生: {message}')
        raise PermissionError(message)

    except Exception as e:
        message = 'スプレッドシートのオープンでエラーが発生しました。'
        print_ex(f'エラー発生: {message}')
        raise Exception(message)

    #print_ex(f'get_spreadsheet 終了')
    return ss

#--------------------------------------------------------------------------------
# OAuth認証
#--------------------------------------------------------------------------------
@retry()
def get_credentials():

    #print_ex(f'get_credentials 開始')

    try:
        # OAuth認証
        credentials = service_account.Credentials.from_service_account_file(FILE_PATH_CREDENTIAL, scopes=SCOPES)

    except Exception as e:
        message = 'スプレッドシートのOAuth認証に失敗しました。'
        print_ex(f'エラー発生: {message}')
        raise

    #print_ex(f'get_credentials 終了')
    return credentials


def main():
    print('テスト実行')
    

if __name__ == "__main__":
    main()