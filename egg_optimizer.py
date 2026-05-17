import json
import itertools
import sys
from collections import Counter

# --- PCG 난수 생성기 클래스 ---
class MetaplayPCG:
    def __init__(self, seed: int):
        self.state = (seed * 0x5851f42d4c957f2d + 0x1a08ee1184ba6d32) & 0xFFFFFFFFFFFFFFFF

    def _next_pcg32(self) -> int:
        old_state = self.state
        self.state = (old_state * 0x5851f42d4c957f2d + 0x14057b7ef767814f) & 0xFFFFFFFFFFFFFFFF
        xorshifted = (((old_state >> 18) ^ old_state) >> 27) & 0xFFFFFFFF
        rot = (old_state >> 59) & 0x1F
        left_shift = (xorshifted << ((~rot + 1) & 0x1F)) & 0xFFFFFFFF
        right_shift = (xorshifted >> rot) & 0xFFFFFFFF
        return (left_shift + right_shift) & 0xFFFFFFFF

    def next_f64(self) -> float:
        return self._next_pcg32() / 4294967296.0

    def next_int(self, max_val: int) -> int:
        if max_val <= 0: return 0
        raw = self._next_pcg32()
        pos_val = (raw >> 1) & 0x7FFFFFFF 
        div = pos_val // max_val
        return pos_val - (div * max_val)

    def next_ulong(self) -> int:
        high = self._next_pcg32()
        low = self._next_pcg32()
        return ((high << 32) | low) & 0xFFFFFFFFFFFFFFFF

    def next_guid(self):
        self.next_ulong()
        self.next_ulong()

def load_data():
    with open('EggSummonConfig.json', 'r', encoding='utf-8') as f:
        summon_config = json.load(f)
    with open('PetLibrary.json', 'r', encoding='utf-8') as f:
        pet_library = json.load(f)
    return summon_config, pet_library

SUBSTATS_INFO = {
    "Critical Chance": (0.01, 0.12),
    "Critical Damage": (0.01, 1.0),
    "Block Chance": (0.01, 0.05),
    "Health Regen": (0.01, 0.04),
    "Life Steal": (0.01, 0.20),
    "Double Chance": (0.01, 0.40),
    "Damage": (0.01, 0.15),
    "Melee Damage": (0.01, 0.50),
    "Ranged Damage": (0.01, 0.15),
    "Attack Speed": (0.01, 0.40),
    "Skill Damage": (0.01, 0.30),
    "Skill Cooldown": (0.01, 0.07),
    "Health": (0.01, 0.15)
}
SUBSTATS_LIST = list(SUBSTATS_INFO.keys())

RARITY_SCORE = {
    "Mythic": 6, "Ultimate": 5, "Legendary": 4, 
    "Epic": 3, "Rare": 2, "Common": 1
}

def get_substat_value(stat_name, pcg_f64_val):
    low, up = SUBSTATS_INFO[stat_name]
    return low + pcg_f64_val * (up - low)

# 🔥 전역 캐시(메모이제이션) 딕셔너리 🔥
PULL_CACHE = {}

def get_pull_result(seed, level, is_bonus, extra_chance_pct, levels_config, rarities, pets_by_rarity, target_substats):
    cache_key = (seed, level, is_bonus)
    if cache_key in PULL_CACHE:
        return PULL_CACHE[cache_key]

    pcg_summon = MetaplayPCG(seed)
    
    bonus_proc = False
    if not is_bonus:
        bonus_roll_raw = pcg_summon._next_pcg32() 
        chance_raw = int(round((extra_chance_pct / 100.0) * 4294967296))
        if bonus_roll_raw < chance_raw:
            bonus_proc = True

    rarity_roll_raw = pcg_summon._next_pcg32() 
    lvl_idx = min(level, len(levels_config) - 1)
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
            
    pcg_hatch = MetaplayPCG(seed)
    available_pets = pets_by_rarity[rolled_rarity]
    _ = pcg_hatch.next_int(len(available_pets)) 
    pcg_hatch.next_guid() 
    
    num_substats = 2 if rolled_rarity in ["Legendary", "Ultimate", "Mythic"] else 1
    available_stats = list(SUBSTATS_LIST)
    
    perfs = {stat: 0.0 for stat in target_substats}
    
    for _ in range(num_substats):
        stat_idx = pcg_hatch.next_int(len(available_stats))
        stat_name = available_stats.pop(stat_idx)
        f64_val = pcg_hatch.next_f64()
        
        if stat_name in target_substats:
            perfection_pct = f64_val * 100.0
            if perfection_pct > perfs[stat_name]:
                perfs[stat_name] = perfection_pct

    result = (bonus_proc, rolled_rarity, perfs)
    PULL_CACHE[cache_key] = result
    return result


