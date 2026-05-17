import json
import os
from metaplay_pcg import MetaplayPCG
from constants import (
    COLOR_RESET, RARITY_KOR, RARITY_COLOR, TYPE_COLOR, 
    SUBSTATS_POOL, RARITY_SCORE, get_gradient_color, get_substat_value
)

os.system("")

def load_data():
    with open('EggSummonConfig.json', 'r', encoding='utf-8') as f:
        summon_config = json.load(f)
    with open('PetLibrary.json', 'r', encoding='utf-8') as f:
        pet_library = json.load(f)
    return summon_config, pet_library

def main():
    try:
        summon_config, pet_library = load_data()
    except FileNotFoundError:
        print("에러: EggSummonConfig.json 또는 PetLibrary.json을 찾을 수 없습니다.")
        return

    levels_config = summon_config["Levels"]
    rarities = ["Common", "Rare", "Epic", "Legendary", "Ultimate", "Mythic"]
    pets_by_rarity = {r: [] for r in rarities}
    
    for key, data in sorted(pet_library.items(), key=lambda x: x[1]["PetId"]["Id"]):
        r = data["PetId"]["Rarity"]
        pets_by_rarity[r].append(key)

    while True:
        print("\n" + "="*45)
        print("Forge Master Egg 시뮬레이터")
        print("="*45)
        
        seed_input = input("Seed(HEX16): ").strip()
        state_input = input("Level/Count(HEX16): ").strip()
        chance_input = input("Extra Summon Chance(%) : ").strip()

        initial_seed = int(seed_input, 16)
        state_val = int(state_input, 16)
        initial_level = (state_val >> 32) & 0xFFFFFFFF
        initial_count = state_val & 0xFFFFFFFF
        extra_chance_pct = float(chance_input)

        current_seed = initial_seed
        current_level = initial_level
        current_count = initial_count
        
        total_base_pulls = 0
        total_bonus_pulls = 0
        pull_history = [] 

        print(f"\n[초기 상태] Level: {current_level+1}, Count: {current_count}, Chance: {extra_chance_pct}%")
        print("(명령어를 모를 경우 help를 입력하세요)")
        
        while True:
            user_cmd = input("\n> ").strip().lower()

            if user_cmd == 'quit':
                return
            elif user_cmd == 'help':
                print("\n[명령어 목록]")
                print("- 1, 15, 50 : 입력한 횟수만큼 소환을 진행합니다.")
                print("- summary   : 현재까지의 소환 요약 통계를 보여줍니다.")
                print("- status    : 현재 레벨, 카운트, 시드 상태를 보여줍니다.")
                print("- reset     : 소환 기록만 초기화합니다 (시드 및 설정 유지).")
                print("- reset all : 모든 설정을 초기화하고 처음부터 다시 시작합니다.")
                print("- quit      : 프로그램을 종료합니다.")
                continue
            elif user_cmd == 'reset all':
                break 
            elif user_cmd == 'reset':
                current_seed = initial_seed
                current_level = initial_level
                current_count = initial_count
                total_base_pulls = 0
                total_bonus_pulls = 0
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
                print(f"- 총 소환: {total_base_pulls + total_bonus_pulls}회 (기본 {total_base_pulls} + 보너스 {total_bonus_pulls})")
                print("-" * 40)
                
                rarity_counts = {r: 0 for r in rarities}
                max_score = 0
                max_rarity_name = "Common"
                
                for p in pull_history:
                    r_name = p['rarity_name']
                    r_score = p['rarity_score']
                    rarity_counts[r_name] += 1
                    if r_score > max_score:
                        max_score = r_score
                        max_rarity_name = r_name
                
                print("[등급별 획득 수]")
                for r in reversed(rarities):
                    if rarity_counts[r] > 0:
                        print(f"- {RARITY_COLOR[r]}{RARITY_KOR[r]}{COLOR_RESET}: {rarity_counts[r]}개")
                
                print("-" * 40)
                print(f"[최고 등급 ({RARITY_COLOR[max_rarity_name]}{RARITY_KOR[max_rarity_name]}{COLOR_RESET}) 스탯 최댓값]")
                max_stats = {}
                for p in pull_history:
                    if p['rarity_score'] == max_score:
                        for s_name, s_val in p['stats'].items():
                            if s_name not in max_stats or s_val > max_stats[s_name]:
                                max_stats[s_name] = s_val
                
                for s_name in sorted(max_stats.keys()):
                    print(f"- {s_name}: +{max_stats[s_name]:.2f}%")
                
                continue
            elif user_cmd in ['1', '15', '50']:
                batch_size = int(user_cmd)
            else:
                print("잘못된 명령어입니다. (help를 입력해 명령어를 확인하세요)")
                continue

            total_target_pulls = batch_size 
            current_pull_idx = 0
            current_bonus_count = 0 
            
            total_base_pulls += batch_size 
            
            batch_prints = []
            batch_rarity_counts = {r: 0 for r in rarities}

            while current_pull_idx < total_target_pulls:
                pcg_summon = MetaplayPCG(current_seed)
                is_bonus_pull = current_pull_idx >= batch_size

                if not is_bonus_pull:
                    bonus_roll_raw = pcg_summon._next_pcg32() 
                    chance_raw = int(round((extra_chance_pct / 100.0) * 4294967296))
                    if bonus_roll_raw < chance_raw:
                        total_target_pulls += 1
                        current_bonus_count += 1
                        total_bonus_pulls += 1 

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

                pcg_hatch = MetaplayPCG(current_seed)
                
                available_pets = pets_by_rarity[rolled_rarity]
                chosen_pet_idx = pcg_hatch.next_int(len(available_pets))
                chosen_pet = available_pets[chosen_pet_idx]

                pcg_hatch.next_guid()

                num_substats = 2 if rolled_rarity in ["Legendary", "Ultimate", "Mythic"] else 1
                available_stats = list(SUBSTATS_POOL)
                
                acquired_stats = []
                stat_dict = {}
                f64_sum = 0.0 
                
                for _ in range(num_substats):
                    stat_idx = pcg_hatch.next_int(len(available_stats))
                    stat_name = available_stats[stat_idx]
                    available_stats.remove(stat_name)
                    
                    f64_val = pcg_hatch.next_f64()
                    f64_sum += f64_val 
                    stat_val = get_substat_value(stat_name, f64_val)
                    
                    acquired_stats.append(f"{stat_name} (+{stat_val*100:.2f}%)")
                    stat_dict[stat_name] = stat_val * 100.0

                perfection_pct = (f64_sum / num_substats) * 100.0
                pet_type = pet_library[chosen_pet]["Type"]
                
                stat1_str = acquired_stats[0] if len(acquired_stats) > 0 else "-"
                stat2_str = acquired_stats[1] if len(acquired_stats) > 1 else "-"
                
                r_color = RARITY_COLOR[rolled_rarity]
                r_kor = RARITY_KOR[rolled_rarity]
                t_color = TYPE_COLOR.get(pet_type, "")
                grad_color = get_gradient_color(perfection_pct)
                
                bonus_str = f" {RARITY_COLOR['Legendary']}🎁{COLOR_RESET}" if is_bonus_pull else ""
                
                r_padded = f"[{r_kor}]"
                t_padded = f"{pet_type:^8}"
                s1_padded = f"{stat1_str:<28}"
                s2_padded = f"{stat2_str:<28}"
                p_padded = f"{perfection_pct:>5.1f}%"

                colored_r = f"{r_color}{r_padded}{COLOR_RESET}"
                colored_t = f"{t_color}{t_padded}{COLOR_RESET}"
                colored_p = f"{grad_color}{p_padded}{COLOR_RESET}"
                
                clean_display = f"{colored_r} | {colored_t} | {s1_padded} | {s2_padded} | {colored_p}{bonus_str}"
                
                batch_prints.append(clean_display)
                batch_rarity_counts[rolled_rarity] += 1
                
                pull_history.append({
                    "rarity_score": RARITY_SCORE[rolled_rarity],
                    "rarity_name": rolled_rarity,
                    "perfection": perfection_pct,
                    "stats": stat_dict,
                    "display": clean_display
                })

                current_count += 1
                summons_required = current_lvl_data.get("SummonsRequired", 9999)
                if current_count >= summons_required:
                    current_count -= summons_required
                    current_level += 1
                    
                current_seed += 1
                current_pull_idx += 1

            total_acquired = batch_size + current_bonus_count
            
            rarity_summary = []
            for r in reversed(rarities):
                if batch_rarity_counts[r] > 0:
                    rarity_summary.append(f"{RARITY_COLOR[r]}{RARITY_KOR[r]}{COLOR_RESET}: {batch_rarity_counts[r]}")
            rarity_summary_str = " | ".join(rarity_summary)
            
            print(f"\n[ {batch_size}회 소환 결과: {total_acquired}개 ({batch_size} + {current_bonus_count}) | {rarity_summary_str} ]")
            
            header = " 등급  |   타입   | 스탯 1" + " "*22 + " | 스탯 2" + " "*22 + " |  완성도"
            print("-" * 92)
            print(header)
            print("-" * 92)
            
            for line in batch_prints:
                print(line)
            
            print("-" * 92)

if __name__ == "__main__":
    main()