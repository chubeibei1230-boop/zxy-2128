import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"

def login(username, password):
    response = requests.post(f"{BASE_URL}/auth/login/", 
                             json={"username": username, "password": password})
    return response.json().get('token')

token = login("admin", "admin123456")
headers = {"Authorization": f"Token {token}"}

print("=== 获取所有预警（不指定项目） ===")
response = requests.get(f"{BASE_URL}/material-warnings/", headers=headers)
print(f"状态码: {response.status_code}")
data = response.json()
results = data.get('results', data)
print(f"预警总数: {len(results)}")
for w in results:
    print(f"  {w['warning_no']} - {w['warning_type_display']} - {w['status_display']} - 项目ID:{w['project']}")

print("\n=== 运行预警检测 ===")
response = requests.post(f"{BASE_URL}/material-warnings/detect/", headers=headers, json={})
print(f"状态码: {response.status_code}")
print(f"响应: {json.dumps(response.json(), ensure_ascii=False)}")

print("\n=== 再次获取预警列表 ===")
response = requests.get(f"{BASE_URL}/material-warnings/", headers=headers)
data = response.json()
results = data.get('results', data)
print(f"预警总数: {len(results)}")
for w in results:
    print(f"  {w['warning_no']} - {w['warning_type_display']} - {w['status_display']} - 项目ID:{w['project']} - {w['material_category_name']}")
