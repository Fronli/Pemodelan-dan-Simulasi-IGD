"""
=============================================================================
Simulasi Antrean Pasien IGD Saat Lonjakan Kasus (DBD/Virus Musiman)
=============================================================================
Jenis  : Discrete Event Simulation (DES)
Library: SimPy, Pandas, Matplotlib
Penulis: [Nama Anda]
Tanggal: 2026-04-21

Deskripsi:
    Model simulasi alur penanganan pasien IGD untuk meminimalisir
    waktu tunggu (waiting time) saat lonjakan kasus musiman.

Entitas:
    - Pasien dibagi 3 prioritas:
        * Merah  (priority=1) : Gawat Darurat
        * Kuning (priority=2) : Sedang
        * Hijau  (priority=3) : Ringan

Resources:
    - Perawat Triage
    - Dokter Jaga
    - Bed IGD

What-If Scenarios:
    1. Tambah 1 Dokter vs Tambah 2 Perawat saat peak hour
    2. Kedatangan pasien melonjak 2x lipat (skenario wabah)
=============================================================================
"""

import simpy
import random
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from collections import defaultdict

# Gunakan "TkAgg" untuk menampilkan grafik sebagai window pop-up
# Ganti ke "Agg" jika ingin menyimpan file tanpa menampilkan pop-up
matplotlib.use("TkAgg")

# ============================================================================
# KONFIGURASI SIMULASI
# ============================================================================

RANDOM_SEED = 42
SIM_DURATION = 480  # durasi simulasi dalam menit (8 jam = 1 shift)

# --- Konfigurasi Resource (Baseline / Skenario Normal) ---
NUM_PERAWAT_TRIAGE = 2   # jumlah perawat triage
NUM_DOKTER_JAGA    = 3   # jumlah dokter jaga
NUM_BED_IGD        = 10  # jumlah bed IGD

# --- Waktu Proses (dalam menit, distribusi eksponensial) ---
WAKTU_TRIAGE_MEAN       = 5    # rata-rata waktu triage per pasien
WAKTU_PERIKSA_MEAN      = {    # rata-rata waktu pemeriksaan dokter
    "Merah":  30,   # pasien gawat → pemeriksaan lebih lama
    "Kuning": 20,
    "Hijau":  10,
}
WAKTU_TREATMENT_MEAN    = {    # rata-rata waktu perawatan di bed
    "Merah":  60,
    "Kuning": 30,
    "Hijau":  15,
}

# --- Kedatangan Pasien ---
INTERVAL_KEDATANGAN = 5  # rata-rata interval kedatangan (menit)

# --- Proporsi Prioritas Pasien ---
PROPORSI_PRIORITAS = {
    "Merah":  0.15,  # 15% kasus gawat
    "Kuning": 0.35,  # 35% kasus sedang
    "Hijau":  0.50,  # 50% kasus ringan
}

# Mapping prioritas ke angka (untuk PriorityResource SimPy: makin kecil = makin prioritas)
PRIORITY_MAP = {"Merah": 1, "Kuning": 2, "Hijau": 3}


# ============================================================================
# MODEL SIMULASI
# ============================================================================

