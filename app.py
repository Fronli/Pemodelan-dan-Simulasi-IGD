"""
Flask Web Server — Simulasi Antrean IGD
Serves the web UI and simulation API.
"""

from flask import Flask, render_template, jsonify, request
from simulation import run_simulation

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/simulate", methods=["POST"])
def simulate():
    data = request.json
    results = []
    for sc in data.get("scenarios", []):
        result = run_simulation(
            num_perawat=int(sc.get("num_perawat", 2)),
            num_dokter=int(sc.get("num_dokter", 3)),
            num_bed=int(sc.get("num_bed", 10)),
            interval_kedatangan=float(sc.get("interval", 5)),
            sim_duration=int(sc.get("duration", 480)),
            label=sc.get("label", "Skenario"),
        )
        results.append(result)
    return jsonify({"results": results})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
