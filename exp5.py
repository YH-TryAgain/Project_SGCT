
import os
import time
import multiprocessing
import numpy as np
import pandas as pd
from tqdm import tqdm


from Framework import run_simulation
from Tool import SimulationAnalytics
from algorithm_base_config import ALGORITHM_LIBRARY, ALGORITHMS_TO_TEST
from Tool import SimulationAnalytics


RESULTS_BASE_DIR = "results"


ALGORITHMS_TO_TEST = ["HLCT-Base", "DRCT", "EMDT", "NLHQT(n=2)"]


EXPERIMENTS_TO_RUN = [
    {
        "name": "exp5_selection_strategy_impact",
        "description": "姣旇緝 '鏈€鏃╀綅缃紭鍏? 涓?'闅忔満閫夋嫨' 绛栫暐鐨勬€ц兘宸紓",
        "varying_param_key": "TOTAL_TAGS",

        "varying_param_values": np.linspace(1000, 10000, 10, dtype=int),
        "scenario_config": {
            'BINARY_LENGTH': 96,

            'id_distribution': 'random',
        },
        "algorithm_specific_config": {
            'ber': 0.0,
            'enable_refined_energy_model': True,
            'enable_resource_monitoring': False,
        }
    },
]


NUM_RUNS_PER_POINT = 1


def run_single_task(task_params: tuple):
    """
    鎵ц鍗曟浠跨湡浠诲姟鐨勫嚱鏁般€?    """
    algo_name, scenario_config, algo_specific_config, run_id = task_params

    algo_info = ALGORITHM_LIBRARY[algo_name]
    algo_class = algo_info["class"]

    final_algo_config = {**algo_info["config"], **algo_specific_config}

    result_dict = run_simulation(
        scenario_config=scenario_config,
        algorithm_class=algo_class,
        algorithm_specific_config=final_algo_config
    )

    full_config_log = {**scenario_config, **algo_specific_config}

    return (result_dict, full_config_log, algo_name, run_id)


def main():

    for experiment in EXPERIMENTS_TO_RUN:
        exp_name = experiment["name"]
        output_dir = os.path.join(RESULTS_BASE_DIR, exp_name)
        os.makedirs(output_dir, exist_ok=True)

        print("\n" + "="*80)
        print(f"寮€濮嬫墽琛屽疄楠? {exp_name}")
        print(f"鎻忚堪: {experiment['description']}")
        print(f"瀵规瘮绠楁硶: {', '.join(ALGORITHMS_TO_TEST)}")
        print(f"鍙彉鍙傛暟: '{experiment['varying_param_key']}'")
        print(f"鍙傛暟鑼冨洿: {str(experiment['varying_param_values'])}")
        print(f"Runs per point: {NUM_RUNS_PER_POINT}")
        print("="*80)

        tasks = []
        varying_key = experiment['varying_param_key']

        for value in experiment['varying_param_values']:
            scenario_conf = experiment['scenario_config'].copy()
            scenario_conf[varying_key] = value
            algo_conf = experiment['algorithm_specific_config'].copy()

            for algo_name in ALGORITHMS_TO_TEST:
                for i in range(NUM_RUNS_PER_POINT):
                    tasks.append(
                        (algo_name, scenario_conf.copy(), algo_conf.copy(), i))

        print(f"\n浠诲姟鎬绘暟: {len(tasks)}")
        num_processes = min(2, max(1, multiprocessing.cpu_count() - 1))
        print(f"灏嗕娇鐢?{num_processes} 涓狢PU鏍稿績骞惰鎵ц...")

        analytics = SimulationAnalytics()
        start_time = time.time()

        with multiprocessing.Pool(processes=num_processes) as pool:
            results_iterator = pool.imap_unordered(run_single_task, tasks)
            for result_tuple in tqdm(results_iterator, total=len(tasks), desc=f"鎵ц [{exp_name}]"):
                analytics.add_run_result(*result_tuple)

        end_time = time.time()
        print(f"\nExperiment [{exp_name}] completed. Total elapsed time: {end_time - start_time:.2f} s")

        print("\n姝ｅ湪澶勭悊鍜屽垎鏋愭暟鎹?..")

        analytics.save_to_csv(x_axis_key=varying_key, output_dir=output_dir)
        analytics.plot_results(
            x_axis_key=varying_key,
            algorithm_library=ALGORITHM_LIBRARY,
            save_path=os.path.join(output_dir, f"{exp_name}_plot.png")
        )

        print(f"\nExperiment [{exp_name}] finished.")
        print(f"All results saved to: {output_dir}")


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()