class IGDSimulation:
    """
    Model simulasi IGD menggunakan SimPy.

    Alur pasien:
        Datang → Triage (perawat) → Pemeriksaan (dokter) → Perawatan (bed) → Keluar

    Resources menggunakan PriorityResource agar pasien Merah didahulukan.
    """

    def __init__(self, env, num_perawat, num_dokter, num_bed,
                 interval_kedatangan=INTERVAL_KEDATANGAN,
                 label="Baseline"):
        self.env = env
        self.label = label
        self.interval_kedatangan = interval_kedatangan

        # Resources dengan sistem prioritas
        self.perawat_triage = simpy.PriorityResource(env, capacity=num_perawat)
        self.dokter_jaga    = simpy.PriorityResource(env, capacity=num_dokter)
        self.bed_igd        = simpy.PriorityResource(env, capacity=num_bed)

        # Data collection
        self.log_pasien = []          # log lengkap setiap pasien
        self.antrean_snapshot = []    # snapshot panjang antrean setiap waktu
        self.utilisasi_dokter = []    # snapshot utilisasi dokter

    def tentukan_prioritas(self):
        """Tentukan prioritas pasien berdasarkan proporsi yang ditentukan."""
        r = random.random()
        if r < PROPORSI_PRIORITAS["Merah"]:
            return "Merah"
        elif r < PROPORSI_PRIORITAS["Merah"] + PROPORSI_PRIORITAS["Kuning"]:
            return "Kuning"
        else:
            return "Hijau"

    def proses_pasien(self, pasien_id):
        """
        Proses satu pasien melalui alur IGD:
            1. Triage oleh perawat
            2. Pemeriksaan oleh dokter
            3. Perawatan di bed IGD
        """
        prioritas = self.tentukan_prioritas()
        priority_num = PRIORITY_MAP[prioritas]
        waktu_datang = self.env.now

        # --- TAHAP 1: TRIAGE ---
        waktu_mulai_tunggu_triage = self.env.now
        with self.perawat_triage.request(priority=priority_num) as req:
            yield req
            waktu_tunggu_triage = self.env.now - waktu_mulai_tunggu_triage
            waktu_triage = max(1, random.expovariate(1.0 / WAKTU_TRIAGE_MEAN))
            yield self.env.timeout(waktu_triage)

        # --- TAHAP 2: PEMERIKSAAN DOKTER ---
        waktu_mulai_tunggu_dokter = self.env.now
        with self.dokter_jaga.request(priority=priority_num) as req:
            yield req
            waktu_tunggu_dokter = self.env.now - waktu_mulai_tunggu_dokter
            waktu_periksa = max(1, random.expovariate(1.0 / WAKTU_PERIKSA_MEAN[prioritas]))
            yield self.env.timeout(waktu_periksa)

        # --- TAHAP 3: PERAWATAN DI BED ---
        waktu_mulai_tunggu_bed = self.env.now
        with self.bed_igd.request(priority=priority_num) as req:
            yield req
            waktu_tunggu_bed = self.env.now - waktu_mulai_tunggu_bed
            waktu_treatment = max(1, random.expovariate(1.0 / WAKTU_TREATMENT_MEAN[prioritas]))
            yield self.env.timeout(waktu_treatment)

        # --- PASIEN SELESAI ---
        waktu_keluar = self.env.now
        total_waktu_tunggu = waktu_tunggu_triage + waktu_tunggu_dokter + waktu_tunggu_bed
        total_waktu_sistem = waktu_keluar - waktu_datang

        self.log_pasien.append({
            "Pasien_ID":            pasien_id,
            "Prioritas":            prioritas,
            "Waktu_Datang":         round(waktu_datang, 2),
            "Waktu_Tunggu_Triage":  round(waktu_tunggu_triage, 2),
            "Waktu_Tunggu_Dokter":  round(waktu_tunggu_dokter, 2),
            "Waktu_Tunggu_Bed":     round(waktu_tunggu_bed, 2),
            "Total_Waktu_Tunggu":   round(total_waktu_tunggu, 2),
            "Total_Waktu_Sistem":   round(total_waktu_sistem, 2),
            "Waktu_Keluar":         round(waktu_keluar, 2),
        })

    def generator_pasien(self):
        """Generator kedatangan pasien ke IGD."""
        pasien_id = 0
        while True:
            # Interval kedatangan mengikuti distribusi eksponensial
            interval = random.expovariate(1.0 / self.interval_kedatangan)
            yield self.env.timeout(interval)
            pasien_id += 1
            self.env.process(self.proses_pasien(pasien_id))

    def monitor(self, interval=1):
        """
        Monitor utilisasi resource dan panjang antrean setiap `interval` menit.
        """
        while True:
            # Panjang antrean = jumlah yang menunggu di masing-masing resource
            q_triage = len(self.perawat_triage.queue)
            q_dokter = len(self.dokter_jaga.queue)
            q_bed    = len(self.bed_igd.queue)

            self.antrean_snapshot.append({
                "Waktu":          round(self.env.now, 2),
                "Antrean_Triage": q_triage,
                "Antrean_Dokter": q_dokter,
                "Antrean_Bed":    q_bed,
                "Total_Antrean":  q_triage + q_dokter + q_bed,
            })

            # Utilisasi dokter = jumlah dokter yang sedang dipakai / total dokter
            utilisasi = self.dokter_jaga.count / self.dokter_jaga.capacity
            self.utilisasi_dokter.append({
                "Waktu":     round(self.env.now, 2),
                "Utilisasi": round(utilisasi, 4),
            })

            yield self.env.timeout(interval)


