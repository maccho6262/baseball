import sqlite3

class AtBat:
    def __init__(self, inning, result, course_index, pitch_type, hit_direction, rbi=0):
        self.inning = inning
        self.result = result
        self.course_index = course_index  # 1〜9のエリア（互換性用）
        self.pitch_type = pitch_type
        self.hit_direction = hit_direction
        self.rbi = rbi

    def is_hit(self):
        return self.result in ["単打(安打)", "二塁打(安打)", "三塁打(安打)", "本塁打(安打)"]

class StatsCalculator:
    def __init__(self, at_bats):
        self.at_bats = at_bats

    def calculate_stats(self):
        total_at_bats = len(self.at_bats)
        if total_at_bats == 0:
            return {
                "打率": ".000", "試合": 0, "打席": 0, "打数": 0, "安打": 0,
                "二塁打": 0, "三塁打": 0, "本塁打": 0, "打点": 0, "得点": 0,
                "三振": 0, "四球": 0, "死球": 0, "犠打": 0, "犠飛": 0,
                "盗塁": 0, "盗塁死": 0, "出塁率": ".000", "長打率": ".000", "OPS": ".000"
            }

        plate_appearances = total_at_bats
        sac_bunts = sum(1 for ab in self.at_bats if ab.result == "犠打")
        sac_flies = sum(1 for ab in self.at_bats if ab.result == "犠飛")
        walks = sum(1 for ab in self.at_bats if ab.result == "四球")
        hit_by_pitch = sum(1 for ab in self.at_bats if ab.result == "死球")
        
        # 打数 = 打席 - (四球 + 死球 + 犠打 + 犠飛)
        ab_count = plate_appearances - (walks + hit_by_pitch + sac_bunts + sac_flies)
        
        singles = sum(1 for ab in self.at_bats if ab.result == "単打(安打)")
        doubles = sum(1 for ab in self.at_bats if ab.result == "二塁打(安打)")
        triples = sum(1 for ab in self.at_bats if ab.result == "三塁打(安打)")
        home_runs = sum(1 for ab in self.at_bats if ab.result == "本塁打(安打)")
        hits = singles + doubles + triples + home_runs
        
        strikeouts = sum(1 for ab in self.at_bats if ab.result == "三振")
        rbi = sum(getattr(ab, "rbi", 0) for ab in self.at_bats)

        avg = hits / ab_count if ab_count > 0 else 0.0
        
        obp_denom = (ab_count + walks + hit_by_pitch + sac_flies)
        obp = (hits + walks + hit_by_pitch) / obp_denom if obp_denom > 0 else 0.0
        
        slg_numerator = (singles * 1) + (doubles * 2) + (triples * 3) + (home_runs * 4)
        slg = slg_numerator / ab_count if ab_count > 0 else 0.0
        
        ops = obp + slg

        def fmt(val):
            if val >= 1.0: return f"{val:.3f}"
            return f"{val:.3f}".lstrip("0") if val > 0 else ".000"

        # 📊 画像の項目順（失策・併殺打抜き）
        return {
            "打率": fmt(avg),
            "試合": "-", 
            "打席": plate_appearances,
            "打数": ab_count,
            "安打": hits,
            "二塁打": doubles,
            "三塁打": triples,
            "本塁打": home_runs,
            "打点": rbi,
            "得点": 0,   
            "三振": strikeouts,
            "四球": walks,
            "死球": hit_by_pitch,
            "犠打": sac_bunts,
            "犠飛": sac_flies,
            "盗塁": 0,   
            "盗塁死": 0, 
            "出塁率": fmt(obp),
            "長打率": fmt(slg),
            "OPS": fmt(ops)
        }

    def calculate_hit_pitch_stats(self):
        hits_ab = [ab for ab in self.at_bats if ab.is_hit()]
        total_hits = len(hits_ab)
        if total_hits == 0: return []
        
        pitch_counts = {}
        for ab in hits_ab:
            pitch_counts[ab.pitch_type] = pitch_counts.get(ab.pitch_type, 0) + 1
            
        return [{"球種": p, "安打数": c, "安打内の割合 (%)": round((c / total_hits) * 100, 1)} for p, c in pitch_counts.items()]

    def calculate_hit_direction_stats(self):
        hits_ab = [ab for ab in self.at_bats if ab.is_hit()]
        total_hits = len(hits_ab)
        if total_hits == 0: return []
        
        dir_counts = {}
        for ab in hits_ab:
            dir_counts[ab.hit_direction] = dir_counts.get(ab.hit_direction, 0) + 1
            
        return [{"打球方向": d, "安打数": c, "安打内の割合 (%)": round((c / total_hits) * 100, 1)} for d, c in dir_counts.items()]

def init_db():
    conn = sqlite3.connect("batting_management.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            opponent TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS at_bats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER,
            inning INTEGER,
            result TEXT,
            course_index INTEGER,
            pitch_type TEXT,
            hit_direction TEXT,
            rbi INTEGER DEFAULT 0,
            FOREIGN KEY (game_id) REFERENCES games (id)
        )
    """)
    conn.commit()
    conn.close()