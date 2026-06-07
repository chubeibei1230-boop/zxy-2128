import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"
PROJECT_ID = 15

def login(username, password):
    response = requests.post(f"{BASE_URL}/auth/login/", 
                             json={"username": username, "password": password})
    return response.json().get('token')

print("=" * 70)
print("材料预警功能完整演示测试 (项目ID: 15)")
print("=" * 70)

admin_token = login("admin", "admin123456")
operator_token = login("operator", "operator123")
auditor_token = login("auditor", "auditor123")

headers = {"Authorization": f"Token {admin_token}"}

print("\n【1/9】仪表盘数据 (含预警统计)")
response = requests.get(f"{BASE_URL}/dashboard/", headers=headers)
data = response.json()
print(f"  预警总数: {data.get('total_warning')}")
print(f"  待处理预警: {data.get('pending_warning')}")
print(f"  处理中预警: {data.get('processing_warning')}")

print("\n【2/9】预警仪表盘 (按类型统计)")
response = requests.get(f"{BASE_URL}/warning-dashboard/?project={PROJECT_ID}", headers=headers)
data = response.json()
ws = data.get('warning_stats', {})
print(f"  预警总数: {ws.get('total')}")
print(f"  待处理: {ws.get('pending')}  处理中: {ws.get('processing')}  已处理: {ws.get('processed')}  已忽略: {ws.get('ignored')}")
print(f"  完成率: {ws.get('completion_rate')}%")
print(f"  按类型: 低库存={ws.get('by_type',{}).get('low_stock')}, 临期={ws.get('by_type',{}).get('expiring')}, 积压={ws.get('by_type',{}).get('overstock')}")

print("\n【3/9】预警列表 (全部)")
response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}", headers=headers)
data = response.json()
results = data.get('results', data)
print(f"  共 {len(results)} 条预警:")
for w in results:
    print(f"    {w['warning_no']} | {w['warning_type_display']:8} | {w['status_display']:6} | {w['priority_display']:4} | {w['material_category_name']}")

print("\n【4/9】按类型筛选 - 低库存预警")
response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}&warning_type=low_stock", headers=headers)
data = response.json()
results = data.get('results', data)
print(f"  找到 {len(results)} 条低库存预警")

print("\n【5/9】按状态筛选 - 待处理预警")
response = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}&status=pending", headers=headers)
data = response.json()
results = data.get('results', data)
print(f"  找到 {len(results)} 条待处理预警")

if results:
    warning_id = results[0]['id']
    print(f"\n【6/9】预警详情 (ID: {warning_id})")
    response = requests.get(f"{BASE_URL}/material-warnings/{warning_id}/", headers=headers)
    w = response.json()
    print(f"  预警编号: {w['warning_no']}")
    print(f"  预警类型: {w['warning_type_display']}")
    print(f"  优先级: {w['priority_display']}")
    print(f"  状态: {w['status_display']}")
    print(f"  项目: {w['project_name']}")
    print(f"  分区: {w['zone_name']} ({w['zone_code']})")
    print(f"  材料: {w['material_category_name']} ({w['material_category_code']})")
    print(f"  批次: {w['material_batch_no']}")
    print(f"  当前数量: {w['current_quantity']}")
    print(f"  阈值数量: {w['threshold_quantity']}")
    print(f"  描述: {w['description']}")

    print(f"\n【7/9】开始处理预警 (操作员) - ID: {warning_id}")
    headers_op = {"Authorization": f"Token {operator_token}"}
    data = {"handling_opinion": "已安排材料员跟进处理", "responsible_person": 2}
    response = requests.post(f"{BASE_URL}/material-warnings/{warning_id}/start_processing/", 
                             headers=headers_op, json=data)
    result = response.json()
    print(f"  状态: {result['status_display']}")
    print(f"  处理意见: {result['handling_opinion']}")
    print(f"  责任人: {result['responsible_person_name']}")

    pending_warnings = []
    response2 = requests.get(f"{BASE_URL}/material-warnings/?project={PROJECT_ID}&status=pending", headers=headers)
    data2 = response2.json()
    pending_warnings = data2.get('results', data2)
    
    if pending_warnings:
        w2_id = pending_warnings[0]['id']
        print(f"\n【8/9】直接处理完成预警 (操作员) - ID: {w2_id}")
        data = {
            "handling_opinion": "已联系供应商补货",
            "handling_result": "采购订单已下达，预计3天内到货50吨",
            "responsible_person": 2
        }
        response = requests.post(f"{BASE_URL}/material-warnings/{w2_id}/process/", 
                                 headers=headers_op, json=data)
        result = response.json()
        print(f"  状态: {result['status_display']}")
        print(f"  处理结果: {result['handling_result']}")
        print(f"  处理人: {result['handled_by_name']}")

print("\n【9/9】处理后统计数据")
response = requests.get(f"{BASE_URL}/material-warnings/statistics/?project={PROJECT_ID}", headers=headers)
data = response.json()
print(f"  总计: {data.get('total')}")
print(f"  待处理: {data.get('pending')}")
print(f"  处理中: {data.get('processing')}")
print(f"  已处理: {data.get('processed')}")
print(f"  已忽略: {data.get('ignored')}")
print(f"  完成率: {data.get('completion_rate')}%")

print("\n" + "=" * 70)
print("✅ 预警功能测试完成！")
print("=" * 70)
print("\n📋 完整业务闭环流程:")
print("  1. 系统自动检测 → 生成预警记录 (低库存/临期/长期未使用/积压)")
print("  2. 预警列表展示 → 按项目/分区/类别/状态/类型/优先级筛选")
print("  3. 查看详情 → 查看完整预警信息、关联库存和批次")
print("  4. 开始处理 → 指定责任人、填写处理意见，状态变为'处理中'")
print("  5. 处理完成 → 填写处理结果，状态变为'已处理'")
print("  6. 或忽略预警 → 填写忽略原因，状态变为'已忽略'")
print("  7. 必要时重新打开 → 已处理/已忽略的可重新变为待处理")
print("  8. 项目概览 → 实时展示预警数量与处理进度")
