/* ============================================================
   Aurora Ticket Booking — Frontend Application
   SPA-style navigation with API-driven content
   ============================================================ */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let allEvents = [];
let currentFilter = 'all';
let currentEventId = null;
let currentBookingPrice = 0;

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------
function navigateTo(page, data) {
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));

    const target = document.getElementById(`page-${page}`);
    if (target) target.classList.remove('hidden');

    const link = document.querySelector(`.nav-link[data-page="${page}"]`);
    if (link) link.classList.add('active');

    window.scrollTo({ top: 0, behavior: 'smooth' });

    switch (page) {
        case 'home':
            loadEvents();
            break;
        case 'event-detail':
            if (data && data.eventId) loadEventDetail(data.eventId);
            break;
        case 'bookings':
            break;
        case 'dashboard':
            loadDashboard();
            break;
    }
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------
async function loadEvents() {
    const grid = document.getElementById('events-grid');
    const loading = document.getElementById('events-loading');
    if (loading) loading.style.display = 'grid';

    try {
        const res = await fetch('/api/events');
        const data = await res.json();
        if (!data.success) throw new Error(data.error || 'Failed to load events');

        allEvents = data.events;
        renderEvents(allEvents);
        updateEndpointIndicator(data.endpoint);
    } catch (err) {
        grid.innerHTML = `<div class="empty-state"><span class="empty-icon">⚠️</span><p>${err.message}</p></div>`;
    }
}

function renderEvents(events) {
    const grid = document.getElementById('events-grid');
    const loading = document.getElementById('events-loading');
    if (loading) loading.style.display = 'none';

    const filtered = currentFilter === 'all'
        ? events
        : events.filter(e => e.category === currentFilter);

    if (filtered.length === 0) {
        grid.innerHTML = '<div class="empty-state"><span class="empty-icon">🎭</span><p>No events found in this category</p></div>';
        return;
    }

    grid.innerHTML = filtered.map((event, i) => {
        const cat = (event.category || 'general').toLowerCase();
        const emoji = getCategoryEmoji(event.category);
        const availPct = event.total_tickets > 0 ? (event.available_tickets / event.total_tickets) * 100 : 0;
        let availClass = 'available';
        let availText = `${event.available_tickets.toLocaleString()} left`;
        if (availPct === 0) { availClass = 'sold-out'; availText = 'Sold Out'; }
        else if (availPct < 10) { availClass = 'low'; availText = `Only ${event.available_tickets} left!`; }

        return `
        <div class="event-card" onclick="navigateTo('event-detail', {eventId: ${event.event_id}})" style="animation-delay: ${i * 0.08}s">
            <div class="event-card-header">
                <div class="event-card-gradient ${cat}">${emoji}</div>
                <span class="event-card-category">${event.category}</span>
            </div>
            <div class="event-card-body">
                <h3 class="event-card-title">${escapeHtml(event.title)}</h3>
                <div class="event-card-meta">
                    <div class="event-card-meta-item">📅 ${formatDate(event.event_date)}</div>
                    <div class="event-card-meta-item">📍 ${escapeHtml(event.venue)}</div>
                </div>
                <div class="event-card-footer">
                    <span class="event-price">₹${Number(event.price).toLocaleString()}</span>
                    <span class="event-availability ${availClass}">${availText}</span>
                </div>
            </div>
        </div>`;
    }).join('');
}

function filterEvents(category) {
    currentFilter = category;
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.category === category);
    });
    renderEvents(allEvents);
}

