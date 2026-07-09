import streamlit as st
import datetime
import sqlite3
import pandas as pd
from models import AtBat, StatsCalculator, init_db
from streamlit_mic_recorder import speech_to_text
from streamlit_image_coordinates import streamlit_image_coordinates
from PIL import Image, ImageDraw

st.set_page_config(page_title="打撃管理アプリ - コースプロット版", layout="wide")
init_db()

st.title("⚾ 打撃管理アプリケーション (投球コース自由プロット式)")

# ------------------------------------------
# 🔄 セッション状態（データの保持）の初期化
# ------------------------------------------
if "temp_at_bats" not in st.session_state:
    st.session_state.temp_at_bats = []
if "voice_key_counter" not in st.session_state:
    st.session_state["voice_key_counter"] = 0

# 🎯 クリックされた座標（初期値はど真ん中の55付近に相当する位置）
if "click_coords" not in st.session_state:
    st.session_state["click_coords"] = (225, 225) # 画像の中心 (450x450想定)

PITCH_OPTIONS = ["ストレート", "スライダー", "カーブ", "フォーク", "その他"]
RESULT_OPTIONS = [
    "単打(安打)", "二塁打(安打)", "三塁打(安打)", "本塁打(安打)",
    "ゴロアウト", "フライアウト", "ライナーアウト",
    "三振", "四球", "死球", "犠打", "犠飛"
]
DIR_OPTIONS = ["投", "捕", "一", "二", "三", "遊", "左", "中", "右", "なし"]
RBI_OPTIONS = [0, 1, 2, 3, 4] 

# 音声バッファ用のセッション
if "current_pitch" not in st.session_state: st.session_state["current_pitch"] = "ストレート"
if "current_result" not in st.session_state: st.session_state["current_result"] = "単打(安打)"
if "current_dir" not in st.session_state: st.session_state["current_dir"] = "中"
if "current_rbi" not in st.session_state: st.session_state["current_rbi"] = 0

# 🎨 63分割のチャート画像をオンデマンドで生成する関数 (数字なしバージョン)
def create_chart_image(dot_coords=None):
    img_size = 450
    img = Image.new("RGB", (img_size, img_size), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    # 外枠（濃い青）
    draw.rectangle([10, 10, img_size-10, img_size-10], outline="#0f3460", width=4)
    
    # 縦列(1〜9)と横列(0〜6)のグリッド線を描画
    cell_w = (img_size - 20) / 9
    cell_h = (img_size - 20) / 7
    
    # 破線のグリッドを描画
    for i in range(1, 9):
        x = 10 + i * cell_w
        draw.line([x, 10, x, img_size-10], fill="#CCCCCC", width=1)
    for j in range(1, 7):
        y = 10 + j * cell_h
        draw.line([10, y, img_size-10, y], fill="#CCCCCC", width=1)
        
    # ストライクゾーン（赤い太枠：横3〜7、縦1〜5に相当するエリア）
    sz_left = 10 + 2 * cell_w
    sz_right = 10 + 7 * cell_w
    sz_top = 10 + 1 * cell_h
    sz_bottom = 10 + 6 * cell_h
    draw.rectangle([sz_left, sz_top, sz_right, sz_bottom], outline="#FF2E93", width=4)
    
    # クリックされた位置に「赤い点」をプロット
    if dot_coords:
        cx, cy = dot_coords
        radius = 8
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill="#FF2E93", outline="#FFFFFF", width=1)
        
    return img

col_left, col_right = st.columns([1, 1.3])

