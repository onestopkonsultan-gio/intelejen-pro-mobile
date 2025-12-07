import streamlit as st
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import google.generativeai as genai
from PIL import Image
from io import BytesIO
from datetime import datetime, timedelta, timezone
import pandas as pd
import isodate
import json
import os
import re
import requests
from collections import Counter

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="Intelejen Pro V9.6 - Final", layout="wide", page_icon="📱")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 50px; }
    h1 { color: #00ff88; } 
    .gap-box { border: 2px dashed #00ff88; background-color: #0d1f14; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; }
    .spy-section { border-left: 5px solid #d900ff; padding-left: 10px; margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("📱 INTELEJEN PRO V9.6")
st.markdown("**Hunter + Unicorn + Oracle + Spy Glass (Updated Libs).**")

# ==========================================
# 2. SISTEM API KEY (SESSION STATE)
# ==========================================
if 'api_key_session' not in st.session_state:
    st.session_state['api_key_session'] = ''

st.sidebar.header("🎛️ Pusat Kontrol")
input_key = st.sidebar.text_input("API Key YouTube", type="password", value=st.session_state['api_key_session'])

if input_key:
    st.session_state['api_key_session'] = input_key
    st.sidebar.success("✅ API Key Terhubung")
else:
    st.sidebar.warning("⚠️ Masukkan API Key Dulu")

api_key_to_use = st.session_state['api_key_session']

# ==========================================
# 3. FUNGSI HELPER
# ==========================================
RPM_RATES = {'🇺🇸 English (Global/US)': 5.00, '🇮🇩 Indonesia': 0.30, '🏳️ Lainnya': 0.50}

def parse_duration(pt_string):
    try: return isodate.parse_duration(pt_string).total_seconds()
    except: return 0

def format_duration(seconds):
    m, s = divmod(seconds, 60); h, m = divmod(m, 60)
    if h > 0: return f"{int(h)}j {int(m)}m {int(s)}d"
    return f"{int(m)}m {int(s)}d"

def sanitize_filename(name): return re.sub(r'[\\/*?:"<>|]', "", name)[:50]

def get_youtube_autocomplete(query):
    try:
        r = requests.get(f"http://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={query}")
        return [i[0] for i in json.loads(r.text[r.text.find('['):r.text.rfind(']')+1])[1]]
    except: return []

# ==========================================
# 4. LOGIKA MODUL (RINGKAS)
# ==========================================

# --- HUNTER ---
def cari_data_hunter_pro(key, query, min_s, max_s, umur_range, c_type):
    try: youtube = build('youtube', 'v3', developerKey=key)
    except: return []
    pub_after = (datetime.now(timezone.utc) - timedelta(days=umur_range[1])).isoformat()
    q_list = [query] if query != "TRENDING_AUTO" else ["Vlog", "Gaming", "Tutorial", "Horor"]
    results = []
    
    with st.status("📡 Radar Hunter...", expanded=True):
        for q in q_list:
            try:
                res = youtube.search().list(q=q, part='snippet', type='video', order='viewCount', publishedAfter=pub_after, maxResults=50).execute()
                c_ids = [i['snippet']['channelId'] for i in res.get('items', [])]
                # Batch Channel
                for i in range(0, len(c_ids), 50):
                    batch = c_ids[i:i+50]
                    ch_res = youtube.channels().list(part='snippet,statistics,contentDetails', id=','.join(batch)).execute()
                    for ch in ch_res.get('items', []):
                        subs = int(ch['statistics'].get('subscriberCount', 0))
                        pub = datetime.fromisoformat(ch['snippet']['publishedAt'].replace('Z', '+00:00'))
                        umur = (datetime.now(timezone.utc) - pub).days
                        if min_s <= subs <= max_s and umur_range[0] <= umur <= umur_range[1]:
                            logo = ch['snippet']['thumbnails']['default']['url']
                            results.append({'Channel': ch['snippet']['title'], 'Subs': subs, 'Umur (Hari)': umur, 'Link': f"https://youtube.com/channel/{ch['id']}", 'Logo': logo})
            except: pass
    return results

# --- UNICORN ---
def find_unicorns(key, niche, min_views, max_days):
    youtube = build('youtube', 'v3', developerKey=key)
    pub_after = (datetime.now(timezone.utc) - timedelta(days=max_days)).isoformat()
    unicorns = []
    with st.status("🦄 Berburu Unicorn...", expanded=True):
        search = youtube.search().list(q=niche, part='snippet', type='video', order='viewCount', publishedAfter=pub_after, maxResults=50).execute()
        v_ids = [i['id']['videoId'] for i in search.get('items', [])]
        c_ids = [i['snippet']['channelId'] for i in search.get('items', [])]
        
        # Batch Stats
        v_stats = youtube.videos().list(part='statistics,snippet', id=','.join(v_ids)).execute()
        c_stats = {}
        unique_c = list(set(c_ids))
        for i in range(0, len(unique_c), 50):
            batch = unique_c[i:i+50]
            cr = youtube.channels().list(part='statistics', id=','.join(batch)).execute()
            for item in cr.get('items', []): c_stats[item['id']] = int(item['statistics'].get('subscriberCount', 0))
            
        for v in v_stats.get('items', []):
            cid = v['snippet']['channelId']
            subs = c_stats.get(cid, 0)
            views = int(v['statistics'].get('viewCount', 0))
            ratio = views/subs if subs > 0 else 0
            if (subs < 10000 and views > 50000) or ratio > 5.0:
                unicorns.append({'Judul': v['snippet']['title'], 'Channel': v['snippet']['channelTitle'], 'Views': views, 'Subs': subs, 'Rasio': round(ratio,1), 'Link': f"https://youtu.be/{v['id']}", 'Thumbnail': v['snippet']['thumbnails']['default']['url']})
    return unicorns

# --- ORACLE ---
def analyze_oracle_pro(key, keyword):
    youtube = build('youtube', 'v3', developerKey=key)
    with st.spinner("🔮 Oracle Ramal..."):
        s = youtube.search().list(q=keyword, part='id,snippet', type='video', maxResults=50, order='relevance').execute()
        vids = [i['id']['videoId'] for i in s.get('items', [])]
        if not vids: return None
        stats = youtube.videos().list(part='statistics,snippet,contentDetails', id=','.join(vids)).execute()
        
        views = []; titles = []; durs = []; total_vpd = 0
        for v in stats.get('items', []):
            vw = int(v['statistics'].get('viewCount', 0)); views.append(vw); titles.append(v['snippet']['title'])
            pub = datetime.fromisoformat(v['snippet']['publishedAt'].replace('Z', '+00:00'))
            age = max(1, (datetime.now(timezone.utc) - pub).days)
            total_vpd += vw/age
            d = parse_duration(v['contentDetails']['duration'])
            if d > 59: durs.append(d)
            
        avg_v = int(sum(views)/len(views)); comp = int((sum(1 for t in titles if keyword.lower() in t.lower())/len(views))*100)
        is_gap = avg_v > 200000 and comp < 10
        score = 100 if is_gap else max(0, min(100, (min(sorted(views)[len(views)//2], 1000000)/10000) - (comp*0.5)))
        
        return {'score': int(score), 'is_gap': is_gap, 'gap_msg': f"Views Besar ({avg_v:,}) tapi Judul Sama 0%", 'volume': int(total_vpd*30), 'avg_views': avg_v, 'comp': f"{comp}%", 'ideal_duration': format_duration(sum(durs)/len(durs) if durs else 0)}

# --- SPY GLASS & AI (V9.6 FIXED) ---
def get_channel_id(youtube, url):
    if "/channel/" in url: return url.split("/channel/")[1].split("/")[0]
    if "@" in url: 
        r = youtube.search().list(part='snippet', q=url.split("/")[-1], type='channel', maxResults=1).execute()
        return r['items'][0]['id']['channelId'] if r['items'] else None
    return None

def scrape_spy(api_key, url, limit):
    try: youtube = build('youtube', 'v3', developerKey=api_key)
    except: return [], ""
    cid = get_channel_id(youtube, url)
    if not cid: st.error("Channel not found"); return [], ""
    
    ch = youtube.channels().list(part='contentDetails,snippet', id=cid).execute()
    uploads = ch['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    name = ch['items'][0]['snippet']['title']
    
    res = []
    pl = youtube.playlistItems().list(part='contentDetails', playlistId=uploads, maxResults=limit).execute()
    ids = [i['contentDetails']['videoId'] for i in pl['items']]
    v_res = youtube.videos().list(part='snippet,statistics', id=','.join(ids)).execute()
    
    for v in v_res['items']:
        thumb = v['snippet']['thumbnails'].get('maxres', v['snippet']['thumbnails']['high'])['url']
        res.append({'Judul': v['snippet']['title'], 'Views': int(v['statistics'].get('viewCount', 0)), 'Link Video': f"https://youtu.be/{v['id']}", 'Thumbnail Link': thumb})
    return res, name

def reverse_engineer_prompt(api_key, img_url, title):
    # PENGATURAN AI TERBARU (V9.6)
    genai.configure(api_key=api_key)
    
    try:
        # Kita gunakan model 'gemini-1.5-flash' yang didukung library baru
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        img_data = requests.get(img_url).content
        img = Image.open(BytesIO(img_data))
        
        prompt = f"""Analyze thumbnail & title: '{title}'. 
        1. Visual Prompt (Midjourney Style). 
        2. Audio Prompt (Suno AI Style)."""
        
        response = model.generate_content([prompt, img])
        return response.text
    except Exception as e:
        return f"Error AI: {e}. \n\nSOLUSI: Pastikan file 'requirements.txt' di GitHub sudah diupdate ke 'google-generativeai>=0.8.3'"

# ==========================================
# 5. UI UTAMA
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["📡 HUNTER", "🦄 UNICORN", "🔮 ORACLE", "🕵️‍♀️ SPY GLASS"])

with tab1:
    if st.button("🚀 SCAN"):
        d = cari_data_hunter_pro(api_key_to_use, "Alur Cerita Film", 500, 50000, (1,60), "Campuran")
        st.dataframe(pd.DataFrame(d), hide_index=True)

with tab2:
    if st.button("🦄 BURU"):
        d = find_unicorns(api_key_to_use, "Minecraft Indonesia", 10000, 30)
        st.dataframe(pd.DataFrame(d), hide_index=True)

with tab3:
    kw = st.text_input("Kata Kunci", "Sholawat Merdu")
    if st.button("🔮 RAMAL"):
        r = analyze_oracle_pro(api_key_to_use, kw)
        if r:
            if r['is_gap']: st.success(f"💎 GOLDEN GAP! {r['gap_msg']}")
            c1, c2 = st.columns(2)
            c1.metric("Skor", r['score']); c2.metric("Durasi", r['ideal_duration'])

with tab4:
    url = st.text_input("Link Channel")
    if st.button("🚀 SPY"):
        d, name = scrape_spy(api_key_to_use, url, 10)
        st.session_state['spy_data'] = d
        st.dataframe(pd.DataFrame(d), hide_index=True)
        
    if 'spy_data' in st.session_state and st.session_state['spy_data']:
        st.markdown("---")
        st.markdown("### 🧪 AI Prompt Lab")
        sel = st.selectbox("Pilih Video", [v['Judul'] for v in st.session_state['spy_data']])
        v = next((x for x in st.session_state['spy_data'] if x['Judul'] == sel), None)
        if st.button("🧬 BEDAH PROMPT"):
            res = reverse_engineer_prompt(api_key_to_use, v['Thumbnail Link'], v['Judul'])
            st.text_area("Hasil:", res, height=300)
