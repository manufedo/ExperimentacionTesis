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
TIMEOUT_SECONDS = 30 * 60  # 30 minutes
FSP_BENCHMARK_DIR = "/home/fedo/Desktop/Tesis/MTSADOS/mtsa/maven-root/mtsa/src/test/benchmarks/OTF-NonBlockingBenchmark/fsp"
EXP_DIR = "/home/fedo/Desktop/Tesis/Experimentacion"
CSV_FILE = os.path.join(EXP_DIR, f"resultados_experimentacion.csv")
MAX_N = 4
MAX_K = 4
# ──────────────────────────────────────────────────────────────────────────────





ALGORITHMS = [
    "MonolithicController",
    "DirectedController",
    "PORController",
    "PORGeneralizedController",
]

PROBLEMS = [
    "AT"
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
                    ya_calculado = any(r["n"] == n and r["k"] == k and r["algoritmo"] == algo and r["problema"] == p for r in rows)
                    if ya_calculado:
                        print(f"Ya calculado para {n} {k} {algo} {p}")
                        continue
                    print(f"Calculando para... {p}-{n}-{k} con {algo}")
                    status, metrics = run_case(p, n, k, algo)
                    new_row = {"problema": p, "n": n, "k": k, "algoritmo": algo, "status": status}
                    if metrics:
                        new_row.update(metrics)
                    rows.append(new_row)
                    append_row(new_row)

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
