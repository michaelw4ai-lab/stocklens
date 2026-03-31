let allStocks = [];
let currentSort = { column: "symbol", dir: "asc" };
let sectorChart = null;
let perfChart = null;
let detailChart = null;

function init(data) {
    allStocks = data.stocks;
    renderSummary(data);
    renderSectorChart(data.sectors);
    renderPerfChart(data.sectors);
    renderTable(allStocks);
    bindEvents();
}

function renderSummary(data) {
    document.getElementById("totalCount").textContent = data.total;
    document.getElementById("gainerCount").textContent = data.gainers;
    document.getElementById("loserCount").textContent = data.losers;
    document.getElementById("sectorCount").textContent = data.sectors.length;
}

function renderSectorChart(sectors) {
    const ctx = document.getElementById("sectorChart").getContext("2d");
    const colors = [
        "#4361ee", "#3a0ca3", "#7209b7", "#f72585", "#e71d36",
        "#ff9f1c", "#2ec4b6", "#06d6a0", "#118ab2", "#073b4c",
        "#8338ec"
    ];
    if (sectorChart) sectorChart.destroy();
    sectorChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: sectors.map(s => s.name),
            datasets: [{
                data: sectors.map(s => s.count),
                backgroundColor: colors.concat(colors),
                borderWidth: 2,
                borderColor: "#fff"
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "right",
                    labels: { font: { size: 11 }, padding: 8 }
                }
            }
        }
    });
}

function renderPerfChart(sectors) {
    const ctx = document.getElementById("perfChart").getContext("2d");
    const sorted = [...sectors].sort((a, b) => a.avg_change_pct - b.avg_change_pct);
    if (perfChart) perfChart.destroy();
    perfChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: sorted.map(s => s.name),
            datasets: [{
                label: "Avg Change %",
                data: sorted.map(s => s.avg_change_pct),
                backgroundColor: sorted.map(s => s.avg_change_pct >= 0 ? "#2ec4b6" : "#e71d36"),
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    grid: { display: true, color: "#f0f0f0" },
                    ticks: { callback: v => v + "%" }
                },
                y: {
                    ticks: { font: { size: 11 } }
                }
            }
        }
    });
}

function renderTable(stocks) {
    const tbody = document.getElementById("stockTableBody");
    tbody.innerHTML = stocks.map(s => {
        const changeClass = s.change_pct > 0 ? "text-gain" : s.change_pct < 0 ? "text-loss" : "";
        const arrow = s.change_pct > 0 ? "&#9650;" : s.change_pct < 0 ? "&#9660;" : "";
        const price = s.price != null ? "$" + s.price.toFixed(2) : "N/A";
        const change = s.change != null ? (s.change > 0 ? "+" : "") + s.change.toFixed(2) : "N/A";
        const changePct = s.change_pct != null ? (s.change_pct > 0 ? "+" : "") + s.change_pct.toFixed(2) + "%" : "N/A";

        return `<tr data-symbol="${s.symbol}" onclick="showDetail('${s.symbol}', '${s.name.replace(/'/g, "\\'")}')">
            <td><strong>${s.symbol}</strong></td>
            <td>${s.name}</td>
            <td><span class="badge bg-secondary badge-sector">${s.sector}</span></td>
            <td class="text-end">${price}</td>
            <td class="text-end ${changeClass}">${arrow} ${change}</td>
            <td class="text-end ${changeClass}">${changePct}</td>
        </tr>`;
    }).join("");
}

function sortTable(column) {
    if (currentSort.column === column) {
        currentSort.dir = currentSort.dir === "asc" ? "desc" : "asc";
    } else {
        currentSort.column = column;
        currentSort.dir = "asc";
    }

    allStocks.sort((a, b) => {
        let va = a[column], vb = b[column];
        if (va == null) return 1;
        if (vb == null) return -1;
        if (typeof va === "string") {
            va = va.toLowerCase(); vb = vb.toLowerCase();
        }
        if (va < vb) return currentSort.dir === "asc" ? -1 : 1;
        if (va > vb) return currentSort.dir === "asc" ? 1 : -1;
        return 0;
    });

    // Update sort arrows
    document.querySelectorAll("#stockTable th").forEach(th => {
        const arrow = th.querySelector(".sort-arrow");
        if (arrow) {
            if (th.dataset.column === column) {
                arrow.innerHTML = currentSort.dir === "asc" ? "&#9650;" : "&#9660;";
            } else {
                arrow.innerHTML = "&#9650;&#9660;";
            }
        }
    });

    filterAndRender();
}