// ---------------------------------------------------------------------------
// Event Detail
// ---------------------------------------------------------------------------
async function loadEventDetail(eventId) {
    currentEventId = eventId;
    const card = document.getElementById('event-detail-card');
    card.innerHTML = '<div class="loading-text">Loading event details...</div>';

    // Show the detail page
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
    document.getElementById('page-event-detail').classList.remove('hidden');

    try {
        const res = await fetch(`/api/events/${eventId}`);
        const data = await res.json();
        if (!data.success) throw new Error(data.error || 'Event not found');

        const event = data.event;
        const cat = (event.category || 'general').toLowerCase();
        const emoji = getCategoryEmoji(event.category);
        const availPct = event.total_tickets > 0 ? (event.available_tickets / event.total_tickets) * 100 : 0;
        let availClass = 'available';
        let availText = `${event.available_tickets.toLocaleString()} tickets available`;
        if (availPct === 0) { availClass = 'sold-out'; availText = 'Sold Out'; }
        else if (availPct < 10) { availClass = 'low'; availText = `Only ${event.available_tickets} tickets left!`; }

        card.innerHTML = `
        <div class="detail-header">
            <div class="detail-header-bg event-card-gradient ${cat}">${emoji}</div>
            <div class="detail-header-content">
                <span class="detail-category-badge">${event.category}</span>
                <h2 class="detail-title">${escapeHtml(event.title)}</h2>
            </div>
        </div>
        <div class="detail-body">
            <p class="detail-description">${escapeHtml(event.description || '')}</p>
            <div class="detail-info-grid">
                <div class="detail-info-item">
                    <div class="detail-info-icon">📅</div>
                    <div>
                        <div class="detail-info-label">Date & Time</div>
                        <div class="detail-info-value">${formatDate(event.event_date)}</div>
                    </div>
                </div>
                <div class="detail-info-item">
                    <div class="detail-info-icon">📍</div>
                    <div>
                        <div class="detail-info-label">Venue</div>
                        <div class="detail-info-value">${escapeHtml(event.venue)}</div>
                    </div>
                </div>
                <div class="detail-info-item">
                    <div class="detail-info-icon">🎟️</div>
                    <div>
                        <div class="detail-info-label">Availability</div>
                        <div class="detail-info-value"><span class="event-availability ${availClass}">${availText}</span></div>
                    </div>
                </div>
                <div class="detail-info-item">
                    <div class="detail-info-icon">📊</div>
                    <div>
                        <div class="detail-info-label">Total Capacity</div>
                        <div class="detail-info-value">${event.total_tickets.toLocaleString()} tickets</div>
                    </div>
                </div>
            </div>
            <div class="detail-actions">
                <div>
                    <div class="detail-price">₹${Number(event.price).toLocaleString()}</div>
                    <div class="detail-price-label">per ticket</div>
                </div>
                ${availPct > 0
                    ? `<button class="btn btn-primary" onclick="openBookingModal(${event.event_id}, '${escapeHtml(event.title)}', ${event.price}, ${event.available_tickets})">🎫 Book Tickets</button>`
                    : `<button class="btn btn-secondary" disabled>Sold Out</button>`}
            </div>
        </div>`;

        updateEndpointIndicator(data.endpoint);
    } catch (err) {
        card.innerHTML = `<div class="empty-state"><span class="empty-icon">⚠️</span><p>${err.message}</p></div>`;
    }
}

// ---------------------------------------------------------------------------
// Booking Modal
// ---------------------------------------------------------------------------
function openBookingModal(eventId, title, price, available) {
    currentEventId = eventId;
    currentBookingPrice = price;

    document.getElementById('modal-event-info').innerHTML =
        `<strong>${escapeHtml(title)}</strong><br>₹${Number(price).toLocaleString()} per ticket · ${available} available`;
    document.getElementById('book-qty').max = Math.min(available, 10);
    document.getElementById('book-qty').value = 1;
    updateTotalPrice();

    // Clear previous state
    document.getElementById('booking-form').reset();
    document.getElementById('book-qty').value = 1;
    clearFieldErrors();
    hideBookingMessage();

    document.getElementById('booking-modal').classList.remove('hidden');
    document.getElementById('book-name').focus();
}

function closeModal() {
    document.getElementById('booking-modal').classList.add('hidden');
}

