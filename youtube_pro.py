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
# 1. KONFIGURASI HALAMAN & CSS
# ==========================================
st.set_page_config(page_title="Intelejen Pro V9.3 - Anti 404", layout="wide", page_icon="📱")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 50px; }
    .metric-card { background-color: #1e1e1e; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    h1 { color: #00ff88; } 
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.0rem; font-weight: bold;
    }
    .gap-box {
        border: 2px dashed #00ff88; background-color: #0d1f14;
        padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px;
    }
    .spy-section { border-left: 5px solid #d900ff; padding-left: 10px; margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("📱 INTELEJEN PRO V9.3")
st.markdown("**Hunter + Unicorn + Oracle + Spy Glass (Multi-Model Support).**")

# ==========================================
# 2. SISTEM API KEY
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
# 3. FUNGSI HELPER (GLOBAL)
# ==========================================
RPM_RATES = {
    '🇺🇸 English (Global/US)': 5.00, '🇷🇺 Russian': 1.20,
    '🇪🇸/🇲🇽 Spanish (Latam)': 1.50, '🇧🇷 Portuguese (Brazil)': 1.10,
    '🇮🇩 Indonesia': 0.30, '🏳️ Lainnya/Unknown': 0.50
}

def parse_duration(pt_string):
    try: return isodate.parse_duration(pt_string).total_seconds()
    except: return 0

def format_duration(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{int(h)}j {int(m)}m {int(s)}d"
    return f"{int(m)} menit {int(s)} detik"

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)[:50]

def detect_language(text):
    text = text.lower()
    if any(w in text for w in ['yang', 'dan', 'ini', 'aku', 'bang', 'kak']): return '🇮🇩 Indonesia'
    if any(w in text for w in ['the', 'is', 'and', 'that', 'this', 'awesome']): return '🇺🇸 English (Global/US)'
    if any(w in text for w in ['de', 'la', 'que', 'el', 'en', 'muy']): return '🇪🇸/🇲🇽 Spanish (Latam)'
    return '🏳️ Lainnya/Unknown'

def get_youtube_autocomplete(query):
    url = f"http://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={query}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            text = response.text
            start = text.find('[')
            end = text.rfind(']') + 1
            if start != -1 and end != -1:
                data = json.loads(text[start:end])
                return [item[0] for item in data[1]]
    except: return []
    return []

# ==========================================
# 4. LOGIKA MODUL: HUNTER, UNICORN, ORACLE
# ==========================================

# --- A. HUNTER LOGIC ---
def cek_tipe_konten(youtube, uploads_playlist_id):
    try:
        playlist_items = youtube.playlistItems().list(part='contentDetails', playlistId=uploads_playlist_id, maxResults=10).execute()
        video_ids = [item['contentDetails']['videoId'] for item in playlist_items.get('items', [])]
        if not video_ids: return "Kosong"
        videos_response = youtube.videos().list(part='contentDetails', id=','.join(video_ids)).execute()
        short_count = 0; long_count = 0
        for video in videos_response.get('items', []):
            dur = parse_duration(video['contentDetails']['duration'])
            if dur <= 60: short_count += 1
            else: long_count += 1
        if short_count > long_count * 2: return "Full Shorts"
        elif long_count > short_count * 2: return "Full Long Video"
        else: return "Campuran"
    except: return "Unknown"

def cari_data_hunter_pro(key, query, min_s, max_s, umur_range, c_type):
    try: youtube = build('youtube', 'v3', developerKey=key)
    except: return []
    pub_after = (datetime.now(timezone.utc) - timedelta(days=umur_range[1])).isoformat()
    target_queries = [query] if query != "TRENDING_AUTO" else ["Skibidi", "Minecraft 2025", "Vlog Desa", "Horor", "Crypto"]
    potential_channels = {}; results = []
    
    with st.status("📡 Radar Hunter bekerja...", expanded=True) as status:
        for q in target_queries:
            st.write(f"Scanning: {q}...")
            next_page = None
            for _ in range(2): 
                try:
                    req = youtube.search().list(q=q, part='snippet', type='video', order='viewCount', publishedAfter=pub_after, maxResults=50, pageToken=next_page)
                    res = req.execute()
                    for item in res.get('items', []): potential_channels[item['snippet']['channelId']] = {'title': item['snippet']['channelTitle']}
                    next_page = res.get('nextPageToken')
                    if not next_page: break
                except: break
        
        c_ids = list(potential_channels.keys())
        prog = st.progress(0); processed = 0
        for i in range(0, len(c_ids), 50):
            batch = c_ids[i:i+50]
            try:
                ch_res = youtube.channels().list(part='snippet,statistics,contentDetails', id=','.join(batch)).execute()
                for ch in ch_res.get('items', []):
                    subs = int(ch['statistics'].get('subscriberCount', 0))
                    vid_count = int(ch['statistics'].get('videoCount', 0))
                    pub = datetime.fromisoformat(ch['snippet']['publishedAt'].replace('Z', '+00:00'))
                    umur = (datetime.now(timezone.utc) - pub).days
                    if min_s <= subs <= max_s and umur_range[0] <= umur <= umur_range[1]:
                        uploads = ch['contentDetails']['relatedPlaylists']['uploads']
                        jenis = cek_tipe_konten(youtube, uploads)
                        if c_type != "Campuran" and jenis != c_type: continue
                        country = ch['snippet'].get('country', 'N/A')
                        country_disp = "🇮🇩 INDONESIA" if country == 'ID' else f"🌍 {country}"
                        daily_uploads = vid_count / umur if umur > 0 else 0
                        act = "🤖 BOT/VPS" if daily_uploads >= 5 else "👤 Normal"
                        daily_growth = subs / umur if umur > 0 else 0
                        score = "🔥🔥🔥 VIRAL" if daily_growth > 50 else "🔥 Normal"
                        results.append({'Channel': ch['snippet']['title'], 'Negara': country_disp, 'Subs': subs, 'Umur (Hari)': umur, 'Tipe': jenis, 'Activity': act, 'Status': score, 'Link': f"https://www.youtube.com/channel/{ch['id']}", 'Logo': ch['snippet']['thumbnails']['default']['url']})
            except: pass
            processed += len(batch); prog.progress(min(int(processed/len(c_ids)*100), 100))
        status.update(label="Selesai!", state="complete", expanded=False)
    return results

# --- B. UNICORN LOGIC ---
def find_unicorns(key, niche, min_views, max_days):
    youtube = build('youtube', 'v3', developerKey=key)
    pub_after = (datetime.now(timezone.utc) - timedelta(days=max_days)).isoformat()
    unicorns = []
    with st.status("🦄 Berburu Unicorn...", expanded=True):
        search_res = youtube.search().list(q=niche, part='snippet', type='video', order='viewCount', publishedAfter=pub_after, maxResults=50).execute()
        video_ids = [item['id']['videoId'] for item in search_res.get('items', [])]
        channel_ids = [item['snippet']['channelId'] for item in search_res.get('items', [])]
        vid_res = youtube.videos().list(part='statistics,snippet', id=','.join(video_ids)).execute()
        
        unique_ch_ids = list(set(channel_ids))
        ch_stats_map = {}
        for i in range(0, len(unique_ch_ids), 50):
            batch = unique_ch_ids[i:i+50]
            ch_res = youtube.channels().list(part='statistics', id=','.join(batch)).execute()
            for item in ch_res.get('items', []): ch_stats_map[item['id']] = int(item['statistics'].get('subscriberCount', 0))

        for vid in vid_res.get('items', []):
            ch_id = vid['snippet']['channelId']
            subs = ch_stats_map.get(ch_id, 0)
            views = int(vid['statistics'].get('viewCount', 0))
            ratio = views / subs if subs > 0 else 0
            is_unicorn = False; label = ""
            if subs < 10000 and views > 50000: is_unicorn = True; label = "🦄 BABY UNICORN"
            elif ratio > 5.0: is_unicorn = True; label = "🔥 VIRAL MONSTER"
            elif ratio > 2.0 and views > min_views: is_unicorn = True; label = "✨ HIDDEN GEM"
            if is_unicorn:
                unicorns.append({'Judul': vid['snippet']['title'], 'Channel': vid['snippet']['channelTitle'], 'Label': label, 'Views': views, 'Subs': subs, 'Rasio': round(ratio, 1), 'Link': f"https://youtu.be/{vid['id']}", 'Thumbnail': vid['snippet']['thumbnails']['default']['url']})
    return unicorns

# --- C. ORACLE LOGIC (GAP HUNTER) ---
def analyze_oracle_pro(key, keyword):
    youtube = build('youtube', 'v3', developerKey=key)
    with st.spinner("🔮 Oracle mencari Golden Gap..."):
        search_res = youtube.search().list(q=keyword, part='id,snippet', type='video', maxResults=50, order='relevance').execute()
        items = search_res.get('items', [])
        if not items: return None
        vid_ids = [x['id']['videoId'] for x in items]
        stats_res = youtube.videos().list(part='statistics,snippet,contentDetails', id=','.join(vid_ids)).execute()
        
        views_list = []; titles = []; durations = []; total_vpd = 0
        for vid in stats_res.get('items', []):
            v = int(vid['statistics'].get('viewCount', 0))
            views_list.append(v); titles.append(vid['snippet']['title'])
            pub = datetime.fromisoformat(vid['snippet']['publishedAt'].replace('Z', '+00:00'))
            age = max(1, (datetime.now(timezone.utc) - pub).days)
            total_vpd += (v / age)
            dur = parse_duration(vid['contentDetails']['duration'])
            if dur > 59: durations.append(dur)

        avg_vpd = total_vpd / len(items); monthly_vol = avg_vpd * 30
        avg_views = int(sum(views_list)/len(views_list))
        exact_match = sum(1 for t in titles if keyword.lower() in t.lower())
        comp_score = (exact_match / len(items)) * 100 
        median_views = sorted(views_list)[len(views_list)//2] if views_list else 0
        
        # GAP HUNTER LOGIC
        base_score = max(0, min(100, (min(median_views, 1000000)/10000) - (comp_score * 0.5)))
        is_golden_gap = False; gap_msg = ""
        if avg_views > 200000 and comp_score < 10:
            is_golden_gap = True; base_score = 100
            verdict = "💎 GOLDEN GAP"; color = "#00ff88"
            gap_msg = f"Anomali: Views Raksasa ({avg_views:,}) tapi Judul Sama 0%. CELAH EMAS!"
        else:
            verdict = "💎 VERY HIGH" if base_score >= 75 else "✅ GOOD" if base_score >= 50 else "⚖️ FAIR" if base_score >= 25 else "⛔ POOR"
            color = "#00ff88" if base_score >= 75 else "#ffd700" if base_score >= 50 else "#ffaa00" if base_score >= 25 else "#ff4b4b"

        avg_dur = sum(durations) / len(durations) if durations else 0
        arus_stat = "🌊 BADAI" if monthly_vol > 1000000 else "🚤 KUAT" if monthly_vol > 100000 else "🚣 TENANG"
        arus_col = "#00ff88" if monthly_vol > 1000000 else "#ffd700" if monthly_vol > 100000 else "#ff4b4b"

        return {'score': int(base_score), 'verdict': verdict, 'color': color, 'is_gap': is_golden_gap, 'gap_msg': gap_msg, 'volume': int(monthly_vol), 'arus_stat': arus_stat, 'arus_col': arus_col, 'avg_views': avg_views, 'comp': f"{int(comp_score)}%", 'ideal_duration': format_duration(avg_dur), 'titles': titles[:5]}

# ==========================================
# 5. LOGIKA MODUL: SPY GLASS (V6 MERGED)
# ==========================================

# --- Smart Link Parser ---
def get_channel_id_smart(youtube, url):
    url = url.strip()
    if url.startswith("UC") and len(url) == 24: return url
    if "/channel/" in url:
        try: return url.split("/channel/")[1].split("/")[0].split("?")[0]
        except: pass
    handle = ""
    if "@" in url: handle = url.split("@")[-1].split("/")[0]
    elif "/c/" in url: handle = url.split("/c/")[1].split("/")[0]
    elif "/user/" in url: handle = url.split("/user/")[1].split("/")[0]
    if handle:
        try:
            res = youtube.search().list(part='snippet', q=f"@{handle}", type='channel', maxResults=1).execute()
            if res['items']: return res['items'][0]['id']['channelId']
        except: pass
    try:
        res = youtube.search().list(part='snippet', q=url, type='channel', maxResults=1).execute()
        if res['items']: return res['items'][0]['id']['channelId']
    except: pass
    return None

# --- Asset Downloaders (Modified for Cloud) ---
def download_assets(video_data, channel_name):
    st.info("ℹ️ Di Versi Android/Cloud, file tidak bisa didownload sebagai ZIP. Silakan COPY teks di bawah ini.")
    result_text = f"=== DOWNLOAD ASSET: {channel_name} ===\n\n"
    for vid in video_data:
        result_text += f"VIDEO: {vid['Judul']}\n"
        result_text += f"THUMBNAIL URL: {vid['Thumbnail Link']}\n"
        result_text += f"LINK: {vid['Link Video']}\n"
        result_text += "-"*30 + "\n"
    return result_text

def download_metadata(video_data, channel_name):
    st.info("ℹ️ Silakan COPY data SEO di bawah ini:")
    result_text = f"=== SEO REPORT: {channel_name} ===\n\n"
    for vid in video_data:
        tags = ", ".join(vid['Tags']) if vid['Tags'] else "No Tags"
        hashtags = " ".join([f"#{h}" for h in vid['Hashtags']]) if vid['Hashtags'] else "No Hash"
        result_text += f"JUDUL: {vid['Judul']}\nTAGS: {tags}\nHASHTAGS: {hashtags}\n\n"
    return result_text

def calculate_revenue(total_views, lang_percentages):
    if not lang_percentages: return 0, 0
    weighted = sum([RPM_RATES.get(l, 0.50) * (p/100) for l, p in lang_percentages.items()])
    return weighted, (total_views/1000)*weighted

# --- AI Reverse Engineer (FIXED: MULTI-MODEL SUPPORT) ---
def reverse_engineer_prompt(api_key, img_url, title):
    genai.configure(api_key=api_key)
    
    # DAFTAR MODEL YANG AKAN DICOBA SATU PER SATU
    models_to_try = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro-vision']
    
    # Download Gambar sekali saja
    try:
        img_data = requests.get(img_url).content
        img = Image.open(BytesIO(img_data))
    except Exception as e:
        return f"Gagal mengambil gambar thumbnail. Error: {e}"

    prompt = f"""Analyze thumbnail & title: '{title}'. 
    Task 1: Reverse engineer Midjourney prompt (Subject, Style, Mood, Lighting). 
    Task 2: Guess audio genre for Suno AI prompt (Genre, BPM, Instruments). 
    Output: [VISUAL PROMPT] ... [AUDIO PROMPT] ..."""

    # LOOPING COBA MODEL
    last_error = ""
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([prompt, img])
            return response.text # Jika sukses, langsung kembali
        except Exception as e:
            last_error = str(e)
            continue # Jika gagal, lanjut ke model berikutnya
            
    return f"Gagal Bedah Prompt. Semua model menolak akses. Error terakhir: {last_error}"

# --- Spy Scraper ---
def scrape_spy(api_key, url, limit):
    try: youtube = build('youtube', 'v3', developerKey=api_key)
    except: return [], {}, ""
    cid = get_channel_id_smart(youtube, url)
    if not cid: st.error("Channel not found"); return [], {}, ""
    
    try:
        ch = youtube.channels().list(part='contentDetails,snippet', id=cid).execute()
        uploads = ch['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        name = ch['items'][0]['snippet']['title']
    except: return [], {}, ""
    
    vids_data = []; all_langs = []; next_p = None
    with st.status("🕵️‍♀️ Membedah Kompetitor...", expanded=True):
        while len(vids_data) < limit:
            try:
                pl = youtube.playlistItems().list(part='contentDetails', playlistId=uploads, maxResults=50, pageToken=next_p).execute()
                ids = [i['contentDetails']['videoId'] for i in pl['items']]
                if not ids: break
                vres = youtube.videos().list(part='snippet,statistics', id=','.join(ids)).execute()
                for v in vres['items']:
                    snip = v['snippet']; stats = v['statistics']; vid = v['id']
                    # Metadata
                    tags = snip.get('tags', []); desc = snip.get('description', ''); hashtags = re.findall(r"#(\w+)", desc)
                    # Comments Lang
                    try:
                        cres = youtube.commentThreads().list(part="snippet", videoId=vid, maxResults=5, order="relevance").execute()
                        clist = []
                        for c in cres.get('items', []):
                            txt = c['snippet']['topLevelComment']['snippet']['textDisplay']
                            clean = re.sub(r'<.*?>', '', txt)
                            l = detect_language(clean); all_langs.append(l); clist.append(f"{clean[:30]}...")
                        s_comm = " | ".join(clist[:3])
                    except: s_comm = "NA"
                    thumb = snip['thumbnails'].get('maxres', snip['thumbnails'].get('high', snip['thumbnails']['default']))['url']
                    vids_data.append({'ID': vid, 'Judul': snip['title'], 'Views': int(stats.get('viewCount', 0)), 'Sampel Komentar': s_comm, 'Link Video': f"https://youtu.be/{vid}", 'Thumbnail Link': thumb, 'Tags': tags, 'Hashtags': hashtags})
                    if len(vids_data) >= limit: break
                next_p = pl.get('nextPageToken')
                if not next_p: break
            except: break
    
    cnt = Counter(all_langs); tot = sum(cnt.values())
    l_stats = {l: (c/tot)*100 for l, c in cnt.most_common()} if tot > 0 else {}
    return vids_data, l_stats, name

# ==========================================
# 6. UI UTAMA (TABBED)
# ==========================================

tab1, tab2, tab3, tab4 = st.tabs(["📡 CHANNEL HUNTER", "🦄 UNICORN CATCHER", "🔮 KEYWORD ORACLE", "🕵️‍♀️ SPY GLASS"])

# === TAB 1: HUNTER ===
with tab1:
    st.subheader("Pencari Channel Viral")
    c1, c2 = st.columns(2)
    mode = c1.radio("Mode:", ["Manual Niche", "Auto Trending"])
    niche = c2.text_input("Niche", "Alur Cerita Film") if mode == "Manual Niche" else "TRENDING_AUTO"
    colA, colB, colC = st.columns(3)
    min_sub = colA.number_input("Min Subs", 500); max_sub = colB.number_input("Max Subs", 50000); umur = colC.slider("Umur (Hari)", 1, 120, (1, 60))
    tipe = st.selectbox("Tipe Konten", ["Campuran", "Full Shorts", "Full Long Video"])
    
    if st.button("🚀 SCAN CHANNEL", key="hunt_btn"):
        if api_key_to_use:
            d = cari_data_hunter_pro(api_key_to_use, niche, min_sub, max_sub, umur, tipe)
            if d:
                df = pd.DataFrame(d).sort_values(by='Subs', ascending=False)
                st.success(f"Ditemukan {len(df)} Channel!")
                st.dataframe(df, column_config={"Logo": st.column_config.ImageColumn("Logo"), "Link": st.column_config.LinkColumn("Link")}, hide_index=True)

# === TAB 2: UNICORN ===
with tab2:
    st.subheader("🦄 Unicorn Video Hunter")
    u_c1, u_c2 = st.columns(2)
    u_niche = u_c1.text_input("Niche", "Minecraft Indonesia", key="uni_kw")
    u_days = u_c2.slider("Hari Terakhir", 7, 90, 30)
    if st.button("🦄 BURU UNICORN"):
        if api_key_to_use:
            uni = find_unicorns(api_key_to_use, u_niche, 10000, u_days)
            if uni:
                dfu = pd.DataFrame(uni).sort_values(by='Rasio', ascending=False)
                st.success(f"Ditemukan {len(dfu)} Unicorn!")
                st.dataframe(dfu, column_config={"Thumbnail": st.column_config.ImageColumn("Thumb"), "Link": st.column_config.LinkColumn("Watch")}, hide_index=True)

# === TAB 3: ORACLE ===
with tab3:
    st.subheader("🔮 Oracle & Gap Detector")
    o_kw = st.text_input("Kata Kunci", "Sholawat Merdu", key="ora_kw") # SAMARAN CINDY TRIMM
    if o_kw:
        sug = get_youtube_autocomplete(o_kw)
        if sug: st.caption(f"Ide: {', '.join(sug[:5])}")
    
    if st.button("🔮 CEK POTENSI"):
        if api_key_to_use:
            res = analyze_oracle_pro(api_key_to_use, o_kw)
            if res:
                if res['is_gap']: st.markdown(f"<div class='gap-box'><h1>{res['verdict']}</h1><h3>{res['gap_msg']}</h3></div>", unsafe_allow_html=True)
                oc1, oc2, oc3 = st.columns(3)
                oc1.markdown(f"<h1 style='color:{res['color']}'>{res['score']}</h1><small>Skor Akhir</small>", unsafe_allow_html=True)
                oc2.markdown(f"<h1 style='color:{res['arus_col']}'>{res['volume']:,}</h1><small>{res['arus_stat']}</small>", unsafe_allow_html=True)
                oc3.markdown(f"<h1>{res['ideal_duration']}</h1><small>Durasi Ideal</small>", unsafe_allow_html=True)
                st.info(f"Avg Views: {res['avg_views']:,} | Title Match: {res['comp']}")

# === TAB 4: SPY GLASS (MERGED) ===
with tab4:
    st.subheader("🕵️‍♀️ Spy Glass: Analisa, Revenue & ATM")
    spy_url = st.text_input("Link Channel Target", placeholder="https://youtube.com/@Channel...")
    spy_limit = st.number_input("Jml Video", 5, 50, 20)
    
    if 'spy_res' not in st.session_state: st.session_state['spy_res'] = None
    if 'spy_name' not in st.session_state: st.session_state['spy_name'] = None
    if 'spy_stat' not in st.session_state: st.session_state['spy_stat'] = None

    if st.button("🚀 MULAI SPY"):
        if api_key_to_use and spy_url:
            d, s, n = scrape_spy(api_key_to_use, spy_url, spy_limit)
            st.session_state['spy_res'] = d
            st.session_state['spy_stat'] = s
            st.session_state['spy_name'] = n

    if st.session_state['spy_res']:
        data = st.session_state['spy_res']; stats = st.session_state['spy_stat']; name = st.session_state['spy_name']
        df_spy = pd.DataFrame(data)
        
        # 1. REVENUE
        rev, earn = calculate_revenue(df_spy['Views'].sum(), stats)
        st.markdown(f"### 💰 Est. Omzet: ${earn:,.2f} (Rp {earn*15500:,.0f})")
        
        # 2. DOWNLOADER (MODE TEKS UNTUK ANDROID)
        st.markdown("### 📥 Asset Downloader (Copy Mode)")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("📂 LIHAT ASET (Link & Thumb)"):
                t = download_assets(data, name)
                st.text_area("Copy data ini:", value=t, height=200)
        with b2:
            if st.button("📝 LIHAT DATA SEO (Tag & Judul)"):
                t = download_metadata(data, name)
                st.text_area("Copy data SEO ini:", value=t, height=200)
        
        st.dataframe(df_spy, column_config={"Thumbnail Link": st.column_config.ImageColumn("Preview")}, hide_index=True)
        
        # 3. AI PROMPT LAB (SUB-SECTION)
        st.markdown("---")
        st.markdown("<div class='spy-section'><h3>🧪 AI Prompt Lab (Reverse Engineer)</h3></div>", unsafe_allow_html=True)
        st.info("Pilih video dari tabel di atas, AI akan menebak prompt gambar & musiknya.")
        
        sel_vid = st.selectbox("Pilih Video:", [v['Judul'] for v in data])
        v_dat = next((x for x in data if x['Judul'] == sel_vid), None)
        
        if v_dat and st.button("🧬 BEDAH PROMPT VIDEO INI"):
            with st.spinner("Meracik Prompt..."):
                res_prompt = reverse_engineer_prompt(api_key_to_use, v_dat['Thumbnail Link'], v_dat['Judul'])
                st.text_area("Hasil Bedah Prompt:", value=res_prompt, height=300)
