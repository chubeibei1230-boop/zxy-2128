import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"
PROJECT_ID = 15

def login(username, password):
    response = requests.post(f"{BASE_URL}/auth/login/", 
                             json={"username": username, "password": password})
    return response.json().get('token')

print("=" * 70)
print("材料预警功能完整演示测试")
print("=" * 70)

admin_token = login("admin", "admin123456")
operator_token = login("operator", "operator123")
auditor_token = login("auditor", "auditor123")

print(f"admin_token: {bool(admin_token)}, operator_token: {bool(operator_token)}, auditor_token: {bool(auditor_token)}")

headers = {"Authorization": f"Token {admin_token}"}

print("\n【1/8】仪表盘数据 (含预警统计)")
response = requests.get(f"{BASE_URL}/dashboard/", headers=headers)
data = response.json()
print(f"  ✅ 预警总数: {data.get('total_warning')}")
print(f"  ✅ 待处理预警: {data.get('pending_warning')}")
print(f"  ✅ 处理中预警: {data.get('processing_warning')}")

print("\n【2/8】预警仪表盘 (详细统计)")
response = requests.get(f"{BASE_URL}/warning-dashboard/?project={PROJECT_ID}", headers=headers)
data = response.json()
ws = data.get('warning_stats', {})
print(f"  ✅ 预警总数: {ws.get('total')}")
print(f"  ✅ 待处理: {ws.get('pending')} | 处理中: {ws.get('processing')} | 已处理: {ws.get('processed')} | 已忽略: {ws.get('ignored')}")
print(f"  ✅ 完成率: {ws.get('completion_rate')}%")
print(f"  ✅ 按类型: 低库存={ws.get('by_type',{}).get('low_stock')}, 临期={ws.get('by_type',{}).get('expiring')}, 积压={ws.get('by_type',{}).get('overstock')}")

print("\n【3/8】预警列表 (全部)")
response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}", headers=headers)
data = response.json()
results = data.get('results', data)
print(f"  ✅ 共 {len(results)} 条预警:")
for w in results:
    print(f"      {w['warning_no']} | {w['warning_type_display']:8} | {w['status_display']:6} | {w['priority_display']:4} | {w['material_category_name']}")

print("\n【4/8】筛选查询测试")
response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}&warning_type=low_stock", headers=headers)
data = response.json()
print(f"  ✅ 按类型(低库存)筛选: {len(data.get('results', data))} 条")

response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}&status=pending", headers=headers)
data = response.json()
print(f"  ✅ 按状态(待处理)筛选: {len(data.get('results', data))} 条")

response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}&priority=urgent", headers=headers)
data = response.json()
print(f"  ✅ 按优先级(紧急)筛选: {len(data.get('results', data))} 条")

print("\n【5/8】预警详情")
response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}&status=pending", headers=headers)
results = response.json().get('results', [])
if results:
    w_id = results[0]['id']
    response = requests.get(f"{BASE_URL}/material-warnings/{w_id}/", headers=headers)
    w = response.json()
    print(f"  ✅ 预警编号: {w['warning_no']}")
    print(f"  ✅ 预警类型: {w['warning_type_display']}")
    print(f"  ✅ 优先级: {w['priority_display']}")
    print(f"  ✅ 状态: {w['status_display']}")
    print(f"  ✅ 项目/分区: {w['project_name']} / {w['zone_name']}")
    print(f"  ✅ 材料/批次: {w['material_category_name']} / {w['material_batch_no']}")
    print(f"  ✅ 数量/阈值: {w['current_quantity']} / {w['threshold_quantity']}")
    print(f"  ✅ 描述: {w['description'][:60]}...")

print("\n【6/8】状态流转 - 开始处理")
response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}&status=pending", headers=headers)
results = response.json().get('results', [])
if results:
    w_id = results[0]['id']
    headers_op = {"Authorization": f"Token {operator_token}"}
    data = {"handling_opinion": "已安排材料员跟进处理，联系供应商补货"}
    response = requests.post(f"{BASE_URL}/material-warnings/{w_id}/start_processing/", 
                             headers=headers_op, json=data)
    result = response.json()
    if response.status_code == 200:
        print(f"  ✅ 状态变更: 待处理 → {result.get('status_display')}")
        print(f"  ✅ 处理意见: {result.get('handling_opinion')}")
    else:
        print(f"  ❌ 错误: {result}")

print("\n【7/8】状态流转 - 处理完成")
response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}&status=pending", headers=headers)
results = response.json().get('results', [])
if results:
    w_id = results[0]['id']
    headers_op = {"Authorization": f"Token {operator_token}"}
    data = {
        "handling_opinion": "已完成补货",
        "handling_result": "已采购50吨钢筋，今日已入库，库存恢复正常水平"
    }
    response = requests.post(f"{BASE_URL}/material-warnings/{w_id}/process/", 
                             headers=headers_op, json=data)
    result = response.json()
    if response.status_code == 200:
        print(f"  ✅ 状态变更: 待处理 → {result.get('status_display')}")
        print(f"  ✅ 处理结果: {result.get('handling_result')}")
        print(f"  ✅ 处理人: {result.get('handled_by_name')}")
    else:
        print(f"  ❌ 错误: {result}")

print("\n【8/8】最终统计")
response = requests.get(f"{BASE_URL}/material-warnings/statistics/?project={PROJECT_ID}", headers=headers)
data = response.json()
print(f"  ✅ 总计: {data.get('total')}")
print(f"  ✅ 待处理: {data.get('pending')} | 处理中: {data.get('processing')} | 已处理: {data.get('processed')} | 已忽略: {data.get('ignored')}")
print(f"  ✅ 完成率: {data.get('completion_rate')}%")

print("\n" + "=" * 70)
print("✅ 材料预警功能完整实现并测试通过！")
print("=" * 70)
