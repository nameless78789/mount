import json
import os
from metaplay_pcg import MetaplayPCG
from constants import (
    COLOR_RESET, RARITY_KOR, RARITY_COLOR, RARITY_SCORE
)

os.system("")

def load_skill_data():
    try:
        with open('SkillSummonConfig.json', 'r', encoding='utf-8') as f:
            summon_config = json.load(f)
        with open('SkillLibrary.json', 'r', encoding='utf-8') as f:
            skill_library = json.load(f)
        return summon_config, skill_library
    except FileNotFoundError:
        print("에러: SkillSummonConfig.json 또는 SkillLibrary.json을 찾을 수 없습니다.")
        return None, None

def main():
    config_data = load_skill_data()
    if config_data == (None, None):
        return
    summon_config, skill_library = config_data

    levels_config = summon_config["Levels"]
    rarities = ["Common", "Rare", "Epic", "Legendary", "Ultimate", "Mythic"]
    skills_by_rarity = {r: [] for r in rarities}
    
    for skill_id, skill_data in skill_library.items():
        skills_by_rarity[skill_data["Rarity"]].append(skill_id)

    while True:
        print("\n" + "="*45)
        print("🪄 Forge Master Skill(스킬) 시뮬레이터")
        print("="*45)
        
        seed_input = input("Seed(HEX16): ").strip()
        state_input = input("Level/Count(HEX16): ").strip()
        chance_input = input("Extra Summon Chance(%) : ").strip()

        initial_seed = int(seed_input, 16)
        state_val = int(state_input, 16)
        initial_level = (state_val >> 32) & 0xFFFFFFFF
        initial_count = state_val & 0xFFFFFFFF
        extra_chance_pct = float(chance_input) if chance_input else 0.0

        current_seed = initial_seed
        current_level = initial_level
        current_count = initial_count
        
        total_base_pulls = 0
        pull_history = [] 

        print(f"\n[초기 상태] Level: {current_level+1}, Count: {current_count}")
        print("(명령어를 모를 경우 help를 입력하세요)")
        
        while True:
            user_cmd = input("\n> ").strip().lower()

            if user_cmd == 'quit':
                return
            elif user_cmd == 'help':
                print("\n[명령어 목록]")
                print("- 1, 15, 50 : 입력한 횟수만큼 스킬 소환을 진행합니다.")
                print("- summary   : 현재까지의 소환 요약 통계를 보여줍니다.")
                print("- status    : 현재 레벨, 카운트, 시드 상태를 보여줍니다.")
                print("- reset     : 소환 기록만 초기화합니다 (시드 및 설정 유지).")
                print("- reset all : 모든 설정을 초기화하고 처음부터 다시 시작합니다.")
                print("- quit      : 현재 시뮬레이터를 종료합니다 (통합 메뉴로 복귀).")
                continue
            elif user_cmd == 'reset all':
                break 
            elif user_cmd == 'reset':
                current_seed = initial_seed
                current_level = initial_level
                current_count = initial_count
                total_base_pulls = 0
                pull_history.clear()
                print("소환 결과 초기화 완료.")
                print(f"Level: {current_level+1}, Count: {current_count}")
                continue
            elif user_cmd == 'status':
                print(f"Level: {current_level+1} | Count: {current_count} | Seed: {current_seed:016X}")
                continue
            elif user_cmd.startswith('summary'):
                if not pull_history:
                    print("소환 기록이 없습니다.")
                    continue

                print("\n[요약 정보]")
                print(f"- 레벨/카운트: Lv {current_level+1} | Count {current_count}")
                print(f"- 총 소환: {total_base_pulls}회")
                print("-" * 40)
                
                rarity_counts = {r: 0 for r in rarities}
                acquired_skills_count = {}
                
                for p in pull_history:
                    r_name = p['rarity_name']
                    s_name = p['skill_name']
                    rarity_counts[r_name] += 1
                    
                    if s_name not in acquired_skills_count:
                        acquired_skills_count[s_name] = {'rarity': r_name, 'count': 0}
                    acquired_skills_count[s_name]['count'] += 1
                
                print("[등급별 획득 수]")
                for r in reversed(rarities):
                    if rarity_counts[r] > 0:
                        print(f"- {RARITY_COLOR[r]}{RARITY_KOR[r]}{COLOR_RESET}: {rarity_counts[r]}개")
                
                print("-" * 40)
                print("[획득한 스킬 목록]")
                
                sorted_skills = sorted(acquired_skills_count.items(), key=lambda x: RARITY_SCORE[x[1]['rarity']], reverse=True)
                for s_name, s_data in sorted_skills:
                    r_col = RARITY_COLOR[s_data['rarity']]
                    r_kor = RARITY_KOR[s_data['rarity']]
                    print(f"- {r_col}[{r_kor}] {s_name}{COLOR_RESET} : {s_data['count']}개")
                
                continue
            elif user_cmd in ['1', '15', '50']:
                batch_size = int(user_cmd)
            else:
                print("잘못된 명령어입니다. (help를 입력해 명령어를 확인하세요)")
                continue

            current_pull_idx = 0
            total_base_pulls += batch_size 
            
            batch_prints = []
            batch_rarity_counts = {r: 0 for r in rarities}

            while current_pull_idx < batch_size:
                pcg_summon = MetaplayPCG(current_seed)
                pcg_summon._next_pcg32()

                rarity_roll_raw = pcg_summon._next_pcg32() 
                
                lvl_idx = min(current_level, len(levels_config) - 1)
                current_lvl_data = levels_config[lvl_idx]
                
                accumulated_raw = 0
                rolled_rarity = "Common"
                for rarity in rarities:
                    chance = current_lvl_data.get(rarity, 0.0)
                    chance_raw = int(round(chance * 4294967296)) 
                    accumulated_raw += chance_raw
                    
                    if rarity_roll_raw < accumulated_raw:
                        rolled_rarity = rarity
                        break

                available_skills = skills_by_rarity[rolled_rarity]
                chosen_skill = pcg_summon.choice(available_skills)

                r_color = RARITY_COLOR[rolled_rarity]
                r_kor = RARITY_KOR[rolled_rarity]
                r_padded = f"[{r_kor}]"
                
                colored_r = f"{r_color}{r_padded}{COLOR_RESET}"
                s_padded = f"{chosen_skill:<25}"
                
                clean_display = f"{colored_r} | {s_padded}"
                
                batch_prints.append(clean_display)
                batch_rarity_counts[rolled_rarity] += 1
                
                pull_history.append({
                    "rarity_score": RARITY_SCORE[rolled_rarity],
                    "rarity_name": rolled_rarity,
                    "skill_name": chosen_skill,
                    "display": clean_display
                })

                current_count += 1
                summons_required = current_lvl_data.get("SummonsRequired", 9999)
                if current_count >= summons_required:
                    current_count -= summons_required
                    current_level += 1
                    
                current_seed += 1
                current_pull_idx += 1

            rarity_summary = []
            for r in reversed(rarities):
                if batch_rarity_counts[r] > 0:
                    rarity_summary.append(f"{RARITY_COLOR[r]}{RARITY_KOR[r]}{COLOR_RESET}: {batch_rarity_counts[r]}")
            rarity_summary_str = " | ".join(rarity_summary)
            
            print(f"\n[ {batch_size}회 소환 결과 | {rarity_summary_str} ]")
            
            header = " 등급  |        스킬 이름"
            print("-" * 40)
            print(header)
            print("-" * 40)
            
            for line in batch_prints:
                print(line)
            
            print("-" * 40)

if __name__ == "__main__":
    main()