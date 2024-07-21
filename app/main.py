

from fastapi import HTTPException, status, Security, FastAPI
from fastapi.security import APIKeyHeader, APIKeyQuery
import uvicorn
from datetime import date, timedelta
import requests
import os
import io
import duckdb
import zipfile
import uuid
from glob import glob
import shutil
from module import utf_converter, edinet_doc

api_key = os.getenv("FASTAPI_APIKEY")
API_KEYS = []
if api_key:
    API_KEYS.append(api_key)

# 参考
# https://joshdimella.com/blog/adding-api-key-auth-to-fast-api

api_key_query = APIKeyQuery(name="api-key", auto_error=False)
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

def get_api_key(
    api_key_query: str = Security(api_key_query),
    api_key_header: str = Security(api_key_header),
) -> str:
    """Retrieve and validate an API key from the query parameters or HTTP header.

    Args:
        api_key_query: The API key passed as a query parameter.
        api_key_header: The API key passed in the HTTP header.

    Returns:
        The validated API key.

    Raises:
        HTTPException: If the API key is invalid or missing.
    """
    if api_key_query in API_KEYS:
        return api_key_query
    if api_key_header in API_KEYS:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key",
    )

app = FastAPI()

@app.get("/")
def hello_world():
    """A public endpoint that does not require any authentication."""
    return "hello world"


@app.get("/edinet_yukashoken")
def get_edinet_json(
    from_date :date,
    to_date: date,
    next_page_token: date = None,
    api_key: str = Security(get_api_key),
    ):
    """EDINETを日付範囲で有価証券報告書を1テーブルで返す。範囲を決めたうえで半ページ送り式でnext_tokenには日付が入る。返ってくるnext_tokenがnoneならおわり。"""

    # 参考
    # https://note.com/python_beginner/n/na0e51d80bc35

    edinet_api_key = os.getenv("EDINET_API_KEY")
    URL = "https://disclosure.edinet-fsa.go.jp/api/v2/documents.json"

    # metadataをとる

    if next_page_token:
        # 最初はNoneが来ることになってるのでそうじゃなかったら続きから
        target_date = next_page_token
    else:
        target_date = from_date

    # メタデータ部分とる。適当。
    while target_date <= to_date:

        params = {
            "date" : target_date,
            "type" : 2,
            "Subscription-Key" : edinet_api_key
        }

        res = requests.get(URL, params = params)
        data = res.json()


        # 有価証券報告書だけとりだす
        data = [doc for doc in data['results'] if doc['docDescription'] is not None and '有価証券報告書' in doc['docDescription']]


        # 各docに "target_date":date を追加
        target_date += timedelta(days=1)
        next_page_token = target_date

        if not data:
            # 空だったらループを継続抜ける。
            continue

        # １日ごとに返す。
        break

    # doc部分とる
    for doc in data:
        doc_data = edinet_doc.get_edinet_doc_json(doc["docID"])
        doc["data"] = doc_data


    if next_page_token >= to_date:
        next_page_token = None

    return {'data': data, 'next_page_token':next_page_token}


@app.get("/edinet_json")
def get_edinet_json(
    target_date :date,
    api_key: str = Security(get_api_key)
    
    ):
    """EDINETを叩いてまずはJSONのところを返す"""

    # 参考
    # https://note.com/python_beginner/n/na0e51d80bc35

    edinet_api_key = os.getenv("EDINET_API_KEY")
    URL = "https://disclosure.edinet-fsa.go.jp/api/v2/documents.json"

    params = {
        "date" : target_date,
        "type" : 2,
        "Subscription-Key" : edinet_api_key
    }

    res = requests.get(URL, params = params)
    data = res.json()

    # 有価証券報告書だけとりだす
    data = [doc for doc in data['results'] if doc['docDescription'] is not None and '有価証券報告書' in doc['docDescription']]

    # 各docに "target_date":date を追加
    for doc in data:
        doc["target_date"] = target_date

    return data

@app.get("/edinet_doc")
def get_edinet_json(
    doc_id :str,
    date: date = date.today(),
    api_key: str = Security(get_api_key)
    
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
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"リクエストエラー: {e}")
    except zipfile.BadZipFile as e:
        try:
            # たぶんステータス404が返ってきてる
            data = res.json()
            print(data)
            return
            
        except:
            raise HTTPException(status_code=400, detail=f"ZIPファイルエラー: {e} res:{res.json()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {e}")

    path_list = glob(f"downloads/{dir_id}/XBRL_TO_CSV/*")
    utf_converter.utf16_to_utf8(path_list)

    duckdb.read_csv(f"downloads/{dir_id}/XBRL_TO_CSV/*.csv")    

    data = duckdb.sql(f"""select gen_random_uuid() as uuid, '{date}' as create_or_insert_date ,'{doc_id}' as doc_id, * from 'downloads/{dir_id}/XBRL_TO_CSV/*.csv'""").to_df().to_dict('records')
    shutil.rmtree(f"downloads/{dir_id}")


    return data


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8083)
