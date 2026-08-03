const GNSS_COLORS = {
    0: '#4fc3f7',   // GPS
    1: '#e94560',   // GLONASS
    2: '#66bb6a',   // Galileo
    3: '#ffa726',   // BeiDou
    4: '#ab47bc',   // QZSS
    5: '#78909c',   // SBAS
    6: '#78909c',   // Other
};
const GNSS_NAMES = {
    0: 'GPS', 1: 'GLONASS', 2: 'Galileo', 3: 'BeiDou',
    4: 'QZSS', 5: 'SBAS', 6: 'Other',
};

// Theme helpers
function isDark() {
    return document.documentElement.getAttribute('data-bs-theme') === 'dark';
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
    localStorage.setItem('bs-theme', theme);
    document.getElementById('theme-icon-dark').style.display = theme === 'dark' ? '' : 'none';
    document.getElementById('theme-icon-light').style.display = theme === 'light' ? '' : 'none';
    drawSkyPlot(lastSatellites || []);
}

// Set initial icon state
(function() {
    var t = localStorage.getItem('bs-theme') || 'dark';
    document.getElementById('theme-icon-dark').style.display = t === 'dark' ? '' : 'none';
    document.getElementById('theme-icon-light').style.display = t === 'light' ? '' : 'none';
})();

document.getElementById('theme-toggle').addEventListener('click', function() {
    applyTheme(isDark() ? 'light' : 'dark');
});

let lastGpsTime = null;

function updateTimeDisplay() {
    const now = lastGpsTime ? new Date(lastGpsTime) : new Date();
    if (lastGpsTime) {
        lastGpsTime.setSeconds(lastGpsTime.getSeconds() + 1);
    }

    // UTC time
    const utcTime = now.toISOString().match(/T(\d{2}:\d{2}:\d{2})/);
    document.getElementById('gps-time').textContent = utcTime ? utcTime[1] : '--:--:--';

    // Date
    const dateStr = now.toLocaleDateString([], { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
    document.getElementById('gps-date').textContent = dateStr;

    // Local time
    const localTime = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    document.getElementById('gps-time-local').textContent = localTime + ' ' + tz;
}

let lastNtpTime = null;

function updateNtpTimeDisplay() {
    const now = lastNtpTime ? new Date(lastNtpTime) : null;
    if (lastNtpTime) {
        lastNtpTime.setSeconds(lastNtpTime.getSeconds() + 1);
    }

    if (now) {
        const utcTime = now.toISOString().match(/T(\d{2}:\d{2}:\d{2})/);
        document.getElementById('ntp-time').textContent = utcTime ? utcTime[1] : '--:--:--';
    } else {
        document.getElementById('ntp-time').textContent = '--:--:--';
    }
}

const canvas = document.getElementById('skyplot');
const ctx = canvas.getContext('2d');

let lastSatellites = null;

function drawSkyPlot(satellites) {
    lastSatellites = satellites;
    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2;
    const cy = h / 2;
    const maxR = Math.min(cx, cy) - 40;
    const dark = isDark();

    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = dark ? '#1a1d21' : '#e8e8e8';
    ctx.beginPath();
    ctx.arc(cx, cy, maxR + 20, 0, Math.PI * 2);
    ctx.fill();

    // Elevation circles (0, 30, 60, 90 degrees)
    [0, 30, 60, 90].forEach(el => {
        const r = maxR * (1 - el / 90);
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = dark ? (el === 0 ? '#555' : '#444') : (el === 0 ? '#bbb' : '#d0d0d0');
        ctx.lineWidth = 1;
        ctx.stroke();

        // Label
        if (el > 0 && el < 90) {
            ctx.fillStyle = dark ? '#ccc' : '#211E1E';
            ctx.font = '10px monospace';
            ctx.textAlign = 'center';
            ctx.fillText(el + '°', cx + 3, cy - r + 12);
        }
    });

    // Cardinal directions
    const dirs = [
        { label: 'N', angle: -Math.PI / 2 },
        { label: 'E', angle: 0 },
        { label: 'S', angle: Math.PI / 2 },
        { label: 'W', angle: Math.PI },
    ];
    ctx.font = 'bold 13px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    dirs.forEach(d => {
        const lx = cx + Math.cos(d.angle) * (maxR + 14);
        const ly = cy + Math.sin(d.angle) * (maxR + 14);
        ctx.fillStyle = d.label === 'N' ? '#e94560' : (dark ? '#ccc' : '#211E1E');
        ctx.fillText(d.label, lx, ly);
    });

    // Cross lines
    ctx.strokeStyle = dark ? '#444' : '#ccc';
    ctx.lineWidth = 1;
    [[-Math.PI/2, Math.PI/2], [0, Math.PI]].forEach(([a1, a2]) => {
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(a1) * maxR, cy + Math.sin(a1) * maxR);
        ctx.lineTo(cx + Math.cos(a2) * maxR, cy + Math.sin(a2) * maxR);
        ctx.stroke();
    });

    // Plot satellites
    satellites.forEach(sat => {
        if (sat.az == null || sat.el == null) return;
        const elRad = sat.el * Math.PI / 180;
        const azRad = sat.az * Math.PI / 180 - Math.PI / 2;
        const r = maxR * (1 - sat.el / 90);
        const x = cx + Math.cos(azRad) * r;
        const y = cy + Math.sin(azRad) * r;

        const color = GNSS_COLORS[sat.gnssid] || GNSS_COLORS[6];

        // Glow for used satellites
        if (sat.used) {
            ctx.beginPath();
            ctx.arc(x, y, 12, 0, Math.PI * 2);
            ctx.fillStyle = color + '33';
            ctx.fill();
        }

        // Satellite dot
        ctx.beginPath();
        ctx.arc(x, y, sat.used ? 7 : 5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        // PRN label
        ctx.fillStyle = dark ? '#ccc' : '#211E1E';
        ctx.font = sat.used ? 'bold 9px monospace' : '9px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(sat.PRN, x, y - (sat.used ? 12 : 10));
    });
}

