import os
import requests
import io
import duckdb
import zipfile
import uuid
from glob import glob
import shutil
from module import utf_converter

def get_edinet_doc_json(
    doc_id :str,
    
    ):
    """EDINETを叩いてまずはdocidの中身を解凍して返す
    日付を何かテーブルに入れたいけどめんどくさい。
    """

    # 参考
    # https://note.com/python_beginner/n/na0e51d80bc35
    # https://qiita.com/kj1729/items/88b2ffc3e21b98c91aea

    edinet_api_key = os.getenv("EDINET_API_KEY")
    URL = f"https://disclosure.edinet-fsa.go.jp/api/v2/documents/{doc_id}"

    params = {
        "type" : 5,
        "Subscription-Key" : edinet_api_key
    }

    dir_id = doc_id + str(uuid.uuid4())
    
    # https://qiita.com/nujust/items/9cb4564e712720549bc1
    extract_dir = f"downloads/{dir_id}"

    try:
        with (
            requests.get(URL, params = params) as res,
            io.BytesIO(res.content) as bytes_io,
            zipfile.ZipFile(bytes_io) as zip,
        ):
            zip.extractall(extract_dir)

    except:
        # たぶんステータス404が返ってきてる
        data = res.json()
        print(data)
        return None


    path_list = glob(f"downloads/{dir_id}/XBRL_TO_CSV/*")
    utf_converter.utf16_to_utf8(path_list)

    duckdb.read_csv(f"downloads/{dir_id}/XBRL_TO_CSV/*.csv")    

    data = duckdb.sql(f"""select * from 'downloads/{dir_id}/XBRL_TO_CSV/*.csv'""").to_df().to_dict('records')
    shutil.rmtree(f"downloads/{dir_id}")

    return data