with col_left:
    st.header("📋 成績の入力")
    
    # ------------------------------------------
    # 🎤 音声入力エリア
    # ------------------------------------------
    st.subheader("🎙️ 声で入力（球種・結果・打球方向・打点）")
    st.caption("ボタンを押して「ストレート ヒット ショート 2打点」のように続けて喋ってください。")
    
    dynamic_key = f"srt_{st.session_state['voice_key_counter']}"
    text = speech_to_text(start_prompt="🎤 音声入力を開始", stop_prompt="■ 録音停止", language='ja', use_container_width=True, key=dynamic_key)
    
    if text:
        st.success(f"聞き取れた音声: 「{text}」")
        
        # ① 球種の判定
        for p in PITCH_OPTIONS:
            if p in text:
                st.session_state["current_pitch"] = p
                break
                
        # ② 結果の判定
        result_keywords = {
            "単打(安打)": ["単打", "ヒット", "ライト前", "レフト前", "センター前"],
            "二塁打(安打)": ["二塁打", "ツーベース"],
            "三塁打(安打)": ["三塁打", "スリーベース"],
            "本塁打(安打)": ["本塁打", "ホームラン"],
            "ゴロアウト": ["ゴロ"],
            "フライアウト": ["フライ"],
            "ライナーアウト": ["ライナー"],
            "三振": ["三振"],
            "四球": ["四球", "フォアボール"],
            "死球": ["死球", "デッドボール"],
            "犠打": ["犠打", "バント"],
            "犠飛": ["犠飛", "タッチアップ"]
        }
        for r, keywords in result_keywords.items():
            if any(k in text for k in keywords):
                st.session_state["current_result"] = r
                break

        # ③ ポジション（方向）の判定
        dir_keywords = {
            "投": ["投", "ピッチャー"],
            "捕": ["捕", "キャッチャー"],
            "一": ["一", "ファースト"],
            "二": ["二", "セカンド"],
            "三": ["三", "サード"],
            "遊": ["遊", "ショート"],
            "左": ["左", "レフト"],
            "中": ["中", "センター"],
            "右": ["右", "ライト"],
            "なし": ["なし", "無し"]
        }
        for d, keywords in dir_keywords.items():
            if any(k in text for k in keywords):
                st.session_state["current_dir"] = d
                break

        # ④ 打点の判定
        rbi_keywords = {
            "1": ["1打点", "1点", "一点", "一打点"],
            "2": ["2打点", "2点", "二点", "二打点"],
            "3": ["3打点", "3点", "三点", "三打点"],
            "4": ["4打点", "4点", "四点", "四打点", "満塁ホームラン", "満塁弾"],
            "0": ["0打点", "0点", "打点なし"]
        }
        rbi_detected = False
        for r_val, keywords in rbi_keywords.items():
            if any(k in text for k in keywords):
                st.session_state["current_rbi"] = int(r_val)
                rbi_detected = True
                break
        
        if not rbi_detected and st.session_state["current_result"] == "本塁打(安打)":
            st.session_state["current_rbi"] = 1
        
        st.toast("音声を入力欄に反映しました！", icon="🤖")
        st.session_state["voice_key_counter"] += 1
        st.rerun()

    st.write("---")

    # 1. 試合情報
    st.subheader("1. 試合情報")
    game_date = st.date_input("試合日付", datetime.date.today())
    opponent = st.text_input("対戦相手", value="〇〇大学")

    # 2. 打席情報
    st.subheader(f"2. 第 {len(st.session_state.temp_at_bats) + 1} 打席の確認")
    
    pitch_idx = PITCH_OPTIONS.index(st.session_state["current_pitch"]) if st.session_state["current_pitch"] in PITCH_OPTIONS else 0
    pitch_type = st.selectbox("球種", PITCH_OPTIONS, index=pitch_idx)
    st.session_state["current_pitch"] = pitch_type

    result_idx = RESULT_OPTIONS.index(st.session_state["current_result"]) if st.session_state["current_result"] in RESULT_OPTIONS else 0
    result = st.selectbox("打撃結果", RESULT_OPTIONS, index=result_idx)
    st.session_state["current_result"] = result

    is_skipped = result in ["三振", "四球", "死球"]
    if is_skipped:
        st.info("💡 三振/四死球のため、打球ポジションは自動スキップされます。")
        hit_direction = "なし"
    else:
        dir_idx = DIR_OPTIONS.index(st.session_state["current_dir"]) if st.session_state["current_dir"] in DIR_OPTIONS else 7
        hit_direction = st.selectbox("打球ポジション（飛んだ場所）", DIR_OPTIONS, index=dir_idx)
        st.session_state["current_dir"] = hit_direction

    rbi_idx = RBI_OPTIONS.index(st.session_state["current_rbi"]) if st.session_state["current_rbi"] in RBI_OPTIONS else 0
    rbi = st.selectbox("打点", RBI_OPTIONS, index=rbi_idx)
    st.session_state["current_rbi"] = rbi

    # ------------------------------------------
    # 🎯 3. 投球チャート自由プロットUI
    # ------------------------------------------
    st.write("---")
    st.markdown("**🎯 3. 投球コースを画像上でクリック（タップ）して点を配置**")
    st.caption("キャッチャー側から見た図です。赤い太枠がストライクゾーン、外側がボールゾーンです。")
    
    # 現在の点をもとに画像を生成
    chart_img = create_chart_image(st.session_state["click_coords"])
    
    # 画像をクリック可能コンポーネントとして表示し、座標を取得
    value = streamlit_image_coordinates(chart_img, key="clickable_chart")
    
    # クリックされたら座標を更新して再描画
    if value:
        new_coords = (value["x"], value["y"])
        if new_coords != st.session_state["click_coords"]:
            st.session_state["click_coords"] = new_coords
            st.rerun()

    # 座標から、従来の「1〜9」のコースIDに簡易マッピング
    cx, cy = st.session_state["click_coords"]
    cell_w = 430 / 9
    cell_h = 430 / 7
    grid_x = int((cx - 10) // cell_w)
    grid_y = int((cy - 10) // cell_h)
    
    if grid_x < 3:   col_zone = 0
    elif grid_x > 5: col_zone = 2
    else:            col_zone = 1
    
    if grid_y < 2:   row_zone = 0
    elif grid_y > 4: row_zone = 2
    else:            row_zone = 1
    
    legacy_course_index = row_zone * 3 + col_zone + 1
    legacy_course_index = max(1, min(9, legacy_course_index))

    st.write("---")
    if st.button("✅ この内容で打席を確定して追加", type="primary", use_container_width=True):
        if not opponent.strip():
            st.error("❌ 对戦相手を入力してください。")
        else:
            new_at_bat = {
                "inning": 1, "result": result, "course_index": legacy_course_index,
                "pitch_type": pitch_type, "hit_direction": hit_direction, "rbi": rbi
            }
            st.session_state.temp_at_bats.append(new_at_bat)
            st.success(f"打席を追加しました！")
            
            # 初期値リセット
            st.session_state["click_coords"] = (225, 225)
            st.session_state["current_pitch"] = "ストレート"
            st.session_state["current_result"] = "単打(安打)"
            st.session_state["current_dir"] = "中"
            st.session_state["current_rbi"] = 0
            st.rerun()

    # 💾 【修正】データベース保存ボタンの入力制限ガード
    st.write("---")
    if not st.session_state.temp_at_bats:
        st.warning("⚠️ まだ確定された打席データがありません。上のボタンから打席を追加してください。")
        st.button("💾 試合結果をまとめてDBに保存する", use_container_width=True, disabled=True)
    else:
        if st.button("💾 試合結果をまとめてDBに保存する", type="secondary", use_container_width=True):
            conn = sqlite3.connect("batting_management.db")
            cursor = conn.cursor()
            try: cursor.execute("ALTER TABLE at_bats ADD COLUMN rbi INTEGER DEFAULT 0")
            except sqlite3.OperationalError: pass

            cursor.execute("INSERT INTO games (date, opponent) VALUES (?, ?)", (str(game_date), opponent))
            game_id = cursor.lastrowid
            for ab in st.session_state.temp_at_bats:
                cursor.execute("""
                    INSERT INTO at_bats (game_id, inning, result, course_index, pitch_type, hit_direction, rbi)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (game_id, ab["inning"], ab["result"], ab["course_index"], ab["pitch_type"], ab["hit_direction"], ab["rbi"]))
            conn.commit()
            conn.close()
            st.session_state.temp_at_bats = [] 
            st.success("🎉 データベースに試合結果を保存しました！")
            st.rerun()

# ==========================================
# 右カラム: 成績出力 & 分析 (公式記録風)
# ==========================================
with col_right:
    st.header("📊 成績の出力")
    conn = sqlite3.connect("batting_management.db")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT inning, result, course_index, pitch_type, hit_direction, rbi FROM at_bats")
        all_rows = cursor.fetchall()
        all_at_bats = [AtBat(r[0], r[1], r[2], r[3], r[4], rbi=r[5]) for r in all_rows]
    except sqlite3.OperationalError:
        cursor.execute("SELECT inning, result, course_index, pitch_type, hit_direction FROM at_bats")
        all_rows = cursor.fetchall()
        all_at_bats = [AtBat(r[0], r[1], r[2], r[3], r[4], rbi=0) for r in all_rows]

    cursor.execute("SELECT id, date, opponent FROM games ORDER BY id DESC")
    games = cursor.fetchall()
    conn.close()

    st.subheader("🏆 【通算】の打撃成績・安打分析")
    if all_at_bats:
        calc_total = StatsCalculator(all_at_bats)
        st.markdown("**■ 基本スタッツ**")
        
        # 通算スタッツの取得と、実際の試合数のカウント反映
        stats_dict = calc_total.calculate_stats()
        conn = sqlite3.connect("batting_management.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT game_id) FROM at_bats")
        stats_dict["試合"] = cursor.fetchone()[0]
        conn.close()

        # 横にスクロールして見られるきれいなデータフレーム形式へ
        st.dataframe(pd.DataFrame([stats_dict]), hide_index=True, use_container_width=True)
        
        st.write("---")
        total_hits = sum(1 for ab in all_at_bats if ab.is_hit())
        if total_hits > 0:
            st.markdown(f"**■ ヒットした球種の割合 (通算ヒット数: {total_hits}本)**")
            df_pitch = pd.DataFrame(calc_total.calculate_hit_pitch_stats())
            st.dataframe(df_pitch, hide_index=True)

            st.markdown("**■ ヒットした打球方向の割合**")
            df_dir = pd.DataFrame(calc_total.calculate_hit_direction_stats())
            st.dataframe(df_dir, hide_index=True)
    else:
        st.write("まだ保存されたデータがありません。")

    st.write("---")
    st.subheader("📅 【試合ごと】の打撃成績")
    if st.session_state.temp_at_bats:
        st.info(f"⏳ 現在入力中: {opponent}")
        current_at_bats = [AtBat(ab["inning"], ab["result"], ab["course_index"], ab["pitch_type"], ab["hit_direction"], rbi=ab["rbi"]) for ab in st.session_state.temp_at_bats]
        curr_stats = StatsCalculator(current_at_bats).calculate_stats()
        curr_stats["試合"] = 1
        st.dataframe(pd.DataFrame([curr_stats]), hide_index=True, use_container_width=True)

    for g_id, g_date, g_opp in games:
        with st.expander(f"📅 {g_date} vs {g_opp} (ID: {g_id})"):
            conn = sqlite3.connect("batting_management.db")
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT inning, result, course_index, pitch_type, hit_direction, rbi FROM at_bats WHERE game_id = ?", (g_id,))
                g_rows = cursor.fetchall()
                game_at_bats = [AtBat(r[0], r[1], r[2], r[3], r[4], rbi=r[5]) for r in g_rows]
            except sqlite3.OperationalError:
                cursor.execute("SELECT inning, result, course_index, pitch_type, hit_direction FROM at_bats WHERE game_id = ?", (g_id,))
                g_rows = cursor.fetchall()
                game_at_bats = [AtBat(r[0], r[1], r[2], r[3], r[4], rbi=0) for r in g_rows]
            conn.close()
            
            game_stats = StatsCalculator(game_at_bats).calculate_stats()
            game_stats["試合"] = 1
            st.dataframe(pd.DataFrame([game_stats]), hide_index=True, use_container_width=True)
            
            # 🗑️ 【追加】データの削除機能
            if st.button(f"🗑️ この試合データを削除する", key=f"del_{g_id}", use_container_width=True):
                conn = sqlite3.connect("batting_management.db")
                cursor = conn.cursor()
                # 該当する試合に紐づく打席データと試合データを削除
                cursor.execute("DELETE FROM at_bats WHERE game_id = ?", (g_id,))
                cursor.execute("DELETE FROM games WHERE id = ?", (g_id,))
                conn.commit()
                conn.close()
                st.toast(f"💥 {g_date} {g_opp} のデータを削除しました。")
                st.rerun()