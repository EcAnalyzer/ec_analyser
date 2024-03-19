#--------------------------------------------------------------------------------
# 毎日の店舗分析データ更新処理
#--------------------------------------------------------------------------------
# ① 注文実績を追加
# 　　・注文実績取得
# 　　・差分を取得してスプレッドシートに追加
# ② 出品データ更新
# 　　・減った分には削除フラグを付ける
# 　　・増えた分には出品データに追加
# ③ 増加した出品データ詳細を取得
# ④ カテゴリ抽出し市場データを取得
#--------------------------------------------------------------------------------
from scraping import *
from datetime import datetime, timedelta

tz = pytz.timezone('Asia/Tokyo')


def get_data_update(url, index, info):

    print_ex('データ更新 処理開始')

    try:
        url_manage = url                 # 外注総合管理ツールURL
        url_sheet = info['sheet_url']    # スプレッドシートURL
        url_order = info['order_url']    # 注文実績URL
        url_item = info['item_url']      # 出品データURL
        state = info['state']            # 状態
        ss_name = info['sheet_name']     # スプレッドシート名

        # 前回更新日時
        update_dt_utc = datetime.strptime(info['update'], '%Y/%m/%d %H:%M:%S')
        update_dt = tz.localize(update_dt_utc)

        # 状態が未取得, 取得中, エラーの場合に処理する
        if (state == GetDataStep.INIT_DONE.value or                     # 初回取得済
            state == GetDataStep.UPDATE_RUN_ORDER.value or              # 更新中(注文実績)
            state == GetDataStep.UPDATE_RUN_LIST.value or               # 更新中(出品リスト)
            state == GetDataStep.UPDATE_RUN_ITEM.value or               # 更新中(出品データ)
            state == GetDataStep.UPDATE_RUN_PRICE.value or              # 更新中(価格)
            state == GetDataStep.UPDATE_RUN_MARKET.value or             # 更新中(市場データ)
            state == GetDataStep.UPDATE_ERROR.value or                  # 更新エラー
            state == GetDataStep.UPDATE_DONE.value):                    # 更新済
            dt_start_total = datetime.now(tz)
            print_ex(f'処理実施 state={state} ss_name={ss_name}')
        else:
            print_ex(f'処理不要なのでスキップ state={state} ss_name={ss_name}')
            return

        #--------------------------------------------------------------------------------
        # step.0 - 初期化 開始
        #--------------------------------------------------------------------------------
        if (state == GetDataStep.INIT_DONE.value or         # 初回取得済
            state == GetDataStep.UPDATE_DONE.value or       # 更新済
            state == GetDataStep.UPDATE_ERROR.value):       # 更新エラー

            print_ex('[St.0] get_data_update 初期化 開始' + ss_name)

            # 開始時間を記録
            update_proc_start_time(url_manage, url_sheet, index)

            # ステップ別処理時間クリア
            clear_step_proc_time_update(url_manage, index)

            # ステップ移行
            state = GetDataStep.UPDATE_RUN_ORDER.value

            print_ex('[St.0] get_data_update 初期化 終了' + ss_name)

        #--------------------------------------------------------------------------------
        # step.1 - 注文実績を追加
        #--------------------------------------------------------------------------------
        if state == GetDataStep.UPDATE_RUN_ORDER.value:       # 更新中(注文実績)

            print_ex('[St.1] get_data_update 注文実績更新 開始 ' + ss_name)
            update_proc_status(url_manage, url_sheet, index, state)

            # 開始時間記録
            dt_start = datetime.now(tz)

            # 注文実績→CSVファイル
            get_order_data_multi(get_dt_str(), url_order)

            # 前回取得データの最新日時を取得
            data_latest = get_ss_all_values(url_sheet, ORDER_SHEET_NAME)

            # 日付の区切りをスラッシュに置換
            col_indexs = [1, 5, 6]   # 取得日時, 出品日, 成約日
            data_latest = replace_date_separator(data_latest, col_indexs)

            if len(data_latest[0]) > 1:
                data_latest = sorted(data_latest[1:], key=sort_key)
                dt_latest = data_latest[-1][6]
                dt_latest = datetime.strptime(dt_latest, '%Y/%m/%d').date()

            # CSVファイルから読込み
            data = csv_to_array(FILE_PATH_ORDER)

            # 日付の区切りをスラッシュに置換
            col_indexs = [1, 5, 6]   # 取得日時, 出品日, 成約日
            data_rep = replace_date_separator(data, col_indexs)

            # 成約日でソート
            data_sorted = sorted(data_rep, key=sort_key)

            # 追加するデータを特定
            dt_today = datetime.now(tz).date()
            dt_yesterday = dt_today - timedelta(days=1)

            no_start = len(data_latest) + 1
            for j, r in enumerate(data_sorted):
                date = datetime.strptime(r[6].split()[0], '%Y/%m/%d').date()
                if dt_latest < date and date <= dt_yesterday:
                    r[0] = no_start     # No.を続きから振る
                    no_start += 1
                    data_latest.append(r)

            # スプレッドシートへ書込み
            set_ss_all_values(url_sheet, ORDER_SHEET_NAME, data_latest)

            # 終了時間記録
            update_step_proc_time(url_manage, index, MANAGE_COL_UPDATE_STEP + 1 - 1, dt_start, datetime.now(tz))

            # ステップ移行
            state = GetDataStep.UPDATE_RUN_LIST.value

            print_ex('[St.1] get_data_update 注文実績更新 終了 ' + ss_name)

        #--------------------------------------------------------------------------------
        # step.2 - 出品データ更新
        #--------------------------------------------------------------------------------
        if state == GetDataStep.UPDATE_RUN_LIST.value:        # 更新中(出品リスト)

            print_ex('[St.2] get_data_update 出品データ更新 開始 ' + ss_name)
            update_proc_status(url_manage, url_sheet, index, state)

            # 開始時間記録
            dt_start = datetime.now(tz)

            # Webサイトから出品データを取得
            get_item_list_multi(url_item, ITEM_COLS)
            df_list = pd.read_csv(FILE_PATH_ITEM)

            # スプレッドシートの出品データ取得
            data = get_ss_all_values(url_sheet, ITEM_SHEET_NAME)
            data_cols = data[0]
            data_rows = data[1:]
            df_item = pd.DataFrame(data_rows, columns=data_cols)

            # IDをキーにマージ
            df_list['ID'] = df_list['ID'].astype(str)
            df_item['ID'] = df_item['ID'].astype(str)
            merged_df = pd.merge(df_list, df_item, on='ID', how='outer', indicator=True)

            # Webサイトに新たに増えた商品データを追加
            df_list_only = merged_df[merged_df['_merge'] == 'left_only']
            df_list_only_ids = df_list_only['ID'].tolist()
            df_add_rows = df_list[df_list['ID'].isin(df_list_only_ids)]
            df_add_rows['No.'] = range(len(df_item) + 1, len(df_item) + 1 + len(df_add_rows))   # No.を続きから振る
            df_item = pd.concat([df_item, df_add_rows], ignore_index=True)
            df_item.loc[df_item['ID'].isin(df_list_only_ids), '出品'] = '未取得'
            df_item.to_csv(FILE_PATH_LIST_INC, index=False)

            # スプレッドシートのみに存在する減った商品データに削除フラグを付ける
            df_item_only = merged_df[merged_df['_merge'] == 'right_only']
            df_item_only_ids = df_item_only['ID'].tolist()
            df_item.loc[df_item['ID'].isin(df_item_only_ids), '出品'] = '削除'
            df_item.to_csv(FILE_PATH_LIST_DEC, index=False)

            # 両方に含まれるデータは出品中とする
            df_both = merged_df[merged_df['_merge'] == 'both']
            df_both_ids = df_both['ID'].tolist()
            df_item.loc[df_item['ID'].isin(df_both_ids), '出品'] = '出品中'
            df_item.to_csv(FILE_PATH_LIST_BOTH, index=False)

            # スプレッドシートへ書込み
            df_item.to_csv(FILE_PATH_ITEM, index=False)
            data = csv_to_array(FILE_PATH_ITEM)
            set_ss_all_values(url_sheet, ITEM_SHEET_NAME, data)

            # 終了時間記録
            update_step_proc_time(url_manage, index, MANAGE_COL_UPDATE_STEP + 2 - 1, dt_start, datetime.now(tz))

            # ステップ移行
            state = GetDataStep.UPDATE_RUN_ITEM.value

            print_ex('[St.2] get_data_update 出品データ更新 終了 ' + ss_name)

        #--------------------------------------------------------------------------------
        # step.3 - 増加した出品データ詳細を取得
        #--------------------------------------------------------------------------------
        if state == GetDataStep.UPDATE_RUN_ITEM.value:        # 更新中(出品データ)

            print_ex('[St.3] get_data_update 出品データ取得(増分) 開始 ' + ss_name)
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
            update_step_proc_time(url_manage, index, MANAGE_COL_UPDATE_STEP + 3 - 1, dt_start, datetime.now(tz))

            # ステップ移行
            diff = datetime.now(tz) - update_dt
            if diff > timedelta(days=MARKET_DAY_SPAN):
                state = GetDataStep.UPDATE_RUN_PRICE.value
            else:
                state = GetDataStep.UPDATE_DONE.value

            print_ex('[St.3] get_data_update 出品データ取得(増分) 終了 ' + ss_name)

        #--------------------------------------------------------------------------------
        # step.4 - 出品データの価格を更新
        #--------------------------------------------------------------------------------
        if state == GetDataStep.UPDATE_RUN_PRICE.value:        # 更新中(価格)

            print_ex('[St.4] get_data_update 価格更新 開始 ' + ss_name)
            update_proc_status(url_manage, url_sheet, index, state)

            # 開始時間記録
            dt_start = datetime.now(tz)

            # 出品データの価格更新
            get_item_price_multi(url_sheet)

            # スプレッドシート出力
            data = csv_to_array(FILE_PATH_PRICE)
            set_ss_all_values(url_sheet, ITEM_SHEET_NAME, data)

            # 終了時間記録
            update_step_proc_time(url_manage, index, MANAGE_COL_UPDATE_STEP + 4 - 1, dt_start, datetime.now(tz))

            # ステップ移行
            state = GetDataStep.UPDATE_RUN_MARKET.value

            print_ex('[St.4] get_data_update 価格更新 終了 ' + ss_name)

        #--------------------------------------------------------------------------------
        # step.5 - カテゴリ抽出し市場データを取得
        #--------------------------------------------------------------------------------
        if state == GetDataStep.UPDATE_RUN_MARKET.value:        # 更新中(市場データ)

            print_ex('[St.5] get_data_update 市場データ更新 開始 ' + ss_name)
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
            update_step_proc_time(url_manage, index, MANAGE_COL_UPDATE_STEP + 5 - 1, dt_start, datetime.now(tz))

            # ステップ移行
            state = GetDataStep.UPDATE_DONE.value

            print_ex('[St.5] get_data_update 市場データ更新 終了 ' + ss_name)

        #--------------------------------------------------------------------------------
        # step.6 - 正常終了
        #--------------------------------------------------------------------------------
        if state == GetDataStep.UPDATE_DONE.value:      # 初回取得済

            print_ex('[St.6] get_data_update 終了処理 開始 ' + ss_name)

            update_proc_status(url_manage, url_sheet, index, state)
            update_proc_end_time(url_manage, url_sheet, index)
            update_proc_time(url_manage, url_sheet, index, dt_start_total, datetime.now(tz))
            update_step_proc_time(url_manage, index, MANAGE_COL_UPDATE_TOTAL, dt_start_total, datetime.now(tz))

            print_ex('[St.6] get_data_update 終了処理 終了 ' + ss_name)

    except Exception as e:
        print_ex(f'エラー発生: {e}')
        state = GetDataStep.UPDATE_ERROR.value
        update_proc_status(url_manage, url_sheet, index, state)

    print_ex('データ更新 処理終了')
    return

def main():
    print('テスト実行')
    #get_data_update()

if __name__ == "__main__":
    main()