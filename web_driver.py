from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium import webdriver

#--------------------------------------------------------------------------------
# Chrome Driver 初期化
#--------------------------------------------------------------------------------
def get_web_driver(lock):

    with lock:
        # Chromerドライバ起動オプション
        driver_path = ChromeDriverManager().install()
        service = Service(executable_path=driver_path)
        options = Options()
        #options.add_argument('--headless')              # ヘッドレスモードで起動
        options.add_argument('--log-level=3')
        #options.add_argument('--disable-gpu')
        #options.page_load_strategy = 'eager'           # ロード戦略をeagerに設定

        # ChromeDriver
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(60)

    return driver