import requests
import json
import datetime
from urllib.parse import urlencode

# ================= 配置区 =================
FOLO_COOKIE = '_ga=GA1.1.1065032222.1765972037; __Secure-better-auth.session_token=Tm8GbaPfpjm76RdIfisLzH9fDCZXmtui.WMHV0N8Zl4g5QZcusOcPPrgMiYEOM42NUSIuMuYIoG4%3D; better-auth.last_used_login_method=google; _ga_DZMBZBW3EC=GS2.1.s1766148703$o5$g0$t1766148703$j60$l0$h0$dkQvIXXsKrhPb70OcEyGDXV57OjqJ1j9j8A; ph_phc_EZGEvBt830JgBHTiwpHqJAEbWnbv63m5UpreojwEWNL_posthog=%7B%22distinct_id%22%3A%22224082579282124800%22%2C%22%24sesid%22%3A%5B1766151439162%2C%22019b36aa-6466-7704-a3df-773ccc4c93b8%22%2C1766148695141%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22https%3A%2F%2Fgithub.com%2Fjustlovemaki%2FCloudFlare-AI-Insight-Daily%22%2C%22u%22%3A%22https%3A%2F%2Fapp.folo.is%2F%22%7D%7D'

HEADERS_FOLO = {
    'Cookie': FOLO_COOKIE,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://app.folo.is/',
    'Origin': 'https://app.folo.is',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

HEADERS_GITHUB = {
    'User-Agent': 'python-requests/n8n-debugger'
}

# ================= 任务定义 =================
tasks = [
    {
        'name': 'GitHub Trending',
        'url': f"https://api.github.com/search/repositories?q=created:>{(datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')}&sort=stars&order=desc&per_page=10",
        'method': 'GET',
        'type': 'project',
        'headers': HEADERS_GITHUB,
        'body': None
    },
    {
        'name': 'News Aggregator',
        'url': 'https://api.follow.is/entries',
        'method': 'POST',
        'type': 'news',
        'headers': HEADERS_FOLO,
        'body': {"listId": "158437828119024640", "view": 1, "withContent": True}
    },
    {
        'name': 'HGPapers',
        'url': 'https://api.follow.is/entries',
        'method': 'POST',
        'type': 'paper',
        'headers': HEADERS_FOLO,
        'body': {"listId": "158437917409783808", "view": 1, "withContent": True}
    },
    {
        'name': 'Twitter',
        'url': 'https://api.follow.is/entries',
        'method': 'POST',
        'type': 'socialMedia',
        'headers': HEADERS_FOLO,
        'body': {"listId": "153028784690326528", "view": 1, "withContent": True}
    },
    {
        'name': 'Reddit',
        'url': 'https://api.follow.is/entries',
        'method': 'POST',
        'type': 'socialMedia',
        'headers': HEADERS_FOLO,
        'body': {"listId": "167576006499975168", "view": 1, "withContent": True}
    }
]

# ================= 执行抓取 =================
def run_fetch():
    all_results = []
    print(f"🚀 开始执行抓取任务 (GitHub: GET, Folo: POST)...\n")

    for task in tasks:
        print(f"📡 正在抓取: {task['name']} [{task['method']}]")
        try:
            if task['method'] == 'GET':
                resp = requests.get(task['url'], headers=task['headers'], timeout=15)
            else:
                resp = requests.post(task['url'], headers=task['headers'], json=task['body'], timeout=15)
            
            if resp.status_code != 200:
                print(f"   ❌ 失败 (Status: {resp.status_code}): {resp.text[:100]}")
                continue
                
            data = resp.json()
            items_found = 0

            # 1. GitHub 处理
            if task['name'] == 'GitHub Trending' and 'items' in data:
                for repo in data['items']:
                    all_results.append({
                        'title': repo.get('full_name'),
                        'url': repo.get('html_url'),
                        'desc': repo.get('description'),
                        'source': 'GitHub',
                        'tag': '🛠️ Project',
                        'stars': f"⭐ {repo.get('stargazers_count')}"
                    })
                    items_found += 1

            # 2. Folo 处理
            elif 'data' in data and isinstance(data['data'], list):
                for item in data['data']:
                    # Folo 返回的数据通常包裹在 'entries' 对象里，或者直接在 items 里
                    # 这里做一个兼容性尝试
                    entry = item.get('entries') or item
                    
                    all_results.append({
                        'title': entry.get('title', 'No Title'),
                        'url': entry.get('url', '#'),
                        'desc': (entry.get('content') or entry.get('contentSnippet') or '')[:200],
                        'source': task['name'],
                        'tag': '📄 Paper' if task['type'] == 'paper' else '📰 News'
                    })
                    items_found += 1
            
            print(f"   ✅ 成功抓取 {items_found} 条数据")

        except Exception as e:
            print(f"   ❌ 异常: {e}")

    # 输出结果
    final_output = {
        "selectedItems": all_results[:50],
        "date": datetime.datetime.now().strftime('%Y-%m-%d')
    }
    print("\n" + "="*20 + " Final JSON Output " + "="*20)
    print(json.dumps(final_output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    run_fetch()