#--------------------------------------------------------------------------------
# データ取得メイン処理
#--------------------------------------------------------------------------------
# ① 外注総合管理ツールを読込み実行順を定める
#--------------------------------------------------------------------------------
import pytz
from get_data_init import get_data_init
from get_data_update import get_data_update
from scraping import *
from datetime import datetime, timedelta
from collections import deque

tz = pytz.timezone('Asia/Tokyo')


def get_data_main():

    print_ex('データ取得メイン処理 開始')

    try:
        clients = []
        for url in MANAGE_SS_URL:
            # 外注管理リスト取得
            url_list = get_management_info(url)

            for i in range(len(url_list)):
                url_list[i]['index'] = i

            clients.append(url_list)
        
        queueInit = deque()
        queueUpdate = deque()

        while any(clients):
            for i, client in enumerate(clients):

                for j, row in enumerate(client):
                    data = client.pop(0)

                    # 初回対象サーチ
                    state = data['state']
                    if (state == GetDataStep.INIT_NONE.value or         # 初回データ取得予約
                        state == GetDataStep.INIT_RUN_ORDER.value or    # 初回取得中(注文実績)
                        state == GetDataStep.INIT_RUN_LIST.value or     # 初回取得中(出品リスト)
                        state == GetDataStep.INIT_RUN_CHECK.value or    # 初回取得中(出品リスト確認)
                        state == GetDataStep.INIT_RUN_ITEM.value or     # 初回取得中(出品データ)
                        state == GetDataStep.INIT_RUN_MARKET.value or   # 初回取得中(市場データ)
                        state == GetDataStep.INIT_ERROR.value):         # 初回取得エラー

                        # 出品データ取得中から再開の場合は出品リスト取得から
                        if ( state == GetDataStep.INIT_RUN_CHECK.value or state == GetDataStep.INIT_RUN_ITEM.value):
                            state = GetDataStep.INIT_RUN_LIST.value

                        queueInit.append({'url': MANAGE_SS_URL[i], 'index': data['index'], 'info': data})
                        break

                    # 更新対象サーチ
                    if (state == GetDataStep.INIT_DONE.value or         # 初回取得済
                        state == GetDataStep.UPDATE_RUN_ORDER.value or  # 更新中(注文実績)
                        state == GetDataStep.UPDATE_RUN_LIST.value or   # 更新中(出品リスト)
                        state == GetDataStep.UPDATE_RUN_ITEM.value or   # 更新中(出品データ)
                        state == GetDataStep.UPDATE_RUN_PRICE.value or  # 更新中(価格)
                        state == GetDataStep.UPDATE_RUN_MARKET.value or # 更新中(市場データ)
                        state == GetDataStep.UPDATE_ERROR.value or      # 更新エラー
                        state == GetDataStep.UPDATE_DONE.value):        # 更新済

                        # 出品データ取得中から再開の場合は出品リスト取得から
                        if state == GetDataStep.UPDATE_RUN_ITEM.value:
                            state = GetDataStep.UPDATE_RUN_LIST.value

                        queueUpdate.append({'url': MANAGE_SS_URL[i], 'index': data['index'], 'info': data})
                        break

        # 更新処理
        while queueUpdate:
            item = queueUpdate.popleft()
            get_data_update(item['url'], item['index'], item['info'])
            time.sleep(60)

        # 初期化処理
        while queueInit:
            item = queueInit.popleft()
            get_data_init(item['url'], item['index'], item['info'])
            time.sleep(60)

    except Exception as e:
        print_ex(f'エラー発生: {e}')
        set_error_detail(item['url'], item['index'], f'{e}')

    print_ex('データ取得メイン処理 終了')
    return


def main():
    get_data_main()


if __name__ == "__main__":
    main()