import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"
PROJECT_ID = 15

def login(username, password):
    response = requests.post(f"{BASE_URL}/auth/login/", 
                             json={"username": username, "password": password})
    return response.json().get('token')

print("=" * 70)
print("预警功能优化验证测试")
print("=" * 70)

admin_token = login("admin", "admin123456")
operator_token = login("operator", "operator123")
auditor_token = login("auditor", "auditor123")

headers = {"Authorization": f"Token {admin_token}"}
headers_op = {"Authorization": f"Token {operator_token}"}

print("\n✅ 【验证1】四种预警类型是否全部覆盖")
response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}", headers=headers)
data = response.json()
results = data.get('results', data)
type_count = {}
for w in results:
    t = w['warning_type_display']
    type_count[t] = type_count.get(t, 0) + 1
print(f"  预警总数: {len(results)}")
for t, c in type_count.items():
    print(f"    - {t}: {c} 条")
has_all_types = len(type_count) >= 4
print(f"  四种预警全覆盖: {'✅ 通过' if has_all_types else '❌ 未通过'}")

print("\n✅ 【验证2】部分入库批次是否触发临期预警")
expiring_warnings = [w for w in results if w['warning_type'] == 'expiring']
has_partial = False
for w in expiring_warnings:
    if '部分' in w.get('material_batch_no', '') or 'PARTIAL' in w.get('material_batch_no', ''):
        has_partial = True
        print(f"    找到部分入库的临期预警: {w['material_batch_no']} - {w['description'][:50]}...")
print(f"  部分入库批次触发预警: {'✅ 通过' if has_partial else '❌ 未通过'}")

print("\n✅ 【验证3】业务联动校验 - 库存问题未解决不能标记已处理")
low_stock_warnings = [w for w in results if w['warning_type'] == 'low_stock' and w['status'] == 'pending']
if low_stock_warnings:
    w_id = low_stock_warnings[0]['id']
    print(f"  测试低库存预警 (ID: {w_id})")
    data = {
        "handling_result": "假装已经补货了",
        "handling_opinion": "测试强制关闭"
    }
    response = requests.post(f"{BASE_URL}/material-warnings/{w_id}/process/", 
                           headers=headers_op, json=data)
    print(f"  状态码: {response.status_code}")
    resp_data = response.json()
    if response.status_code == 400:
        print(f"  正确拦截成功 - {resp_data.get('error', '')[:80]}...")
        print(f"  业务校验生效: ✅ 通过")
    else:
        print(f"  未拦截 - {resp_data}")

print("\n✅ 【验证4】强制关闭功能 (仅管理员/审核员)")
if low_stock_warnings:
    w_id = low_stock_warnings[0]['id']
    data = {
        "handling_result": "项目变更，不再需要此材料",
        "handling_opinion": "审核员确认可以强制关闭",
        "force_close": True
    }
    response = requests.post(f"{BASE_URL}/material-warnings/{w_id}/process/", 
                           headers=headers_op, json=data)
    print(f"  操作员尝试强制关闭: 状态码 {response.status_code}")
    if response.status_code == 403:
        print(f"  权限校验生效: 操作员无强制关闭权限")
    response = requests.post(f"{BASE_URL}/material-warnings/{w_id}/process/", 
                           headers=headers, json=data)
    print(f"  管理员尝试强制关闭: 状态码 {response.status_code}")
    if response.status_code == 200:
        print(f"  管理员成功强制关闭")

print("\n✅ 【验证5】预警不重复生成")
before_count = len(results)
print(f"  当前预警数: {before_count}")
response = requests.post(f"{BASE_URL}/material-warnings/detect/", headers=headers, json={"project": PROJECT_ID})
resp_data = response.json()
print(f"  再次检测新增数: {resp_data.get('total_count', 0)}")
response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}", headers=headers)
results = response.json().get('results', response.json())
after_count = len(results)
print(f"  检测后预警数: {after_count}")
print(f"  未重复生成: {'✅ 通过' if before_count == after_count else f'❌ 未通过 (新增 {after_count - before_count} 条)'}")

print("\n✅ 【验证6】处理后再次检测，问题仍存在会重新打开而非新建")
pending_warnings = [w for w in results if w['status'] == 'pending']
if pending_warnings:
    w_id = pending_warnings[0]['id']
    print(f"  处理预警 ID: {w_id}")
    data = {
        "handling_result": "临时处理，但问题实际还在",
        "force_close": True
    }
    requests.post(f"{BASE_URL}/material-warnings/{w_id}/process/", 
                  headers=headers, json=data)
    
    response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}", headers=headers)
    results = response.json().get('results', response.json())
    processed = [w for w in results if w['id'] == w_id]
    print(f"  处理后状态: {processed[0]['status_display'] if processed else '找不到'}")
    
    response = requests.post(f"{BASE_URL}/material-warnings/detect/", headers=headers, json={"project": PROJECT_ID})
    
    response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}", headers=headers)
    results = response.json().get('results', response.json())
    reopened = [w for w in results if w['id'] == w_id]
    print(f"  检测后状态: {reopened[0]['status_display'] if reopened else '找不到'}")
    if reopened and reopened[0]['status'] == 'pending':
        print(f"  预警重新打开而不是新建: ✅ 通过")

print("\n" + "=" * 70)
print("所有验证完成!")
print("=" * 70)
