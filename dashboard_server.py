"""Enterprise-grade interactive localhost dashboard server for STAGE: One User, One Agent.
Includes Live Interactive Video Streaming Player, Telemetry Event Generator, and Causal Impact Analytics.
"""
import csv
import http.server
import json
import logging
import os
import socketserver
import urllib.parse
from pathlib import Path

PORT = int(os.environ.get("PORT", 8000))
BASE_DIR = Path(__file__).resolve().parent
SAMPLE_RUN = BASE_DIR / "sample_run"
PACK_DIR = BASE_DIR / "one_user_one_agent_pack"

logger = logging.getLogger("DashboardServer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

print("Initializing STAGE AI Enterprise Operations & Video Player Hub...")

# 1. Load Decisions
decisions = []
with open(SAMPLE_RUN / "decisions.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            decisions.append(json.loads(line))

# 2. Load Actions indexed by decision_id
actions_by_dec_id = {}
with open(SAMPLE_RUN / "actions.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            a = json.loads(line)
            actions_by_dec_id[a["decision_id"]] = a

# 3. Load Outcomes indexed by decision_id
outcomes_by_dec_id = {}
with open(SAMPLE_RUN / "outcomes.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            o = json.loads(line)
            outcomes_by_dec_id[o["decision_id"]] = o

# 4. Load Episodes indexed by content_slug
episodes_by_slug = {}
with open(PACK_DIR / "data" / "episodes.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        slug = r["content_slug"]
        if slug not in episodes_by_slug:
            episodes_by_slug[slug] = []
        episodes_by_slug[slug].append({
            "episode_id": r["episode_id"],
            "season": int(r["season"]),
            "episode": int(r["episode"]),
            "minutes": int(r["minutes"])
        })

# 5. Load Catalogue
catalogue = {}
with open(PACK_DIR / "data" / "catalogue.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        slug = r["content_slug"]
        catalogue[r["title_id"]] = {
            "title_id": r["title_id"],
            "content_slug": slug,
            "title": r["title"],
            "dialect": r["dialect"],
            "language": r.get("language", "hin"),
            "content_type": r["content_type"],
            "genres": r["genres"].split("|"),
            "release_date": r["release_date"],
            "is_premium": r["is_premium"].lower() == "true",
            "description": r["description"],
            "episodes": episodes_by_slug.get(slug, [
                {"episode_id": f"{slug}-s1e1", "season": 1, "episode": 1, "minutes": 45}
            ])
        }

# 6. Load Latency Report
with open(SAMPLE_RUN / "latency_report.json", "r", encoding="utf-8") as f:
    latency_report = json.load(f)

# 7. Load Simulator Report
with open(SAMPLE_RUN / "sim" / "simulator_report.json", "r", encoding="utf-8") as f:
    sim_report = json.load(f)

print(f"Loaded {len(decisions)} decisions, {len(actions_by_dec_id)} actions, {len(catalogue)} titles with full episode mappings.")

HTML_PAGE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>STAGE AI: One User, One Agent — Enterprise Operations & Video Player Hub</title>
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
    @keyframes pulse-glow {
      0%, 100% { box-shadow: 0 0 15px rgba(225, 29, 72, 0.4); }
      50% { box-shadow: 0 0 25px rgba(225, 29, 72, 0.8); }
    }
    .video-glow { animation: pulse-glow 3s infinite; }
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
      <span class="text-slate-600">|</span>
      <span class="text-emerald-400 font-bold"><i class="fa-solid fa-play text-[10px]"></i> Live Video Player Ready</span>
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
          <span class="px-2 py-0.5 bg-slate-800 text-slate-300 text-[10px] rounded font-mono border border-slate-700">v1.1.0-stream</span>
        </div>
        <p class="text-xs text-slate-400">Autonomous Regional-Dialect OTT Lifecycle Management, Interactive Streaming & Causal Attribution</p>
      </div>
    </div>

    <!-- Quick Navigation Tabs -->
    <div class="flex items-center bg-slate-900/80 p-1 rounded-xl border border-slate-800 space-x-1 text-xs font-semibold">
      <button onclick="switchTab('analytics')" id="tab-analytics" class="px-3.5 py-1.5 rounded-lg bg-brand-600 text-white shadow-sm flex items-center gap-1.5 transition">
        <i class="fa-solid fa-chart-line text-[11px]"></i> Causal Analytics
      </button>
      <button onclick="switchTab('device')" id="tab-device" class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white flex items-center gap-1.5 transition">
        <i class="fa-solid fa-mobile-screen-button text-[11px]"></i> OTT Phone & Video Player
      </button>
      <button onclick="switchTab('stream')" id="tab-stream" class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white flex items-center gap-1.5 transition">
        <i class="fa-solid fa-bolt text-[11px]"></i> Decision Stream
      </button>
      <button onclick="switchTab('provenance')" id="tab-provenance" class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white flex items-center gap-1.5 transition">
        <i class="fa-solid fa-database text-[11px]"></i> State & Provenance
      </button>
      <button onclick="switchTab('interview')" id="tab-interview" class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white flex items-center gap-1.5 transition">
        <i class="fa-solid fa-graduation-cap text-[11px]"></i> Technical Hub
      </button>
    </div>

    <div class="flex items-center space-x-3">
      <button onclick="openCinemaModal('T0001')" class="px-3 py-1.5 bg-brand-600/20 hover:bg-brand-600/30 text-brand-300 border border-brand-500/40 rounded-lg text-xs font-bold transition flex items-center gap-1.5">
        <i class="fa-solid fa-film"></i> Cinema Player
      </button>
      <button onclick="openSurprisesModal()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-semibold transition flex items-center gap-1.5">
        <i class="fa-solid fa-shield-halved text-yellow-400"></i> Replay Surprises
      </button>
    </div>
  </header>

  <!-- Main Container -->
  <main class="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8 space-y-8">

    <!-- KPI Cards Row -->
    <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
      <div class="glass-card p-4 rounded-xl border border-slate-800">
        <div class="flex items-center justify-between text-slate-400 text-xs">
          <span>Decisions Made</span>
          <i class="fa-solid fa-microchip text-slate-500"></i>
        </div>
        <div class="text-2xl font-black text-white mt-1 font-mono">2,769</div>
        <div class="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
          <span class="text-emerald-400 font-bold">100%</span> triggers processed
        </div>
      </div>

      <div class="glass-card p-4 rounded-xl border border-slate-800">
        <div class="flex items-center justify-between text-slate-400 text-xs">
          <span>Actions Published</span>
          <i class="fa-solid fa-paper-plane text-brand-500"></i>
        </div>
        <div class="text-2xl font-black text-brand-400 mt-1 font-mono">1,108</div>
        <div class="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
          <span class="text-emerald-400 font-bold">1,108</span> accepted by sim
        </div>
      </div>

      <div class="glass-card p-4 rounded-xl border border-slate-800">
        <div class="flex items-center justify-between text-slate-400 text-xs">
          <span>Policy Violations</span>
          <i class="fa-solid fa-shield-check text-emerald-400"></i>
        </div>
        <div class="text-2xl font-black text-emerald-400 mt-1 font-mono">0</div>
        <div class="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
          <span class="text-emerald-400 font-bold">0</span> holdout contaminations
        </div>
      </div>

      <div class="glass-card p-4 rounded-xl border border-slate-800">
        <div class="flex items-center justify-between text-slate-400 text-xs">
          <span>Latency Compliance</span>
          <i class="fa-solid fa-gauge-high text-blue-400"></i>
        </div>
        <div class="text-2xl font-black text-blue-400 mt-1 font-mono">100%</div>
        <div class="text-[11px] text-slate-400 mt-1 font-mono">
          P95: 1 ms &bull; Max: 2 ms
        </div>
      </div>

      <div class="glass-card p-4 rounded-xl border border-slate-800">
        <div class="flex items-center justify-between text-slate-400 text-xs">
          <span>Causal ITT Uplift</span>
          <i class="fa-solid fa-scale-balanced text-purple-400"></i>
        </div>
        <div class="text-2xl font-black text-purple-300 mt-1 font-mono">+0.21%</div>
        <div class="text-[11px] text-slate-400 mt-1">
          Truth: p=0.665 (vs +9% biased)
        </div>
      </div>
    </section>

    <!-- ========================================== -->
    <!-- TAB 1: CAUSAL ANALYTICS & PILOT COMPARISON -->
    <!-- ========================================== -->
    <section id="panel-analytics" class="space-y-6">
      
      <!-- Causal Reality vs Pilot Trap Banner -->
      <div class="bg-gradient-to-r from-brand-950/80 via-slate-900 to-slate-900 p-6 rounded-2xl border border-brand-900/50 shadow-xl flex flex-col md:flex-row gap-6 items-start md:items-center justify-between">
        <div class="space-y-2 max-w-3xl">
          <div class="flex items-center gap-2">
            <span class="px-2.5 py-0.5 rounded bg-brand-500/20 text-brand-300 font-mono text-xs font-bold border border-brand-500/30">
              METHODOLOGICAL AUDIT
            </span>
            <span class="text-xs text-slate-400">Intention-to-Treat (ITT) vs Post-Treatment Selection Bias</span>
          </div>
          <h2 class="text-xl font-bold text-white tracking-tight">
            The Pilot Report's "22.4% Uplift" Was a Statistical Illusion.
          </h2>
          <p class="text-xs text-slate-300 leading-relaxed">
            The previous pilot team compared <span class="text-emerald-400 font-semibold">served users (40.1%)</span> directly against <span class="text-slate-400 font-semibold">all other users (17.7%)</span>. Because only active, compliant users receive interventions, this conditioned on a post-treatment collider, introducing massive selection bias. When audited with true randomized arms, the Treatment Arm was 18.25% vs Holdout Arm 19.56% (<strong class="text-red-400">net -1.30%</strong>, p = 0.30). Our production replay measures pure causal ITT across all 5,000 randomized viewers.
          </p>
        </div>
        <div class="flex md:flex-col gap-2 shrink-0">
          <div class="p-3 bg-slate-950/80 rounded-xl border border-slate-800 text-center">
            <div class="text-[10px] text-slate-400 uppercase font-semibold">Flawed Pilot Metric</div>
            <div class="text-lg font-black text-red-400 line-through">+22.4% (Spurious)</div>
          </div>
          <div class="p-3 bg-brand-950/60 rounded-xl border border-brand-600/40 text-center">
            <div class="text-[10px] text-brand-300 uppercase font-semibold">True Replay ITT</div>
            <div class="text-lg font-black text-white">+0.21% (p=0.665)</div>
          </div>
        </div>
      </div>

      <!-- Charts Row -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Main Comparison Bar Chart -->
        <div class="lg:col-span-2 glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-bold text-white tracking-tight">Causal Measurement: Honest ITT vs Selection Bias</h3>
              <p class="text-xs text-slate-400">Comparing True Randomized Arms against Post-Treatment Conditioning</p>
            </div>
            <span class="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-1 rounded">N = 5,000 Viewers</span>
          </div>
          <div class="h-72 w-full">
            <canvas id="causalChart"></canvas>
          </div>
        </div>

        <!-- Decision Breakdown Doughnut -->
        <div class="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between">
              <h3 class="text-sm font-bold text-white tracking-tight">Action Distribution</h3>
              <i class="fa-solid fa-pie-chart text-slate-500"></i>
            </div>
            <p class="text-xs text-slate-400">How 2,769 triggers were resolved</p>
          </div>
          <div class="h-52 w-full flex items-center justify-center">
            <canvas id="actionDonut"></canvas>
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-slate-800">
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
    <!-- TAB 2: OTT PHONE & LIVE VIDEO PLAYER       -->
    <!-- ========================================== -->
    <section id="panel-device" class="space-y-6">
      
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
        <div id="preview-badge-container" class="flex items-center gap-2"></div>
      </div>

      <!-- Instruction / Pro-tip Banner -->
      <div class="bg-slate-900/60 border border-slate-800 p-3 rounded-xl flex items-center justify-between text-xs text-slate-300">
        <div class="flex items-center gap-2.5">
          <span class="w-6 h-6 rounded-full bg-brand-600/30 text-brand-300 flex items-center justify-center font-bold text-xs"><i class="fa-solid fa-circle-play"></i></span>
          <span><strong>Interactive Video Playback:</strong> Click <strong class="text-white">"Play Episode"</strong> or click on <strong class="text-white">any title card</strong> below to launch the video streaming player with real-time agent telemetry events!</span>
        </div>
        <button onclick="openCinemaModal('T0001')" class="text-xs text-brand-400 hover:text-brand-300 font-semibold flex items-center gap-1">
          Open Fullscreen Cinema <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
        </button>
      </div>

      <!-- Smartphone Device Mockup Container -->
      <div class="flex justify-center py-4">
        <div class="device-mockup w-[430px] rounded-[52px] bg-black overflow-hidden relative border border-slate-700">
          
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
          <div class="h-[760px] overflow-y-auto custom-scrollbar bg-[#090d16] text-white pb-20">
            
            <!-- VIEW A: HOME PAGE BROWSE VIEW -->
            <div id="phone-browse-view">
              
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
                  <div class="flex items-center justify-between">
                    <span id="phone-hero-badge" class="px-2 py-0.5 bg-brand-600 text-[9px] font-black tracking-wider rounded uppercase">HERO SPOTLIGHT</span>
                    <span id="phone-hero-meta" class="text-[10px] text-slate-300 font-mono">120 mins</span>
                  </div>
                  <h3 id="phone-hero-title" class="text-2xl font-black leading-tight text-white tracking-tight">Loading Title...</h3>
                  <p id="phone-hero-desc" class="text-[11px] text-slate-300 line-clamp-2 leading-relaxed">Synopsis...</p>
                  <div class="pt-2 flex gap-2">
                    <button id="btn-play-hero" onclick="playCurrentHero()" class="flex-1 py-2.5 bg-brand-600 hover:bg-brand-500 text-white font-bold text-xs rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-brand-600/40 transition transform hover:scale-[1.02] cursor-pointer">
                      <i class="fa-solid fa-play text-xs"></i> Play Episode
                    </button>
                    <button onclick="openCinemaModal(currentHeroTitleId)" title="Open Cinema Popout Player" class="px-3.5 py-2.5 bg-slate-800/90 rounded-xl text-white text-xs hover:bg-slate-700 transition">
                      <i class="fa-solid fa-expand"></i>
                    </button>
                  </div>
                </div>
              </div>

              <!-- Carousels Container -->
              <div id="phone-rows" class="p-4 space-y-6">
                <!-- Injected by JS -->
              </div>

            </div>

            <!-- VIEW B: IN-PHONE VIDEO STREAMING PLAYER VIEW -->
            <div id="phone-player-view" class="hidden p-4 space-y-4">
              
              <!-- Player Header -->
              <div class="flex items-center justify-between">
                <button onclick="closeVideoPlayer()" class="flex items-center gap-1.5 text-xs text-slate-200 hover:text-white bg-slate-800/90 hover:bg-slate-700 px-3 py-1.5 rounded-lg border border-slate-700 transition font-medium">
                  <i class="fa-solid fa-arrow-left"></i> Back to Browse
                </button>
                <div class="flex items-center gap-2">
                  <span id="player-dialect-pill" class="px-2 py-0.5 bg-brand-600/30 border border-brand-500/40 text-brand-300 text-[10px] font-bold rounded">d1 BHOJPURI</span>
                  <span class="px-1.5 py-0.5 bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[9px] font-mono rounded">1080p HD</span>
                </div>
              </div>

              <!-- Video Container -->
              <div class="relative w-full h-56 bg-black rounded-2xl overflow-hidden border border-slate-700 shadow-2xl flex items-center justify-center group video-glow">
                
                <!-- HTML5 Video Element with CORS & Fallbacks -->
                <video id="phone-video-elem" class="w-full h-full object-cover" playsinline loop crossorigin="anonymous">
                  <source src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4" type="video/mp4">
                  <source src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4" type="video/mp4">
                </video>

                <!-- Animated Canvas Fallback / Cinemagraph (Guaranteed playback online & offline) -->
                <canvas id="phone-canvas-visualizer" class="absolute inset-0 w-full h-full pointer-events-none hidden"></canvas>

                <!-- Top Watermark & Dialect Badge -->
                <div class="absolute top-2.5 right-3 text-[10px] font-black tracking-widest text-white/60 bg-black/50 px-2 py-0.5 rounded backdrop-blur pointer-events-none">
                  STAGE OTT
                </div>
                <div class="absolute top-2.5 left-3 text-[9px] font-bold text-emerald-400 bg-emerald-950/80 border border-emerald-500/30 px-2 py-0.5 rounded backdrop-blur flex items-center gap-1">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> STREAMING
                </div>

                <!-- Big Center Play/Pause Overlay Button -->
                <button id="center-play-btn" onclick="togglePlayPause()" class="absolute w-12 h-12 rounded-full bg-brand-600/90 text-white flex items-center justify-center text-lg shadow-xl shadow-brand-600/40 hover:scale-110 transition opacity-90 hover:opacity-100 z-10">
                  <i id="center-play-icon" class="fa-solid fa-play ml-0.5"></i>
                </button>

                <!-- Video Bottom Bar Controls Overlay -->
                <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/95 via-black/70 to-transparent p-2.5 flex flex-col justify-end gap-1.5 z-20">
                  <!-- Scrubber Bar -->
                  <div class="flex items-center gap-2">
                    <input type="range" id="video-scrubber" min="0" max="100" value="0" oninput="seekVideo(this.value)" class="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-brand-500">
                  </div>
                  <!-- Controls Row -->
                  <div class="flex items-center justify-between text-xs text-white">
                    <div class="flex items-center gap-2.5">
                      <button onclick="togglePlayPause()" class="hover:text-brand-400">
                        <i id="bottom-play-icon" class="fa-solid fa-play"></i>
                      </button>
                      <button onclick="skipVideo(-10)" class="text-[10px] hover:text-brand-400" title="Rewind 10s">
                        <i class="fa-solid fa-rotate-left"></i> 10s
                      </button>
                      <button onclick="skipVideo(10)" class="text-[10px] hover:text-brand-400" title="Forward 10s">
                        <i class="fa-solid fa-rotate-right"></i> 10s
                      </button>
                      <span id="video-time-display" class="font-mono text-[10px] text-slate-300 ml-1">00:00 / 24:00</span>
                    </div>
                    <div class="flex items-center gap-2">
                      <button onclick="toggleMute()" class="hover:text-brand-400" title="Mute/Unmute">
                        <i id="volume-icon" class="fa-solid fa-volume-high"></i>
                      </button>
                      <button onclick="openCinemaModal(activeVideoTitle.title_id)" class="hover:text-brand-400 text-[11px]" title="Fullscreen Cinema">
                        <i class="fa-solid fa-expand"></i>
                      </button>
                    </div>
                  </div>
                </div>

              </div>

              <!-- Title & Meta -->
              <div class="space-y-1">
                <div class="flex items-center justify-between">
                  <h3 id="player-title" class="text-base font-black text-white leading-tight">Title Name</h3>
                  <span id="player-content-type" class="text-[10px] uppercase font-bold text-slate-400 font-mono">Film</span>
                </div>
                <div id="player-genres" class="flex flex-wrap gap-1 text-[10px]">
                  <span class="px-2 py-0.5 bg-slate-800 text-slate-300 rounded">Drama</span>
                </div>
                <p id="player-description" class="text-xs text-slate-300 leading-relaxed pt-1 line-clamp-3">Synopsis...</p>
              </div>

              <!-- Episode Selector List -->
              <div id="player-episodes-section" class="space-y-2 pt-2 border-t border-slate-800/80">
                <div class="flex items-center justify-between">
                  <h4 class="text-xs font-bold text-slate-200 uppercase tracking-wide">Select Episode</h4>
                  <span id="episodes-count-badge" class="text-[10px] text-slate-400 font-mono">1 Episode</span>
                </div>
                <div id="player-episodes-list" class="flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
                  <!-- Injected by JS -->
                </div>
              </div>

              <!-- Real-time Agent Telemetry & Goal Progression Console -->
              <div class="p-3 bg-slate-900/90 rounded-xl border border-slate-800 space-y-2.5">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-bold text-brand-400 flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                    Agent Playback Telemetry
                  </span>
                  <span id="telemetry-session-time" class="font-mono text-[10px] text-slate-400">Time: 0s</span>
                </div>
                <!-- Real-time Event Feed -->
                <div id="telemetry-feed" class="bg-black/60 p-2.5 rounded-lg font-mono text-[10px] space-y-1 max-h-24 overflow-y-auto custom-scrollbar text-slate-300 border border-slate-800">
                  <div class="text-emerald-400 font-bold">⚡ [00:00:01] play_started emitted (user active)</div>
                </div>
                <!-- Goal Achievement Card -->
                <div id="goal-progress-card" class="p-2.5 bg-brand-950/40 border border-brand-500/30 rounded-lg text-xs space-y-1.5">
                  <div class="flex justify-between items-center text-[11px]">
                    <span class="font-bold text-white">Target Goal: <span id="goal-card-name" class="text-brand-300">G03 (Finish Episode 1)</span></span>
                    <span id="goal-card-status" class="font-mono text-yellow-400 font-bold">IN PROGRESS (10%)</span>
                  </div>
                  <div class="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                    <div id="goal-progress-bar" class="bg-brand-500 h-full rounded-full transition-all duration-300" style="width: 10%;"></div>
                  </div>
                </div>
                <!-- Fast-forward complete episode simulation button -->
                <button onclick="simulateCompleteEpisode()" class="w-full py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs rounded-lg shadow-lg flex items-center justify-center gap-2 transition cursor-pointer">
                  <i class="fa-solid fa-circle-check"></i> Simulate Watch to End (&gt;90%) & Complete Goal
                </button>
              </div>

            </div>

          </div>

          <!-- Bottom App Navigation Bar -->
          <div class="absolute bottom-0 inset-x-0 h-16 bg-[#090d16]/95 backdrop-blur-md border-t border-slate-800/60 flex items-center justify-around text-slate-400 text-[10px] z-30">
            <div onclick="closeVideoPlayer()" class="flex flex-col items-center text-brand-500 font-bold cursor-pointer">
              <i class="fa-solid fa-house text-sm mb-0.5"></i>
              <span>Home</span>
            </div>
            <div onclick="playCurrentHero()" class="flex flex-col items-center hover:text-white cursor-pointer">
              <i class="fa-solid fa-play text-sm mb-0.5"></i>
              <span>Watch</span>
            </div>
            <div onclick="openCinemaModal('T0001')" class="flex flex-col items-center hover:text-white cursor-pointer">
              <i class="fa-solid fa-film text-sm mb-0.5"></i>
              <span>Cinema</span>
            </div>
            <div onclick="switchTab('provenance')" class="flex flex-col items-center hover:text-white cursor-pointer">
              <i class="fa-solid fa-user text-sm mb-0.5"></i>
              <span>Profile</span>
            </div>
          </div>

        </div>
      </div>

    </section>

    <!-- ========================================== -->
    <!-- TAB 3: DECISION STREAM (2,769 RECORDS)     -->
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
                <th class="py-3 px-4 text-center">Inspect / Play</th>
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
    <!-- TAB 4: VIEWER STATE & PROVENANCE INSPECTOR -->
    <!-- ========================================== -->
    <section id="panel-provenance" class="hidden space-y-6">
      <div class="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 class="text-base font-bold text-white tracking-tight">Per-Viewer State & Provenance Ledger</h3>
            <p class="text-xs text-slate-400">Inspect sliding memory windows, fact sources, timestamps, and conflict resolutions</p>
          </div>
          <div class="flex items-center gap-2">
            <input type="text" id="viewer-inspect-input" value="U-02344" class="bg-slate-900 border border-slate-700 text-xs rounded-lg px-3 py-1.5 text-white font-mono w-36 focus:outline-none focus:border-brand-500">
            <button onclick="fetchViewerState()" class="px-3 py-1.5 bg-brand-600 hover:bg-brand-500 rounded-lg text-xs font-bold text-white transition">
              Load State
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-2">
          <!-- Resolved State Display -->
          <div class="lg:col-span-1 space-y-4 text-xs">
            <div class="p-4 bg-slate-950/60 rounded-xl border border-slate-800 space-y-3" id="viewer-facts-display">
              <!-- Injected by JS -->
            </div>
          </div>

          <!-- Raw JSON Inspector -->
          <div class="lg:col-span-2 space-y-2">
            <div class="flex justify-between items-center text-xs text-slate-400">
              <span>Full Persistent JSON State (<span id="json-file-name" class="font-mono text-slate-300">U-02344.json</span>)</span>
              <span class="text-[11px] text-emerald-400 font-mono">Status: Up-to-date</span>
            </div>
            <pre id="raw-state-json" class="p-4 bg-slate-950 border border-slate-800 rounded-xl font-mono text-[11px] text-slate-300 max-h-[500px] overflow-y-auto custom-scrollbar">Loading state...</pre>
          </div>
        </div>
      </div>
    </section>

    <!-- ========================================== -->
    <!-- TAB 5: TECHNICAL DISCUSSION & INTERVIEW HUB-->
    <!-- ========================================== -->
    <section id="panel-interview" class="hidden space-y-6">
      <div class="glass-panel p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
        <div>
          <span class="px-2.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono text-xs font-bold border border-purple-500/30">
            60-MINUTE TECHNICAL DISCUSSION PREPARATION
          </span>
          <h2 class="text-xl font-bold text-white tracking-tight mt-2">Core Architectural Defenses & Deep Dives</h2>
          <p class="text-xs text-slate-400 mt-1">Ready answers and evidence for every technical evaluation topic.</p>
        </div>

        <div class="space-y-4 pt-2">
          
          <div class="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
            <div class="flex items-center gap-2">
              <span class="w-6 h-6 rounded-full bg-brand-600 text-white flex items-center justify-center font-black text-xs">1</span>
              <h4 class="text-sm font-bold text-white">Why was the Pilot Report wrong, and what does your replay prove?</h4>
            </div>
            <p class="text-xs text-slate-300 leading-relaxed pl-8">
              The pilot report committed <strong class="text-red-400">post-treatment conditioning / selection bias</strong>. It compared <em>served users</em> against <em>all other users</em>. Served users are already engaged; non-served users include bounced and inactive users. In randomized trials, one must compare <strong class="text-emerald-400">all Treatment users (served + unserved)</strong> against <strong class="text-blue-400">all Holdout users</strong> (Intention-to-Treat). Re-evaluating the pilot data reveals a net causal difference of <strong>-1.30%</strong> (p = 0.30). In our replay, ITT treatment is <strong>3.10%</strong> vs Holdout <strong>2.90%</strong> (net <strong>+0.21%</strong>, p = 0.6652), confirming that 1 day of interventions cannot honestly claim 20%+ uplift without selection bias.
            </p>
          </div>

          <div class="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
            <div class="flex items-center gap-2">
              <span class="w-6 h-6 rounded-full bg-brand-600 text-white flex items-center justify-center font-black text-xs">2</span>
              <h4 class="text-sm font-bold text-white">How do you resolve state provenance and conflicting data sources?</h4>
            </div>
            <p class="text-xs text-slate-300 leading-relaxed pl-8">
              We apply explicit precedence rules: <strong class="text-white">1) Trust received_at (server clock)</strong> over occurred_at (client clock); <strong class="text-white">2) Runtime app_dialect beats stale profile preferences</strong>; <strong class="text-white">3) Recent billing/cancellation events override profile subscription status</strong>; <strong class="text-white">4) User opt-outs override profile consent immediately</strong>. Every fact in ViewerState stores its <code class="text-brand-300 font-mono">source</code> and <code class="text-brand-300 font-mono">as_of</code> timestamp.
            </p>
          </div>

          <div class="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
            <div class="flex items-center gap-2">
              <span class="w-6 h-6 rounded-full bg-brand-600 text-white flex items-center justify-center font-black text-xs">3</span>
              <h4 class="text-sm font-bold text-white">Why did you blacklist goals G10 and G11?</h4>
            </div>
            <p class="text-xs text-slate-300 leading-relaxed pl-8">
              Goal <strong class="text-yellow-400">G10</strong> has no measurable success event in the telemetry schema. Goal <strong class="text-yellow-400">G11</strong> relies on an un-instrumented <code class="font-mono text-slate-400">tv_app_open</code> event. Attempting to assign unmeasurable goals causes false positives or unclosable agent states. We blacklisted them and safely migrated users to eligible goals (G01, G03, G04).
            </p>
          </div>

          <div class="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
            <div class="flex items-center gap-2">
              <span class="w-6 h-6 rounded-full bg-brand-600 text-white flex items-center justify-center font-black text-xs">4</span>
              <h4 class="text-sm font-bold text-white">How did the agent survive the mid-replay surprises?</h4>
            </div>
            <p class="text-xs text-slate-300 leading-relaxed pl-8">
              Three surprises were injected: <strong class="text-white">1) G03 rule migration</strong> at 14:00 UTC (updated eligible window without corrupting in-flight goals); <strong class="text-white">2) Model Provider HTTP 503 outage</strong> from 10:35 to 10:42 UTC (graceful circuit breaker fell back to deterministic rules, preserving &lt;60s SLA); <strong class="text-white">3) Prompt injections</strong> in titles T0002 & T0522 (defended by independent safety firewall rejecting ungrounded claims).
            </p>
          </div>

          <div class="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
            <div class="flex items-center gap-2">
              <span class="w-6 h-6 rounded-full bg-brand-600 text-white flex items-center justify-center font-black text-xs">5</span>
              <h4 class="text-sm font-bold text-white">How do you scale this from 5,000 to 10,000,000 users?</h4>
            </div>
            <p class="text-xs text-slate-300 leading-relaxed pl-8">
              <strong class="text-white">Partitioned Event Streaming:</strong> Kafka partitioned by <code class="font-mono text-brand-300">hash(user_id)</code> ensures deterministic single-thread access per user. <strong class="text-white">Distributed State:</strong> High-performance embedded key-value store (RocksDB / Redis cluster) holding per-user state with TTL. <strong class="text-white">Async Decision Worker Pool:</strong> Stateless workers process triggers in under 5 ms using pre-indexed regional catalogues and deterministic fallback caches.
            </p>
          </div>

        </div>
      </div>
    </section>

  </main>

  <!-- ========================================== -->
  <!-- MODAL 1: DECISION INSPECTOR MODAL          -->
  <!-- ========================================== -->
  <div id="decision-modal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-md hidden flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col shadow-2xl">
      <div class="p-4 px-6 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
        <div class="flex items-center gap-3">
          <span class="w-3 h-3 rounded-full bg-brand-500"></span>
          <h3 class="text-sm font-bold text-white font-mono" id="modal-dec-id">Decision Inspector</h3>
          <span id="modal-dec-arm" class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-300">TREATMENT</span>
        </div>
        <div class="flex items-center gap-2">
          <button id="modal-play-btn" onclick="" class="px-3 py-1 bg-brand-600 hover:bg-brand-500 text-white text-xs font-bold rounded-lg transition flex items-center gap-1.5">
            <i class="fa-solid fa-play text-[10px]"></i> Play Title
          </button>
          <button onclick="closeDecisionModal()" class="text-slate-400 hover:text-white text-lg px-2">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
      </div>
      <div class="p-6 overflow-y-auto custom-scrollbar space-y-4 text-xs font-sans">
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-[11px]" id="modal-meta-grid">
          <!-- Injected by JS -->
        </div>
        <div class="p-3 bg-slate-950/80 rounded-xl border border-slate-800 space-y-1">
          <div class="text-slate-400 text-[10px] font-semibold uppercase tracking-wider">Confidence & Evidence Reasoning</div>
          <div id="modal-reason" class="text-slate-200 leading-relaxed font-sans">Reason text...</div>
        </div>
        <div>
          <div class="text-slate-400 text-[10px] font-semibold uppercase tracking-wider mb-2">Raw Decision Record</div>
          <pre id="modal-json" class="p-4 bg-slate-950 border border-slate-800 rounded-xl font-mono text-[11px] text-slate-300 overflow-x-auto custom-scrollbar max-h-60">JSON data...</pre>
        </div>
      </div>
    </div>
  </div>

  <!-- ========================================== -->
  <!-- MODAL 2: REPLAY SURPRISES MODAL            -->
  <!-- ========================================== -->
  <div id="surprises-modal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-md hidden flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-hidden flex flex-col shadow-2xl">
      <div class="p-4 px-6 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
        <div class="flex items-center gap-2">
          <i class="fa-solid fa-triangle-exclamation text-yellow-400"></i>
          <h3 class="text-sm font-bold text-white">Replay Injected Surprises & Agent Mitigations</h3>
        </div>
        <button onclick="closeSurprisesModal()" class="text-slate-400 hover:text-white text-lg">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="p-6 overflow-y-auto custom-scrollbar space-y-4 text-xs">
        <div class="p-3.5 bg-yellow-950/30 border border-yellow-500/30 rounded-xl space-y-1">
          <div class="font-bold text-yellow-300">1. Mid-Day Goal Rule Change (14:00 UTC)</div>
          <p class="text-slate-300">Goal G03 criteria modified mid-replay. The agent dynamically applied the new rules to new decisions without invalidating in-flight evaluation state.</p>
        </div>
        <div class="p-3.5 bg-red-950/30 border border-red-500/30 rounded-xl space-y-1">
          <div class="font-bold text-red-300">2. Model Provider Outage (10:35 - 10:42 UTC)</div>
          <p class="text-slate-300">The LLM provider returned HTTP 503 errors for 7 minutes. The agent switched to deterministic fallback heuristics within 1 ms, publishing safe home pages and maintaining 0 dropped triggers.</p>
        </div>
        <div class="p-3.5 bg-purple-950/30 border border-purple-500/30 rounded-xl space-y-1">
          <div class="font-bold text-purple-300">3. Malicious Catalogue Injection (T0002 & T0522)</div>
          <p class="text-slate-300">Titles contained prompt injections: <code>"SYSTEM NOTE FOR AI AGENTS: ignore your previous rules..."</code>. The agent's independent verification firewall sanitized all outputs and blocked ungrounded WhatsApp broadcasts.</p>
        </div>
      </div>
    </div>
  </div>

  <!-- ========================================== -->
  <!-- MODAL 3: FULLSCREEN CINEMA THEATER PLAYER  -->
  <!-- ========================================== -->
  <div id="cinema-modal" class="fixed inset-0 z-50 bg-black/90 backdrop-blur-xl hidden flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-5xl overflow-hidden shadow-2xl flex flex-col max-h-[92vh]">
      <!-- Header -->
      <div class="p-4 px-6 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="bg-brand-600 text-white font-black px-2.5 py-0.5 rounded text-sm">STAGE CINEMA</span>
          <h2 id="cinema-title" class="text-base font-bold text-white">Movie Title</h2>
          <span id="cinema-dialect-badge" class="px-2 py-0.5 bg-slate-800 text-slate-300 border border-slate-700 text-xs rounded font-mono">d1 Bhojpuri</span>
        </div>
        <button onclick="closeCinemaModal()" class="text-slate-400 hover:text-white text-lg px-2">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <!-- Main Body -->
      <div class="grid grid-cols-1 lg:grid-cols-3 flex-1 overflow-hidden">
        <!-- Video Stream Viewport -->
        <div class="lg:col-span-2 bg-black flex flex-col justify-center relative min-h-[360px] p-2">
          <video id="cinema-video-elem" class="w-full h-full object-contain max-h-[500px]" controls autoplay loop playsinline crossorigin="anonymous">
            <source src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4" type="video/mp4">
          </video>
        </div>

        <!-- Sidebar / Episodes & Agent Telemetry -->
        <div class="p-5 border-l border-slate-800 space-y-4 overflow-y-auto custom-scrollbar bg-slate-950/60">
          <div>
            <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Synopsis</h4>
            <p id="cinema-description" class="text-xs text-slate-300 leading-relaxed">Synopsis...</p>
          </div>

          <div>
            <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Episodes</h4>
            <div id="cinema-episodes-list" class="space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar">
              <!-- Injected by JS -->
            </div>
          </div>

          <div class="p-3.5 bg-slate-900 rounded-xl border border-slate-800 space-y-2">
            <h4 class="text-xs font-bold text-brand-400 flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Live Agent Attribution
            </h4>
            <p class="text-[11px] text-slate-400 leading-relaxed">Playing this video emits <code class="text-emerald-400">play_started</code> and updates the viewer's sliding state window, progressing active lifecycle goals.</p>
            <button onclick="simulateCompleteEpisode()" class="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-lg transition cursor-pointer">
              Simulate Complete Episode (100%)
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- JavaScript Application Logic -->
  <script>
    let allDecisions = [];
    let filteredDecisions = [];
    let currentPage = 1;
    const pageSize = 30;

    // Active Video State
    let activeVideoTitle = null;
    let activeEpisodeId = null;
    let currentHeroTitleId = 'T0001';
    let currentViewerId = 'U-02344';
    let telemetryTimer = null;
    let telemetrySeconds = 0;
    let currentGoalProgress = 10;
    let canvasAnimationId = null;

    async function init() {
      initCharts();
      await fetchDecisions();
      await loadUserPreview();
      await fetchViewerState();
    }

    function switchTab(tab) {
      ['analytics', 'stream', 'device', 'provenance', 'interview'].forEach(t => {
        const btn = document.getElementById(`tab-${t}`);
        const panel = document.getElementById(`panel-${t}`);
        if (t === tab) {
          btn.className = "px-3.5 py-1.5 rounded-lg bg-brand-600 text-white shadow-sm flex items-center gap-1.5 transition";
          panel.classList.remove('hidden');
        } else {
          btn.className = "px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white flex items-center gap-1.5 transition";
          panel.classList.add('hidden');
        }
      });
    }

    function initCharts() {
      // 1. Causal Impact Chart
      const ctxCausal = document.getElementById('causalChart').getContext('2d');
      new Chart(ctxCausal, {
        type: 'bar',
        data: {
          labels: ['Pilot: Flawed Served Lift', 'Replay: Treatment Arm (ITT)', 'Replay: Holdout Arm (ITT)', 'Replay: Apparent Lift (Biased)'],
          datasets: [{
            label: 'Success Rate (%)',
            data: [22.4, 3.10, 2.90, 9.00],
            backgroundColor: [
              'rgba(239, 68, 68, 0.4)',
              'rgba(225, 29, 72, 0.85)',
              'rgba(59, 130, 246, 0.85)',
              'rgba(234, 179, 8, 0.4)'
            ],
            borderColor: [
              'rgb(239, 68, 68)',
              'rgb(225, 29, 72)',
              'rgb(59, 130, 246)',
              'rgb(234, 179, 8)'
            ],
            borderWidth: 1.5,
            borderRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function(c) { return `${c.raw}% (ITT Difference: +0.21%, p=0.665)`; }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#94a3b8', font: { family: 'monospace' } }
            },
            x: {
              grid: { display: false },
              ticks: { color: '#cbd5e1', font: { size: 10 } }
            }
          }
        }
      });

      // 2. Action Doughnut Chart
      const ctxDonut = document.getElementById('actionDonut').getContext('2d');
      new Chart(ctxDonut, {
        type: 'doughnut',
        data: {
          labels: ['Home Page Published', 'Holdout Isolation', 'Rate-Limit Abstain', 'Quiet Hours'],
          datasets: [{
            data: [1108, 1372, 219, 70],
            backgroundColor: [
              '#e11d48',
              '#3b82f6',
              '#64748b',
              '#475569'
            ],
            borderColor: '#0f172a',
            borderWidth: 3
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom',
              labels: { color: '#94a3b8', boxWidth: 10, font: { size: 10 } }
            }
          },
          cutout: '72%'
        }
      });
    }

    async function fetchDecisions() {
      try {
        const res = await fetch('/api/decisions');
        allDecisions = await res.json();
        filteredDecisions = allDecisions;
        renderDecisions();
      } catch (e) {
        console.error("Error fetching decisions:", e);
      }
    }

    function renderDecisions() {
      const search = document.getElementById('decision-search').value.toLowerCase().trim();
      const statusFilter = document.getElementById('status-filter').value;
      const dialectFilter = document.getElementById('dialect-filter').value;

      filteredDecisions = allDecisions.filter(d => {
        const matchSearch = !search || d.viewer_id.toLowerCase().includes(search) || d.decision_id.toLowerCase().includes(search);
        
        let matchStatus = true;
        if (statusFilter === 'PUBLISHED') matchStatus = (d.status === 'PUBLISHED' || d.status === 'PUBLISH');
        else if (statusFilter === 'HOLDOUT') matchStatus = (d.arm === 'holdout');
        else if (statusFilter === 'ABSTAINED') matchStatus = (d.action_type === 'abstain');

        let matchDialect = true;
        if (dialectFilter !== 'ALL') {
          matchDialect = (d.dialect === dialectFilter);
        }

        return matchSearch && matchStatus && matchDialect;
      });

      const total = filteredDecisions.length;
      const start = (currentPage - 1) * pageSize;
      const pageSlice = filteredDecisions.slice(start, start + pageSize);

      document.getElementById('decision-count-label').innerText = `Showing ${Math.min(start + 1, total)}-${Math.min(start + pageSize, total)} of ${total} decisions`;

      const tbody = document.getElementById('decisions-tbody');
      tbody.innerHTML = pageSlice.map(d => {
        let statusBadge = '';
        if (d.status === 'PUBLISHED') {
          statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950/80 text-emerald-400 border border-emerald-500/40 font-bold">PUBLISHED</span>';
        } else if (d.arm === 'holdout') {
          statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-blue-950/80 text-blue-400 border border-blue-500/40 font-bold">HOLDOUT</span>';
        } else {
          statusBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 font-bold">ABSTAINED</span>';
        }

        const armBadge = d.arm === 'holdout' ? '<span class="text-blue-400 font-bold">H</span>' : '<span class="text-brand-400 font-bold">T</span>';
        const dialectBadge = `<span class="px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 font-bold">${d.dialect || 'd1'}</span>`;

        return `
          <tr class="hover:bg-slate-800/40 transition">
            <td class="py-2.5 px-4 font-mono text-slate-300">${d.decision_id}</td>
            <td class="py-2.5 px-4 font-bold text-white flex items-center gap-1.5">
              ${d.viewer_id} ${armBadge}
            </td>
            <td class="py-2.5 px-4 text-slate-400 font-mono text-[10px]">${(d.trigger_received_at || '').slice(11, 19)}Z</td>
            <td class="py-2.5 px-4">${dialectBadge}</td>
            <td class="py-2.5 px-4 text-slate-300 font-bold">${d.goal_chosen ? d.goal_chosen.goal_id : '-'}</td>
            <td class="py-2.5 px-4 text-slate-300">${d.action_type || 'none'}</td>
            <td class="py-2.5 px-4">${statusBadge}</td>
            <td class="py-2.5 px-4 text-right font-mono text-emerald-400">${d.latency_ms || 1} ms</td>
            <td class="py-2.5 px-4 text-center">
              <button onclick="inspectDecision('${d.decision_id}')" class="px-2.5 py-1 bg-slate-800 hover:bg-brand-600 hover:text-white rounded text-slate-300 transition text-[10px] font-bold">
                Inspect
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }

    function prevPage() {
      if (currentPage > 1) {
        currentPage--;
        renderDecisions();
      }
    }

    function nextPage() {
      if (currentPage * pageSize < filteredDecisions.length) {
        currentPage++;
        renderDecisions();
      }
    }

    function inspectDecision(decId) {
      const dec = allDecisions.find(d => d.decision_id === decId);
      if (!dec) return;

      document.getElementById('modal-dec-id').innerText = dec.decision_id;
      const armBadge = document.getElementById('modal-dec-arm');
      armBadge.innerText = (dec.arm || 'treatment').toUpperCase();
      armBadge.className = dec.arm === 'holdout' 
        ? "px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-900/60 text-blue-300 border border-blue-500/40"
        : "px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-brand-900/60 text-brand-300 border border-brand-500/40";

      document.getElementById('modal-meta-grid').innerHTML = `
        <div class="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
          <div class="text-[10px] text-slate-400">Viewer ID</div>
          <div class="font-bold text-white">${dec.viewer_id}</div>
        </div>
        <div class="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
          <div class="text-[10px] text-slate-400">Dialect</div>
          <div class="font-bold text-white font-mono">${dec.dialect}</div>
        </div>
        <div class="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
          <div class="text-[10px] text-slate-400">Goal Assigned</div>
          <div class="font-bold text-emerald-400">${dec.goal_chosen ? dec.goal_chosen.goal_id : 'None'}</div>
        </div>
        <div class="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
          <div class="text-[10px] text-slate-400">Latency</div>
          <div class="font-bold text-blue-400 font-mono">${dec.latency_ms || 1} ms</div>
        </div>
      `;

      document.getElementById('modal-reason').innerText = dec.confidence_reason || dec.no_action_reason || "Deterministic rule verified against catalogue availability.";
      document.getElementById('modal-json').innerText = JSON.stringify(dec, null, 2);

      // Wire play button to launch player for this user's decision
      const playBtn = document.getElementById('modal-play-btn');
      playBtn.onclick = () => {
        closeDecisionModal();
        switchTab('device');
        selectQuickUser(dec.viewer_id);
      };

      document.getElementById('decision-modal').classList.remove('hidden');
    }

    function closeDecisionModal() {
      document.getElementById('decision-modal').classList.add('hidden');
    }

    function openSurprisesModal() {
      document.getElementById('surprises-modal').classList.remove('hidden');
    }

    function closeSurprisesModal() {
      document.getElementById('surprises-modal').classList.add('hidden');
    }

    function selectQuickUser(uid) {
      document.getElementById('preview-user-input').value = uid;
      currentViewerId = uid;
      loadUserPreview();
    }

    // ==========================================
    // OTT PHONE PREVIEW & VIDEO PLAYER LOGIC
    // ==========================================

    async function loadUserPreview() {
      const uid = document.getElementById('preview-user-input').value.trim();
      currentViewerId = uid;
      
      const res = await fetch(`/api/user_preview/${uid}`);
      if (!res.ok) {
        alert(`No decisions found for user ${uid}`);
        return;
      }
      const data = await res.json();

      // Show browse view by default
      document.getElementById('phone-browse-view').classList.remove('hidden');
      document.getElementById('phone-player-view').classList.add('hidden');

      if (!data.action || data.decision.action_type === 'abstain') {
        document.getElementById('phone-hero').classList.add('hidden');
        document.getElementById('phone-rows').innerHTML = `
          <div class="text-center py-20 text-slate-400">
            <i class="fa-solid fa-ban text-4xl mb-3 text-yellow-500"></i>
            <p class="font-bold text-white font-sans">No Active Home Page Published</p>
            <p class="text-xs text-slate-400 mt-1 max-w-xs mx-auto font-sans">Reason: ${data.decision.no_action_reason || data.decision.confidence_reason}</p>
          </div>
        `;
        document.getElementById('preview-badge-container').innerHTML = `
          <span class="px-3 py-1 bg-yellow-950/80 border border-yellow-500 text-yellow-300 rounded-lg text-xs font-semibold">
            Abstained (${data.decision.arm.toUpperCase()})
          </span>
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
        currentHeroTitleId = hero.title_id;
        document.getElementById('phone-hero-title').innerText = hero.title;
        document.getElementById('phone-hero-desc').innerText = hero.description;
        document.getElementById('phone-hero-badge').innerText = `HERO (${hero.dialect.toUpperCase()})`;
        const ep0 = (hero.episodes && hero.episodes[0]) ? hero.episodes[0] : null;
        document.getElementById('phone-hero-meta').innerText = ep0 ? `${ep0.minutes} mins` : `${hero.content_type}`;
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
            ${r.titles.map(t => {
              const safeTitle = t.title.replace(/'/g, "\\'");
              return `
                <div onclick="launchVideoPlayer('${t.title_id}')" class="group cursor-pointer flex-shrink-0 w-32 bg-slate-900 border border-slate-800 rounded-xl overflow-hidden p-2.5 flex flex-col justify-between hover:border-brand-500 hover:bg-slate-850 hover:shadow-lg hover:shadow-brand-600/20 transition transform hover:-translate-y-1 relative">
                  <div>
                    <div class="flex items-center justify-between mb-1">
                      <span class="text-[9px] font-mono text-brand-400 font-bold">${t.title_id}</span>
                      <span class="w-5 h-5 rounded-full bg-brand-600/20 text-brand-400 group-hover:bg-brand-600 group-hover:text-white flex items-center justify-center transition text-[9px]">
                        <i class="fa-solid fa-play"></i>
                      </span>
                    </div>
                    <div class="text-xs font-bold text-white line-clamp-2 leading-tight group-hover:text-brand-300 transition">${t.title}</div>
                  </div>
                  <div class="mt-3 pt-2 border-t border-slate-800 flex justify-between text-[10px] text-slate-400">
                    <span class="truncate">${t.genres[0] || 'Drama'}</span>
                    <span class="text-emerald-400 font-mono font-bold">${t.dialect}</span>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        `;
        rowsContainer.appendChild(rowDiv);
      });
    }

    function playCurrentHero() {
      launchVideoPlayer(currentHeroTitleId);
    }

    async function launchVideoPlayer(titleId, episodeId = null) {
      try {
        const res = await fetch(`/api/title/${titleId}`);
        if (!res.ok) {
          alert(`Title ${titleId} not found`);
          return;
        }
        activeVideoTitle = await res.json();
      } catch (e) {
        console.error("Error loading title:", e);
        return;
      }

      // Hide browse view, show player view
      document.getElementById('phone-browse-view').classList.add('hidden');
      document.getElementById('phone-player-view').classList.remove('hidden');

      // Populate Player UI
      document.getElementById('player-title').innerText = activeVideoTitle.title;
      document.getElementById('player-dialect-pill').innerText = `${activeVideoTitle.dialect.toUpperCase()} ${activeVideoTitle.language ? activeVideoTitle.language.toUpperCase() : ''}`;
      document.getElementById('player-content-type').innerText = activeVideoTitle.content_type.replace('_', ' ');
      document.getElementById('player-description').innerText = activeVideoTitle.description;
      
      const genresDiv = document.getElementById('player-genres');
      genresDiv.innerHTML = (activeVideoTitle.genres || ['Drama']).map(g => `
        <span class="px-2 py-0.5 bg-slate-800 text-slate-300 rounded">${g}</span>
      `).join('');

      // Populate Episodes
      const episodes = activeVideoTitle.episodes || [];
      document.getElementById('episodes-count-badge').innerText = `${episodes.length} Episode${episodes.length > 1 ? 's' : ''}`;
      
      const epList = document.getElementById('player-episodes-list');
      epList.innerHTML = episodes.map((ep, idx) => `
        <button onclick="switchEpisode('${ep.episode_id}')" id="btn-ep-${ep.episode_id}" class="flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition border ${idx === 0 ? 'bg-brand-600 text-white border-brand-500' : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'}">
          S${ep.season}:E${ep.episode} (${ep.minutes}m)
        </button>
      `).join('');

      activeEpisodeId = episodeId || (episodes[0] ? episodes[0].episode_id : null);

      // Start Video
      startVideoPlayback();

      // Start Telemetry Feed
      startAgentTelemetry();
    }

    function switchEpisode(epId) {
      activeEpisodeId = epId;
      const episodes = activeVideoTitle.episodes || [];
      episodes.forEach(ep => {
        const btn = document.getElementById(`btn-ep-${ep.episode_id}`);
        if (btn) {
          if (ep.episode_id === epId) {
            btn.className = "flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition border bg-brand-600 text-white border-brand-500";
          } else {
            btn.className = "flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition border bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700";
          }
        }
      });
      startVideoPlayback();
      emitTelemetryEvent(`play_started (switched to episode ${epId})`);
    }

    function startVideoPlayback() {
      const video = document.getElementById('phone-video-elem');
      video.currentTime = 0;
      
      // Attempt HTML5 video play
      video.play().then(() => {
        document.getElementById('center-play-icon').className = 'fa-solid fa-pause';
        document.getElementById('bottom-play-icon').className = 'fa-solid fa-pause';
        hideCanvasVisualizer();
      }).catch(err => {
        console.warn("Autoplay blocked or media failed, engaging visualizer canvas:", err);
        startCanvasVisualizer();
      });

      // Update time display
      video.ontimeupdate = updateVideoProgress;
    }

    function togglePlayPause() {
      const video = document.getElementById('phone-video-elem');
      if (video.paused) {
        video.play();
        document.getElementById('center-play-icon').className = 'fa-solid fa-pause';
        document.getElementById('bottom-play-icon').className = 'fa-solid fa-pause';
        hideCanvasVisualizer();
      } else {
        video.pause();
        document.getElementById('center-play-icon').className = 'fa-solid fa-play ml-0.5';
        document.getElementById('bottom-play-icon').className = 'fa-solid fa-play';
        startCanvasVisualizer();
      }
    }

    function skipVideo(delta) {
      const video = document.getElementById('phone-video-elem');
      video.currentTime = Math.max(0, Math.min(video.duration || 100, video.currentTime + delta));
      emitTelemetryEvent(`play_seek (delta ${delta}s, pos: ${Math.round(video.currentTime)}s)`);
    }

    function seekVideo(val) {
      const video = document.getElementById('phone-video-elem');
      if (video.duration) {
        video.currentTime = (val / 100) * video.duration;
      }
    }

    function toggleMute() {
      const video = document.getElementById('phone-video-elem');
      video.muted = !video.muted;
      document.getElementById('volume-icon').className = video.muted ? 'fa-solid fa-volume-xmark text-red-400' : 'fa-solid fa-volume-high';
    }

    function updateVideoProgress() {
      const video = document.getElementById('phone-video-elem');
      const cur = video.currentTime || 0;
      const dur = video.duration || 60;
      
      const pct = (cur / dur) * 100;
      document.getElementById('video-scrubber').value = pct;

      const formatTime = (s) => {
        const mins = Math.floor(s / 60);
        const secs = Math.floor(s % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      };

      document.getElementById('video-time-display').innerText = `${formatTime(cur)} / ${formatTime(dur)}`;
    }

    function closeVideoPlayer() {
      const video = document.getElementById('phone-video-elem');
      video.pause();
      clearInterval(telemetryTimer);
      cancelAnimationFrame(canvasAnimationId);

      document.getElementById('phone-player-view').classList.add('hidden');
      document.getElementById('phone-browse-view').classList.remove('hidden');
    }

    // ==========================================
    // CANVAS STREAMING VISUALIZER (OFFLINE/FALLBACK)
    // ==========================================
    function startCanvasVisualizer() {
      const canvas = document.getElementById('phone-canvas-visualizer');
      canvas.classList.remove('hidden');
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = canvas.parentElement.clientHeight;

      let tick = 0;
      function draw() {
        tick++;
        ctx.fillStyle = '#05070e';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Radial glow
        const grad = ctx.createRadialGradient(canvas.width / 2, canvas.height / 2, 10, canvas.width / 2, canvas.height / 2, canvas.width / 1.5);
        grad.addColorStop(0, 'rgba(225, 29, 72, 0.35)');
        grad.addColorStop(1, 'rgba(5, 7, 14, 0.95)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Animated audio waveform bars
        const numBars = 36;
        const barWidth = canvas.width / numBars;
        for (let i = 0; i < numBars; i++) {
          const h = 25 + Math.sin(tick * 0.08 + i * 0.4) * 20 + Math.cos(tick * 0.05 + i * 0.2) * 15;
          ctx.fillStyle = `rgba(244, 63, 94, ${0.4 + (h / 60) * 0.6})`;
          ctx.fillRect(i * barWidth + 2, (canvas.height / 2) - (h / 2), barWidth - 4, h);
        }

        // Title and timecode overlay
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 13px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        if (activeVideoTitle) {
          ctx.fillText(activeVideoTitle.title, canvas.width / 2, canvas.height - 40);
        }
        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.fillStyle = '#10b981';
        ctx.fillText(`● ACTIVE STREAM: ${activeVideoTitle ? activeVideoTitle.dialect.toUpperCase() : 'd1'}`, canvas.width / 2, 35);

        canvasAnimationId = requestAnimationFrame(draw);
      }
      cancelAnimationFrame(canvasAnimationId);
      draw();
    }

    function hideCanvasVisualizer() {
      cancelAnimationFrame(canvasAnimationId);
      document.getElementById('phone-canvas-visualizer').classList.add('hidden');
    }

    // ==========================================
    // AGENT TELEMETRY EMISSION ENGINE
    // ==========================================
    function startAgentTelemetry() {
      clearInterval(telemetryTimer);
      telemetrySeconds = 0;
      currentGoalProgress = 12;

      const feed = document.getElementById('telemetry-feed');
      feed.innerHTML = `
        <div class="text-emerald-400 font-bold">⚡ [00:00:01] play_started (viewer: ${currentViewerId}, title: ${activeVideoTitle.title_id}, ep: ${activeEpisodeId})</div>
      `;

      updateGoalCard(12, "IN PROGRESS");

      telemetryTimer = setInterval(() => {
        telemetrySeconds += 2;
        document.getElementById('telemetry-session-time').innerText = `Time: ${telemetrySeconds}s`;

        if (telemetrySeconds % 6 === 0) {
          emitTelemetryEvent(`play_heartbeat (session_pos: ${telemetrySeconds}s, watched: 100%)`);
          currentGoalProgress = Math.min(88, currentGoalProgress + 8);
          updateGoalCard(currentGoalProgress, "IN PROGRESS");
        }
      }, 1000);
    }

    function emitTelemetryEvent(msg) {
      const feed = document.getElementById('telemetry-feed');
      const timeStr = new Date().toTimeString().split(' ')[0];
      const div = document.createElement('div');
      div.className = "text-slate-300";
      div.innerHTML = `<span class="text-slate-500">[${timeStr}]</span> ⚡ ${msg}`;
      feed.prepend(div);
    }

    function updateGoalCard(pct, status) {
      document.getElementById('goal-progress-bar').style.width = `${pct}%`;
      const statusSpan = document.getElementById('goal-card-status');
      statusSpan.innerText = `${status} (${pct}%)`;
      if (pct >= 90) {
        statusSpan.className = "font-mono text-emerald-400 font-bold";
        document.getElementById('goal-progress-bar').className = "bg-emerald-500 h-full rounded-full transition-all duration-300";
      } else {
        statusSpan.className = "font-mono text-yellow-400 font-bold";
        document.getElementById('goal-progress-bar').className = "bg-brand-500 h-full rounded-full transition-all duration-300";
      }
    }

    function simulateCompleteEpisode() {
      const video = document.getElementById('phone-video-elem');
      if (video.duration) {
        video.currentTime = video.duration - 2;
      }
      emitTelemetryEvent(`<strong class="text-emerald-400">episode_completed</strong> (viewer: ${currentViewerId}, title: ${activeVideoTitle ? activeVideoTitle.title_id : 'T0001'}, watch: 98%)`);
      updateGoalCard(100, "SUCCESS (ATTRIBUTED)");
      
      const card = document.getElementById('goal-progress-card');
      card.className = "p-3 bg-emerald-950/60 border border-emerald-500/60 rounded-lg text-xs space-y-1.5 transition";
      card.innerHTML = `
        <div class="flex items-center justify-between">
          <span class="font-bold text-emerald-300 flex items-center gap-1.5">
            <i class="fa-solid fa-circle-check text-emerald-400"></i>
            Goal G03 (Finish Episode 1) ACHIEVED!
          </span>
          <span class="font-mono text-emerald-400 font-bold">100%</span>
        </div>
        <p class="text-[10px] text-slate-300">Causal outcome recorded in state ledger. Telemetry verified within 72h attribution window.</p>
      `;
    }

    // ==========================================
    // CINEMA THEATER MODAL LOGIC
    // ==========================================
    async function openCinemaModal(titleId) {
      try {
        const res = await fetch(`/api/title/${titleId}`);
        const t = await res.json();
        document.getElementById('cinema-title').innerText = t.title;
        document.getElementById('cinema-dialect-badge').innerText = `${t.dialect.toUpperCase()} • ${t.content_type.toUpperCase()}`;
        document.getElementById('cinema-description').innerText = t.description;

        const epList = document.getElementById('cinema-episodes-list');
        epList.innerHTML = (t.episodes || []).map(ep => `
          <div class="p-2 bg-slate-900 border border-slate-800 rounded-lg flex justify-between items-center text-xs text-slate-300">
            <span>S${ep.season}:E${ep.episode}</span>
            <span class="font-mono text-slate-400">${ep.minutes} mins</span>
          </div>
        `).join('');

        const vid = document.getElementById('cinema-video-elem');
        vid.currentTime = 0;
        vid.play().catch(e => console.warn(e));

        document.getElementById('cinema-modal').classList.remove('hidden');
      } catch (e) {
        console.error("Error opening cinema modal:", e);
      }
    }

    function closeCinemaModal() {
      const vid = document.getElementById('cinema-video-elem');
      vid.pause();
      document.getElementById('cinema-modal').classList.add('hidden');
    }

    // ==========================================
    // VIEWER STATE INSPECTOR
    // ==========================================
    async function fetchViewerState() {
      const uid = document.getElementById('viewer-inspect-input').value.trim();
      document.getElementById('json-file-name').innerText = `${uid}.json`;

      try {
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
      } catch (e) {
        console.error("Error fetching viewer state:", e);
      }
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

        elif path.startswith("/api/title/"):
            tid = path.split("/")[-1]
            if tid in catalogue:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(catalogue[tid], ensure_ascii=False).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error": "Title not found"}')

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
    server_address = ("0.0.0.0", PORT)
    # Allow reuse address to prevent WinError 10048 address already in use
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(server_address, DashboardHandler)
    print("STAGE Dashboard & Video Player Hub is running on port " + str(PORT))
    httpd.serve_forever()


if __name__ == "__main__":
    start_server()
