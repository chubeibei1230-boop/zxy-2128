"""
预警闭环处置中心功能测试脚本
"""
import requests
import json

BASE_URL = 'http://localhost:8000/api'
TOKEN = None

def login(username='admin', password='admin123456'):
    """登录获取token"""
    global TOKEN
    url = f'{BASE_URL}/auth/login/'
    response = requests.post(url, data={
        'username': username,
        'password': password
    })
    if response.status_code == 200:
        TOKEN = response.json().get('token')
        print(f'登录成功，Token: {TOKEN}')
    else:
        print(f'登录失败: {response.text}')
    return TOKEN

def get_headers():
    """获取请求头"""
    return {'Authorization': f'Token {TOKEN}'} if TOKEN else {}

def test_warning_closure_center():
    """测试预警闭环处置中心概览"""
    print('\n=== 测试预警闭环处置中心概览 ===')
    url = f'{BASE_URL}/warning-closure-center/'
    response = requests.get(url, headers=get_headers())
    print(f'状态码: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f'错误: {response.text}')

def test_warning_list():
    """测试预警列表，获取一个待处理的预警"""
    print('\n=== 测试预警列表 ===')
    url = f'{BASE_URL}/material-warnings/'
    params = {'page_size': 20, 'status': 'pending'}
    response = requests.get(url, headers=get_headers(), params=params)
    print(f'状态码: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print(f'待处理预警总数: {data.get("count")}')
        results = data.get('results', [])
        if results:
            print(f'第一个待处理预警ID: {results[0]["id"]}')
            print(f'预警编号: {results[0]["warning_no"]}')
            print(f'预警类型: {results[0]["warning_type_display"]}')
            print(f'状态: {results[0]["status_display"]}')
            return results[0]["id"]
        else:
            # 如果没有待处理的，获取任意一个
            params = {'page_size': 5}
            response = requests.get(url, headers=get_headers(), params=params)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                if results:
                    print(f'使用任意预警ID: {results[0]["id"]}')
                    return results[0]["id"]
    else:
        print(f'错误: {response.text}')
    return None

def test_warning_detail(warning_id):
    """测试预警详情（闭环处置视图）"""
    print(f'\n=== 测试预警详情 ID={warning_id} ===')
    url = f'{BASE_URL}/material-warnings/{warning_id}/'
    response = requests.get(url, headers=get_headers())
    print(f'状态码: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print(f'预警编号: {data["warning_no"]}')
        print(f'预警类型: {data["warning_type_display"]}')
        print(f'状态: {data["status_display"]}')
        print(f'责任人: {data["responsible_person_name"]}')
        print(f'自动闭环检查: {data.get("auto_closure_check", {})}')
        process_logs = data.get("process_logs", [])
        print(f'处理轨迹数量: {len(process_logs)}')
        if process_logs:
            print('最近轨迹:')
            for log in process_logs[:3]:
                print(f'  - {log["action_display"]} - {log["created_at"]}')
    else:
        print(f'错误: {response.text}')

def test_assign_responsible(warning_id):
    """测试指派责任人"""
    print(f'\n=== 测试指派责任人 ID={warning_id} ===')
    
    users_url = f'{BASE_URL}/users/'
    users_resp = requests.get(users_url, headers=get_headers(), params={'page_size': 1})
    user_id = None
    if users_resp.status_code == 200 and users_resp.json().get('results'):
        user_id = users_resp.json()['results'][0]['id']
        print(f'选择用户ID: {user_id}')
    
    if user_id:
        url = f'{BASE_URL}/material-warnings/{warning_id}/assign/'
        data = {
            'responsible_person': user_id,
            'remark': '测试指派责任人'
        }
        response = requests.post(url, headers=get_headers(), json=data)
        print(f'状态码: {response.status_code}')
        if response.status_code == 200:
            result = response.json()
            print(f'指派成功，责任人: {result["responsible_person_name"]}')
        else:
            print(f'错误: {response.text}')

def test_start_processing(warning_id):
    """测试开始处理预警"""
    print(f'\n=== 测试开始处理预警 ID={warning_id} ===')
    url = f'{BASE_URL}/material-warnings/{warning_id}/start_processing/'
    data = {
        'handling_opinion': '开始处理此预警，安排补货'
    }
    response = requests.post(url, headers=get_headers(), json=data)
    print(f'状态码: {response.status_code}')
    if response.status_code == 200:
        result = response.json()
        print(f'处理成功，状态变为: {result["status_display"]}')
    else:
        print(f'错误: {response.text}')

def test_process_logs(warning_id):
    """测试获取处理轨迹"""
    print(f'\n=== 测试获取处理轨迹 ID={warning_id} ===')
    url = f'{BASE_URL}/material-warnings/{warning_id}/process_logs/'
    response = requests.get(url, headers=get_headers())
    print(f'状态码: {response.status_code}')
    if response.status_code == 200:
        logs = response.json()
        print(f'处理轨迹数量: {len(logs)}')
        for log in logs:
            print(f'  [{log["created_at"]}] {log["action_display"]}: {log.get("action_detail", "")}')
    else:
        print(f'错误: {response.text}')

def test_related_documents(warning_id):
    """测试获取关联单据"""
    print(f'\n=== 测试获取关联单据 ID={warning_id} ===')
    url = f'{BASE_URL}/material-warnings/{warning_id}/related_documents/'
    response = requests.get(url, headers=get_headers())
    print(f'状态码: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print(f'关联领用单: {data.get("related_usage")}')
        print(f'关联异常单: {data.get("related_exception")}')
        print(f'关联盘点单: {data.get("related_inventory_check")}')
        print(f'可选领用单数量: {len(data.get("available_usages", []))}')
        print(f'可选异常单数量: {len(data.get("available_exceptions", []))}')
        print(f'可选盘点单数量: {len(data.get("available_inventory_checks", []))}')
    else:
        print(f'错误: {response.text}')

def test_auto_closure_check():
    """测试自动闭环检测"""
    print('\n=== 测试自动闭环检测 ===')
    url = f'{BASE_URL}/material-warnings/auto_closure_check/'
    data = {
        'auto_execute': False
    }
    response = requests.post(url, headers=get_headers(), json=data)
    print(f'状态码: {response.status_code}')
    if response.status_code == 200:
        result = response.json()
        print(f'可自动闭环数量: {result.get("can_auto_close_count")}')
        print(f'需重新打开数量: {result.get("need_reopen_count")}')
    else:
        print(f'错误: {response.text}')

def test_warning_statistics():
    """测试预警统计"""
    print('\n=== 测试预警统计 ===')
    url = f'{BASE_URL}/material-warnings/statistics/'
    response = requests.get(url, headers=get_headers())
    print(f'状态码: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f'错误: {response.text}')

def main():
    print('预警闭环处置中心功能测试')
    print('=' * 50)
    
    # 登录
    if not login('admin', 'admin123456'):
        # 尝试其他常见账号
        login('operator', 'operator123')
    
    if not TOKEN:
        print('无法登录，请确保服务器运行且有可用账号')
        return
    
    # 测试预警闭环处置中心概览
    test_warning_closure_center()
    
    # 测试预警统计
    test_warning_statistics()
    
    # 获取预警列表
    warning_id = test_warning_list()
    
    if warning_id:
        # 测试预警详情
        test_warning_detail(warning_id)
        
        # 测试指派责任人
        test_assign_responsible(warning_id)
        
        # 测试开始处理
        test_start_processing(warning_id)
        
        # 测试处理轨迹
        test_process_logs(warning_id)
        
        # 测试关联单据
        test_related_documents(warning_id)
        
        # 再次查看详情
        test_warning_detail(warning_id)
    
    # 测试自动闭环检测
    test_auto_closure_check()
    
    print('\n' + '=' * 50)
    print('测试完成！')

if __name__ == '__main__':
    main()