def jalankan_simulasi(num_perawat, num_dokter, num_bed,
                      interval_kedatangan=INTERVAL_KEDATANGAN,
                      sim_duration=SIM_DURATION,
                      label="Baseline"):
    """
    Jalankan satu skenario simulasi dan kembalikan hasilnya.

    Returns:
        dict: {
            'label': str,
            'df_pasien': DataFrame,
            'df_antrean': DataFrame,
            'df_utilisasi': DataFrame,
        }
    """
    random.seed(RANDOM_SEED)
    env = simpy.Environment()
    sim = IGDSimulation(env, num_perawat, num_dokter, num_bed,
                        interval_kedatangan=interval_kedatangan,
                        label=label)

    env.process(sim.generator_pasien())
    env.process(sim.monitor(interval=1))
    env.run(until=sim_duration)

    df_pasien    = pd.DataFrame(sim.log_pasien)
    df_antrean   = pd.DataFrame(sim.antrean_snapshot)
    df_utilisasi = pd.DataFrame(sim.utilisasi_dokter)

    return {
        "label":        label,
        "df_pasien":    df_pasien,
        "df_antrean":   df_antrean,
        "df_utilisasi": df_utilisasi,
    }


# ============================================================================
# FUNGSI ANALISIS & VISUALISASI
# ============================================================================

def cetak_ringkasan(hasil):
    """Cetak ringkasan statistik dari hasil simulasi."""
    label = hasil["label"]
    df    = hasil["df_pasien"]
    df_u  = hasil["df_utilisasi"]

    print(f"\n{'='*60}")
    print(f"  RINGKASAN: {label}")
    print(f"{'='*60}")
    print(f"  Total pasien dilayani  : {len(df)}")

    if len(df) == 0:
        print("  (Tidak ada data pasien)")
        return

    print(f"\n  --- Rata-rata Waktu Tunggu (menit) per Prioritas ---")
    for p in ["Merah", "Kuning", "Hijau"]:
        subset = df[df["Prioritas"] == p]
        if len(subset) > 0:
            mean_wait = subset["Total_Waktu_Tunggu"].mean()
            max_wait  = subset["Total_Waktu_Tunggu"].max()
            print(f"    {p:8s}: Mean = {mean_wait:6.1f} | Max = {max_wait:6.1f} | N = {len(subset)}")

    print(f"\n  --- Rata-rata Total Waktu di Sistem (menit) ---")
    for p in ["Merah", "Kuning", "Hijau"]:
        subset = df[df["Prioritas"] == p]
        if len(subset) > 0:
            mean_sys = subset["Total_Waktu_Sistem"].mean()
            print(f"    {p:8s}: {mean_sys:.1f}")

    if len(df_u) > 0:
        mean_util = df_u["Utilisasi"].mean()
        print(f"\n  --- Utilisasi Dokter ---")
        print(f"    Rata-rata: {mean_util*100:.1f}%")

    print(f"{'='*60}\n")


