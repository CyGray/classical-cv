document.addEventListener("DOMContentLoaded", () => {
  const data = window.ROBUSTNESS_DATA;
  if (!data) {
    console.error("ROBUSTNESS_DATA not loaded");
    return;
  }

  let activeTrackId = data.tracks[0].id;
  let activeTab = "holistic"; // "holistic" | "tracks" | "simulator" | "matrix"
  let activeMode = "all"; // "all" | "lbph" | "sface" | "hybrid"

  // Elements
  const navBtns = document.querySelectorAll(".nav-btn");
  const tabSections = document.querySelectorAll(".tab-section");
  const trackSwitcherGrid = document.getElementById("trackSwitcherGrid");
  const trackDetailContainer = document.getElementById("trackDetailContainer");
  const modeChips = document.querySelectorAll(".mode-chip");

  // Init Nav Tabs
  navBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      navBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeTab = btn.dataset.tab;
      
      tabSections.forEach((sec) => {
        if (sec.id === `tab-${activeTab}`) {
          sec.classList.remove("hidden");
        } else {
          sec.classList.add("hidden");
        }
      });
    });
  });

  // Init Mode Chips Toggler
  modeChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      modeChips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      activeMode = chip.dataset.mode;
      renderHolisticOverview();
    });
  });

  // Render Holistic Overview Master Table & Cards (with dynamic column hiding per mode)
  function renderHolisticOverview() {
    const tableThead = document.getElementById("holisticThead");
    const tableBody = document.getElementById("holisticTableBody");
    const cardsGrid = document.getElementById("holisticCardsGrid");

    if (tableThead) {
      if (activeMode === "lbph") {
        tableThead.innerHTML = `
          <tr>
            <th>Rank</th>
            <th>Track</th>
            <th>Dataset & Condition</th>
            <th>LBPH TAR Clean (+/- Delta)</th>
            <th>Core Takeaway</th>
          </tr>
        `;
      } else if (activeMode === "sface") {
        tableThead.innerHTML = `
          <tr>
            <th>Rank</th>
            <th>Track</th>
            <th>Dataset & Condition</th>
            <th>SFace TAR (Clean)</th>
            <th>Core Takeaway</th>
          </tr>
        `;
      } else if (activeMode === "hybrid") {
        tableThead.innerHTML = `
          <tr>
            <th>Rank</th>
            <th>Track</th>
            <th>Dataset & Condition</th>
            <th>Cascade (Hybrid) TAR</th>
            <th>Escalation %</th>
            <th>Mean Latency</th>
            <th>Core Takeaway</th>
          </tr>
        `;
      } else {
        // "all"
        tableThead.innerHTML = `
          <tr>
            <th>Rank</th>
            <th>Track</th>
            <th>Dataset & Condition</th>
            <th>LBPH TAR Clean (+/- Delta)</th>
            <th>SFace TAR</th>
            <th>Cascade TAR</th>
            <th>Escalation %</th>
            <th>Latency</th>
            <th>Core Takeaway</th>
          </tr>
        `;
      }
    }

    if (tableBody) {
      tableBody.innerHTML = data.tracks
        .map((t, idx) => {
          const tarCombined = t.tarCombinedStr;
          const sfaceMetric = t.metrics.find((m) => m.label.includes("SFace AR") || m.label.includes("Standalone"))?.value || "92.02%";
          const cascadeMetric = t.metrics.find((m) => m.label.includes("Cascade AR"))?.value || "80.65%";
          const escalationMetric = t.metrics.find((m) => m.label.includes("Escalation"))?.value || "—";
          const latencyMetric = t.metrics.find((m) => m.label.includes("Latency"))?.value || "82.54 ms";

          if (activeMode === "lbph") {
            return `
              <tr>
                <td class="font-mono" style="font-weight: 800; color: #0f172a;">#0${idx + 1}</td>
                <td style="font-weight: 700; color: #0f172a;">
                  <span class="track-btn-tag" style="margin-right: 6px;">${t.tag}</span>
                  ${t.title.replace(/^\d+\.\s*/, '')}
                </td>
                <td style="font-size: 13px; color: #334155;">${t.subtitle}</td>
                <td class="font-mono" style="font-weight: 800; color: #0f172a;">
                  <span class="delta-badge ${t.isBaseline ? 'baseline' : ''}">
                    ${tarCombined}
                  </span>
                </td>
                <td style="font-size: 12px; color: #334155; max-width: 320px; line-height: 1.4;">${t.takeaway}</td>
              </tr>
            `;
          } else if (activeMode === "sface") {
            return `
              <tr>
                <td class="font-mono" style="font-weight: 800; color: #0f172a;">#0${idx + 1}</td>
                <td style="font-weight: 700; color: #0f172a;">
                  <span class="track-btn-tag" style="margin-right: 6px;">${t.tag}</span>
                  ${t.title.replace(/^\d+\.\s*/, '')}
                </td>
                <td style="font-size: 13px; color: #334155;">${t.subtitle}</td>
                <td class="font-mono" style="font-weight: 700; color: #334155;">${sfaceMetric}</td>
                <td style="font-size: 12px; color: #334155; max-width: 320px; line-height: 1.4;">${t.takeaway}</td>
              </tr>
            `;
          } else if (activeMode === "hybrid") {
            return `
              <tr>
                <td class="font-mono" style="font-weight: 800; color: #0f172a;">#0${idx + 1}</td>
                <td style="font-weight: 700; color: #0f172a;">
                  <span class="track-btn-tag" style="margin-right: 6px;">${t.tag}</span>
                  ${t.title.replace(/^\d+\.\s*/, '')}
                </td>
                <td style="font-size: 13px; color: #334155;">${t.subtitle}</td>
                <td class="font-mono" style="font-weight: 700; color: #334155;">${cascadeMetric}</td>
                <td class="font-mono" style="font-weight: 700; color: #475569;">${escalationMetric}</td>
                <td class="font-mono" style="font-weight: 700; color: #0f172a;">${latencyMetric}</td>
                <td style="font-size: 12px; color: #334155; max-width: 280px; line-height: 1.4;">${t.takeaway}</td>
              </tr>
            `;
          } else {
            // "all"
            return `
              <tr>
                <td class="font-mono" style="font-weight: 800; color: #0f172a;">#0${idx + 1}</td>
                <td style="font-weight: 700; color: #0f172a;">
                  <span class="track-btn-tag" style="margin-right: 6px;">${t.tag}</span>
                  ${t.title.replace(/^\d+\.\s*/, '')}
                </td>
                <td style="font-size: 13px; color: #334155;">${t.subtitle}</td>
                <td class="font-mono" style="font-weight: 800; color: #0f172a;">
                  <span class="delta-badge ${t.isBaseline ? 'baseline' : ''}">
                    ${tarCombined}
                  </span>
                </td>
                <td class="font-mono" style="font-weight: 700; color: #334155;">${sfaceMetric}</td>
                <td class="font-mono" style="font-weight: 700; color: #334155;">${cascadeMetric}</td>
                <td class="font-mono" style="font-weight: 700; color: #475569;">${escalationMetric}</td>
                <td class="font-mono" style="font-weight: 700; color: #0f172a;">${latencyMetric}</td>
                <td style="font-size: 12px; color: #334155; max-width: 260px; line-height: 1.4;">${t.takeaway}</td>
              </tr>
            `;
          }
        })
        .join("");
    }

    if (cardsGrid) {
      cardsGrid.innerHTML = data.tracks
        .map((t, idx) => `
          <div class="glass-card" style="padding: 20px; display: flex; flex-direction: column; justify-content: space-between; gap: 12px;">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <span style="font-size: 11px; font-weight: 800; color: var(--text-faint); text-transform: uppercase;">Rank #0${idx + 1}</span>
                <span class="badge" style="font-size: 10px; padding: 2px 8px;">${t.tag}</span>
              </div>
              <h4 style="font-size: 16px; font-weight: 800; color: #0f172a; line-height: 1.3;">${t.title.replace(/^\d+\.\s*/, '')}</h4>
              <p style="font-size: 13px; color: var(--text-muted); margin-top: 6px; line-height: 1.5;">${t.summary}</p>
            </div>

            <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: var(--radius-md); padding: 12px;">
              <div style="font-size: 10px; color: var(--text-faint); font-weight: 700;">LBPH TAR CLEAN (+/- DELTA)</div>
              <div class="font-mono" style="font-size: 16px; font-weight: 800; color: #0f172a; margin-top: 2px;">${t.tarCombinedStr}</div>
            </div>

            <button class="nav-btn" style="width: 100%; text-align: center; justify-content: center; font-size: 12px;" onclick="window.inspectTrack('${t.id}')">
              Inspect Track Details &rarr;
            </button>
          </div>
        `)
        .join("");
    }
  }

  // Global helper to switch to Track Inspector tab from card button
  window.inspectTrack = function (trackId) {
    activeTrackId = trackId;
    navBtns.forEach((b) => b.classList.remove("active"));
    const trackTabBtn = document.querySelector('.nav-btn[data-tab="tracks"]');
    if (trackTabBtn) trackTabBtn.classList.add("active");

    activeTab = "tracks";
    tabSections.forEach((sec) => {
      if (sec.id === "tab-tracks") sec.classList.remove("hidden");
      else sec.classList.add("hidden");
    });

    renderTrackCards();
    renderTrackDetail();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Render Track Switcher Cards
  function renderTrackCards() {
    if (!trackSwitcherGrid) return;
    trackSwitcherGrid.innerHTML = data.tracks
      .map((t, idx) => `
        <button class="track-card-btn ${t.id === activeTrackId ? 'active' : ''}" data-id="${t.id}">
          <div class="track-btn-num">Rank #0${idx + 1}</div>
          <div class="track-btn-name">${t.title.replace(/^\d+\.\s*/, '')}</div>
          <span class="track-btn-tag">
            ${t.tag}
          </span>
        </button>
      `)
      .join("");

    document.querySelectorAll(".track-card-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeTrackId = btn.dataset.id;
        renderTrackCards();
        renderTrackDetail();
      });
    });
  }

  // Render Track Details
  function renderTrackDetail() {
    if (!trackDetailContainer) return;
    const track = data.tracks.find((t) => t.id === activeTrackId);
    if (!track) return;

    trackDetailContainer.innerHTML = `
      <div class="track-main-info">
        <div class="track-header-row">
          <div>
            <h2 class="track-title">${track.title}</h2>
            <div class="track-subtitle">${track.subtitle}</div>
          </div>
          <span class="badge">${track.tag}</span>
        </div>

        <p style="color: var(--text-muted); font-size: 15px; line-height: 1.6; font-weight: 500;">
          ${track.summary}
        </p>

        <!-- Key Metrics -->
        <div class="metrics-grid">
          ${track.metrics
            .map(
              (m) => `
            <div class="metric-box">
              <div class="metric-label">${m.label}</div>
              <div class="metric-val">${m.value}</div>
              <div class="metric-note">${m.note}</div>
            </div>
          `
            )
            .join("")}
        </div>

        <!-- Modes Table -->
        <div>
          <h3 style="font-size: 16px; margin-bottom: 12px; font-weight: 800; color: #0f172a;">Benchmark Summary Table</h3>
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Execution Mode</th>
                  <th>AR % (Clean)</th>
                  <th>AR % (41-Mod Avg)</th>
                  <th>Escalation %</th>
                  <th>Mean Latency</th>
                </tr>
              </thead>
              <tbody>
                ${track.modesTable
                  .map(
                    (r) => `
                  <tr>
                    <td style="font-weight: 700; color: #0f172a;">${r.mode}</td>
                    <td style="font-family: 'JetBrains Mono'; color: #0f172a; font-weight: 700;">${r.arClean}</td>
                    <td style="font-family: 'JetBrains Mono'; color: #334155; font-weight: 700;">${r.ar41Avg}</td>
                    <td style="font-family: 'JetBrains Mono'; color: #475569; font-weight: 600;">${r.escalation}</td>
                    <td style="font-family: 'JetBrains Mono'; color: #0f172a; font-weight: 700;">${r.latency}</td>
                  </tr>
                `
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>

        <!-- Takeaway Callout -->
        <div class="takeaway-box">
          <div class="takeaway-icon">💡</div>
          <div class="takeaway-text">
            <strong>Key Finding:</strong> ${track.takeaway}<br/>
            <span style="font-size: 12px; color: var(--text-faint); margin-top: 4px; display: inline-block;">Source: <code class="font-mono">${track.docLink}</code></span>
          </div>
        </div>
      </div>
    `;
  }

  // --- Trade-off Simulator ---
  const farRange = document.getElementById("farRange");
  const farValBadge = document.getElementById("farValBadge");
  const simTau = document.getElementById("simTau");
  const simCleanTar = document.getElementById("simCleanTar");
  const simOverallTar = document.getElementById("simOverallTar");
  const simEscalation = document.getElementById("simEscalation");
  const simLatency = document.getElementById("simLatency");
  const barTarClean = document.getElementById("barTarClean");
  const barTarOverall = document.getElementById("barTarOverall");
  const barEscalation = document.getElementById("barEscalation");

  function updateSimulator(index) {
    const item = data.farSweepData[index];
    if (!item) return;

    farValBadge.textContent = item.targetFar;
    simTau.textContent = item.tau.toFixed(4);
    simCleanTar.textContent = `${item.cleanTar.toFixed(2)}%`;
    simOverallTar.textContent = `${item.overallTar.toFixed(2)}%`;
    simEscalation.textContent = `${item.escalationPct.toFixed(1)}%`;
    simLatency.textContent = `${item.estLatency.toFixed(2)} ms`;

    barTarClean.style.width = `${Math.min(100, item.cleanTar * 1.5)}%`;
    barTarOverall.style.width = `${Math.min(100, item.overallTar * 1.5)}%`;
    barEscalation.style.width = `${item.escalationPct}%`;
  }

  if (farRange) {
    farRange.addEventListener("input", (e) => {
      updateSimulator(parseInt(e.target.value, 10));
    });
    updateSimulator(0);
  }

  // --- Per-Modification Matrix ---
  const modTableBody = document.getElementById("modTableBody");
  const searchInput = document.getElementById("searchInput");
  const filterChips = document.querySelectorAll(".filter-chip");
  let activeTierFilter = "All";

  function renderModTable() {
    if (!modTableBody) return;
    const query = (searchInput.value || "").toLowerCase();

    const filtered = data.modificationsData.filter((item) => {
      const matchQuery =
        item.family.toLowerCase().includes(query) ||
        item.tier.toLowerCase().includes(query);
      const matchTier =
        activeTierFilter === "All" ||
        item.tier.toLowerCase().startsWith(activeTierFilter.toLowerCase());
      return matchQuery && matchTier;
    });

    modTableBody.innerHTML = filtered
      .map(
        (item) => `
      <tr>
        <td style="font-weight: 700; color: #0f172a;">
          <span style="margin-right: 8px;">${item.icon}</span> ${item.family}
        </td>
        <td>
          <span class="filter-chip" style="font-size: 11px; padding: 2px 8px; border-radius: 4px; pointer-events: none; background: #f1f5f9; color: #334155; border-color: #cbd5e1;">
            ${item.tier}
          </span>
        </td>
        <td class="font-mono" style="color: #0f172a; font-weight: 700;">${item.lbph}</td>
        <td class="font-mono" style="color: #334155; font-weight: 700;">${item.sface}</td>
        <td class="font-mono" style="color: #0f172a; font-weight: 800;">${item.cascade}</td>
      </tr>
    `
      )
      .join("");
  }

  if (searchInput) {
    searchInput.addEventListener("input", renderModTable);
  }

  filterChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      filterChips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      activeTierFilter = chip.dataset.tier;
      renderModTable();
    });
  });

  // Init views
  renderHolisticOverview();
  renderTrackCards();
  renderTrackDetail();
  renderModTable();
});
