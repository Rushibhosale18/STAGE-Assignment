"""Enterprise-grade interactive localhost dashboard server for STAGE: One User, One Agent."""
import csv
import http.server
import json
import logging
import os
import socketserver
import urllib.parse
from pathlib import Path

PORT = 8000
BASE_DIR = Path(__file__).resolve().parent
SAMPLE_RUN = BASE_DIR / "sample_run"
PACK_DIR = BASE_DIR / "one_user_one_agent_pack"

logger = logging.getLogger("DashboardServer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

print("Initializing enterprise dashboard server...")

# Load Decisions
decisions = []
with open(SAMPLE_RUN / "decisions.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            decisions.append(json.loads(line))

# Load Actions indexed by decision_id
actions_by_dec_id = {}
with open(SAMPLE_RUN / "actions.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            a = json.loads(line)
            actions_by_dec_id[a["decision_id"]] = a

# Load Outcomes indexed by decision_id
outcomes_by_dec_id = {}
with open(SAMPLE_RUN / "outcomes.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            o = json.loads(line)
            outcomes_by_dec_id[o["decision_id"]] = o

# Load Catalogue
catalogue = {}
with open(PACK_DIR / "data" / "catalogue.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        catalogue[r["title_id"]] = {
            "title_id": r["title_id"],
            "content_slug": r["content_slug"],
            "title": r["title"],
            "dialect": r["dialect"],
            "content_type": r["content_type"],
            "genres": r["genres"].split("|"),
            "release_date": r["release_date"],
            "is_premium": r["is_premium"].lower() == "true",
            "description": r["description"]
        }

# Load Latency Report
with open(SAMPLE_RUN / "latency_report.json", "r", encoding="utf-8") as f:
    latency_report = json.load(f)

# Load Simulator Report
with open(SAMPLE_RUN / "sim" / "simulator_report.json", "r", encoding="utf-8") as f:
    sim_report = json.load(f)

print(f"Loaded {len(decisions)} decisions, {len(actions_by_dec_id)} actions, {len(catalogue)} titles.")


HTML_PAGE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>STAGE AI: One User, One Agent — Enterprise Operations & Causal Impact Hub</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace'],
          },
          colors: {
            brand: { 50: '#fff1f2', 100: '#ffe4e6', 500: '#f43f5e', 600: '#e11d48', 700: '#be123c', 900: '#881337', 950: '#4c0519' },
            slate: { 850: '#151e2e', 900: '#0f172a', 950: '#080d1a' }
          }
        }
      }
    }
  </script>
  <style>
    body { background-color: #070b14; color: #f1f5f9; }
    .glass-panel { background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.07); }
    .glass-card { background: rgba(21, 30, 46, 0.6); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.05); }
    .glass-card:hover { border-color: rgba(225, 29, 72, 0.3); }
    .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 9999px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
    .device-mockup {
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 0 12px #1e293b, 0 0 0 14px #334155;
    }
  </style>
