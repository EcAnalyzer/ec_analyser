#--------------------------------------------------------------------------------
# 初回データ取得処理
#--------------------------------------------------------------------------------
# ① 注文実績を取得する(最大900件)
# ② 出品データのリストを取得
# ③ 出品停止リスト追加
# ④ 出品データの詳細データを取得
# ⑤ カテゴリ抽出し市場データを取得する
#--------------------------------------------------------------------------------
from scraping import *
from datetime import datetime, timedelta
import pytz

tz = pytz.timezone('Asia/Tokyo')


def get_data_init(url, index, info):

    print_ex('初回データ取得 処理開始')

    try:
        url_manage = url                 # 外注総合管理ツールURL
        url_sheet = info['sheet_url']    # スプレッドシートURL
        url_order = info['order_url']    # 注文実績URL
        url_item = info['item_url']      # 出品データURL
        state = info['state']            # 状態
        ss_name = info['sheet_name']     # スプレッドシート名

        # 状態判定
        if (state == GetDataStep.INIT_NONE.value or         # 初回データ取得予約
            state == GetDataStep.INIT_RUN_ORDER.value or    # 初回取得中(注文実績)
            state == GetDataStep.INIT_RUN_LIST.value or     # 初回取得中(出品リスト)
            state == GetDataStep.INIT_RUN_CHECK.value or    # 初回取得中(出品リスト確認)
            state == GetDataStep.INIT_RUN_ITEM.value or     # 初回取得中(出品データ)
            state == GetDataStep.INIT_RUN_MARKET.value or   # 初回取得中(市場データ)
            state == GetDataStep.INIT_ERROR.value):         # 初回取得エラー
            dt_start_total = datetime.now(tz)
            print_ex(f'処理実施 state={state} ss_name={ss_name}')
        else:
            print_ex(f'処理不要なのでスキップ state={state} ss_name={ss_name}')
            return

        #--------------------------------------------------------------------------------
        # step.0 - 初期化 開始
        #--------------------------------------------------------------------------------
        if (state == GetDataStep.INIT_NONE.value or         # 初回データ取得予約
            state == GetDataStep.INIT_ERROR.value):         # 初回取得エラー

            print_ex('[St.0] get_data_init 初期化 開始' + ss_name)

            # 開始時間を記録
            update_proc_start_time(url_manage, url_sheet, index)

            # ステップ別処理時間クリア
            clear_step_proc_time_init(url_manage, index)

            # ステップ移行
            state = GetDataStep.INIT_RUN_ORDER.value

            print_ex('[St.0] get_data_init 初期化 終了' + ss_name)

        #--------------------------------------------------------------------------------
        # step.1 - 注文実績を取得する(最大900件)
        #--------------------------------------------------------------------------------
        if state == GetDataStep.INIT_RUN_ORDER.value:       # 初回取得中(注文実績)

            print_ex('[St.1] get_data_init 注文実績取得 開始 ' + ss_name)
            update_proc_status(url_manage, url_sheet, index, state)

            # 開始時間記録
            dt_start = datetime.now(tz)

            # 注文実績→CSVファイル
            get_order_data_multi(get_dt_str(), url_order)

            # CSVファイルから読込み
            data = csv_to_array(FILE_PATH_ORDER)
            
            # 日付の区切りをスラッシュに置換
            col_indexs = [1, 5, 6]   # 取得日時, 出品日, 成約日
            data_rep = replace_date_separator(data, col_indexs)

            # 成約日でソート
            data_sorted = sorted(data_rep, key=sort_key)

            # 前日までのデータとする
            dt_today = datetime.now(tz).date()
            dt_yesterday = dt_today - timedelta(days=1)            
            
            data_filtered = []
            for r in data_sorted:
                date = datetime.strptime(r[6].split()[0], '%Y/%m/%d').date()
                if date <= dt_yesterday:
                    data_filtered.append(r)

            # No.列を振り直し
            for j, r in enumerate(data_filtered):
                r[0] = str(j + 1)
            
            # スプレッドシートへ書込み
            set_ss_all_values(url_sheet, ORDER_SHEET_NAME, data_filtered)

            # 終了時間記録
            update_step_proc_time(url_manage, index, MANAGE_COL_INIT_STEP + 1 - 1, dt_start, datetime.now(tz))

            # ステップ移行
            state = GetDataStep.INIT_RUN_LIST.value

            print_ex('[St.1] get_data_init 注文実績取得 終了 ' + ss_name)

        #--------------------------------------------------------------------------------
        # step.2 - 出品データのリストを取得
        #--------------------------------------------------------------------------------
        if state == GetDataStep.INIT_RUN_LIST.value:        # 初回取得中(出品リスト)

            print_ex('[St.2] get_data_init 出品データ(リスト)取得 開始 ' + ss_name)
            update_proc_status(url_manage, url_sheet, index, state)

            # 開始時間記録
            dt_start = datetime.now(tz)

            # 商品データ(リスト)取得
            get_item_list_multi(url_item, ITEM_COLS)

            # スプレッドシート出力
            data = csv_to_array(FILE_PATH_ITEM)
            set_ss_all_values(url_sheet, ITEM_SHEET_NAME, data)

            # 終了時間記録
            update_step_proc_time(url_manage, index, MANAGE_COL_INIT_STEP + 2 - 1, dt_start, datetime.now(tz))

            # ステップ移行
            state = GetDataStep.INIT_RUN_CHECK.value
            print_ex('[St.2] get_data_init 出品データ(リスト)取得 終了 ' + ss_name)

        #--------------------------------------------------------------------------------
        # step.3 - 出品停止リスト追加
        #--------------------------------------------------------------------------------
        if state == GetDataStep.INIT_RUN_CHECK.value:       # 初回取得中(出品リスト確認)

            print_ex('[St.3] get_data_init 出品データ確認 開始 ' + ss_name)
            update_proc_status(url_manage, url_sheet, index, state)

            # 開始時間記録
            dt_start = datetime.now(tz)

            # 注文実績にしか存在しない商品IDを出品データに追加
            get_compare_order_of_item(url_sheet)

            # 終了時間記録
            update_step_proc_time(url_manage, index, MANAGE_COL_INIT_STEP + 3 - 1, dt_start, datetime.now(tz))

            # ステップ移行
            state = GetDataStep.INIT_RUN_ITEM.value
            print_ex('[St.3] get_data_init 出品データ確認 終了 ' + ss_name)

        #--------------------------------------------------------------------------------
        # step.4 - 出品データの詳細データを取得
        #--------------------------------------------------------------------------------
        if state == GetDataStep.INIT_RUN_ITEM.value:        # 初回取得中(出品データ)

            print_ex('[St.4] get_data_init 出品データ(詳細) 開始 ' + ss_name)
            update_proc_status(url_manage, url_sheet, index, state)

            # 開始時間記録
            dt_start = datetime.now(tz)

            # 商品データ(詳細)取得
            get_item_detail_multi(url_sheet)

            # スプレッドシート出力
            data = csv_to_array(FILE_PATH_DETAIL)
            set_ss_all_values(url_sheet, ITEM_SHEET_NAME, data)

            # スプレッドシート出力(型番)
            data = csv_to_array(FILE_PATH_MODEL)
            set_ss_all_values(url_sheet, MODEL_SHEET_NAME, data)

            # 終了時間記録
            update_step_proc_time(url_manage, index, MANAGE_COL_INIT_STEP + 4 - 1, dt_start, datetime.now(tz))

            # ステップ移行
            state = GetDataStep.INIT_RUN_MARKET.value
            print_ex('[St.4] get_data_init 出品データ(詳細) 終了 ' + ss_name)

        #--------------------------------------------------------------------------------
        # step.5 - カテゴリ抽出し市場データを取得する
        #--------------------------------------------------------------------------------
        if state == GetDataStep.INIT_RUN_MARKET.value:      # 初回取得中(市場データ)

            print_ex('[St.5] get_data_init 市場データ取得 開始 ' + ss_name)
            update_proc_status(url_manage, url_sheet, index, state)

            # 開始時間記録
            dt_start = datetime.now(tz)

            # 出品データ→市場データ用リスト
            item_to_market(url_sheet)

            # 市場データの出品数取得
            get_market_data_multi()

            # スプレッドシート出力
            data = csv_to_array(FILE_PATH_MARKET)
            set_ss_all_values(url_sheet, MARKET_SHEET_NAME, data)

            # 終了時間記録
            update_step_proc_time(url_manage, index, MANAGE_COL_INIT_STEP + 5 - 1, dt_start, datetime.now(tz))

            # ステップ移行
            state = GetDataStep.INIT_DONE.value
            print_ex('[St.5] get_data_init 市場データ取得 終了 ' + ss_name)

        #--------------------------------------------------------------------------------
        # step.6 - 正常終了
        #--------------------------------------------------------------------------------
        if state == GetDataStep.INIT_DONE.value:      # 初回取得済

            print_ex('[St.6] get_data_init 終了処理 開始 ' + ss_name)

            update_proc_status(url_manage, url_sheet, index, state)
            update_proc_end_time(url_manage, url_sheet, index)
            update_proc_time(url_manage, url_sheet, index, dt_start_total, datetime.now(tz))
            update_step_proc_time(url_manage, index, MANAGE_COL_INIT_TOTAL, dt_start_total, datetime.now(tz))

            print_ex('[St.6] get_data_init 終了処理 終了 ' + ss_name)          

    except Exception as e:
        print_ex(f'エラー発生: {e}')
        state = GetDataStep.INIT_ERROR.value
        update_proc_status(url_manage, url_sheet, index, state)

    print_ex('初回データ取得 終了')
    return


def main():
    print('テスト実行')
    #get_data_init()


if __name__ == "__main__":
    main()