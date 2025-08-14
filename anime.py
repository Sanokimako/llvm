import requests
import re
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser

PORT = 8000
video_urls = []

def fetch_series_from_page(page_number):
    url = f"https://anifume.com/page/{page_number}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        html = response.text

        pattern = r'<a href="https://anifume\.com/(\d+)">(.*?)</a>'
        matches = re.findall(pattern, html)

        seen = set()
        series_list = []
        for anime_id, title in matches:
            if anime_id not in seen:
                seen.add(anime_id)
                series_list.append((anime_id, title))
                print(f"ID: {anime_id} | Title: {title}")
        return series_list

    except requests.RequestException as e:
        print(f"❌ Failed to fetch page: {e}")
        return []

def get_episode_links(series_url):
    response = requests.get(series_url)
    response.raise_for_status()
    html = response.text
    pattern = r'<div class="eplink"><a href="([^"]+)"'
    return re.findall(pattern, html)

def get_player_urls(page_url):
    response = requests.get(page_url)
    response.raise_for_status()
    html = response.text
    pattern = r'https://anifume\.com/player/[^\s"\'<>]+'
    return re.findall(pattern, html)

def get_video_files(player_url):
    response = requests.get(player_url)
    response.raise_for_status()
    html = response.text
    pattern = r'"file"\s*:\s*"([^"]+)"'
    return re.findall(pattern, html)

def parse_selection(selection_str, max_index):
    selection_str = selection_str.strip().lower()
    if selection_str == "all":
        return list(range(max_index))
    indices = set()
    for part in selection_str.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            if start.isdigit() and end.isdigit():
                indices.update(range(int(start)-1, int(end)))
        elif part.isdigit():
            indices.add(int(part)-1)
    return sorted(i for i in indices if 0 <= i < max_index)

class VideoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html = self.build_video_html()
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def build_video_html(self):
        unique_urls = list(dict.fromkeys(video_urls))
        videos_html = ""
        for idx, url in enumerate(unique_urls, 1):
            videos_html += f"""
                <div class="video-container" style="animation-delay: {idx * 0.2}s">
                    <div class="loader"></div>
                    <video controls style="display:none;">
                        <source src="{url}" type="video/mp4">
                        Your browser does not support the video tag.
                    </video>
                </div>
            """
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Anime Stream</title>
            <style>
                body {{
                    font-family: 'Segoe UI', sans-serif;
                    background: linear-gradient(to right, #1f1c2c, #928dab);
                    margin: 0;
                    padding: 20px;
                    color: #fff;
                }}
                .video-container {{
                    background: rgba(255, 255, 255, 0.05);
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px auto;
                    max-width: 800px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
                    animation: fadeInUp 1s ease forwards;
                    opacity: 0;
                    position: relative;
                }}
                video {{
                    width: 100%;
                    height: auto;
                    border-radius: 10px;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.3);
                }}
                .loader {{
                    border: 8px solid #f3f3f3;
                    border-top: 8px solid #3498db;
                    border-radius: 50%;
                    width: 50px;
                    height: 50px;
                    animation: spin 1s linear infinite;
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                }}
                @keyframes fadeInUp {{
                    from {{ opacity: 0; transform: translateY(40px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
            </style>
        </head>
        <body>
            {videos_html}
            <script>
                const containers = document.querySelectorAll('.video-container');
                containers.forEach(container => {{
                    const video = container.querySelector('video');
                    const loader = container.querySelector('.loader');
                    video.addEventListener('canplay', () => {{
                        loader.style.display = 'none';
                        video.style.display = 'block';
                    }});
                    video.load();
                }});
            </script>
        </body>
        </html>
        """

def start_server():
    httpd = HTTPServer(('localhost', PORT), VideoHandler)
    print(f"\n📺 Serving at http://localhost:{PORT}")
    httpd.serve_forever()

def select_episodes(series_id):
    series_url = f"https://anifume.com/{series_id}"
    while True:
        try:
            episode_links = get_episode_links(series_url)
            if not episode_links:
                print("❌ No episode links found.")
                return False
            print(f"✅ Found {len(episode_links)} episode(s):")
            for i, link in enumerate(episode_links, 1):
                print(f"{i}. {link}")

            selection = input("\n🎬 Which episodes? (e.g., 1,3,5-7 or 'all', or 'back' to choose anime again): ").strip().lower()
            if selection == "back":
                return False

            selected_indices = parse_selection(selection, len(episode_links))
            if not selected_indices:
                print("❌ No valid selections.")
                continue

            video_urls.clear()
            for idx in selected_indices:
                ep_link = episode_links[idx]
                print(f"\n▶️ Processing episode {idx+1}: {ep_link}")
                player_urls = get_player_urls(ep_link)
                if not player_urls:
                    print("  ⚠️ No player URLs found.")
                    continue

                player_url = player_urls[0]
                video_files = get_video_files(player_url)
                if video_files:
                    print(f"    ✅ Found video: {video_files[0]}")
                    video_urls.append(video_files[0])
                else:
                    print("    ⚠️ No video files found.")
                time.sleep(0.01)
            return True

        except requests.RequestException as e:
            print(f"❌ Request error: {e}")
            return False

if __name__ == "__main__":
    while True:
        page_input = input("📄 Page number to browse (e.g. 1, 2, 3): ").strip()
        if not page_input.isdigit():
            print("❌ Invalid input. Please enter a number.")
            continue

        print(f"\n🔍 Fetching anime list from page {page_input}...\n")
        series_list = fetch_series_from_page(page_input)
        if not series_list:
            print("❌ No series found.")
            continue

        while True:
            selected_id = input("\n🎯 Enter the anime ID to stream (or 'back' to pick another page): ").strip()
            if selected_id.lower() == "back":
                break
            if not selected_id.isdigit():
                print("❌ Invalid ID.")
                continue

            if select_episodes(selected_id):
                if video_urls:
                    threading.Thread(target=start_server, daemon=True).start()
                    webbrowser.open(f"http://localhost:{PORT}")
                    print("\n🌐 Browser opened — press Ctrl+C to stop the server.")
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        print("\n🛑 Server stopped.")
                        exit()
                else:
                    print("❌ No videos to stream.")
            # If select_episodes returned False, user typed 'back' to choose anime again