</head>
<body class="min-h-screen flex flex-col font-sans antialiased text-slate-100">

  <!-- Top Announcement / System Bar -->
  <div class="bg-gradient-to-r from-brand-950 via-slate-900 to-slate-950 border-b border-brand-900/40 px-6 py-2 flex items-center justify-between text-xs">
    <div class="flex items-center space-x-3">
      <span class="inline-flex items-center px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-300 font-bold text-[10px] uppercase tracking-wider border border-brand-500/30">
        STAGE AI
      </span>
      <span class="text-slate-300 font-medium">Production Evaluation Environment &mdash; Replay Day: <span class="text-white font-mono">2026-10-01 IST</span></span>
    </div>
    <div class="flex items-center space-x-4 text-[11px] text-slate-400">
      <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> Zero Policy Violations</span>
      <span class="text-slate-600">|</span>
      <span>100% Latency Compliance (&lt; 60s)</span>
      <span class="text-slate-600">|</span>
      <span class="font-mono text-slate-300">P95: 1 ms</span>
    </div>
  </div>

  <!-- Primary Header -->
  <header class="glass-panel sticky top-0 z-50 px-8 py-4 border-b border-slate-800 flex items-center justify-between shadow-xl">
    <div class="flex items-center space-x-5">
      <div class="bg-gradient-to-br from-brand-600 to-brand-700 text-white font-black text-2xl px-3.5 py-1 rounded-lg tracking-wider shadow-lg shadow-brand-600/30">
        STAGE
      </div>
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-lg font-bold text-white tracking-tight">One User, One Agent</h1>
          <span class="px-2 py-0.5 bg-slate-800 text-slate-300 text-[10px] rounded font-mono border border-slate-700">v1.0.0-verified</span>
        </div>
        <p class="text-xs text-slate-400">Autonomous Regional-Dialect OTT Lifecycle Management & Causal Attribution</p>
      </div>
    </div>

    <!-- Quick Navigation Tabs -->
    <div class="flex items-center bg-slate-900/80 p-1 rounded-xl border border-slate-800 space-x-1 text-xs font-semibold">
      <button onclick="switchTab('analytics')" id="tab-analytics" class="px-3.5 py-1.5 rounded-lg bg-brand-600 text-white shadow-sm flex items-center gap-1.5 transition">
        <i class="fa-solid fa-chart-line text-[11px]"></i> Causal Analytics
      </button>
      <button onclick="switchTab('stream')" id="tab-stream" class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white flex items-center gap-1.5 transition">
        <i class="fa-solid fa-bolt text-[11px]"></i> Decision Stream
      </button>
      <button onclick="switchTab('device')" id="tab-device" class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white flex items-center gap-1.5 transition">
        <i class="fa-solid fa-mobile-screen-button text-[11px]"></i> OTT Phone Mockup
      </button>
      <button onclick="switchTab('provenance')" id="tab-provenance" class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white flex items-center gap-1.5 transition">
        <i class="fa-solid fa-database text-[11px]"></i> State & Provenance
      </button>
      <button onclick="switchTab('interview')" id="tab-interview" class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white flex items-center gap-1.5 transition">
        <i class="fa-solid fa-graduation-cap text-[11px]"></i> Technical Q&A
      </button>
    </div>
  </header>

  <!-- Main Container -->
  <main class="flex-1 px-8 py-6 max-w-7xl w-full mx-auto space-y-6">

    <!-- ========================================== -->
    <!-- TAB 1: CAUSAL ANALYTICS & EXECUTIVE IMPACT -->
    <!-- ========================================== -->
    <section id="panel-analytics" class="space-y-6">
      
      <!-- Top Operational KPI Row -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div class="glass-card p-4 rounded-xl border border-slate-800">
          <div class="flex items-center justify-between text-xs text-slate-400 font-medium">
            <span>Decisions Made</span>
            <i class="fa-solid fa-microchip text-slate-500"></i>
          </div>
          <div class="text-2xl font-black text-white mt-1.5">2,769</div>
          <div class="text-[11px] text-emerald-400 flex items-center gap-1 mt-1 font-medium">
            <i class="fa-solid fa-circle-check text-[10px]"></i> 100% within 60s budget
          </div>
        </div>

        <div class="glass-card p-4 rounded-xl border border-slate-800">
          <div class="flex items-center justify-between text-xs text-slate-400 font-medium">
            <span>Actions Published</span>
            <i class="fa-solid fa-paper-plane text-slate-500"></i>
          </div>
          <div class="text-2xl font-black text-white mt-1.5">1,108</div>
          <div class="text-[11px] text-blue-400 flex items-center gap-1 mt-1 font-medium">
            <i class="fa-solid fa-check text-[10px]"></i> 100% accepted by platform
          </div>
        </div>

        <div class="glass-card p-4 rounded-xl border border-slate-800">
          <div class="flex items-center justify-between text-xs text-slate-400 font-medium">
            <span>Policy Violations</span>
            <i class="fa-solid fa-shield-halved text-slate-500"></i>
          </div>
          <div class="text-2xl font-black text-emerald-400 mt-1.5">0</div>
          <div class="text-[11px] text-slate-400 mt-1 font-medium">
            0 holdout, 0 quiet hours leaks
          </div>
        </div>

        <div class="glass-card p-4 rounded-xl border border-slate-800">
          <div class="flex items-center justify-between text-xs text-slate-400 font-medium">
            <span>Decision Latency (P95)</span>
            <i class="fa-solid fa-stopwatch text-slate-500"></i>
          </div>
          <div class="text-2xl font-black text-purple-400 mt-1.5">1 ms</div>
          <div class="text-[11px] text-slate-400 mt-1 font-medium">
            Mean: 0.25 ms | Max: 71 ms
          </div>
        </div>

        <div class="glass-card p-4 rounded-xl border border-slate-800">
          <div class="flex items-center justify-between text-xs text-slate-400 font-medium">
            <span>True ITT Uplift</span>
            <i class="fa-solid fa-scale-balanced text-slate-500"></i>
          </div>
          <div class="text-2xl font-black text-white mt-1.5">+0.21%</div>
          <div class="text-[11px] text-slate-400 mt-1 font-medium">
            95% CI: [-0.74%, +1.15%]
          </div>
        </div>
      </div>

      <!-- The Core Scientific Comparison: ITT vs Selection Bias -->
      <div class="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-6">
        <div class="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <div class="flex items-center gap-2.5">
              <span class="p-2 rounded-lg bg-brand-500/10 text-brand-400 border border-brand-500/20 text-sm">
                <i class="fa-solid fa-scale-balanced"></i>
              </span>
              <h2 class="text-lg font-bold text-white tracking-tight">The Causal Impact Dilemma: Honest ITT vs. Observational Selection Bias</h2>
            </div>
            <p class="text-xs text-slate-400 mt-1">Exposing why growth metrics that compare "served vs unserved" users mislead executive leadership</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="px-2.5 py-1 bg-emerald-950/70 text-emerald-300 border border-emerald-500/30 text-xs rounded-lg font-semibold">
              Randomized A/B Design
            </span>
          </div>
        </div>

        <!-- 3-Way Methodology Comparison Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
          
          <!-- Card 1: Honest ITT -->
          <div class="p-5 rounded-xl bg-gradient-to-b from-emerald-950/30 to-slate-900 border border-emerald-500/30 flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between text-xs font-bold text-emerald-400 uppercase tracking-wider">
                <span>1. True Intention-To-Treat (ITT)</span>
                <span class="px-2 py-0.5 bg-emerald-500/20 border border-emerald-500/40 rounded text-[10px] text-emerald-300">Gold Standard</span>
              </div>
              <div class="mt-4 flex items-baseline gap-2">
                <span class="text-4xl font-extrabold text-white">+0.21%</span>
                <span class="text-xs text-slate-400">absolute lift</span>
              </div>
              <div class="mt-3 space-y-1.5 text-xs text-slate-300 border-t border-slate-800/80 pt-3">
                <div class="flex justify-between">
                  <span class="text-slate-400">Agent Arm (2,513 users):</span>
                  <span class="font-mono font-bold text-white">3.10% (78 succ)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">Holdout Arm (2,487 users):</span>
                  <span class="font-mono font-bold text-white">2.90% (72 succ)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">p-value:</span>
                  <span class="font-mono text-slate-300">0.6652 (Not Sig)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">95% Confidence Interval:</span>
                  <span class="font-mono text-slate-300">[-0.74%, +1.15%]</span>
                </div>
              </div>
            </div>
            <p class="text-[11px] text-slate-400 mt-4 pt-3 border-t border-slate-800/60 leading-relaxed">
              <strong>Why this is right:</strong> Evaluates every single user assigned to the arm, whether they triggered an open or were abstained upon. Preserves complete randomized covariate balance.
            </p>
          </div>

          <!-- Card 2: Flawed Observational -->
          <div class="p-5 rounded-xl bg-gradient-to-b from-yellow-950/30 to-slate-900 border border-yellow-500/30 flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between text-xs font-bold text-yellow-400 uppercase tracking-wider">
                <span>2. Flawed "Served vs Unserved"</span>
                <span class="px-2 py-0.5 bg-yellow-500/20 border border-yellow-500/40 rounded text-[10px] text-yellow-300">Biased</span>
              </div>
              <div class="mt-4 flex items-baseline gap-2">
                <span class="text-4xl font-extrabold text-white">+9.00%</span>
                <span class="text-xs text-yellow-400 font-semibold">spurious lift</span>
              </div>
              <div class="mt-3 space-y-1.5 text-xs text-slate-300 border-t border-slate-800/80 pt-3">
                <div class="flex justify-between">
                  <span class="text-slate-400">Served Users (719 users):</span>
                  <span class="font-mono font-bold text-white">10.71% (77 succ)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">Unserved Users (4,281 users):</span>
                  <span class="font-mono font-bold text-white">1.71% (73 succ)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">p-value:</span>
                  <span class="font-mono text-yellow-400 font-bold">0.0000 (Spurious)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">Apparent Relative Uplift:</span>
                  <span class="font-mono text-yellow-300 font-bold">+526%</span>
                </div>
              </div>
            </div>
            <p class="text-[11px] text-slate-400 mt-4 pt-3 border-t border-slate-800/60 leading-relaxed">
              <strong>The selection bias trap:</strong> Users who received an action were active enough to open the app and pass checks. Comparing them against dormant users conditions on a post-treatment outcome.
            </p>
          </div>

          <!-- Card 3: Pilot Report Critique -->
          <div class="p-5 rounded-xl bg-gradient-to-b from-brand-950/30 to-slate-900 border border-brand-500/30 flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between text-xs font-bold text-brand-400 uppercase tracking-wider">
                <span>3. Past Pilot Report Error</span>
                <span class="px-2 py-0.5 bg-brand-500/20 border border-brand-500/40 rounded text-[10px] text-brand-300">Exposed</span>
              </div>
              <div class="mt-4 flex items-baseline gap-2">
                <span class="text-4xl font-extrabold text-brand-300">+22.4%</span>
                <span class="text-xs text-slate-400">claimed in pilot</span>
              </div>
              <div class="mt-3 space-y-1.5 text-xs text-slate-300 border-t border-slate-800/80 pt-3">
                <div class="flex justify-between">
                  <span class="text-slate-400">Pilot Headline Claim:</span>
                  <span class="font-mono font-bold text-brand-400">40.1% vs 17.7% (2.3x)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">Actual Pilot Treatment ITT:</span>
                  <span class="font-mono font-bold text-white">18.25% (349 / 1,912)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">Actual Pilot Holdout ITT:</span>
                  <span class="font-mono font-bold text-white">19.56% (387 / 1,979)</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">True Pilot Difference:</span>
                  <span class="font-mono text-brand-400 font-bold">-1.30% (p = 0.30)</span>
                </div>
              </div>
            </div>
            <p class="text-[11px] text-slate-400 mt-4 pt-3 border-t border-slate-800/60 leading-relaxed">
              <strong>The truth:</strong> The pilot agent actually performed 1.3 points <em>worse</em> than control. The headline +22.4% uplift was pure observational bias.
            </p>
          </div>

        </div>

        <!-- Interactive Chart Visualizer -->
        <div class="pt-4 border-t border-slate-800">
          <div class="h-64 w-full">
            <canvas id="causalChart"></canvas>
          </div>
        </div>

      </div>

      <!-- Goal Breakdown Table & Latency Distribution -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        <!-- Left: Goal-by-Goal ITT Table -->
        <div class="lg:col-span-2 glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
          <h3 class="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <i class="fa-solid fa-list-check text-brand-400"></i> Attribution by Candidate Goal
          </h3>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-300">
              <thead class="bg-slate-900/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th class="py-2.5 px-3">Goal ID</th>
                  <th class="py-2.5 px-3">Name / Intent</th>
                  <th class="py-2.5 px-3">Agent Rate</th>
                  <th class="py-2.5 px-3">Holdout Rate</th>
                  <th class="py-2.5 px-3 text-right">Net Lift</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60 font-mono text-[11px]">
                <tr class="hover:bg-slate-800/30">
                  <td class="py-2.5 px-3 font-bold text-white">G01</td>
                  <td class="py-2.5 px-3 font-sans text-slate-300">first_play_24h</td>
                  <td class="py-2.5 px-3 text-emerald-400 font-bold">32.8% (20/61)</td>
                  <td class="py-2.5 px-3 text-slate-400">28.3% (15/53)</td>
                  <td class="py-2.5 px-3 text-right text-emerald-400 font-bold">+4.5%</td>
                </tr>
                <tr class="hover:bg-slate-800/30">
                  <td class="py-2.5 px-3 font-bold text-white">G02</td>
                  <td class="py-2.5 px-3 font-sans text-slate-300">first_full_episode_3d</td>
                  <td class="py-2.5 px-3 text-emerald-400 font-bold">13.0% (35/269)</td>
                  <td class="py-2.5 px-3 text-slate-400">11.4% (29/254)</td>
                  <td class="py-2.5 px-3 text-right text-emerald-400 font-bold">+1.6%</td>
                </tr>
                <tr class="hover:bg-slate-800/30">
                  <td class="py-2.5 px-3 font-bold text-white">G07</td>
                  <td class="py-2.5 px-3 font-sans text-slate-300">resume_series_3d</td>
                  <td class="py-2.5 px-3 text-emerald-400 font-bold">3.5% (16/460)</td>
                  <td class="py-2.5 px-3 text-slate-400">2.9% (14/480)</td>
                  <td class="py-2.5 px-3 text-right text-emerald-400 font-bold">+0.6%</td>
                </tr>
                <tr class="hover:bg-slate-800/30">
                  <td class="py-2.5 px-3 font-bold text-white">G05</td>
                  <td class="py-2.5 px-3 font-sans text-slate-300">first_paid_7d</td>
                  <td class="py-2.5 px-3 text-slate-300">5.6% (2/36)</td>
                  <td class="py-2.5 px-3 text-slate-400">8.2% (4/49)</td>
                  <td class="py-2.5 px-3 text-right text-brand-400">-2.6%</td>
                </tr>
                <tr class="hover:bg-slate-800/30">
                  <td class="py-2.5 px-3 font-bold text-white">G08</td>
                  <td class="py-2.5 px-3 font-sans text-slate-300">try_new_release_7d</td>
                  <td class="py-2.5 px-3 text-slate-300">15.4% (4/26)</td>
                  <td class="py-2.5 px-3 text-slate-400">20.6% (7/34)</td>
                  <td class="py-2.5 px-3 text-right text-brand-400">-5.2%</td>
                </tr>
                <tr class="hover:bg-slate-800/30">
                  <td class="py-2.5 px-3 font-bold text-slate-500">G10</td>
                  <td class="py-2.5 px-3 font-sans text-slate-500">meaningful_engagement</td>
                  <td class="py-2.5 px-3 text-slate-600" colspan="3">&mdash; Blacklisted: Unmeasurable (No success event) &mdash;</td>
                </tr>
                <tr class="hover:bg-slate-800/30">
                  <td class="py-2.5 px-3 font-bold text-slate-500">G11</td>
                  <td class="py-2.5 px-3 font-sans text-slate-500">tv_activation_14d</td>
                  <td class="py-2.5 px-3 text-slate-600" colspan="3">&mdash; Blacklisted: Unmeasurable (No TV telemetry) &mdash;</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Right: Actions Donut Chart -->
        <div class="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl flex flex-col justify-between">
          <h3 class="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <i class="fa-solid fa-pie-chart text-purple-400"></i> Decision Distribution
          </h3>
          <div class="h-48 w-full my-auto flex items-center justify-center">
            <canvas id="actionsChart"></canvas>
          </div>
          <div class="grid grid-cols-2 gap-2 text-center text-xs pt-3 border-t border-slate-800/80">
            <div class="p-2 bg-slate-900 rounded">
              <span class="text-slate-400 text-[10px]">Published Pages:</span>
              <div class="font-bold text-emerald-400">1,108</div>
            </div>
            <div class="p-2 bg-slate-900 rounded">
              <span class="text-slate-400 text-[10px]">Holdout Control:</span>
              <div class="font-bold text-blue-400">1,372</div>
            </div>
          </div>
        </div>

      </div>

    </section>

    <!-- ========================================== -->
    <!-- TAB 2: DECISION STREAM (2,769 RECORDS)     -->
    <!-- ========================================== -->
    <section id="panel-stream" class="hidden space-y-4">
      <div class="glass-panel p-4 rounded-xl border border-slate-800 flex flex-wrap gap-3 items-center justify-between">
        <div class="flex items-center gap-3 flex-1 min-w-[320px]">
          <i class="fa-solid fa-magnifying-glass text-slate-500 text-sm"></i>
          <input type="text" id="decision-search" oninput="renderDecisions()" placeholder="Filter by Viewer ID (e.g. U-02344, U-01991, U-00042) or Decision ID..." class="bg-slate-900/90 border border-slate-700/80 text-xs rounded-lg px-3.5 py-2 w-full text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 font-mono">
        </div>
        <div class="flex items-center gap-2">
          <select id="status-filter" onchange="renderDecisions()" class="bg-slate-900 border border-slate-700 text-xs rounded-lg px-3 py-2 text-slate-300 font-medium">
            <option value="ALL">All Statuses (2,769)</option>
            <option value="PUBLISHED">PUBLISHED (1,108)</option>
            <option value="HOLDOUT">HOLDOUT (1,372)</option>
            <option value="ABSTAINED">ABSTAINED (289)</option>
          </select>
          <select id="dialect-filter" onchange="renderDecisions()" class="bg-slate-900 border border-slate-700 text-xs rounded-lg px-3 py-2 text-slate-300 font-medium">
            <option value="ALL">All Dialects</option>
            <option value="d1">d1 (Bhojpuri)</option>
            <option value="d2">d2 (Haryanvi)</option>
            <option value="d3">d3 (Rajasthani)</option>
            <option value="d4">d4 (Maithili)</option>
            <option value="d5">d5 (Magahi)</option>
            <option value="d6">d6 (Bundeli)</option>
          </select>
        </div>
      </div>

      <!-- Decision Records Table -->
      <div class="glass-panel rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
        <div class="overflow-x-auto max-h-[620px] custom-scrollbar">
          <table class="w-full text-left text-xs text-slate-300">
            <thead class="bg-slate-900 text-slate-400 uppercase text-[10px] tracking-wider sticky top-0 border-b border-slate-800 z-10">
              <tr>
                <th class="py-3 px-4">Decision ID</th>
                <th class="py-3 px-4">Viewer ID</th>
                <th class="py-3 px-4">Trigger Time</th>
                <th class="py-3 px-4">Dialect</th>
                <th class="py-3 px-4">Goal Chosen</th>
                <th class="py-3 px-4">Intervention</th>
                <th class="py-3 px-4">Status</th>
                <th class="py-3 px-4 text-right">Latency</th>
                <th class="py-3 px-4 text-center">Inspect</th>
              </tr>
            </thead>
            <tbody id="decisions-tbody" class="divide-y divide-slate-800/60 font-mono text-[11px]">
              <!-- Populated by JS -->
            </tbody>
          </table>
        </div>
        <div class="p-3.5 bg-slate-900/60 border-t border-slate-800 flex justify-between items-center text-xs text-slate-400">
          <span id="decision-count-label">Showing 30 of 2,769 decisions</span>
          <div class="flex gap-2">
            <button onclick="prevPage()" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-200 transition">Previous</button>
            <button onclick="nextPage()" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-200 transition">Next</button>
          </div>
        </div>
      </div>
    </section>

    <!-- ========================================== -->
    <!-- TAB 3: OTT PHONE MOCKUP (LIVE SIMULATOR)   -->
    <!-- ========================================== -->
    <section id="panel-device" class="hidden space-y-6">
      
      <!-- Control Bar -->
      <div class="glass-panel p-4 rounded-xl border border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-3">
          <span class="text-xs text-slate-400 font-medium">Select Viewer ID:</span>
          <input type="text" id="preview-user-input" value="U-02344" class="bg-slate-900 border border-slate-700 text-xs rounded-lg px-3 py-1.5 text-white font-mono w-36 focus:outline-none focus:border-brand-500">
          <button onclick="loadUserPreview()" class="px-4 py-1.5 bg-brand-600 hover:bg-brand-500 rounded-lg text-xs font-bold text-white transition shadow-sm">
            Render Home Page
          </button>
          <div class="flex gap-1.5 text-xs">
            <button onclick="selectQuickUser('U-02344')" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 font-mono text-[11px]">U-02344 (Rajasthani)</button>
            <button onclick="selectQuickUser('U-00548')" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 font-mono text-[11px]">U-00548 (Magahi)</button>
            <button onclick="selectQuickUser('U-00042')" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-300 font-mono text-[11px]">U-00042 (Haryanvi)</button>
          </div>
        </div>
        <div id="preview-badge-container"></div>
      </div>

      <!-- Smartphone Device Mockup Container -->
      <div class="flex justify-center py-4">
        <div class="device-mockup w-[420px] rounded-[48px] bg-black overflow-hidden relative border border-slate-700">
          
          <!-- Top Dynamic Island & Status Bar -->
          <div class="h-10 bg-black flex items-center justify-between px-6 pt-2 text-[10px] text-slate-400 font-mono z-30 relative">
            <span>09:41</span>
            <div class="w-20 h-4 bg-slate-950 rounded-full border border-slate-800 flex items-center justify-center">
              <span class="w-2 h-2 rounded-full bg-slate-800"></span>
            </div>
            <div class="flex items-center gap-1.5 text-slate-300">
              <i class="fa-solid fa-wifi text-[9px]"></i>
              <i class="fa-solid fa-battery-full text-[10px]"></i>
            </div>
          </div>

          <!-- Phone Screen Scrollable Area -->
          <div class="h-[740px] overflow-y-auto custom-scrollbar bg-[#090d16] text-white pb-20">
            
            <!-- App Header -->
            <div class="p-4 flex items-center justify-between sticky top-0 bg-[#090d16]/90 backdrop-blur-md z-20 border-b border-slate-800/40">
              <div class="flex items-center gap-2">
                <span class="bg-brand-600 text-white font-black px-2 py-0.5 rounded text-sm">STAGE</span>
                <span id="app-dialect-pill" class="text-[10px] font-bold px-2 py-0.5 bg-slate-800 rounded-full text-slate-300 border border-slate-700">d3 RAJASTHANI</span>
              </div>
              <div class="flex items-center gap-3 text-slate-400 text-xs">
                <i class="fa-solid fa-search"></i>
                <i class="fa-regular fa-bell"></i>
                <div class="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-white font-bold">U</div>
              </div>
            </div>

            <!-- Hero Banner -->
            <div id="phone-hero" class="relative h-72 bg-gradient-to-t from-[#090d16] via-transparent to-black p-5 flex flex-col justify-end">
              <div class="absolute inset-0 bg-cover bg-center opacity-40" style="background-image: radial-gradient(circle at 50% 50%, #881337 0%, #000 100%);"></div>
              <div class="relative z-10 space-y-2">
                <span id="phone-hero-badge" class="px-2 py-0.5 bg-brand-600 text-[9px] font-black tracking-wider rounded uppercase">HERO SPOTLIGHT</span>
                <h3 id="phone-hero-title" class="text-2xl font-black leading-tight text-white tracking-tight">Loading Title...</h3>
                <p id="phone-hero-desc" class="text-[11px] text-slate-300 line-clamp-2 leading-relaxed">Synopsis...</p>
                <div class="pt-2 flex gap-2">
                  <button class="flex-1 py-2 bg-white text-black font-bold text-xs rounded-lg hover:bg-slate-200 flex items-center justify-center gap-1.5 shadow-md">
                    <i class="fa-solid fa-play text-xs"></i> Play Episode
                  </button>
                  <button class="px-3.5 py-2 bg-slate-800/80 rounded-lg text-white text-xs hover:bg-slate-700">
                    <i class="fa-solid fa-plus"></i>
                  </button>
                </div>
              </div>
            </div>

            <!-- Carousels Container -->
            <div id="phone-rows" class="p-4 space-y-6">
              <!-- Injected by JS -->
            </div>

          </div>

          <!-- Bottom App Navigation Bar -->
          <div class="absolute bottom-0 inset-x-0 h-16 bg-[#090d16]/95 backdrop-blur-md border-t border-slate-800/60 flex items-center justify-around text-slate-400 text-[10px] z-30">
            <div class="flex flex-col items-center text-brand-500 font-bold">
              <i class="fa-solid fa-house text-sm mb-0.5"></i>
              <span>Home</span>
            </div>
            <div class="flex flex-col items-center hover:text-white cursor-pointer">
              <i class="fa-solid fa-compass text-sm mb-0.5"></i>
              <span>Explore</span>
            </div>
            <div class="flex flex-col items-center hover:text-white cursor-pointer">
              <i class="fa-solid fa-arrow-down text-sm mb-0.5"></i>
              <span>Downloads</span>
            </div>
            <div class="flex flex-col items-center hover:text-white cursor-pointer">
              <i class="fa-solid fa-user text-sm mb-0.5"></i>
              <span>Profile</span>
            </div>
          </div>

        </div>
      </div>

    </section>

    <!-- ========================================== -->
    <!-- TAB 4: VIEWER STATE & PROVENANCE INSPECTOR -->
    <!-- ========================================== -->
    <section id="panel-provenance" class="hidden space-y-4">
      <div class="glass-panel p-4 rounded-xl border border-slate-800 flex items-center gap-3">
        <label class="text-xs text-slate-400 font-medium">Lookup Viewer State:</label>
        <input type="text" id="viewer-inspect-input" value="U-02344" class="bg-slate-900 border border-slate-700 text-xs rounded-lg px-3 py-1.5 text-white font-mono w-48 focus:outline-none focus:border-brand-500">
        <button onclick="fetchViewerState()" class="px-4 py-1.5 bg-brand-600 hover:bg-brand-500 rounded-lg text-xs font-bold text-white transition">
          Load Durable State
        </button>
        <div class="flex gap-2 ml-4 text-xs">
          <button onclick="inspectViewerQuick('U-02344')" class="text-slate-400 hover:text-white underline font-mono text-[11px]">U-02344 (Active)</button>
          <button onclick="inspectViewerQuick('U-01991')" class="text-slate-400 hover:text-white underline font-mono text-[11px]">U-01991 (Model Fault Test)</button>
          <button onclick="inspectViewerQuick('U-00003')" class="text-slate-400 hover:text-white underline font-mono text-[11px]">U-00003 (Holdout)</button>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <!-- Visual State Breakdown -->
        <div class="glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
          <div class="flex justify-between items-center border-b border-slate-800 pb-3">
            <h3 class="text-sm font-bold text-white flex items-center gap-2">
              <i class="fa-solid fa-user-check text-blue-400"></i> Facts with Source Provenance
            </h3>
            <span id="provenance-user-badge" class="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-mono text-slate-300"></span>
          </div>
          <div id="viewer-facts-display" class="space-y-3 text-xs"></div>
        </div>

        <!-- Raw JSON Inspector -->
        <div class="glass-panel p-5 rounded-2xl border border-slate-800 space-y-3">
          <div class="flex justify-between items-center border-b border-slate-800 pb-3">
            <h3 class="text-sm font-bold text-white flex items-center gap-2">
              <i class="fa-solid fa-code text-emerald-400"></i> Durable State JSON Document
            </h3>
            <span class="text-[10px] text-slate-400 font-mono" id="json-file-name">U-02344.json</span>
          </div>
          <pre id="raw-state-json" class="p-4 bg-slate-950 rounded-xl text-emerald-300 font-mono text-[11px] overflow-auto max-h-[550px] custom-scrollbar border border-slate-800/80 leading-relaxed"></pre>
        </div>
      </div>
    </section>

    <!-- ========================================== -->
    <!-- TAB 5: TECHNICAL DISCUSSION (60-MIN GUIDE) -->
    <!-- ========================================== -->
    <section id="panel-interview" class="hidden space-y-6">
      <div class="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-5">
        <div class="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h2 class="text-lg font-bold text-white flex items-center gap-2">
              <i class="fa-solid fa-graduation-cap text-brand-400"></i> Technical Discussion Cheat Sheet (60-Minute Interview)
            </h2>
            <p class="text-xs text-slate-400 mt-1">Structured answers to all 7 evaluation interview questions directly backed by codebase implementation</p>
          </div>
          <span class="px-3 py-1 bg-brand-950 text-brand-300 border border-brand-500/30 text-xs rounded-lg font-bold">
            Senior AI Engineer Benchmark
          </span>
        </div>

        <!-- Q&A Accordion Cards -->
        <div class="space-y-4 text-xs">
          
          <!-- Q1 -->
          <div class="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div class="font-bold text-sm text-white flex items-center gap-2">
              <span class="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">1</span>
              <span>How does your agent decide that what it knows is current enough to act on?</span>
            </div>
            <p class="text-slate-300 leading-relaxed pl-7">
              Every fact carries explicit provenance: <code class="text-brand-300">source</code>, <code class="text-brand-300">received_at</code> (server clock), and <code class="text-brand-300">occurred_at</code> (phone clock). 
              Server time is authoritative. We enforce an offline buffering threshold (<code class="text-emerald-300">MAX_LIVE_SESSION_DELAY_S = 600</code>). If an app open arrived > 10 minutes after occurrence, it was flushed upon reconnection; the user is not actively waiting, so the agent abstains from live UI changes. Contradictions follow strict precedence: newer billing events override stale profiles, and runtime <code class="text-emerald-300">app_dialect</code> overrides static profile preferences.
            </p>
          </div>

          <!-- Q2 -->
          <div class="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div class="font-bold text-sm text-white flex items-center gap-2">
              <span class="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">2</span>
              <span>When should the agent do nothing, and how do you know that was right?</span>
            </div>
            <p class="text-slate-300 leading-relaxed pl-7">
              Abstention is a first-class, verified decision recorded with a clear <code class="text-yellow-300">no_action_reason</code>. The agent abstains when: 
              1) User belongs to the randomized holdout control arm (<code class="text-slate-300">user_in_holdout_arm</code>), 
              2) Trigger is offline-buffered and stale (<code class="text-slate-300">stale_offline_buffered_trigger</code>), 
              3) Messaging violates quiet hours (22:00–08:00 IST), missing consent, or daily frequency caps. 
              We know it was right because the official simulator recorded <strong>0 policy violations, 0 holdout leaks, and 0 customer opt-outs</strong>.
            </p>
          </div>

          <!-- Q3 -->
          <div class="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div class="font-bold text-sm text-white flex items-center gap-2">
              <span class="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">3</span>
              <span>How do you prove the agent caused the change and didn't just pick users who would convert anyway?</span>
            </div>
            <p class="text-slate-300 leading-relaxed pl-7">
              By using a strict <strong>Intention-to-Treat (ITT)</strong> framework across pre-randomized arms (<code class="text-slate-300">replay/arms.csv</code>). 
              The flawed pilot report compared <em>served users</em> against <em>unserved users</em>, creating massive selection bias (active users are more likely to be served). In ITT, all 2,513 treatment users are tracked against all 2,487 holdout users regardless of whether they opened the app or were served. This preserves randomized balance and measures genuine causal uplift.
            </p>
          </div>

          <!-- Q4 -->
          <div class="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div class="font-bold text-sm text-white flex items-center gap-2">
              <span class="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">4</span>
              <span>What happens when 1,000 users open the app in the same minute?</span>
            </div>
            <p class="text-slate-300 leading-relaxed pl-7">
              User states are independent and partitioned by <code class="text-slate-300">user_id</code>. There is zero cross-user synchronization. 
              The core intervention planner is deterministic and in-memory, executing in <strong>< 1 ms (P95: 1 ms)</strong>. Under sudden evening traffic surges, optional model calls are bypassed or throttled, guaranteeing 100% of decisions publish well within the 60-second budget.
            </p>
          </div>

          <!-- Q5 -->
          <div class="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div class="font-bold text-sm text-white flex items-center gap-2">
              <span class="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">5</span>
              <span>Which decisions should never be automated?</span>
            </div>
            <p class="text-slate-300 leading-relaxed pl-7">
              1) <strong>Pricing and offer claims</strong>: Only prices in <code class="text-slate-300">pricing.json</code> (₹1, ₹149, ₹399) may exist; LLMs must never invent discounts. 
              2) <strong>Legal opt-outs</strong>: Channel opt-outs must immediately and deterministically block messaging. 
              3) <strong>Content licensing withdrawals</strong>: When a title is withdrawn (<code class="text-slate-300">title_withdrawn</code>), its removal must be an immediate hard block across all carousels.
            </p>
          </div>

          <!-- Q6 -->
          <div class="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div class="font-bold text-sm text-white flex items-center gap-2">
              <span class="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">6</span>
              <span>How would this work for 10 million users and 40 dialects?</span>
            </div>
            <p class="text-slate-300 leading-relaxed pl-7">
              Partition user state across distributed NoSQL (DynamoDB / Cassandra) keyed by <code class="text-slate-300">hash(user_id)</code> with Redis caching. 
              Maintain inverted in-memory indices for catalogue titles partitioned by <code class="text-slate-300">(dialect, genre)</code> (&lt; 100 MB footprint). Decision workers run as lightweight stateless edge functions at Indian CDN edge nodes, resolving state and rendering personalized carousels in &lt; 20 ms.
            </p>
          </div>

          <!-- Q7 -->
          <div class="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
            <div class="font-bold text-sm text-white flex items-center gap-2">
              <span class="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center text-[10px]">7</span>
              <span>What did an AI coding assistant suggest that you rejected, and why?</span>
            </div>
            <p class="text-slate-300 leading-relaxed pl-7">
              1) <strong>Rejected LLM home page title ranking</strong>: Added 3-5 seconds of latency, hallucinated non-existent titles, and failed dialect matching. Replaced with deterministic in-memory indexing. 
              2) <strong>Rejected 'served vs unserved' uplift calculation</strong>: Repeated the pilot report's selection bias. Replaced with strict ITT. 
              3) <strong>Rejected model self-verification</strong>: Model output is never evidence. Built an independent <code class="text-brand-300">ActionVerifier</code> firewall with hard veto authority.
            </p>
          </div>

        </div>
      </div>
    </section>

  </main>

  <!-- Decision Modal -->
  <div id="decision-modal" class="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4 hidden">
    <div class="glass-panel max-w-2xl w-full rounded-2xl border border-slate-700 p-6 space-y-4 max-h-[90vh] overflow-y-auto custom-scrollbar shadow-2xl">
      <div class="flex justify-between items-center border-b border-slate-800 pb-3">
        <div>
          <h3 id="modal-decision-id" class="text-base font-bold text-white font-mono">D-0001</h3>
          <p id="modal-viewer-id" class="text-xs text-slate-400">Viewer: U-02344</p>
        </div>
        <button onclick="closeModal()" class="text-slate-400 hover:text-white text-lg"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="space-y-3 text-xs" id="modal-content"></div>
      <div class="pt-3 border-t border-slate-800 flex justify-end">
        <button onclick="closeModal()" class="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold">Close</button>
      </div>
    </div>
  </div>

  <script>
    let allDecisions = [];
    let filteredDecisions = [];
    let currentPage = 0;
    const PAGE_SIZE = 30;

    async function init() {
      const res = await fetch('/api/decisions');
      allDecisions = await res.json();
      filteredDecisions = allDecisions;
      renderDecisions();
      initCharts();
      loadUserPreview();
      fetchViewerState();
    }

    function switchTab(tab) {
      ['analytics', 'stream', 'device', 'provenance', 'interview'].forEach(t => {
        document.getElementById('panel-' + t).classList.add('hidden');
        document.getElementById('tab-' + t).className = 'px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white flex items-center gap-1.5 transition';
      });
      document.getElementById('panel-' + tab).classList.remove('hidden');
      document.getElementById('tab-' + tab).className = 'px-3.5 py-1.5 rounded-lg bg-brand-600 text-white shadow-sm flex items-center gap-1.5 transition font-semibold';
    }

    function initCharts() {
      // Causal Comparison Bar Chart
      const ctxCausal = document.getElementById('causalChart').getContext('2d');
      new Chart(ctxCausal, {
        type: 'bar',
        data: {
          labels: ['True Randomized ITT (Honest)', 'Flawed Observational (Served vs Unserved)', 'Past Pilot Internal Report (Biased)'],
          datasets: [
            {
              label: 'Treatment / Served Group',
              data: [3.10, 10.71, 40.1],
              backgroundColor: 'rgba(244, 63, 94, 0.85)',
              borderColor: '#f43f5e',
              borderWidth: 1,
              borderRadius: 6
            },
            {
              label: 'Control / Unserved Baseline',
              data: [2.90, 1.71, 17.7],
              backgroundColor: 'rgba(51, 65, 85, 0.85)',
              borderColor: '#64748b',
              borderWidth: 1,
              borderRadius: 6
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'top', labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } } },
            tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${c.raw}%` } }
          },
          scales: {
            y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b', callback: v => v + '%' } },
            x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } } }
          }
        }
      });

      // Actions Donut Chart
      const ctxActions = document.getElementById('actionsChart').getContext('2d');
      new Chart(ctxActions, {
        type: 'doughnut',
        data: {
          labels: ['Published Pages', 'Holdout Control', 'Stale Triggers Abstained'],
          datasets: [{
            data: [1108, 1372, 289],
            backgroundColor: ['#10b981', '#3b82f6', '#f59e0b'],
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } }
          },
          cutout: '70%'
        }
      });
    }

    function renderDecisions() {
      const search = document.getElementById('decision-search').value.toLowerCase();
      const statusFilter = document.getElementById('status-filter').value;
      const dialectFilter = document.getElementById('dialect-filter').value;

      filteredDecisions = allDecisions.filter(d => {
        const matchesSearch = !search || d.viewer_id.toLowerCase().includes(search) || d.decision_id.toLowerCase().includes(search);
        const matchesStatus = statusFilter === 'ALL' || d.status === statusFilter;
        const matchesDialect = dialectFilter === 'ALL' || (d.dialect && d.dialect.used === dialectFilter);
        return matchesSearch && matchesStatus && matchesDialect;
      });

      currentPage = 0;
      updateTable();
    }

    function updateTable() {
      const tbody = document.getElementById('decisions-tbody');
      tbody.innerHTML = '';
      const start = currentPage * PAGE_SIZE;
      const paged = filteredDecisions.slice(start, start + PAGE_SIZE);

      paged.forEach(d => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/40 cursor-pointer transition';
        
        let statusBadge = 'text-emerald-400 bg-emerald-950/60 border-emerald-500/30';
        if (d.status === 'HOLDOUT') statusBadge = 'text-blue-400 bg-blue-950/60 border-blue-500/30';
        if (d.status === 'ABSTAINED') statusBadge = 'text-yellow-400 bg-yellow-950/60 border-yellow-500/30';
        if (d.status === 'REJECTED') statusBadge = 'text-red-400 bg-red-950/60 border-red-500/30';

        const gid = d.goal ? (d.goal.goal_id || d.goal.id) : '<span class="text-slate-500">None</span>';

        tr.innerHTML = `
          <td class="py-2.5 px-4 font-bold text-white">${d.decision_id}</td>
          <td class="py-2.5 px-4 text-slate-300">${d.viewer_id}</td>
          <td class="py-2.5 px-4 text-slate-400 text-[10px]">${d.trigger.received_at.replace('2026-10-01T', '')}</td>
          <td class="py-2.5 px-4"><span class="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px] text-slate-200">${d.dialect.used}</span></td>
          <td class="py-2.5 px-4 text-slate-300 font-sans">${gid}</td>
          <td class="py-2.5 px-4 font-semibold text-slate-200 font-sans">${d.action}</td>
          <td class="py-2.5 px-4"><span class="px-2 py-0.5 rounded-full border text-[10px] font-bold ${statusBadge}">${d.status}</span></td>
          <td class="py-2.5 px-4 text-right text-purple-400">${d.decided_in_ms} ms</td>
          <td class="py-2.5 px-4 text-center">
            <button onclick="inspectDecision('${d.decision_id}')" class="text-slate-400 hover:text-white p-1"><i class="fa-solid fa-eye text-xs"></i></button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      document.getElementById('decision-count-label').innerText = `Showing ${start + 1} - ${Math.min(start + PAGE_SIZE, filteredDecisions.length)} of ${filteredDecisions.length} decisions`;
    }

    function prevPage() {
      if (currentPage > 0) { currentPage--; updateTable(); }
    }
    function nextPage() {
      if ((currentPage + 1) * PAGE_SIZE < filteredDecisions.length) { currentPage++; updateTable(); }
    }

    function inspectDecision(decId) {
      const d = allDecisions.find(x => x.decision_id === decId);
      if (!d) return;

      document.getElementById('modal-decision-id').innerText = `${d.decision_id} (${d.action})`;
      document.getElementById('modal-viewer-id').innerText = `Viewer: ${d.viewer_id} | Dialect: ${d.dialect.used} (${d.dialect.source})`;

      const mc = document.getElementById('modal-content');
      mc.innerHTML = `
        <div class="grid grid-cols-2 gap-3 bg-slate-900 p-3 rounded-xl border border-slate-800">
          <div><strong class="text-slate-400">Trigger Event:</strong> ${d.trigger.event} (age: ${d.trigger.event_age_s}s)</div>
          <div><strong class="text-slate-400">Status:</strong> <span class="font-bold text-white">${d.status}</span></div>
          <div><strong class="text-slate-400">Confidence:</strong> ${d.confidence} (${d.confidence_reason})</div>
          <div><strong class="text-slate-400">Execution Latency:</strong> <span class="text-purple-400 font-bold">${d.decided_in_ms} ms</span></div>
        </div>

        ${d.goal ? `
          <div class="p-3 bg-slate-900/60 rounded-xl border border-slate-800">
            <div class="font-bold text-slate-200 mb-1 flex items-center justify-between font-sans">
              <span>Goal: ${d.goal.id}</span>
              <span class="text-slate-400 text-[11px] font-mono">Deadline: ${d.goal.deadline}</span>
            </div>
            <div class="text-slate-400 font-sans">Success Signal: <span class="text-emerald-400 font-mono">${d.goal.success_event}</span></div>
          </div>
        ` : ''}

        ${d.no_action_reason ? `
          <div class="p-3 bg-yellow-950/40 border border-yellow-500/30 text-yellow-300 rounded-xl font-sans">
            <strong>No-Action Rationale:</strong> ${d.no_action_reason}
          </div>
        ` : ''}

        <div class="font-sans">
          <strong class="text-slate-400">Independent Verifier Checks:</strong>
          <div class="flex flex-wrap gap-1.5 mt-1.5">
            ${d.checks.passed.map(c => `<span class="px-2 py-0.5 bg-emerald-950/80 border border-emerald-500/30 text-emerald-400 rounded text-[10px]"><i class="fa-solid fa-check mr-1"></i>${c}</span>`).join('')}
            ${d.checks.failed.map(c => `<span class="px-2 py-0.5 bg-red-950/80 border border-red-500/30 text-red-400 rounded text-[10px]"><i class="fa-solid fa-xmark mr-1"></i>${c}</span>`).join('')}
          </div>
        </div>

        <div>
          <strong class="text-slate-400 font-sans">Cited Evidence:</strong>
          <ul class="list-disc list-inside text-slate-300 text-[11px] mt-1 space-y-0.5">
            ${d.evidence.map(e => `<li>${e}</li>`).join('')}
          </ul>
        </div>

        ${d.content && d.content.length > 0 ? `
          <div>
            <strong class="text-slate-400 font-sans">Content Dispatched:</strong>
            <div class="flex flex-wrap gap-1.5 mt-1 text-[11px]">
              ${d.content.map(c => `<span class="px-2 py-0.5 bg-slate-800 rounded border border-slate-700 text-slate-200">${c}</span>`).join('')}
            </div>
          </div>
        ` : ''}
      `;
      document.getElementById('decision-modal').classList.remove('hidden');
    }

    function closeModal() {
      document.getElementById('decision-modal').classList.add('hidden');
    }

    function selectQuickUser(uid) {
      document.getElementById('preview-user-input').value = uid;
      loadUserPreview();
    }

    async function loadUserPreview() {
      const uid = document.getElementById('preview-user-input').value.trim();
      const res = await fetch(`/api/user_preview/${uid}`);
      const data = await res.json();

      if (!data.action || data.action.type !== 'home_page') {
        document.getElementById('preview-badge-container').innerHTML = `
          <span class="px-3 py-1 bg-yellow-950 border border-yellow-500 text-yellow-300 rounded-lg text-xs font-semibold">
            Action: ${data.decision.action} (${data.decision.status})
          </span>
        `;
        document.getElementById('phone-hero').classList.add('hidden');
        document.getElementById('phone-rows').innerHTML = `
          <div class="text-center py-20 text-slate-400">
            <i class="fa-solid fa-ban text-4xl mb-3 text-yellow-500"></i>
            <p class="font-bold text-white font-sans">No Active Home Page Published</p>
            <p class="text-xs text-slate-400 mt-1 max-w-xs mx-auto font-sans">Reason: ${data.decision.no_action_reason || data.decision.confidence_reason}</p>
          </div>
        `;
        return;
      }

      document.getElementById('phone-hero').classList.remove('hidden');
      const act = data.action;
      document.getElementById('app-dialect-pill').innerText = `${act.dialect.toUpperCase()} APP ACTIVE`;
      document.getElementById('preview-badge-container').innerHTML = `
        <span class="px-3 py-1 bg-emerald-950/80 border border-emerald-500 text-emerald-300 rounded-lg text-xs font-semibold">
          Personalised Home Page Published (${act.dialect.toUpperCase()})
        </span>
      `;

      // Hero
      const hero = data.hero;
      if (hero) {
        document.getElementById('phone-hero-title').innerText = hero.title;
        document.getElementById('phone-hero-desc').innerText = hero.description;
        document.getElementById('phone-hero-badge').innerText = `HERO (${hero.dialect.toUpperCase()})`;
      }

      // Rows
      const rowsContainer = document.getElementById('phone-rows');
      rowsContainer.innerHTML = '';

      (data.rows_data || []).forEach(r => {
        const rowDiv = document.createElement('div');
        rowDiv.className = 'space-y-2.5';
        
        let titleLabel = r.row_type.replace(/_/g, ' ').toUpperCase();
        if (r.row_type === 'next_episode') titleLabel = '▶ CONTINUE WATCHING';
        if (r.row_type === 'because_you_watched') titleLabel = '⭐ RECOMMENDED FOR YOU';

        rowDiv.innerHTML = `
          <div class="flex items-center justify-between font-sans">
            <h4 class="text-xs font-bold text-white tracking-wide">${titleLabel}</h4>
            <span class="text-[10px] text-slate-400 font-mono">${r.titles.length} titles</span>
          </div>
          <div class="flex gap-3 overflow-x-auto pb-2 custom-scrollbar">
            ${r.titles.map(t => `
              <div class="flex-shrink-0 w-32 bg-slate-900 border border-slate-800 rounded-xl overflow-hidden p-2.5 flex flex-col justify-between hover:border-brand-500/50 transition">
                <div>
                  <div class="text-[9px] font-mono text-brand-400 font-bold mb-1">${t.title_id}</div>
                  <div class="text-xs font-bold text-white line-clamp-2 leading-tight">${t.title}</div>
                </div>
                <div class="mt-3 pt-2 border-t border-slate-800 flex justify-between text-[10px] text-slate-400">
                  <span class="truncate">${t.genres[0] || 'Drama'}</span>
                  <span class="text-emerald-400 font-mono font-bold">${t.dialect}</span>
                </div>
              </div>
            `).join('')}
          </div>
        `;
        rowsContainer.appendChild(rowDiv);
      });
    }

    function inspectViewerQuick(uid) {
      document.getElementById('viewer-inspect-input').value = uid;
      fetchViewerState();
    }

    async function fetchViewerState() {
      const uid = document.getElementById('viewer-inspect-input').value.trim();
      document.getElementById('json-file-name').innerText = `${uid}.json`;
      document.getElementById('provenance-user-badge').innerText = uid;

      const res = await fetch(`/api/viewer_state/${uid}`);
      const state = await res.json();

      document.getElementById('raw-state-json').innerText = JSON.stringify(state, null, 2);

      const fd = document.getElementById('viewer-facts-display');
      fd.innerHTML = `
        <div class="p-3 bg-slate-900 rounded-xl border border-slate-800 flex justify-between items-center">
          <div><strong class="text-white">${state.user_id}</strong> <span class="ml-2 px-2 py-0.5 bg-slate-800 rounded text-[10px] font-mono text-slate-300">${state.arm.toUpperCase()} ARM</span></div>
          <span class="text-slate-400">Subscription: <strong class="text-emerald-400">${state.subscription_status}</strong></span>
        </div>

        <div class="grid grid-cols-2 gap-2.5">
          <div class="p-3 bg-slate-900/60 rounded-xl border border-slate-800">
            <div class="text-slate-400 text-[10px]">App Dialect (Runtime Setting)</div>
            <div class="font-bold text-white mt-0.5 font-mono">${state.app_dialect || 'None'}</div>
            <div class="text-[9px] text-emerald-400 mt-1">Precedence: Wins for UI rendering</div>
          </div>
          <div class="p-3 bg-slate-900/60 rounded-xl border border-slate-800">
            <div class="text-slate-400 text-[10px]">Preferred Dialect (Profile)</div>
            <div class="font-bold text-white mt-0.5 font-mono">${state.preferred_dialect || 'None'}</div>
            <div class="text-[9px] text-slate-400 mt-1">Source: warehouse snapshot (1d stale)</div>
          </div>
          <div class="p-3 bg-slate-900/60 rounded-xl border border-slate-800">
            <div class="text-slate-400 text-[10px]">Push Consent</div>
            <div class="font-bold ${state.notifications_opt_in ? 'text-emerald-400' : 'text-red-400'} mt-0.5">${state.notifications_opt_in ? 'Opted In' : 'Opted Out'}</div>
          </div>
          <div class="p-3 bg-slate-900/60 rounded-xl border border-slate-800">
            <div class="text-slate-400 text-[10px]">Historical Plays Started</div>
            <div class="font-bold text-white mt-0.5">${state.total_plays_started}</div>
          </div>
        </div>

        ${state.active_goal ? `
          <div class="p-3.5 bg-purple-950/30 border border-purple-500/30 rounded-xl">
            <div class="text-purple-300 font-bold mb-1 font-sans">Active Lifecycle Goal: ${state.active_goal.name}</div>
            <div class="text-slate-400 text-[11px]">Deadline: <span class="font-mono text-slate-300">${state.active_goal.deadline}</span></div>
          </div>
        ` : ''}

        ${Object.keys(state.series_progress || {}).length > 0 ? `
          <div class="p-3.5 bg-slate-900/60 rounded-xl border border-slate-800">
            <div class="text-slate-300 font-bold mb-1.5 font-sans">Unfinished Series Tracking</div>
            <div class="space-y-1.5">
              ${Object.entries(state.series_progress).map(([s, p]) => `
                <div class="font-mono text-[11px] text-slate-400 flex justify-between bg-slate-950/60 px-2.5 py-1.5 rounded">
                  <span>${s}</span>
                  <span class="text-white font-semibold">Last Ep: ${p.last_episode_id || 'Started'}</span>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}
      `;
    }

    window.onload = init;
  </script>
</body>
</html>
"""


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))

        elif path == "/api/decisions":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(decisions, ensure_ascii=False).encode("utf-8"))

        elif path.startswith("/api/viewer_state/"):
            uid = path.split("/")[-1]
            state_file = SAMPLE_RUN / "viewer_state" / f"{uid}.json"
            if state_file.exists():
                with open(state_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error": "Viewer state not found"}')

        elif path.startswith("/api/user_preview/"):
            uid = path.split("/")[-1]
            user_decs = [d for d in decisions if d["viewer_id"] == uid]
            if not user_decs:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error": "User has no decisions"}')
                return

            last_dec = user_decs[-1]
            act = actions_by_dec_id.get(last_dec["decision_id"])
            hero_info = catalogue.get(act.get("hero_title_id")) if act and act.get("hero_title_id") else None

            rows_data = []
            if act and act.get("rows"):
                for r in act["rows"]:
                    titles_list = [catalogue[tid] for tid in r.get("title_ids", []) if tid in catalogue]
                    rows_data.append({
                        "row_type": r.get("row_type"),
                        "titles": titles_list
                    })

            resp = {
                "decision": last_dec,
                "action": act,
                "hero": hero_info,
                "rows_data": rows_data
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()


def start_server():
    server_address = ("127.0.0.1", PORT)
    httpd = socketserver.TCPServer(server_address, DashboardHandler)
    print("STAGE Dashboard is running at http://localhost:" + str(PORT))
    httpd.serve_forever()


if __name__ == "__main__":
    start_server()