def get_batch_combinations(total_pulls, sizes=[50, 15, 1]):
    res = []
    def dfs(remain, path, start_idx):
        if remain == 0:
            res.append(path)
            return
        for i in range(start_idx, len(sizes)):
            if remain >= sizes[i]:
                dfs(remain - sizes[i], path + [sizes[i]], i)
    dfs(total_pulls, [], 0)
    return res

def get_unique_permutations(combo, limit=100000):
    counts = Counter(combo)
    res = []
    def dfs(path, remaining):
        if len(res) >= limit: return
        if remaining == 0:
            res.append(list(path))
            return
        for k in counts:
            if counts[k] > 0:
                counts[k] -= 1
                path.append(k)
                dfs(path, remaining - 1)
                path.pop()
                counts[k] += 1
    dfs([], len(combo))
    return res

def simulate_sequence(batch_sequence, start_seed, start_level, start_count, extra_chance_pct, 
                      levels_config, rarities, pets_by_rarity, target_substats):
    current_seed = start_seed
    current_level = start_level
    current_count = start_count
    
    max_perfs_by_rarity = {r: {stat: 0.0 for stat in target_substats} for r in rarities}
    total_bonus = 0
    
    rarity_counts = {r: 0 for r in rarities}

    for batch_size in batch_sequence:
        total_target_pulls = batch_size 
        current_pull_idx = 0

        while current_pull_idx < total_target_pulls:
            is_bonus_pull = current_pull_idx >= batch_size

            bonus_proc, rolled_rarity, perfs = get_pull_result(
                current_seed, current_level, is_bonus_pull, extra_chance_pct, 
                levels_config, rarities, pets_by_rarity, tuple(target_substats)
            )

            if bonus_proc:
                total_target_pulls += 1
                total_bonus += 1

            rarity_counts[rolled_rarity] += 1

            for stat, perf in perfs.items():
                if perf > max_perfs_by_rarity[rolled_rarity][stat]:
                    max_perfs_by_rarity[rolled_rarity][stat] = perf

            current_count += 1
            lvl_idx = min(current_level, len(levels_config) - 1)
            summons_required = levels_config[lvl_idx].get("SummonsRequired", 9999)
            
            if current_count >= summons_required:
                current_count -= summons_required
                current_level += 1
                
            current_seed += 1
            current_pull_idx += 1
            
    return max_perfs_by_rarity, total_bonus, rarity_counts