def plot_perbandingan_waktu_tunggu(hasil_list):
    """
    Plot perbandingan rata-rata waktu tunggu per prioritas
    untuk semua skenario.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    prioritas_list = ["Merah", "Kuning", "Hijau"]
    warna = {"Merah": "#e74c3c", "Kuning": "#f39c12", "Hijau": "#27ae60"}
    x = np.arange(len(prioritas_list))
    width = 0.8 / len(hasil_list)

    for i, hasil in enumerate(hasil_list):
        df = hasil["df_pasien"]
        means = []
        for p in prioritas_list:
            subset = df[df["Prioritas"] == p]
            means.append(subset["Total_Waktu_Tunggu"].mean() if len(subset) > 0 else 0)

        bars = ax.bar(x + i * width, means, width,
                      label=hasil["label"], alpha=0.85, edgecolor="white")

        # Tambahkan label nilai di atas bar
        for bar, val in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    f"{val:.1f}", ha="center", va="bottom", fontsize=8, fontweight="bold")

    ax.set_xlabel("Prioritas Pasien", fontsize=12)
    ax.set_ylabel("Rata-rata Waktu Tunggu (menit)", fontsize=12)
    ax.set_title("Perbandingan Waktu Tunggu per Prioritas — Semua Skenario", fontsize=14, fontweight="bold")
    ax.set_xticks(x + width * (len(hasil_list) - 1) / 2)
    ax.set_xticklabels(prioritas_list)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig("c:/Users/Fronli/CODE/Kuliah/PS/grafik_waktu_tunggu.png", dpi=150)
    plt.show()


def plot_panjang_antrean(hasil_list):
    """
    Plot panjang total antrean dari waktu ke waktu untuk semua skenario.
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    for hasil in hasil_list:
        df_q = hasil["df_antrean"]
        if len(df_q) > 0:
            ax.plot(df_q["Waktu"], df_q["Total_Antrean"],
                    label=hasil["label"], alpha=0.8, linewidth=1.2)

    ax.set_xlabel("Waktu Simulasi (menit)", fontsize=12)
    ax.set_ylabel("Total Pasien dalam Antrean", fontsize=12)
    ax.set_title("Panjang Antrean IGD dari Waktu ke Waktu", fontsize=14, fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("c:/Users/Fronli/CODE/Kuliah/PS/grafik_antrean.png", dpi=150)
    plt.show()


def plot_utilisasi_dokter(hasil_list):
    """
    Plot utilisasi dokter dari waktu ke waktu untuk semua skenario.
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    for hasil in hasil_list:
        df_u = hasil["df_utilisasi"]
        if len(df_u) > 0:
            # Gunakan rolling average agar grafik lebih smooth
            window = min(30, max(1, len(df_u) // 10))
            smoothed = df_u["Utilisasi"].rolling(window=window, min_periods=1).mean()
            ax.plot(df_u["Waktu"], smoothed * 100,
                    label=hasil["label"], alpha=0.8, linewidth=1.2)

    ax.set_xlabel("Waktu Simulasi (menit)", fontsize=12)
    ax.set_ylabel("Utilisasi Dokter (%)", fontsize=12)
    ax.set_title("Utilisasi Dokter Jaga dari Waktu ke Waktu", fontsize=14, fontweight="bold")
    ax.axhline(y=100, color="red", linestyle="--", alpha=0.5, label="Kapasitas Penuh")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_ylim(0, 110)
    plt.tight_layout()
    plt.savefig("c:/Users/Fronli/CODE/Kuliah/PS/grafik_utilisasi.png", dpi=150)
    plt.show()


def plot_distribusi_waktu_tunggu(hasil):
    """
    Plot distribusi (histogram) waktu tunggu per prioritas untuk satu skenario.
    """
    df = hasil["df_pasien"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

    warna = {"Merah": "#e74c3c", "Kuning": "#f39c12", "Hijau": "#27ae60"}

    for ax, p in zip(axes, ["Merah", "Kuning", "Hijau"]):
        subset = df[df["Prioritas"] == p]["Total_Waktu_Tunggu"]
        if len(subset) > 0:
            ax.hist(subset, bins=20, color=warna[p], alpha=0.7, edgecolor="white")
            ax.axvline(subset.mean(), color="black", linestyle="--", linewidth=1.5,
                       label=f"Mean = {subset.mean():.1f}")
            ax.legend()
        ax.set_title(f"Prioritas {p}", fontsize=13, fontweight="bold")
        ax.set_xlabel("Waktu Tunggu (menit)")
        ax.grid(axis="y", alpha=0.3)

    axes[0].set_ylabel("Jumlah Pasien")
    fig.suptitle(f"Distribusi Waktu Tunggu — {hasil['label']}", fontsize=15, fontweight="bold")
    plt.tight_layout()
    plt.savefig("c:/Users/Fronli/CODE/Kuliah/PS/grafik_distribusi.png", dpi=150)
    plt.show()


# ============================================================================
# MAIN — JALANKAN SEMUA SKENARIO
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  SIMULASI ANTREAN PASIEN IGD")
    print("  Discrete Event Simulation (DES) dengan SimPy")
    print("=" * 60)

    # ------------------------------------------------------------------
    # SKENARIO BASELINE: Kondisi normal
    # ------------------------------------------------------------------
    print("\n[1/4] Menjalankan Skenario BASELINE...")
    baseline = jalankan_simulasi(
        num_perawat=NUM_PERAWAT_TRIAGE,
        num_dokter=NUM_DOKTER_JAGA,
        num_bed=NUM_BED_IGD,
        label="Baseline (Normal)"
    )
    cetak_ringkasan(baseline)

    # ------------------------------------------------------------------
    # SKENARIO 1A: Tambah 1 Dokter Jaga
    # ------------------------------------------------------------------
    print("[2/4] Menjalankan Skenario 1A: +1 Dokter Jaga...")
    skenario_1a = jalankan_simulasi(
        num_perawat=NUM_PERAWAT_TRIAGE,
        num_dokter=NUM_DOKTER_JAGA + 1,    # 3 → 4 dokter
        num_bed=NUM_BED_IGD,
        label="Skenario 1A: +1 Dokter"
    )
    cetak_ringkasan(skenario_1a)

    # ------------------------------------------------------------------
    # SKENARIO 1B: Tambah 2 Perawat Triage
    # ------------------------------------------------------------------
    print("[3/4] Menjalankan Skenario 1B: +2 Perawat Triage...")
    skenario_1b = jalankan_simulasi(
        num_perawat=NUM_PERAWAT_TRIAGE + 2, # 2 → 4 perawat
        num_dokter=NUM_DOKTER_JAGA,
        num_bed=NUM_BED_IGD,
        label="Skenario 1B: +2 Perawat"
    )
    cetak_ringkasan(skenario_1b)

    # ------------------------------------------------------------------
    # SKENARIO 2: Lonjakan 2x lipat (Wabah)
    # ------------------------------------------------------------------
    print("[4/4] Menjalankan Skenario 2: Lonjakan 2x (Wabah)...")
    skenario_2 = jalankan_simulasi(
        num_perawat=NUM_PERAWAT_TRIAGE,
        num_dokter=NUM_DOKTER_JAGA,
        num_bed=NUM_BED_IGD,
        interval_kedatangan=INTERVAL_KEDATANGAN / 2,  # 2x lebih sering
        label="Skenario 2: Wabah (2x Pasien)"
    )
    cetak_ringkasan(skenario_2)

    # ------------------------------------------------------------------
    # VISUALISASI
    # ------------------------------------------------------------------
    print("\nMembuat grafik...")

    semua_skenario = [baseline, skenario_1a, skenario_1b, skenario_2]

    # 1. Distribusi waktu tunggu (baseline only)
    plot_distribusi_waktu_tunggu(baseline)

    # 2. Perbandingan waktu tunggu semua skenario
    plot_perbandingan_waktu_tunggu(semua_skenario)

    # 3. Panjang antrean dari waktu ke waktu
    plot_panjang_antrean(semua_skenario)

    # 4. Utilisasi dokter
    plot_utilisasi_dokter(semua_skenario)

    # ------------------------------------------------------------------
    # KESIMPULAN
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  KESIMPULAN AWAL (SCRATCH MODEL)")
    print("=" * 60)
    print("""
    Model scratch ini mensimulasikan alur pasien IGD dengan 4 skenario:

    1. BASELINE      : Kondisi normal (2 Perawat, 3 Dokter, 10 Bed)
    2. +1 DOKTER     : Menambah 1 dokter jaga
    3. +2 PERAWAT    : Menambah 2 perawat triage
    4. WABAH (2x)    : Kedatangan pasien 2x lipat

    Dari hasil simulasi, perhatikan:
    - Skenario mana yang paling menurunkan waktu tunggu pasien Merah (kritis)?
    - Bagaimana perbandingan efektivitas menambah dokter vs perawat?
    - Apakah sistem kolaps saat lonjakan 2x? (Lihat grafik antrean)

    >> Ini masih model KASAR. Parameter bisa di-tune lebih lanjut
       berdasarkan data riil rumah sakit.
    """)
    print("=" * 60)
    print("  Grafik disimpan di folder: c:/Users/Fronli/CODE/Kuliah/PS/")
    print("  File: grafik_waktu_tunggu.png, grafik_antrean.png,")
    print("         grafik_utilisasi.png, grafik_distribusi.png")
    print("=" * 60)
