import subprocess
import re
import csv
import time
import argparse
import os
import pandas as pd
from pathlib import Path
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────────
JAVA = "/home/fedo/.jdks/openjdk-25.0.2/bin/java"
MTSA_JAR = "/home/fedo/Desktop/Tesis/MTSADOS/mtsa/maven-root/mtsa/target/mtsa-1.0-SNAPSHOT.jar"
GENERALIZED_CLI_CLASS = "MTSTools.ac.ic.doc.mtstools.model.operations.DCS.partialOrderReduction.generalization.handMadeBenchmarks.PORGeneralizedCLI"
TIMEOUT_SECONDS = 30 * 60  # 30 minutes
FSP_BENCHMARK_DIR = "/home/fedo/Desktop/Tesis/MTSADOS/mtsa/maven-root/mtsa/src/test/benchmarks/OTF-NonBlockingBenchmark/fsp"
EXP_DIR = "/home/fedo/Desktop/Tesis/Experimentacion"
CSV_FILE = os.path.join(EXP_DIR, f"resultados_experimentacion.csv")
MAX_N = 15
MAX_K = 15
# ──────────────────────────────────────────────────────────────────────────────





ALGORITHMS = [
    "MonolithicController",
    "DirectedController",
    "PORController",
    "PORGeneralizedController",
]

PROBLEMS = [
    "AT",
    "CM",
    "BW"
]

n_values = range(1,MAX_N + 1)
k_values = range(1,MAX_K + 1)

def parse_output(output: str) -> dict:                                                                                               
      def extract_number(pattern, cast=None):
          m = re.search(pattern, output)                                                                                               
          if not m:
              return None                                                                                                              
          return cast(m.group(1)) if cast else m.group(1)                                                                              
   
      def extract_memory_mb():                                                                                                         
          m = re.search(r"maxMemoryUsed:\s*([\d.]+)\s*(MB|KB|GB)?", output)
          if not m:                                                                                                                    
              return None
          value = float(m.group(1))                                                                                                    
          unit = m.group(2)
          if unit == "KB":
              return value / 1024
          elif unit == "GB":
              return value * 1024                                                                                                      
          return value  # MB o sin unidad
                                                                                                                                       
      def extract_time_ms(pattern):                                                                                                    
          m = re.search(pattern + r"\s*(ms|s)?", output)
          if not m:                                                                                                                    
              return None
          value = float(m.group(1))                                                                                                    
          unit = m.group(2)
          if unit == "s":
              return int(value * 1000)                                                                                                 
          return int(value)  # ms o sin unidad
                                                                                                                                       
      return {    
          "synthesis_time_ms":    extract_time_ms(r"Elapsed in Synthesis:\s*(\d+)"),
          "max_memory_mb":        extract_memory_mb(),                                                                                 
          "expanded_states":      extract_number(r"ExpandedStates:\s*(\d+)", int),
          "used_states":          extract_number(r"UsedStates:\s*(\d+)", int),                                                         
          "expanded_transitions": extract_number(r"ExpandedTransitions:\s*(\d+)", int),
          "used_transitions":     extract_number(r"UsedTransitions:\s*(\d+)", int),                                                    
          "heuristic_time_ms":    extract_time_ms(r"heuristicTime:\s*(\d+)"),
      }

def case_file(problem, n, k):
    return f"{FSP_BENCHMARK_DIR}/{problem}/{problem}-{n}-{k}.fsp"  

def run_case(problem, n, k, algorithm) -> dict:
    cmd = [
        JAVA, "-cp", MTSA_JAR,
        "-Dfile.encoding=UTF-8",
        "-Dsun.stdout.encoding=UTF-8",
        "-Dsun.stderr.encoding=UTF-8",
        "ltsa.ui.LTSABatch", "-i", case_file(problem, n, k), "-c", algorithm,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        output = proc.stdout + proc.stderr
        if proc.returncode != 0 or "OutOfMemoryError" in output:
              return "OM", None
        return "OK", parse_output(output)
    except subprocess.TimeoutExpired:
        return "TO", None

# Corre PORController pero sin calcular el isomorfismo con IsomorphismCalculator: arma los LTSs y los
# grupos de isomorfismo directo con el generador a mano de cada problema (ver PORGeneralizedCLI), para
# poder comparar el tiempo de síntesis sin que el cálculo del isomorfismo lo infle.
def run_case_without_isomorphism(problem, n, k) -> dict:
    cmd = [
        JAVA, "-cp", MTSA_JAR,
        "-Dfile.encoding=UTF-8",
        "-Dsun.stdout.encoding=UTF-8",
        "-Dsun.stderr.encoding=UTF-8",
        GENERALIZED_CLI_CLASS, problem, str(n), str(k),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        output = proc.stdout + proc.stderr
        if proc.returncode != 0 or "OutOfMemoryError" in output:
              return "OM", None
        return "OK", parse_output(output)
    except subprocess.TimeoutExpired:
        return "TO", None

FIELDNAMES = [
    "problema", "n", "k", "algoritmo", "status",
    "synthesis_time_ms", "max_memory_mb", "expanded_states", "used_states",
    "expanded_transitions", "used_transitions", "heuristic_time_ms",
]

def append_row(row: dict):
    write_header = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore", restval="")
        if write_header:
            writer.writeheader()
        writer.writerow(row)

# Corre run_fn(p, n, k) y lo guarda en la tabla bajo el nombre de algoritmo "algo", salvo que ese caso
# ya esté calculado (retomando desde el CSV).
def run_and_record(rows, p, n, k, algo, run_fn):
    ya_calculado = any(r["n"] == n and r["k"] == k and r["algoritmo"] == algo and r["problema"] == p for r in rows)
    if ya_calculado:
        print(f"Ya calculado para {n} {k} {algo} {p}")
        return
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Calculando para... {p}-{n}-{k} con {algo}")
    status, metrics = run_fn(p, n, k)
    new_row = {"problema": p, "n": n, "k": k, "algoritmo": algo, "status": status}
    if metrics:
        new_row.update(metrics)
    rows.append(new_row)
    append_row(new_row)

def run_experiment():
    # Cargar resultados previos si existen
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        rows = df.to_dict("records")
        print(f"Retomando desde {CSV_FILE} ({len(rows)} casos ya calculados)")
    else:
        rows = []

    for p in PROBLEMS:
        for n in n_values:
            for k in k_values:
                for algo in ALGORITHMS:
                    run_and_record(rows, p, n, k, algo, lambda p, n, k, algo=algo: run_case(p, n, k, algo))

                    # Además de PORController "normal", corro la misma síntesis pero sin calcular el
                    # isomorfismo (usando el generador a mano de cada problema), para poder comparar
                    # cuánto pesa ese cálculo por separado.
                    if algo == "PORController":
                        run_and_record(rows, p, n, k, "PORControllerGivenIsomorphisms", run_case_without_isomorphism)

    print("\n \nLISTO PAPU")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=MAX_N)
    parser.add_argument("-k", type=int, default=MAX_K)
    args = parser.parse_args()
    n_values = range(1, args.n + 1)
    k_values = range(1, args.k + 1)
    run_experiment()