function updateTotalPrice() {
    const qty = parseInt(document.getElementById('book-qty').value) || 0;
    const total = qty * currentBookingPrice;
    document.getElementById('total-price').textContent = `₹${total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
}

// Listen for quantity changes
document.addEventListener('DOMContentLoaded', () => {
    const qtyInput = document.getElementById('book-qty');
    if (qtyInput) {
        qtyInput.addEventListener('input', updateTotalPrice);
        qtyInput.addEventListener('change', updateTotalPrice);
    }
});

async function submitBooking(e) {
    e.preventDefault();
    clearFieldErrors();
    hideBookingMessage();

    const name = document.getElementById('book-name').value.trim();
    const email = document.getElementById('book-email').value.trim();
    const phone = document.getElementById('book-phone').value.trim();
    const numTickets = parseInt(document.getElementById('book-qty').value);

    // Client-side validation
    let valid = true;
    if (!name) { showFieldError('name', 'Name is required'); valid = false; }
    if (!email || !email.includes('@')) { showFieldError('email', 'Valid email is required'); valid = false; }
    if (!numTickets || numTickets < 1) { showFieldError('qty', 'At least 1 ticket required'); valid = false; }
    if (!valid) return;

    const btn = document.getElementById('submit-booking-btn');
    setButtonLoading(btn, true);

    try {
        const res = await fetch('/api/book', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                event_id: currentEventId,
                name, email, phone,
                num_tickets: numTickets
            })
        });

        const data = await res.json();

        if (data.success) {
            showBookingMessage('success',
                `✅ Booking confirmed! Reference: <strong>${data.booking_ref}</strong><br>` +
                `${data.num_tickets} ticket(s) · Total: ₹${Number(data.total_price).toLocaleString()}<br>` +
                `<small>Routed via: ${data.endpoint} endpoint (${data.duration_ms}ms)</small>`
            );
            showToast('success', `Booking ${data.booking_ref} confirmed!`);

            // Refresh the event detail after booking
            setTimeout(() => {
                loadEventDetail(currentEventId);
            }, 1500);
        } else {
            const errMsg = data.errors ? data.errors.join('<br>') : (data.error || 'Booking failed');
            showBookingMessage('error', `❌ ${errMsg}`);
            showToast('error', data.error || 'Booking failed');
        }
    } catch (err) {
        showBookingMessage('error', `❌ Network error: ${err.message}`);
        showToast('error', 'Network error');
    } finally {
        setButtonLoading(btn, false);
    }
}

// ---------------------------------------------------------------------------
// Bookings Page
// ---------------------------------------------------------------------------
async function searchBookings() {
    const email = document.getElementById('bookings-email').value.trim();
    if (!email) {
        showToast('error', 'Please enter your email address');
        return;
    }

    const list = document.getElementById('bookings-list');
    list.innerHTML = '<div class="loading-text">Searching bookings...</div>';

    try {
        const res = await fetch(`/api/bookings?email=${encodeURIComponent(email)}`);
        const data = await res.json();
        if (!data.success) throw new Error(data.error || 'Failed to load bookings');

        if (data.bookings.length === 0) {
            list.innerHTML = '<div class="empty-state"><span class="empty-icon">🎫</span><p>No bookings found for this email</p></div>';
            return;
        }

        list.innerHTML = data.bookings.map((b, i) => `
        <div class="booking-card" style="animation-delay: ${i * 0.1}s">
            <div class="booking-card-header">
                <div class="booking-card-title">${escapeHtml(b.event_title)}</div>
                <span class="booking-status ${b.status}">${b.status}</span>
            </div>
            <div class="booking-card-details">
                <div class="booking-detail-item">
                    <div class="booking-detail-label">Booking Ref</div>
                    <div class="booking-detail-value">${b.booking_ref}</div>
                </div>
                <div class="booking-detail-item">
                    <div class="booking-detail-label">Tickets</div>
                    <div class="booking-detail-value">${b.num_tickets}</div>
                </div>
                <div class="booking-detail-item">
                    <div class="booking-detail-label">Total</div>
                    <div class="booking-detail-value">₹${Number(b.total_price).toLocaleString()}</div>
                </div>
                <div class="booking-detail-item">
                    <div class="booking-detail-label">Venue</div>
                    <div class="booking-detail-value">${escapeHtml(b.venue)}</div>
                </div>
                <div class="booking-detail-item">
                    <div class="booking-detail-label">Event Date</div>
                    <div class="booking-detail-value">${formatDate(b.event_date)}</div>
                </div>
                <div class="booking-detail-item">
                    <div class="booking-detail-label">Booked At</div>
                    <div class="booking-detail-value">${formatDate(b.booked_at)}</div>
                </div>
            </div>
            ${b.status === 'confirmed' ? `
            <div class="booking-card-actions">
                <button class="btn btn-danger btn-sm" onclick="cancelBooking('${b.booking_ref}')">
                    Cancel Booking
                </button>
            </div>` : `
            <div class="booking-card-actions">
                <span style="font-size: 0.8rem; color: var(--text-muted);">
                    Cancelled on ${formatDate(b.cancelled_at)}
                </span>
            </div>`}
        </div>`).join('');

    } catch (err) {
        list.innerHTML = `<div class="empty-state"><span class="empty-icon">⚠️</span><p>${err.message}</p></div>`;
    }
}

async function cancelBooking(bookingRef) {
    if (!confirm(`Cancel booking ${bookingRef}? This will release your tickets.`)) return;

    try {
        const res = await fetch('/api/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ booking_ref: bookingRef })
        });

        const data = await res.json();

        if (data.success) {
            showToast('success', `Booking ${bookingRef} cancelled`);
            searchBookings(); // Refresh
        } else {
            showToast('error', data.error || 'Cancellation failed');
        }
    } catch (err) {
        showToast('error', `Network error: ${err.message}`);
    }
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
async function loadDashboard() {
    loadConfig();
    loadStats();
    loadEndpointSummary();
    loadActivityLog();
}

async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        if (!data.success) return;

        const cfg = data.config;
        const banner = document.getElementById('config-banner');
        banner.innerHTML = `
            <div class="config-item">
                <span class="config-label">Mode</span>
                <span class="config-value">${cfg.use_local_db ? '🟡 Local SQLite' : '🟢 Aurora PostgreSQL'}</span>
            </div>
            <div class="config-item">
                <span class="config-label">Writer Endpoint</span>
                <span class="config-value">${escapeHtml(cfg.writer_host)}</span>
            </div>
            <div class="config-item">
                <span class="config-label">Reader Endpoint</span>
                <span class="config-value">${escapeHtml(cfg.reader_host)}</span>
            </div>
            <div class="config-item">
                <span class="config-label">Database</span>
                <span class="config-value">${escapeHtml(cfg.db_name)}</span>
            </div>`;

        // Update nav indicator
        const indicator = document.querySelector('.nav-indicator');
        if (cfg.use_local_db) {
            indicator.classList.remove('connected');
            indicator.querySelector('.indicator-text').textContent = 'Local DB';
        } else {
            indicator.classList.add('connected');
            indicator.querySelector('.indicator-text').textContent = 'Aurora';
        }
    } catch (err) { /* ignore */ }
}

async function loadStats() {
    try {
        const res = await fetch('/api/dashboard/stats');
        const data = await res.json();
        if (!data.success) return;

        const s = data.stats;
        animateNumber('stat-events', s.total_events);
        animateNumber('stat-bookings', s.total_bookings);
        animateNumber('stat-tickets', s.total_tickets_sold);
        document.getElementById('stat-revenue').textContent = `₹${Number(s.total_revenue).toLocaleString()}`;
        animateNumber('stat-customers', s.total_customers);
    } catch (err) { /* ignore */ }
}

async function loadEndpointSummary() {
    try {
        const res = await fetch('/api/dashboard/endpoint-summary');
        const data = await res.json();
        if (!data.success) return;

        const container = document.getElementById('routing-summary');
        if (data.summary.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No activity recorded yet. Browse events or make a booking to generate data.</p></div>';
            return;
        }

        container.innerHTML = data.summary.map((item, i) => `
        <div class="routing-card" style="animation-delay: ${i * 0.1}s">
            <div class="routing-card-header">
                <span class="routing-endpoint ${item.endpoint_used}">${item.endpoint_used.toUpperCase()}</span>
                <span class="routing-operation">${item.operation}</span>
            </div>
            <div class="routing-stat">
                <span class="routing-stat-label">Total Queries</span>
                <span class="routing-stat-value">${item.count}</span>
            </div>
            <div class="routing-stat">
                <span class="routing-stat-label">Avg Duration</span>
                <span class="routing-stat-value">${item.avg_duration_ms}ms</span>
            </div>
        </div>`).join('');
    } catch (err) { /* ignore */ }
}

async function loadActivityLog() {
    try {
        const res = await fetch('/api/dashboard/activity?limit=30');
        const data = await res.json();
        if (!data.success) return;

        const tbody = document.getElementById('activity-tbody');
        if (data.activity.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading-text">No activity yet</td></tr>';
            return;
        }

        tbody.innerHTML = data.activity.map(a => `
        <tr>
            <td>${formatTime(a.recorded_at)}</td>
            <td><span class="operation-badge ${a.operation}">${a.operation}</span></td>
            <td><span class="endpoint-badge ${a.endpoint_used}">${a.endpoint_used}</span></td>
            <td>${escapeHtml(a.query_type || '—')}</td>
            <td>${a.duration_ms !== null ? a.duration_ms + 'ms' : '—'}</td>
        </tr>`).join('');
    } catch (err) { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Load Test Results Display
// ---------------------------------------------------------------------------
function loadTestResults(input) {
    const file = input.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            const results = JSON.parse(e.target.result);
            displayLoadTestResults(results);
        } catch (err) {
            showToast('error', 'Invalid JSON file');
        }
    };
    reader.readAsText(file);
}

function displayLoadTestResults(results) {
    const container = document.getElementById('load-test-results');
    container.classList.remove('hidden');

    let html = '';

    if (results.read_load_test) {
        const r = results.read_load_test;
        html += `
        <div class="load-test-card">
            <h4>📖 Read Load Test Results</h4>
            <p style="color: var(--text-secondary); margin-bottom: var(--space-md); font-size: 0.85rem;">
                ${r.total_requests} requests · ${r.concurrent_workers} workers · ${r.duration_seconds}s
            </p>
            <div class="load-test-metrics">
                <div class="metric-item"><div class="metric-value">${r.requests_per_second?.toFixed(1) || '—'}</div><div class="metric-label">Req/sec</div></div>
                <div class="metric-item"><div class="metric-value">${r.avg_latency_ms?.toFixed(1) || '—'}ms</div><div class="metric-label">Avg Latency</div></div>
                <div class="metric-item"><div class="metric-value">${r.p50_latency_ms?.toFixed(1) || '—'}ms</div><div class="metric-label">P50 Latency</div></div>
                <div class="metric-item"><div class="metric-value">${r.p95_latency_ms?.toFixed(1) || '—'}ms</div><div class="metric-label">P95 Latency</div></div>
                <div class="metric-item"><div class="metric-value">${r.p99_latency_ms?.toFixed(1) || '—'}ms</div><div class="metric-label">P99 Latency</div></div>
                <div class="metric-item"><div class="metric-value">${r.error_count || 0}</div><div class="metric-label">Errors</div></div>
            </div>
        </div>`;
    }

    if (results.concurrency_test) {
        const c = results.concurrency_test;
        html += `
        <div class="load-test-card">
            <h4>⚡ Concurrency Test Results</h4>
            <p style="color: var(--text-secondary); margin-bottom: var(--space-md); font-size: 0.85rem;">
                ${c.total_attempts} concurrent booking attempts for ${c.available_tickets} available tickets
            </p>
            <div class="load-test-metrics">
                <div class="metric-item"><div class="metric-value">${c.successful_bookings}</div><div class="metric-label">Succeeded</div></div>
                <div class="metric-item"><div class="metric-value">${c.failed_bookings}</div><div class="metric-label">Failed (expected)</div></div>
                <div class="metric-item"><div class="metric-value">${c.oversold ? '❌ YES' : '✅ NO'}</div><div class="metric-label">Oversold?</div></div>
                <div class="metric-item"><div class="metric-value">${c.inventory_correct ? '✅ YES' : '❌ NO'}</div><div class="metric-label">Inventory OK?</div></div>
            </div>
        </div>`;
    }

    if (results.endpoint_comparison) {
        const ec = results.endpoint_comparison;
        html += `
        <div class="load-test-card">
            <h4>🔄 Writer vs Reader Endpoint Comparison</h4>
            <p style="color: var(--text-secondary); margin-bottom: var(--space-md); font-size: 0.85rem;">
                Comparing read performance through writer and reader endpoints
            </p>
            <div class="load-test-metrics">
                <div class="metric-item"><div class="metric-value">${ec.writer_avg_ms?.toFixed(1) || '—'}ms</div><div class="metric-label">Writer Avg</div></div>
                <div class="metric-item"><div class="metric-value">${ec.reader_avg_ms?.toFixed(1) || '—'}ms</div><div class="metric-label">Reader Avg</div></div>
                <div class="metric-item"><div class="metric-value">${ec.writer_rps?.toFixed(1) || '—'}</div><div class="metric-label">Writer RPS</div></div>
                <div class="metric-item"><div class="metric-value">${ec.reader_rps?.toFixed(1) || '—'}</div><div class="metric-label">Reader RPS</div></div>
            </div>
        </div>`;
    }

    container.innerHTML = html || '<div class="empty-state"><p>No recognizable test results in the file</p></div>';
}

// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-IN', {
            day: 'numeric', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    } catch {
        return dateStr;
    }
}

function formatTime(dateStr) {
    if (!dateStr) return '—';
    try {
        const d = new Date(dateStr);
        return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
        return dateStr;
    }
}

function getCategoryEmoji(category) {
    const map = {
        'Music': '🎵', 'Sports': '🏏', 'Comedy': '😂',
        'Conference': '🎤', 'Exhibition': '🎨', 'General': '🎭'
    };
    return map[category] || '🎭';
}

function animateNumber(elementId, target) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const duration = 800;
    const start = performance.now();
    const initial = 0;

    function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        el.textContent = Math.round(initial + (target - initial) * eased).toLocaleString();
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

function showFieldError(field, msg) {
    const el = document.getElementById(`error-${field}`);
    if (el) el.textContent = msg;
}

function clearFieldErrors() {
    document.querySelectorAll('.field-error').forEach(el => el.textContent = '');
}

function showBookingMessage(type, msg) {
    const el = document.getElementById('booking-message');
    el.className = `form-message ${type}`;
    el.innerHTML = msg;
}

function hideBookingMessage() {
    const el = document.getElementById('booking-message');
    el.className = 'form-message hidden';
    el.innerHTML = '';
}

function setButtonLoading(btn, loading) {
    if (!btn) return;
    const text = btn.querySelector('.btn-text');
    const spinner = btn.querySelector('.btn-spinner');
    if (loading) {
        btn.disabled = true;
        if (text) text.textContent = 'Processing...';
        if (spinner) spinner.classList.remove('hidden');
    } else {
        btn.disabled = false;
        if (text) text.textContent = 'Confirm Booking';
        if (spinner) spinner.classList.add('hidden');
    }
}

function showToast(type, message) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    toast.innerHTML = `${icons[type] || ''} ${escapeHtml(message)}`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function updateEndpointIndicator(endpoint) {
    // Visual feedback on which endpoint was used (shown briefly in nav)
}

// Handle Enter key in bookings search
document.addEventListener('DOMContentLoaded', () => {
    const emailInput = document.getElementById('bookings-email');
    if (emailInput) {
        emailInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') searchBookings();
        });
    }
});

// ---------------------------------------------------------------------------
// Initial Load
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    loadEvents();
    loadConfig();
});
