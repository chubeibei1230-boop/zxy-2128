import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8028/api"

def test_login(username, password):
    print(f"\n=== 测试登录: {username} ===")
    try:
        response = requests.post(f"{BASE_URL}/auth/login/", 
                                 json={"username": username, "password": password})
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Token: {data.get('token', 'N/A')}")
            return data.get('token')
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"连接失败: {e}")
    return None

def test_current_user(token):
    print("\n=== 测试获取当前用户 ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        response = requests.get(f"{BASE_URL}/auth/current-user/", headers=headers)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"用户名: {data.get('username')}")
            print(f"角色: {data.get('role')}")
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")

def test_projects(token):
    print("\n=== 测试项目列表 ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        response = requests.get(f"{BASE_URL}/projects/", headers=headers)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', data)
            print(f"项目数量: {len(results)}")
            for proj in results[:3]:
                print(f"  - {proj.get('name')} ({proj.get('id')})")
            return results
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    return []

def test_zones(token, project_id):
    print(f"\n=== 测试分区树形结构 (项目ID: {project_id}) ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        response = requests.get(f"{BASE_URL}/zones/tree/?project={project_id}", headers=headers)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"树形数据加载成功")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
            return data
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")
    return []

def test_zone_statistics(token, zone_id):
    print(f"\n=== 测试分区统计 (分区ID: {zone_id}) ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        response = requests.get(f"{BASE_URL}/zones/{zone_id}/statistics/", headers=headers)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"统计数据: {json.dumps(data, ensure_ascii=False)}")
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")

def test_material_categories(token):
    print("\n=== 测试材料类别树形结构 ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        response = requests.get(f"{BASE_URL}/material-categories/tree/", headers=headers)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"材料类别树加载成功")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")

def test_dashboard(token):
    print("\n=== 测试仪表盘数据 ===")
    try:
        headers = {"Authorization": f"Token {token}"}
        response = requests.get(f"{BASE_URL}/dashboard/", headers=headers)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"项目总数: {data.get('total_projects')}")
            print(f"分区总数: {data.get('total_zones')}")
            print(f"库存总量: {data.get('total_stock')}")
            print(f"待审核领用: {data.get('pending_usage')}")
            print(f"待处理异常: {data.get('pending_exception')}")
            print(f"待确认转移: {data.get('pending_transfer')}")
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"请求失败: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("施工项目材料管理系统 API 测试")
    print("=" * 60)

    admin_token = test_login("admin", "admin123456")
    if not admin_token:
        print("管理员登录失败，请检查服务器是否启动")
        print("\n启动命令: python manage.py runserver 0.0.0.0:8028")
        sys.exit(1)

    test_current_user(admin_token)
    
    projects = test_projects(admin_token)
    if projects:
        project_id = projects[0]['id']
        zone_tree = test_zones(admin_token, project_id)
        if zone_tree and len(zone_tree) > 0:
            zone_id = zone_tree[0]['id']
            test_zone_statistics(admin_token, zone_id)
    
    test_material_categories(admin_token)
    test_dashboard(admin_token)
    
    operator_token = test_login("operator", "operator123")
    if operator_token:
        test_current_user(operator_token)
        test_projects(operator_token)
    
    auditor_token = test_login("auditor", "auditor123")
    if auditor_token:
        test_current_user(auditor_token)
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