function filterAndRender() {
    const query = document.getElementById("searchBox").value.toLowerCase();
    const filtered = allStocks.filter(s =>
        s.symbol.toLowerCase().includes(query) ||
        s.name.toLowerCase().includes(query) ||
        s.sector.toLowerCase().includes(query)
    );
    renderTable(filtered);
}

let searchTimeout;
function onSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(filterAndRender, 200);
}

async function showDetail(symbol, name) {
    document.getElementById("modalTitle").textContent = `${symbol} - ${name}`;
    const modal = new bootstrap.Modal(document.getElementById("stockModal"));
    modal.show();

    document.getElementById("modalLoading").style.display = "block";
    document.getElementById("modalChartContainer").style.display = "none";

    try {
        const res = await fetch(`/api/stock/${symbol}`);
        const data = await res.json();

        document.getElementById("modalLoading").style.display = "none";
        document.getElementById("modalChartContainer").style.display = "block";

        const ctx = document.getElementById("detailChart").getContext("2d");
        if (detailChart) detailChart.destroy();

        const priceChange = data.prices.length >= 2
            ? data.prices[data.prices.length - 1] - data.prices[0]
            : 0;
        const lineColor = priceChange >= 0 ? "#2ec4b6" : "#e71d36";

        detailChart = new Chart(ctx, {
            type: "line",
            data: {
                labels: data.dates,
                datasets: [{
                    label: "Close Price ($)",
                    data: data.prices,
                    borderColor: lineColor,
                    backgroundColor: lineColor + "20",
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => "$" + ctx.parsed.y.toFixed(2)
                        }
                    }
                },
                scales: {
                    x: { grid: { display: false } },
                    y: {
                        ticks: { callback: v => "$" + v }
                    }
                }
            }
        });
    } catch (e) {
        document.getElementById("modalLoading").textContent = "Failed to load data.";
    }
}

async function refreshData() {
    const btn = document.getElementById("refreshBtn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Refreshing (30-60s)...';

    // Show dashboard area if it was hidden (first load)
    const loadingScreen = document.getElementById("loadingScreen");
    if (loadingScreen) {
        loadingScreen.innerHTML = '<div class="spinner-border text-primary mb-3" style="width:3rem;height:3rem"></div>'
            + '<h5>Fetching S&P 500 Data...</h5>'
            + '<p class="text-muted">Downloading from Yahoo Finance. This takes 30-60 seconds.</p>';
        loadingScreen.style.display = "block";
        loadingScreen.className = "text-center py-5";
    }

    try {
        const res = await fetch("/api/refresh", { method: "POST" });
        if (res.status === 401) {
            window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
            return;
        }
        const data = await res.json();

        if (loadingScreen) loadingScreen.style.display = "none";
        document.getElementById("dashboardContent").style.display = "block";

        allStocks = data.stocks;
        renderSummary(data);
        renderSectorChart(data.sectors);
        renderPerfChart(data.sectors);
        filterAndRender();
        document.getElementById("lastUpdated").textContent = data.last_updated;
    } catch (e) {
        if (loadingScreen) {
            loadingScreen.innerHTML = '<div class="text-danger"><i class="bi bi-exclamation-triangle" style="font-size:2rem"></i>'
                + '<h5 class="mt-2">Refresh failed</h5><p>' + e.message + '</p>'
                + '<button class="btn btn-primary btn-sm" onclick="refreshData()">Retry</button></div>';
        } else {
            alert("Refresh failed. Please try again.");
        }
    }

    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh';
}

function bindEvents() {
    document.getElementById("searchBox").addEventListener("input", onSearch);
    document.getElementById("refreshBtn").addEventListener("click", refreshData);
    document.querySelectorAll("#stockTable th[data-column]").forEach(th => {
        th.addEventListener("click", () => sortTable(th.dataset.column));
    });
}
