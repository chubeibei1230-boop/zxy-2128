import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"

def login(username, password):
    response = requests.post(f"{BASE_URL}/auth/login/", 
                             json={"username": username, "password": password})
    return response.json().get('token')

token = login("operator", "operator123")
headers = {"Authorization": f"Token {token}"}

print("测试 start_processing 接口...")
data = {"handling_opinion": "已安排材料员跟进处理", "responsible_person": 2}
response = requests.post(f"{BASE_URL}/material-warnings/4/start_processing/", 
                         headers=headers, json=data)
print(f"状态码: {response.status_code}")
print(f"响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
