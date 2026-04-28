"""
Core DES Simulation Module — Antrean Pasien IGD
Extracted for use by Flask web API.
"""

import simpy
import random
import numpy as np

RANDOM_SEED = 42

WAKTU_TRIAGE_MEAN = 5
WAKTU_PERIKSA_MEAN = {"Merah": 30, "Kuning": 20, "Hijau": 10}
WAKTU_TREATMENT_MEAN = {"Merah": 60, "Kuning": 30, "Hijau": 15}
PROPORSI_PRIORITAS = {"Merah": 0.15, "Kuning": 0.35, "Hijau": 0.50}
PRIORITY_MAP = {"Merah": 1, "Kuning": 2, "Hijau": 3}


class IGDSimulation:
    def __init__(self, env, num_perawat, num_dokter, num_bed,
                 interval_kedatangan=5, label="Baseline"):
        self.env = env
        self.label = label
        self.interval_kedatangan = interval_kedatangan
        self.perawat_triage = simpy.PriorityResource(env, capacity=num_perawat)
        self.dokter_jaga = simpy.PriorityResource(env, capacity=num_dokter)
        self.bed_igd = simpy.PriorityResource(env, capacity=num_bed)
        self.log_pasien = []
        self.antrean_snapshot = []
        self.utilisasi_dokter = []

    def tentukan_prioritas(self):
        r = random.random()
        if r < PROPORSI_PRIORITAS["Merah"]:
            return "Merah"
        elif r < PROPORSI_PRIORITAS["Merah"] + PROPORSI_PRIORITAS["Kuning"]:
            return "Kuning"
        else:
            return "Hijau"

    def proses_pasien(self, pasien_id):
        prioritas = self.tentukan_prioritas()
        priority_num = PRIORITY_MAP[prioritas]
        waktu_datang = self.env.now

        t0 = self.env.now
        with self.perawat_triage.request(priority=priority_num) as req:
            yield req
            wt_triage = self.env.now - t0
            yield self.env.timeout(max(1, random.expovariate(1.0 / WAKTU_TRIAGE_MEAN)))

        t1 = self.env.now
        with self.dokter_jaga.request(priority=priority_num) as req:
            yield req
            wt_dokter = self.env.now - t1
            yield self.env.timeout(max(1, random.expovariate(1.0 / WAKTU_PERIKSA_MEAN[prioritas])))

        t2 = self.env.now
        with self.bed_igd.request(priority=priority_num) as req:
            yield req
            wt_bed = self.env.now - t2
            yield self.env.timeout(max(1, random.expovariate(1.0 / WAKTU_TREATMENT_MEAN[prioritas])))

        total_wait = wt_triage + wt_dokter + wt_bed
        self.log_pasien.append({
            "id": pasien_id,
            "prioritas": prioritas,
            "waktu_datang": round(waktu_datang, 2),
            "wt_triage": round(wt_triage, 2),
            "wt_dokter": round(wt_dokter, 2),
            "wt_bed": round(wt_bed, 2),
            "total_wait": round(total_wait, 2),
            "total_system": round(self.env.now - waktu_datang, 2),
        })

    def generator_pasien(self):
        pid = 0
        while True:
            yield self.env.timeout(random.expovariate(1.0 / self.interval_kedatangan))
            pid += 1
            self.env.process(self.proses_pasien(pid))

    def monitor(self, interval=2):
        while True:
            qt = len(self.perawat_triage.queue)
            qd = len(self.dokter_jaga.queue)
            qb = len(self.bed_igd.queue)
            self.antrean_snapshot.append({
                "t": round(self.env.now, 1),
                "qt": qt, "qd": qd, "qb": qb, "total": qt + qd + qb,
            })
            util = self.dokter_jaga.count / self.dokter_jaga.capacity
            self.utilisasi_dokter.append({
                "t": round(self.env.now, 1),
                "u": round(util, 4),
            })
            yield self.env.timeout(interval)


def run_simulation(num_perawat, num_dokter, num_bed,
                   interval_kedatangan=5, sim_duration=480, label="Baseline"):
    random.seed(RANDOM_SEED)
    env = simpy.Environment()
    sim = IGDSimulation(env, num_perawat, num_dokter, num_bed,
                        interval_kedatangan, label)
    env.process(sim.generator_pasien())
    env.process(sim.monitor(interval=2))
    env.run(until=sim_duration)

    # Build summary
    per_prioritas = {}
    for p in ["Merah", "Kuning", "Hijau"]:
        subset = [x for x in sim.log_pasien if x["prioritas"] == p]
        waits = [x["total_wait"] for x in subset]
        sys_times = [x["total_system"] for x in subset]
        per_prioritas[p] = {
            "count": len(subset),
            "mean_wait": round(float(np.mean(waits)), 1) if waits else 0,
            "max_wait": round(float(np.max(waits)), 1) if waits else 0,
            "mean_system": round(float(np.mean(sys_times)), 1) if sys_times else 0,
            "wait_times": [round(w, 1) for w in waits],
        }

    all_waits = [x["total_wait"] for x in sim.log_pasien]
    util_values = [x["u"] for x in sim.utilisasi_dokter]

    return {
        "label": label,
        "total_pasien": len(sim.log_pasien),
        "mean_wait_all": round(float(np.mean(all_waits)), 1) if all_waits else 0,
        "max_wait_critical": per_prioritas["Merah"]["max_wait"],
        "utilisasi_mean": round(float(np.mean(util_values)) * 100, 1) if util_values else 0,
        "per_prioritas": per_prioritas,
        "antrean_t": [s["t"] for s in sim.antrean_snapshot],
        "antrean_total": [s["total"] for s in sim.antrean_snapshot],
        "antrean_triage": [s["qt"] for s in sim.antrean_snapshot],
        "antrean_dokter": [s["qd"] for s in sim.antrean_snapshot],
        "antrean_bed": [s["qb"] for s in sim.antrean_snapshot],
        "util_t": [s["t"] for s in sim.utilisasi_dokter],
        "util_v": [round(s["u"] * 100, 1) for s in sim.utilisasi_dokter],
    }