def main():
    print("="*75)
    print("⚡ Forge Master 펫 종결 옵티마이저 (Lightning Cached) ⚡")
    print("="*75)

    try:
        summon_config, pet_library = load_data()
    except FileNotFoundError:
        print("에러: JSON 파일을 찾을 수 없습니다.")
        return

    seed_input = input("현재 Seed 값(HEX16): ").strip()
    state_input = input("현재 Level/Count(HEX16): ").strip()
    extra_chance_pct = float(input("테크트리 추가 소환 확률(%) (예: 20.0): ").strip())
    
    total_eggs = int(input("\n현재 보유 중인 알(Eggshells) 개수 (예: 3000): ").strip())
    total_pulls = total_eggs // 100
    print(f"▶ 총 {total_pulls}번의 소환 기회가 있습니다.")

    rarities = ["Common", "Rare", "Epic", "Legendary", "Ultimate", "Mythic"]
    
    print(f"\n[목표 서브스탯 선택]")
    for i, s in enumerate(SUBSTATS_LIST):
        print(f"{i+1:>2}. {s}")
    sub_inputs = input("\n원하는 서브스탯 번호를 쉼표로 구분해 모두 입력 (예: 5,6,10)\n> ").strip().split(',')
    target_substats = [SUBSTATS_LIST[int(x.strip())-1] for x in sub_inputs]
    
    combo_size = min(len(target_substats), 3)
    target_combos = list(itertools.combinations(target_substats, combo_size))
    
    print(f"\n✅ 타겟 설정: 가장 높은 등급을 우선 추적합니다.")
    print(f"✅ 총 {len(target_substats)}개의 스탯을 선택하셨습니다. (최대 3슬롯 기준 {len(target_combos)}개의 서브스탯 조합 평가)\n")

    current_seed = int(seed_input, 16)
    state_val = int(state_input, 16)
    current_level = (state_val >> 32) & 0xFFFFFFFF
    current_count = state_val & 0xFFFFFFFF

    levels_config = summon_config["Levels"]
    pets_by_rarity = {r: [] for r in rarities}
    for key, data in sorted(pet_library.items(), key=lambda x: x[1]["PetId"]["Id"]):
        r = data["PetId"]["Rarity"]
        pets_by_rarity[r].append(key)

    combinations = get_batch_combinations(total_pulls)
    all_sequences = []
    for combo in combinations:
        perms = get_unique_permutations(combo)
        all_sequences.extend(perms)

    total_seqs = len(all_sequences)
    print(f"🚀 총 {total_seqs}개의 경우의 수 탐색 시작...\n")

    PULL_CACHE.clear()

    results = []
    spinner = itertools.cycle(['..\\', '..|', '../', '..-'])
    
    for i, seq in enumerate(all_sequences):
        if i % 5000 == 0:
            sys.stdout.write(f"\r🔍 탐색 중 {next(spinner)} ({i}/{total_seqs}) - {(i/total_seqs)*100:.1f}% 진행됨")
            sys.stdout.flush()

        perfs_by_rarity, t_bonus, r_counts = simulate_sequence(
            seq, current_seed, current_level, current_count, extra_chance_pct, 
            levels_config, rarities, pets_by_rarity, target_substats
        )
        
        results.append({
            "sequence": seq,
            "perfs_by_rarity": perfs_by_rarity,
            "total_bonus": t_bonus,
            "rarity_counts": r_counts 
        })

    sys.stdout.write(f"\r✅ 탐색 완료!{' '*40}\n\n")
    sys.stdout.flush()

    print("🏆 [서브스탯 조합별 최적의 뽑기 순서] 🏆")
    for i, combo in enumerate(target_combos):
        def combo_score_fn(res):
            perfs = res["perfs_by_rarity"]
            for r in reversed(rarities):
                score = sum(perfs[r][stat] for stat in combo)
                if score > 0: 
                    return (RARITY_SCORE[r], score, res["total_bonus"], r)
            return (0, 0.0, res["total_bonus"], "None")
            
        best_res = max(results, key=combo_score_fn)
        best_eval = combo_score_fn(best_res)
        
        best_rarity = best_eval[3]
        best_score = best_eval[1]
        
        best_rarity_count = best_res["rarity_counts"][best_rarity] if best_rarity != "None" else 0
        
        seq_str = " -> ".join([f"{x}뽑" for x in best_res["sequence"]])
        combo_str = ", ".join(combo)
        
        print(f"\n[{i+1}] 🎯 타겟 조합: [{combo_str}]")
        if best_rarity == "None":
            print("   ▶ 이 경로에서는 해당 조합을 획득할 수 없습니다.")
            continue
            
        rarity_tag = f"[{best_rarity}]"
        if best_rarity in ["Legendary", "Ultimate", "Mythic"]: rarity_tag = f"🔥 {rarity_tag}"
        elif best_rarity == "Epic": rarity_tag = f"🌟 {rarity_tag}"
        
        print(f"   ▶ 추천 순서: {seq_str}")
        print(f"   ▶ 최고 도달: {rarity_tag} (총 {best_rarity_count}마리) | 합산 점수: {best_score:.2f}점")
        
        perf_details = []
        for stat in combo:
            val = best_res["perfs_by_rarity"][best_rarity][stat]
            if val > 0:
                actual_val = get_substat_value(stat, val / 100.0)
                perf_details.append(f"{stat}: +{actual_val*100:.2f}% (완성도 {val:.1f}%)")
            else:
                perf_details.append(f"{stat}: 획득 실패")
        print(f"   ▶ 스탯 상세: " + " | ".join(perf_details))
        print(f"   ▶ (참고) 이 경로의 추가 보너스: +{best_res['total_bonus']}회")

    print("\n" + "="*65)
    print("🎁 [최다 보너스 소환 (스노우볼링 우선) 경로] 🎁")
    
    def bonus_score_fn(res):
        best_r_score = 0
        best_perf = 0.0
        best_r_name = "Common"
        for r in reversed(rarities):
            s = sum(res["perfs_by_rarity"][r].values())
            if s > 0:
                best_r_score = RARITY_SCORE[r]
                best_perf = s
                best_r_name = r
                break
        return (res["total_bonus"], best_r_score, best_perf, best_r_name)
        
    best_bonus_res = max(results, key=bonus_score_fn)
    bonus_eval = bonus_score_fn(best_bonus_res)
    bonus_rarity = bonus_eval[3]
    bonus_rarity_count = best_bonus_res["rarity_counts"][bonus_rarity]

    seq_str = " -> ".join([f"{x}뽑" for x in best_bonus_res["sequence"]])
    print(f"   ▶ 추천 순서: {seq_str}")
    print(f"   ▶ 총 보너스: +{best_bonus_res['total_bonus']}회")
    
    perf_details = []
    if bonus_rarity != "Common" or sum(best_bonus_res["perfs_by_rarity"]["Common"].values()) > 0:
        for stat in target_substats:
            val = best_bonus_res["perfs_by_rarity"][bonus_rarity][stat]
            if val > 0:
                actual_val = get_substat_value(stat, val / 100.0)
                perf_details.append(f"{stat}: +{actual_val*100:.2f}%")
    
    if not perf_details:
        perf_details.append("타겟 스탯 획득 없음")
        
    print(f"   ▶ (참고) 획득한 최고 스탯 ({bonus_rarity}, 총 {bonus_rarity_count}마리): " + " | ".join(perf_details))

if __name__ == "__main__":
    main()