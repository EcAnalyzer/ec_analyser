import os
import time
import gspread
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from tool import print_ex


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
PROCESS_WAIT = 60
API_CALL_LIMIT = 15
api_call_count = 0
api_call_time = datetime.now()
credentials = None

#--------------------------------------------------------------------------------
# スプレッドシートにデータを格納
#--------------------------------------------------------------------------------
def set_ss_all_values(url, sheet, data, start_row=2, start_col=1):

    #print_ex(f'スプレッドシート更新 開始')

    try:
        # OAuth認証
        global credentials
        if credentials == None:
            credentials = get_credentials()     

        # Google API 認証
        ss = get_spreadsheet(credentials, url)
        ws = ss.worksheet(sheet)

        # スプレッドシートを一旦消去
        api_call_check()
        last_row = len(ws.get_all_values())
        last_column = len(ws.get_all_values()[0])

        start_a1 = gspread.utils.rowcol_to_a1(start_row, start_col)

        if last_row > 1:
            end_a1 = gspread.utils.rowcol_to_a1(last_row, last_column)
            ws.batch_clear([f"{start_a1}:{end_a1}"])

        # スプレッドシートを更新
        api_call_check()
        ws.update(start_a1, data, value_input_option="USER_ENTERED")
        
    except Exception as e:
        print_ex(f'エラー発生: {e}')
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
        api_call_check()
        values = ws.get_all_values()

    except Exception as e:
        print_ex(f'エラー発生: {e}')
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
        api_call_check()
        cell_label = gspread.utils.rowcol_to_a1(row, col)
        ws.update(cell_label, [[data]], value_input_option="USER_ENTERED")
        print_ex(f'set_ss_value sheet={sheet}, cell_label={cell_label}, data={[[data]]}')
        
    except Exception as e:
        print_ex(f'エラー発生: {e}')
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
        api_call_check()
        data = ws.cell(row, col).value
        
    except Exception as e:
        print_ex(f'エラー発生: {e}')
        raise

    #print_ex(f'スプレッドシート更新 終了')
    return data

#--------------------------------------------------------------------------------
# スプレッドシート取得
#--------------------------------------------------------------------------------
def get_spreadsheet(credentials, url):

    #print_ex(f'get_spreadsheet 開始')

    try:
        # スプレッドシート取得
        gc = gspread.authorize(credentials)
        ss = gc.open_by_url(url)

    except Exception as e:
        print_ex(f'エラー発生: {e}')
        raise

    #print_ex(f'get_spreadsheet 終了')
    return ss

#--------------------------------------------------------------------------------
# OAuth認証
#--------------------------------------------------------------------------------
def get_credentials():

    #print_ex(f'get_credentials 開始')

    try:
        # OAuth認証
        credentials = service_account.Credentials.from_service_account_file(FILE_PATH_CREDENTIAL, scopes=SCOPES)

    except Exception as e:
        print_ex(f'エラー発生: {e}')
        raise

    #print_ex(f'get_credentials 終了')
    return credentials

#--------------------------------------------------------------------------------
# APIチェック
#--------------------------------------------------------------------------------
def api_call_check():

    global api_call_count, api_call_time

    # 現在時刻
    current_time = datetime.now()

    # 前回呼び出しから経過時間確認
    time_span = (current_time - api_call_time).total_seconds()
    if time_span >= API_CALL_LIMIT:
        api_call_count = 0
        api_call_time = current_time

    api_call_count += 1

    if api_call_count >= API_CALL_LIMIT:
        print_ex(f'API利用制限到達のため {PROCESS_WAIT} 秒待機')
        time.sleep(PROCESS_WAIT)
        api_call_count = 0
        api_call_time = current_time


def main():
    print('テスト実行')


if __name__ == "__main__":
    main()