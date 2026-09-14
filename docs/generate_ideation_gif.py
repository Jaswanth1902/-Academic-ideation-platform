"""
generate_ideation_gif.py - Deterministic Academic Ideation Platform Demo GIF Generator
Uses Playwright + Pillow to generate a 60fps-smooth simulation of the research workbench
(Paper Search -> Cross-Grounding -> 4-Axis Feasibility Radar Matrix).
"""

import sys
import os
import time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

IDEATION_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #080706;
    display: flex;
    justify-content: center;
    align-items: center;
    width: 1040px;
    height: 540px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    overflow: hidden;
  }
  .app-window {
    width: 980px;
    height: 480px;
    background: #110E0C;
    border-radius: 12px;
    border: 1px solid rgba(197, 160, 89, 0.4);
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.9), 0 0 30px rgba(197, 160, 89, 0.12);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .navbar {
    height: 44px;
    background: #181411;
    border-bottom: 1px solid rgba(197, 160, 89, 0.25);
    display: flex;
    align-items: center;
    padding: 0 18px;
    justify-content: space-between;
  }
  .nav-title {
    font-family: 'Cinzel', 'Playfair Display', serif;
    color: #FDFBF7;
    font-size: 13px;
    letter-spacing: 1.5px;
  }
  .nav-badge {
    font-family: monospace;
    font-size: 10px;
    background: rgba(197, 160, 89, 0.15);
    color: #E5C77A;
    padding: 3px 8px;
    border-radius: 4px;
    border: 1px solid rgba(197, 160, 89, 0.3);
  }
  .workbench {
    flex: 1;
    display: flex;
    padding: 18px;
    gap: 18px;
  }
  .left-pane {
    flex: 1.2;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .right-pane {
    flex: 0.8;
    background: #16120F;
    border: 1px solid rgba(197, 160, 89, 0.2);
    border-radius: 8px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
  }
  .search-box {
    background: #1A1612;
    border: 1px solid rgba(197, 160, 89, 0.4);
    border-radius: 6px;
    padding: 10px 14px;
    color: #FDFBF7;
    font-size: 13px;
    font-family: 'JetBrains Mono', Consolas, monospace;
    display: flex;
    align-items: center;
  }
  .cursor {
    display: inline-block;
    width: 8px;
    height: 15px;
    background: #C5A059;
    margin-left: 4px;
    animation: blink 0.9s infinite;
  }
  @keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }
  .paper-card {
    background: #171310;
    border: 1px solid rgba(197, 160, 89, 0.18);
    border-radius: 6px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .paper-title { font-size: 12px; font-weight: 600; color: #FDFBF7; }
  .paper-meta { font-size: 10px; color: #8E857B; font-family: monospace; }
  .radar-container {
    width: 100%;
    text-align: center;
  }
  .radar-title {
    font-size: 12px;
    font-weight: bold;
    color: #E5C77A;
    margin-bottom: 8px;
    letter-spacing: 1px;
    font-family: 'Cinzel', serif;
  }
  .metric-row {
    display: flex;
    justify-content: space-between;
    width: 100%;
    font-size: 11px;
    padding: 6px 0;
    border-bottom: 1px solid rgba(197, 160, 89, 0.1);
    color: #D4AF37;
    font-family: monospace;
  }
  .metric-val { color: #4ADE80; font-weight: bold; }
</style>
</head>
<body>
<div class="app-window">
  <div class="navbar">
    <div class="nav-title">ACADEMIC IDEATION PLATFORM</div>
    <div class="nav-badge">AIR-GAPPED • OLLAMA LOCAL</div>
  </div>
  <div class="workbench">
    <div class="left-pane">
      <div class="search-box" id="search-bar">
        <span id="search-text">Search hypothesis topic...</span>
        <span class="cursor" id="search-cursor"></span>
      </div>
      <div id="results-container" style="display: none; flex-direction: column; gap: 8px;">
        <div class="paper-card">
          <div class="paper-title">arXiv:2403.18942 — AST Symbol Graph Navigation for Code LLMs</div>
          <div class="paper-meta">Citations: 48 • Match Relevance: 98.4% • Feasibility: 9.5/10</div>
        </div>
        <div class="paper-card">
          <div class="paper-title">IEEE Trans — Low-Latency In-Memory Codebase Indexing Without Vector DBs</div>
          <div class="paper-meta">Citations: 112 • Match Relevance: 94.1% • Feasibility: 9.2/10</div>
        </div>
      </div>
    </div>
    <div class="right-pane" id="radar-pane">
      <div class="radar-container" id="radar-content">
        <div class="radar-title">FEASIBILITY RADAR MATRIX</div>
        <div style="font-size: 11px; color: #8E857B; margin-top: 10px;">Awaiting Query Grounding...</div>
      </div>
    </div>
  </div>
</div>

<script>
  const searchText = document.getElementById('search-text');
  const searchCursor = document.getElementById('search-cursor');
  const resultsContainer = document.getElementById('results-container');
  const radarContent = document.getElementById('radar-content');

  window.setDemoState = function(state) {
    if (state === 'typing') {
      searchText.textContent = 'AST Symbol Codebase Memory for AI Agents';
      searchText.style.color = '#FDFBF7';
    } else if (state === 'grounded') {
      resultsContainer.style.display = 'flex';
      radarContent.innerHTML = `
        <div class="radar-title">FEASIBILITY RADAR MATRIX</div>
        <div class="metric-row"><span>TECHNICAL VIABILITY</span><span class="metric-val">9.6 / 10</span></div>
        <div class="metric-row"><span>COMPUTE EFFICIENCY</span><span class="metric-val">9.8 / 10</span></div>
        <div class="metric-row"><span>NOVELTY INDEX</span><span class="metric-val">8.9 / 10</span></div>
        <div class="metric-row"><span>AIR-GAP COMPLIANCE</span><span class="metric-val">100% PASS</span></div>
        <div style="margin-top: 14px; font-size: 10px; color: #4ADE80; font-family: monospace;">✓ 5 Viable Research Angles Generated</div>
      `;
    }
  };
</script>
</body>
</html>
"""

def generate_ideation_gif():
    docs_dir = Path(__file__).resolve().parent
    repo_dir = docs_dir.parent
    assets_dir = repo_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    temp_dir = docs_dir / "temp_ideation_frames"
    temp_dir.mkdir(exist_ok=True)

    html_file = docs_dir / "ideation_canvas.html"
    html_file.write_text(IDEATION_HTML, encoding="utf-8")

    print("[1/3] Launching Playwright to capture Academic Ideation workbench...")
    frames = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1040, "height": 540})
        page.goto(html_file.as_uri())
        page.wait_for_timeout(300)

        # Sequence: (state, repeats)
        sequence = [
            ("idle", 6),
            ("typing", 10),
            ("grounded", 16)
        ]

        frame_idx = 0
        for state_name, repeat_count in sequence:
            page.evaluate(f"window.setDemoState('{state_name}')")
            page.wait_for_timeout(400)
            
            frame_path = temp_dir / f"ideation_frame_{frame_idx:04d}.png"
            page.screenshot(path=str(frame_path))
            img = Image.open(frame_path)
            
            for _ in range(repeat_count):
                frames.append(img.copy())
            frame_idx += 1

        browser.close()

    print(f"[2/3] Captured {len(frames)} frames. Compiling palette-optimized GIF...")
    output_gif = assets_dir / "ideation_quickstart.gif"

    frames[0].save(
        output_gif,
        save_all=True,
        append_images=frames[1:],
        optimize=True,
        duration=200,
        loop=0
    )

    gif_size_kb = round(os.path.getsize(output_gif) / 1024, 1)
    print(f"[3/3] [SUCCESS] Generated {output_gif.name} ({gif_size_kb} KB)")

    # Cleanup
    for f in temp_dir.glob("*.png"):
        f.unlink()
    temp_dir.rmdir()
    if html_file.exists():
        html_file.unlink()

if __name__ == "__main__":
    generate_ideation_gif()