function updateSatTable(satellites) {
    const tbody = document.getElementById('sat-table-body');
    const sorted = [...satellites].sort((a, b) => (b.ss || 0) - (a.ss || 0));

    tbody.innerHTML = sorted.map(sat => {
        const color = GNSS_COLORS[sat.gnssid] || GNSS_COLORS[6];
        const name = GNSS_NAMES[sat.gnssid] || 'Unknown';
        const ss = sat.ss != null ? sat.ss : 0;
        const barWidth = Math.max(0, Math.min(100, ss * 100 / 50));
        const usedBadge = sat.used
            ? '<span class="badge bg-success">Yes</span>'
            : '<span class="badge bg-secondary">No</span>';
        return `<tr>
            <td style="color:${color}; font-weight:600;">${sat.PRN}</td>
            <td style="color:${color};">${name}</td>
            <td>${sat.az != null ? sat.az.toFixed(0) + '°' : '--'}</td>
            <td>${sat.el != null ? sat.el.toFixed(0) + '°' : '--'}</td>
            <td>${sat.ss != null ? sat.ss.toFixed(1) : '--'}</td>
            <td><div class="snr-bar" style="width:${barWidth}%; background:${color};"></div></td>
            <td>${usedBadge}</td>
        </tr>`;
    }).join('');
}

// Socket.IO
const socket = io();

socket.on('connect', () => console.log('Connected to server'));

socket.on('gps_status', (data) => {
    const badge = document.getElementById('status-badge');
    badge.textContent = data.connected ? 'Connected' : 'Disconnected';
    badge.className = 'badge ' + (data.connected ? 'bg-success' : 'bg-danger');
});

socket.on('gps_update', (data) => {
    document.getElementById('device-name').textContent = data.device || '';

    const badge = document.getElementById('status-badge');
    badge.textContent = data.connected ? 'Connected' : 'Disconnected';
    badge.className = 'badge ' + (data.connected ? 'bg-success' : 'bg-danger');

    const fixEl = document.getElementById('fix-mode');
    if (data.mode === 3) { fixEl.textContent = '3D Fix'; fixEl.className = 'badge bg-success'; }
    else if (data.mode === 2) { fixEl.textContent = '2D Fix'; fixEl.className = 'badge bg-warning text-dark'; }
    else { fixEl.textContent = 'No Fix'; fixEl.className = 'badge bg-secondary'; }

    document.getElementById('latitude').textContent =
        data.latitude != null ? data.latitude.toFixed(6) + '°' : '--';
    document.getElementById('longitude').textContent =
        data.longitude != null ? data.longitude.toFixed(6) + '°' : '--';
    document.getElementById('altitude').textContent =
        data.altitude != null ? data.altitude.toFixed(1) + ' m' : '--';

    // Format time - extract HH:MM:SS from ISO string and show local time
    if (data.time) {
        lastGpsTime = new Date(data.time);
        updateTimeDisplay();
    }

    const sats = data.satellites || [];
    document.getElementById('sats-visible').textContent = sats.length;
    document.getElementById('sats-used').textContent = sats.filter(s => s.used).length;

    document.getElementById('epx').textContent =
        data.epx != null ? data.epx.toFixed(1) + ' m' : '--';
    document.getElementById('epy').textContent =
        data.epy != null ? data.epy.toFixed(1) + ' m' : '--';
    document.getElementById('epv').textContent =
        data.epv != null ? data.epv.toFixed(1) + ' m' : '--';
    document.getElementById('eps').textContent =
        data.eps != null ? data.eps.toFixed(1) + ' m/s' : '--';
    document.getElementById('epc').textContent =
        data.epc != null ? data.epc.toFixed(1) + ' m/s' : '--';

    drawSkyPlot(sats);
    updateSatTable(sats);
});

socket.on('ntp_update', (data) => {
    const card = document.getElementById('ntp-card');
    if (!data.enabled) {
        card.style.display = 'none';
        return;
    }
    card.style.display = '';

    document.getElementById('ntp-host').textContent = data.host || '--';

    const statusEl = document.getElementById('ntp-status');
    if (data.connected) {
        statusEl.textContent = 'Connected';
        statusEl.className = 'badge bg-success';
    } else {
        statusEl.textContent = 'Disconnected';
        statusEl.className = 'badge bg-danger';
    }

    if (data.time) {
        lastNtpTime = new Date(data.time);
        updateNtpTimeDisplay();
    } else {
        lastNtpTime = null;
        document.getElementById('ntp-time').textContent = '--:--:--';
    }

    document.getElementById('ntp-offset').textContent =
        data.offset != null ? (data.offset * 1000).toFixed(2) : '--';
    document.getElementById('ntp-delay').textContent =
        data.delay != null ? (data.delay * 1000).toFixed(2) : '--';
    document.getElementById('ntp-stratum').textContent = data.stratum || '--';
    document.getElementById('ntp-refid').textContent = data.ref_id || '--';
    document.getElementById('ntp-precision').textContent = data.precision || '--';
    document.getElementById('ntp-root-delay').textContent =
        data.root_delay != null ? (data.root_delay * 1000).toFixed(2) : '--';
    document.getElementById('ntp-root-disp').textContent =
        data.root_dispersion != null ? (data.root_dispersion * 1000).toFixed(2) : '--';
    document.getElementById('ntp-leap').textContent = data.leap != null ? data.leap : '--';
});

// Update time every second
setInterval(updateTimeDisplay, 1000);
setInterval(updateNtpTimeDisplay, 1000);
