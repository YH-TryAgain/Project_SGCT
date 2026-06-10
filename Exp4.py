import multiprocessing
import os
import time

from tqdm import tqdm

from Framework import run_simulation
from Tool import SimulationAnalytics
from algorithm_base_config import ALGORITHM_LIBRARY


RESULTS_BASE_DIR = "results"
EXPERIMENT_NAME = "exp4_sg_suffix_tuning"
OUTPUT_DIR = os.path.join(RESULTS_BASE_DIR, EXPERIMENT_NAME)
os.makedirs(OUTPUT_DIR, exist_ok=True)


SUFFIX_D_VALUES = [8, 10, 12]
ALGORITHMS_TO_TUNE = [f"SGCT(suffix_d={value})" for value in SUFFIX_D_VALUES]
BASELINE_ALGORITHMS_TO_TEST = ["HLCT-Base", "DRCT", "EMDT", "NLHQT(n=2)"]


SCENARIO_CONFIG = {
    "TOTAL_TAGS": 4000,
    "BINARY_LENGTH": 96,
    "id_distribution": "prefixed",
    "prefix_length": 80,
}


ALGORITHM_CONFIG = {
    "ber": 0.0,
    "enable_refined_energy_model": True,
    "enable_resource_monitoring": True,
}


NUM_RUNS_PER_POINT = 1


def run_single_task(task_params: tuple):
    algo_name, scenario_config, algo_specific_config, run_id, algo_class = task_params

    result_dict = run_simulation(
        scenario_config=scenario_config,
        algorithm_class=algo_class,
        algorithm_specific_config=algo_specific_config,
    )

    full_config_log = {**scenario_config, **algo_specific_config}
    return (result_dict, full_config_log, algo_name, run_id)


def main():
    print("\n" + "=" * 80)
    print(f"寮€濮嬪疄楠? {EXPERIMENT_NAME}")
    print("Experiment purpose: tune SGCT suffix extension width and compare with baselines")
    print(f"鍥哄畾鍦烘櫙: {SCENARIO_CONFIG}")
    print(f"suffix_signature_d_max 鑼冨洿: {SUFFIX_D_VALUES}")
    print("=" * 80)

    tasks = []
    dynamic_algorithm_library = {}
    pb_info = ALGORITHM_LIBRARY["SGCT"]

    for suffix_d in SUFFIX_D_VALUES:
        algo_name = f"SGCT(suffix_d={suffix_d})"
        algo_conf = {
            **pb_info["config"],
            **ALGORITHM_CONFIG,
            "suffix_signature_d_max": suffix_d,
            "suffix_signature_slot_cap": 1 << suffix_d,
            "suffix_signature_min_tags_per_slot": 0.0,
        }
        dynamic_algorithm_library[algo_name] = {
            **pb_info,
            "config": algo_conf,
        }
        for i in range(NUM_RUNS_PER_POINT):
            tasks.append((algo_name, SCENARIO_CONFIG.copy(), algo_conf.copy(), i, pb_info["class"]))

        for baseline_name in BASELINE_ALGORITHMS_TO_TEST:
            baseline_info = ALGORITHM_LIBRARY[baseline_name]
            baseline_conf = {
                **baseline_info["config"],
                **ALGORITHM_CONFIG,
                "suffix_signature_d_max": suffix_d,
            }
            dynamic_algorithm_library[baseline_name] = baseline_info
            for i in range(NUM_RUNS_PER_POINT):
                tasks.append((baseline_name, SCENARIO_CONFIG.copy(), baseline_conf.copy(), i, baseline_info["class"]))

    print(f"\n浠诲姟鎬绘暟: {len(tasks)}")
    num_processes = min(2, max(1, multiprocessing.cpu_count() - 1))
    print(f"灏嗕娇鐢?{num_processes} 涓狢PU鏍稿績骞惰鎵ц...")

    analytics = SimulationAnalytics()
    start_time = time.time()

    with multiprocessing.Pool(processes=num_processes) as pool:
        results_iterator = pool.imap_unordered(run_single_task, tasks)
        for result_tuple in tqdm(results_iterator, total=len(tasks), desc=f"鎵ц [{EXPERIMENT_NAME}]"):
            analytics.add_run_result(*result_tuple)

    end_time = time.time()
    print(f"\nAll simulation tasks completed. Total elapsed time: {end_time - start_time:.2f} s")
    print("\nProcessing and analyzing data...")

    x_axis_key = "suffix_signature_d_max"
    analytics.save_to_csv(x_axis_key=x_axis_key, output_dir=OUTPUT_DIR)
    analytics.plot_results(
        x_axis_key=x_axis_key,
        algorithm_library=dynamic_algorithm_library,
        save_path=os.path.join(OUTPUT_DIR, f"{EXPERIMENT_NAME}_plot.png"),
    )

    print("\nExperiment completed.")
    print(f"All CSV files and plots have been saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()


