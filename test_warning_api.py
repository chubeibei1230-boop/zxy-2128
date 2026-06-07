import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api"

def test_login(username, password):
    print(f"\n=== 测试登录: {username} ===")
    try:
        response = requests.post(f"{BASE_URL}/auth/login/", 
                                 json={"username": username, "password": password})
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Token 获取成功")
            return data.get('token')
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"连接失败: {e}")
    return None

def test_dashboard(token):
    print("\n=== 测试仪表盘 (含预警统计) ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        response = requests.get(f"{BASE_URL}/dashboard/", headers=headers)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"项目总数: {data.get('total_projects')}")
            print(f"分区总数: {data.get('total_zones')}")
            print(f"库存总量: {data.get('total_stock')}")
            print(f"待处理预警: {data.get('pending_warning')}")
            print(f"处理中预警: {data.get('processing_warning')}")
            print(f"预警总数: {data.get('total_warning')}")
            return data
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    return {}

def test_warning_dashboard(token, project_id=None):
    print("\n=== 测试预警仪表盘 ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        url = f"{BASE_URL}/warning-dashboard/"
        if project_id:
            url += f"?project={project_id}"
        response = requests.get(url, headers=headers)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            warning_stats = data.get('warning_stats', {})
            print(f"预警总数: {warning_stats.get('total')}")
            print(f"待处理: {warning_stats.get('pending')}")
            print(f"处理中: {warning_stats.get('processing')}")
            print(f"已处理: {warning_stats.get('processed')}")
            print(f"已忽略: {warning_stats.get('ignored')}")
            print(f"完成率: {warning_stats.get('completion_rate')}%")
            print(f"按类型统计: {json.dumps(warning_stats.get('by_type', {}), ensure_ascii=False)}")
            return data
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    return {}

def test_warning_list(token, project_id=None, status=None, warning_type=None):
    print("\n=== 测试预警列表 ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        params = {}
        if project_id:
            params['project'] = project_id
        if status:
            params['status'] = status
        if warning_type:
            params['warning_type'] = warning_type
        response = requests.get(f"{BASE_URL}/material-warnings/", headers=headers, params=params)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', data)
            print(f"预警数量: {len(results)}")
            for warn in results:
                print(f"  - {warn.get('warning_no')} | {warn.get('warning_type_display')} | "
                      f"{warn.get('status_display')} | {warn.get('priority_display')} | "
                      f"{warn.get('material_category_name')}: {warn.get('current_quantity')}")
            return results
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    return []

def test_warning_detail(token, warning_id):
    print(f"\n=== 测试预警详情 (ID: {warning_id}) ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        response = requests.get(f"{BASE_URL}/material-warnings/{warning_id}/", headers=headers)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"预警编号: {data.get('warning_no')}")
            print(f"预警类型: {data.get('warning_type_display')}")
            print(f"优先级: {data.get('priority_display')}")
            print(f"状态: {data.get('status_display')}")
            print(f"项目: {data.get('project_name')}")
            print(f"分区: {data.get('zone_name')}")
            print(f"材料: {data.get('material_category_name')}")
            print(f"批次: {data.get('material_batch_no')}")
            print(f"当前数量: {data.get('current_quantity')}")
            print(f"阈值数量: {data.get('threshold_quantity')}")
            print(f"描述: {data.get('description')}")
            print(f"处理意见: {data.get('handling_opinion')}")
            print(f"处理结果: {data.get('handling_result')}")
            print(f"责任人: {data.get('responsible_person_name')}")
            print(f"创建人: {data.get('created_by_name')}")
            print(f"处理人: {data.get('handled_by_name')}")
            return data
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    return {}

def test_start_processing(token, warning_id):
    print(f"\n=== 测试开始处理预警 (ID: {warning_id}) ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        data = {
            "handling_opinion": "已安排材料员进行处理",
            "responsible_person": 2
        }
        response = requests.post(f"{BASE_URL}/material-warnings/{warning_id}/start_processing/", 
                                 headers=headers, json=data)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"状态更新为: {result.get('status_display')}")
            print(f"处理意见: {result.get('handling_opinion')}")
            return result
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    return {}

def test_process_warning(token, warning_id):
    print(f"\n=== 测试完成处理预警 (ID: {warning_id}) ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        data = {
            "handling_opinion": "已联系供应商补货",
            "handling_result": "已下达采购订单，预计3天内到货",
            "responsible_person": 2
        }
        response = requests.post(f"{BASE_URL}/material-warnings/{warning_id}/process/", 
                                 headers=headers, json=data)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"状态更新为: {result.get('status_display')}")
            print(f"处理结果: {result.get('handling_result')}")
            return result
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    return {}

def test_ignore_warning(token, warning_id):
    print(f"\n=== 测试忽略预警 (ID: {warning_id}) ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        data = {
            "handling_opinion": "该材料为应急储备物资，当前库存水平可接受"
        }
        response = requests.post(f"{BASE_URL}/material-warnings/{warning_id}/ignore/", 
                                 headers=headers, json=data)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"状态更新为: {result.get('status_display')}")
            return result
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    return {}

def test_warning_statistics(token, project_id=None):
    print("\n=== 测试预警统计 ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        url = f"{BASE_URL}/material-warnings/statistics/"
        if project_id:
            url += f"?project={project_id}"
        response = requests.get(url, headers=headers)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return data
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    return {}

def test_projects(token):
    print("\n=== 获取项目列表 ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        response = requests.get(f"{BASE_URL}/projects/", headers=headers)
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', data)
            print(f"项目数量: {len(results)}")
            for proj in results:
                print(f"  - ID:{proj.get('id')} {proj.get('name')}")
            return results
    except Exception as e:
        print(f"请求失败: {e}")
    return []

if __name__ == "__main__":
    print("=" * 70)
    print("材料预警功能完整测试")
    print("=" * 70)

    admin_token = test_login("admin", "admin123456")
    if not admin_token:
        print("\n登录失败，请检查服务器是否启动在端口 8000")
        sys.exit(1)

    operator_token = test_login("operator", "operator123")
    auditor_token = test_login("auditor", "auditor123")

    projects = test_projects(admin_token)
    project_id = projects[0]['id'] if projects else None

    test_dashboard(admin_token)
    test_warning_dashboard(admin_token, project_id)
    test_warning_statistics(admin_token, project_id)

    warnings = test_warning_list(admin_token, project_id=project_id)
    
    if warnings:
        first_warning_id = warnings[0]['id']
        test_warning_detail(admin_token, first_warning_id)
        
        if warnings[0]['status'] == 'pending':
            test_start_processing(operator_token, first_warning_id)
        
        pending_warnings = [w for w in warnings if w['status'] == 'pending']
        if pending_warnings:
            test_process_warning(operator_token, pending_warnings[0]['id'])
        
        processing_warnings = [w for w in warnings if w['status'] == 'processing']
        if processing_warnings:
            test_process_warning(operator_token, processing_warnings[0]['id'])

    print("\n=== 测试筛选功能 ===")
    test_warning_list(admin_token, project_id=project_id, status='pending')
    test_warning_list(admin_token, project_id=project_id, warning_type='low_stock')
    test_warning_list(admin_token, project_id=project_id, status='processed')

    print("\n" + "=" * 70)
    print("预警功能测试完成!")
    print("=" * 70)
    print("\n接口列表:")
    print("  列表查询: GET /api/material-warnings/")
    print("  详情查看: GET /api/material-warnings/{id}/")
    print("  预警检测: POST /api/material-warnings/detect/")
    print("  开始处理: POST /api/material-warnings/{id}/start_processing/")
    print("  处理完成: POST /api/material-warnings/{id}/process/")
    print("  忽略预警: POST /api/material-warnings/{id}/ignore/")
    print("  重新打开: POST /api/material-warnings/{id}/reopen/")
    print("  预警统计: GET /api/material-warnings/statistics/")
    print("  预警仪表盘: GET /api/warning-dashboard/")
    print("\n筛选参数: project, zone, material_category, status, warning_type, priority")
