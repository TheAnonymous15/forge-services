<?php
/**
 * ForgeForth Africa — Coming Soon Page
 * ====================================
 * 100% standalone PHP file.
 * Only external dependency: one.jpg (place in same directory).
 *
 * Features:
 *   - Coming-soon landing page with waitlist modal + contact modal
 *   - Self-contained config via config.json (same dir) — optional
 *   - SQLite databases for secure persistent storage:
 *       • earlyaccess.db  — registrants from "Get Early Access" waitlist
 *       • messages.db     — contact form direct messages
 *   - Built-in health-check API  → ?action=health
 *   - Built-in waitlist POST API → ?action=waitlist
 *   - Built-in contact POST API  → ?action=contact
 *   - No external CSS/JS files needed (Tailwind CDN + inline JS)
 */

// ─── No caching ──────────────────────────────────────
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');

// ─── Config ──────────────────────────────────────────
$config_file = __DIR__ . '/config.json';
$config = file_exists($config_file)
    ? (json_decode(file_get_contents($config_file), true) ?: [])
    : [];

// If coming-soon mode is explicitly OFF, redirect to main site
if (isset($config['coming_soon_mode']) && !$config['coming_soon_mode']) {
    $redirect = isset($config['redirect_url']) ? $config['redirect_url'] : '/';
    header('Location: ' . $redirect);
    exit;
}

// ─── Database helpers ────────────────────────────────
$db_dir = __DIR__ . '/data';
if (!is_dir($db_dir)) {
    mkdir($db_dir, 0755, true);
}

// Protect the data directory with .htaccess
$htaccess = $db_dir . '/.htaccess';
if (!file_exists($htaccess)) {
    file_put_contents($htaccess, "Deny from all\n");
}

/**
 * Initialise the early-access (waitlist) SQLite database.
 */
function get_earlyaccess_db() {
    global $db_dir;
    $db_path = $db_dir . '/earlyaccess.db';
    $db = new SQLite3($db_path);
    $db->busyTimeout(5000);
    $db->exec('PRAGMA journal_mode=WAL');
    $db->exec('PRAGMA foreign_keys=ON');
    $db->exec('
        CREATE TABLE IF NOT EXISTS registrants (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name      TEXT NOT NULL,
            last_name       TEXT DEFAULT "",
            email           TEXT NOT NULL,
            phone           TEXT DEFAULT "",
            country         TEXT DEFAULT "",
            user_type       TEXT DEFAULT "talent",
            opportunity_types TEXT DEFAULT "",
            skills          TEXT DEFAULT "",
            preferred_field TEXT DEFAULT "",
            referral_source TEXT DEFAULT "",
            ip_address      TEXT DEFAULT "",
            user_agent      TEXT DEFAULT "",
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_confirmed    INTEGER DEFAULT 0,
            notes           TEXT DEFAULT ""
        )
    ');
    // Unique constraint on email to prevent duplicates
    $db->exec('CREATE UNIQUE INDEX IF NOT EXISTS idx_registrants_email ON registrants(email)');
    return $db;
}

/**
 * Initialise the messages (contact) SQLite database.
 */
function get_messages_db() {
    global $db_dir;
    $db_path = $db_dir . '/messages.db';
    $db = new SQLite3($db_path);
    $db->busyTimeout(5000);
    $db->exec('PRAGMA journal_mode=WAL');
    $db->exec('PRAGMA foreign_keys=ON');
    $db->exec('
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name   TEXT NOT NULL,
            email       TEXT NOT NULL,
            phone       TEXT DEFAULT "",
            country     TEXT DEFAULT "",
            message     TEXT NOT NULL,
            channel     TEXT DEFAULT "direct",
            ip_address  TEXT DEFAULT "",
            user_agent  TEXT DEFAULT "",
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_read     INTEGER DEFAULT 0,
            is_replied  INTEGER DEFAULT 0,
            notes       TEXT DEFAULT ""
        )
    ');
    $db->exec('CREATE INDEX IF NOT EXISTS idx_messages_email ON messages(email)');
    $db->exec('CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)');

    // Users table for admin dashboard auth
    $db->exec('
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT NOT NULL UNIQUE,
            password_hash   TEXT NOT NULL,
            display_name    TEXT DEFAULT "",
            role            TEXT DEFAULT "admin",
            is_active       INTEGER DEFAULT 1,
            last_login      DATETIME DEFAULT NULL,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ');

    // Seed default admin user if no users exist
    $user_count = $db->querySingle('SELECT COUNT(*) FROM users');
    if ($user_count == 0) {
        $hashed = password_hash('ForthAdmin2026', PASSWORD_BCRYPT);
        $stmt = $db->prepare('INSERT INTO users (username, password_hash, display_name, role) VALUES (:u, :p, :d, :r)');
        $stmt->bindValue(':u', 'admin', SQLITE3_TEXT);
        $stmt->bindValue(':p', $hashed, SQLITE3_TEXT);
        $stmt->bindValue(':d', 'Administrator', SQLITE3_TEXT);
        $stmt->bindValue(':r', 'admin', SQLITE3_TEXT);
        $stmt->execute();
    }

    return $db;
}

/**
 * Sanitise user input.
 */
function clean($value) {
    if (!is_string($value)) return '';
    return trim(strip_tags($value));
}

/**
 * Get client IP (handles proxies).
 */
function get_client_ip() {
    $headers = ['HTTP_CF_CONNECTING_IP', 'HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP', 'REMOTE_ADDR'];
    foreach ($headers as $h) {
        if (!empty($_SERVER[$h])) {
            $ip = explode(',', $_SERVER[$h])[0];
            $ip = trim($ip);
            if (filter_var($ip, FILTER_VALIDATE_IP)) return $ip;
        }
    }
    return $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
}

// ─── API: Health check ───────────────────────────────
if (isset($_GET['action']) && $_GET['action'] === 'health') {
    header('Content-Type: application/json');
    header('Access-Control-Allow-Origin: *');
    $coming = isset($config['coming_soon_mode']) ? (bool)$config['coming_soon_mode'] : true;
    echo json_encode([
        'status'    => $coming ? 'coming_soon' : 'healthy',
        'timestamp' => date('c'),
    ]);
    exit;
}

// ─── API: Early Access (Waitlist) submission ─────────
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_GET['action']) && $_GET['action'] === 'waitlist') {
    header('Content-Type: application/json');
    header('Access-Control-Allow-Origin: *');

    $body = json_decode(file_get_contents('php://input'), true);
    if (!$body || empty($body['email']) || empty($body['first_name'])) {
        http_response_code(400);
        echo json_encode(['detail' => 'Missing required fields (first_name, email).']);
        exit;
    }

    try {
        $db = get_earlyaccess_db();

        // Check for duplicate email
        $check = $db->prepare('SELECT id FROM registrants WHERE email = :email');
        $check->bindValue(':email', clean($body['email']), SQLITE3_TEXT);
        $existing = $check->execute()->fetchArray();

        if ($existing) {
            // Update existing record instead of failing
            $stmt = $db->prepare('
                UPDATE registrants SET
                    first_name = :first_name,
                    last_name = :last_name,
                    phone = :phone,
                    country = :country,
                    user_type = :user_type,
                    opportunity_types = :opportunity_types,
                    skills = :skills,
                    preferred_field = :preferred_field,
                    referral_source = :referral_source,
                    ip_address = :ip,
                    user_agent = :ua,
                    created_at = CURRENT_TIMESTAMP
                WHERE email = :email
            ');
        } else {
            $stmt = $db->prepare('
                INSERT INTO registrants
                    (first_name, last_name, email, phone, country, user_type,
                     opportunity_types, skills, preferred_field, referral_source,
                     ip_address, user_agent)
                VALUES
                    (:first_name, :last_name, :email, :phone, :country, :user_type,
                     :opportunity_types, :skills, :preferred_field, :referral_source,
                     :ip, :ua)
            ');
        }

        $opp_types = '';
        if (isset($body['opportunity_types']) && is_array($body['opportunity_types'])) {
            $opp_types = implode(', ', array_map('clean', $body['opportunity_types']));
        }

        $stmt->bindValue(':first_name',       clean($body['first_name'] ?? ''),       SQLITE3_TEXT);
        $stmt->bindValue(':last_name',         clean($body['last_name'] ?? ''),        SQLITE3_TEXT);
        $stmt->bindValue(':email',             clean($body['email']),                  SQLITE3_TEXT);
        $stmt->bindValue(':phone',             clean($body['phone'] ?? ''),            SQLITE3_TEXT);
        $stmt->bindValue(':country',           clean($body['country'] ?? ''),          SQLITE3_TEXT);
        $stmt->bindValue(':user_type',         clean($body['user_type'] ?? 'talent'),  SQLITE3_TEXT);
        $stmt->bindValue(':opportunity_types', $opp_types,                             SQLITE3_TEXT);
        $stmt->bindValue(':skills',            clean($body['skills'] ?? ''),           SQLITE3_TEXT);
        $stmt->bindValue(':preferred_field',   clean($body['preferred_field'] ?? ''),  SQLITE3_TEXT);
        $stmt->bindValue(':referral_source',   clean($body['referral_source'] ?? ''),  SQLITE3_TEXT);
        $stmt->bindValue(':ip',                get_client_ip(),                        SQLITE3_TEXT);
        $stmt->bindValue(':ua',                clean($_SERVER['HTTP_USER_AGENT'] ?? ''), SQLITE3_TEXT);

        $stmt->execute();

        // Get total count for fun
        $count = $db->querySingle('SELECT COUNT(*) FROM registrants');
        $db->close();

        echo json_encode([
            'status'  => 'ok',
            'message' => 'You are on the list!',
            'position' => (int)$count
        ]);
    } catch (Exception $e) {
        error_log('ForgeForth Waitlist Error: ' . $e->getMessage());
        http_response_code(500);
        echo json_encode(['detail' => 'Something went wrong. Please try again.']);
    }
    exit;
}

// ─── API: Contact (Direct Message) submission ────────
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_GET['action']) && $_GET['action'] === 'contact') {
    header('Content-Type: application/json');
    header('Access-Control-Allow-Origin: *');

    $body = json_decode(file_get_contents('php://input'), true);
    if (!$body || empty($body['name']) || empty($body['email']) || empty($body['message'])) {
        http_response_code(400);
        echo json_encode(['detail' => 'Missing required fields (name, email, message).']);
        exit;
    }

    try {
        $db = get_messages_db();

        // Rate limiting: max 5 messages per IP per hour
        $ip = get_client_ip();
        $rate_check = $db->prepare('
            SELECT COUNT(*) FROM messages
            WHERE ip_address = :ip AND created_at > datetime("now", "-1 hour")
        ');
        $rate_check->bindValue(':ip', $ip, SQLITE3_TEXT);
        $recent_count = $rate_check->execute()->fetchArray()[0];

        if ($recent_count >= 5) {
            http_response_code(429);
            echo json_encode(['detail' => 'Too many messages. Please try again later.']);
            $db->close();
            exit;
        }

        $stmt = $db->prepare('
            INSERT INTO messages
                (full_name, email, phone, country, message, channel, ip_address, user_agent)
            VALUES
                (:name, :email, :phone, :country, :message, :channel, :ip, :ua)
        ');

        $stmt->bindValue(':name',    clean($body['name']),              SQLITE3_TEXT);
        $stmt->bindValue(':email',   clean($body['email']),             SQLITE3_TEXT);
        $stmt->bindValue(':phone',   clean($body['phone'] ?? ''),      SQLITE3_TEXT);
        $stmt->bindValue(':country', clean($body['country'] ?? ''),    SQLITE3_TEXT);
        $stmt->bindValue(':message', clean($body['message']),           SQLITE3_TEXT);
        $stmt->bindValue(':channel', clean($body['channel'] ?? 'direct'), SQLITE3_TEXT);
        $stmt->bindValue(':ip',      $ip,                               SQLITE3_TEXT);
        $stmt->bindValue(':ua',      clean($_SERVER['HTTP_USER_AGENT'] ?? ''), SQLITE3_TEXT);

        $stmt->execute();
        $msg_id = $db->lastInsertRowID();
        $db->close();

        echo json_encode([
            'status'  => 'ok',
            'message' => 'Message received!',
            'id'      => $msg_id
        ]);
    } catch (Exception $e) {
        error_log('ForgeForth Contact Error: ' . $e->getMessage());
        http_response_code(500);
        echo json_encode(['detail' => 'Something went wrong. Please try again.']);
    }
    exit;
}

// ─── CORS preflight ──────────────────────────────────
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    header('Access-Control-Allow-Origin: *');
    header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type');
    http_response_code(204);
    exit;
}

// ─── Render page ─────────────────────────────────────
header('Content-Type: text/html; charset=UTF-8');
$year = date('Y');
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Coming Soon - ForgeForth Africa</title>
    <meta name="description" content="ForgeForth Africa - Forging Africa's Future Through Talents. AI-powered talent infrastructure connecting skills to global opportunities.">
    <meta property="og:title" content="Coming Soon - ForgeForth Africa">
    <meta property="og:description" content="Africa's AI-powered talent infrastructure is on the way.">
    <meta property="og:type" content="website">
    <link rel="icon" type="image/x-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#x1F30D;</text></svg>">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        primary: '#0F4C81',
                        'forgeforth-blue-light': '#1E88E5',
                        secondary: '#F7A600',
                        accent: '#4CAF50',
                    },
                    fontFamily: {
                        display: ['Inter', 'sans-serif'],
                    },
                }
            }
        }
    </script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: #050a12; overflow-x: hidden; }
        #mesh-canvas { position: fixed; inset: 0; z-index: 0; opacity: 0.35; }
        .orb-center {
            width: 280px; height: 280px; border-radius: 50%;
            background: radial-gradient(circle at 40% 40%, rgba(56,189,248,0.12) 0%, rgba(99,102,241,0.08) 40%, rgba(15,20,40,0.95) 70%, rgba(10,14,30,0.98) 100%);
            position: relative; z-index: 10;
        }
        .orbit-system { position: relative; width: 440px; height: 440px; }
        .orbit-ring { position: absolute; border-radius: 50%; border: 1px solid transparent; top: 50%; left: 50%; transform-origin: center; }
        .orbit-ring-1 { width: 320px; height: 320px; margin-top: -160px; margin-left: -160px; border-color: rgba(56,189,248,0.15); border-top-color: rgba(56,189,248,0.5); border-right-color: rgba(56,189,248,0.3); animation: spin-cw 10s linear infinite; }
        .orbit-ring-2 { width: 370px; height: 370px; margin-top: -185px; margin-left: -185px; border-color: rgba(139,92,246,0.1); border-bottom-color: rgba(139,92,246,0.45); border-left-color: rgba(139,92,246,0.25); animation: spin-ccw 14s linear infinite; }
        .orbit-ring-3 { width: 420px; height: 420px; margin-top: -210px; margin-left: -210px; border-color: rgba(99,102,241,0.06); border-top-color: rgba(99,102,241,0.35); border-left-color: rgba(99,102,241,0.18); animation: spin-cw 20s linear infinite; }
        .orbit-ring-4 { width: 348px; height: 348px; margin-top: -174px; margin-left: -174px; border: none; border-top: 1px dashed rgba(56,189,248,0.2); border-bottom: 1px dashed rgba(139,92,246,0.2); animation: spin-ccw 18s linear infinite; }
        .orbit-dot  { position: absolute; width: 6px; height: 6px; border-radius: 50%; top: -3px; left: 50%; margin-left: -3px; }
        .orbit-dot-2 { position: absolute; width: 5px; height: 5px; border-radius: 50%; bottom: -2.5px; left: 25%; margin-left: -2.5px; }
        .orbit-dot-3 { position: absolute; width: 4px; height: 4px; border-radius: 50%; top: 50%; right: -2px; margin-top: -2px; }
        @keyframes spin-cw  { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes spin-ccw { from { transform: rotate(0deg); } to { transform: rotate(-360deg); } }
        @keyframes dot-pulse { 0%, 100% { opacity: 0.5; box-shadow: 0 0 4px currentColor; } 50% { opacity: 1; box-shadow: 0 0 12px currentColor, 0 0 24px currentColor; } }
        .reveal-text { opacity: 0; transform: translateY(24px); animation: reveal 0.8s cubic-bezier(0.16,1,0.3,1) forwards; }
        .reveal-d1 { animation-delay: 0.15s; } .reveal-d2 { animation-delay: 0.3s; } .reveal-d3 { animation-delay: 0.45s; }
        .reveal-d4 { animation-delay: 0.6s; }  .reveal-d5 { animation-delay: 0.75s; } .reveal-d6 { animation-delay: 0.9s; }
        @keyframes reveal { to { opacity: 1; transform: translateY(0); } }
        .glow-btn { position: relative; overflow: hidden; }
        .glow-btn::before { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent); transform: translateX(-100%); transition: transform 0.6s ease; }
        .glow-btn:hover::before { transform: translateX(100%); }
        .stat-value { background: linear-gradient(135deg, #e2e8f0, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .hide-scroll::-webkit-scrollbar { display: none; } .hide-scroll { scrollbar-width: none; }
        .opp-pill.opp-active-volunteer  { border-color: #34d399 !important; background-color: rgba(16,185,129,0.18) !important; box-shadow: 0 0 0 1px rgba(52,211,153,0.3), 0 2px 10px rgba(16,185,129,0.2) !important; }
        .opp-pill.opp-active-volunteer .opp-label { color: #6ee7b7 !important; }
        .opp-pill.opp-active-internship { border-color: #38bdf8 !important; background-color: rgba(14,165,233,0.18) !important; box-shadow: 0 0 0 1px rgba(56,189,248,0.3), 0 2px 10px rgba(14,165,233,0.2) !important; }
        .opp-pill.opp-active-internship .opp-label { color: #7dd3fc !important; }
        .opp-pill.opp-active-job        { border-color: #fbbf24 !important; background-color: rgba(245,158,11,0.18) !important; box-shadow: 0 0 0 1px rgba(251,191,36,0.3), 0 2px 10px rgba(245,158,11,0.2) !important; }
        .opp-pill.opp-active-job .opp-label { color: #fcd34d !important; }
        .opp-pill.opp-active-skillup    { border-color: #a78bfa !important; background-color: rgba(139,92,246,0.18) !important; box-shadow: 0 0 0 1px rgba(167,139,250,0.3), 0 2px 10px rgba(139,92,246,0.2) !important; }
        .opp-pill.opp-active-skillup .opp-label { color: #c4b5fd !important; }
        .skill-pill.active-pill { border-color: #a78bfa !important; background-color: rgba(139,92,246,0.18) !important; color: #c4b5fd !important; box-shadow: 0 0 0 1px rgba(167,139,250,0.3), 0 2px 8px rgba(139,92,246,0.2) !important; }
        .field-pill.active-pill { border-color: #f472b6 !important; background-color: rgba(236,72,153,0.18) !important; color: #f9a8d4 !important; box-shadow: 0 0 0 1px rgba(244,114,182,0.3), 0 2px 8px rgba(236,72,153,0.2) !important; }
    </style>
</head>
<body class="h-[95vh] max-h-[95vh] flex flex-col overflow-hidden">

    <!-- Background image — one.jpg in same directory -->
    <div class="fixed inset-0 z-0">
        <img src="one.jpg" alt="" class="w-full h-full object-cover" />
        <div class="absolute inset-0 bg-[#050a12]/85"></div>
    </div>

    <!-- Animated geometric mesh -->
    <canvas id="mesh-canvas"></canvas>

    <!-- Ambient gradient orbs -->
    <div class="fixed inset-0 z-[1] pointer-events-none overflow-hidden">
        <div class="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full bg-sky-600/[0.04] blur-3xl"></div>
        <div class="absolute -bottom-40 -right-40 w-[500px] h-[500px] rounded-full bg-indigo-600/[0.05] blur-3xl"></div>
    </div>

    <!-- ══════════ MAIN CONTENT ══════════ -->
    <main class="relative z-10 flex-1 flex items-center overflow-hidden">
        <div class="w-full max-w-7xl mx-auto px-6 sm:px-10 py-4 lg:py-0">
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-6 items-center">

                <!-- LEFT : 7 cols -->
                <div class="lg:col-span-7 flex flex-col gap-3 lg:gap-5 py-4 lg:py-10">

                    <!-- Status pill -->
                    <div class="reveal-text reveal-d1">
                        <span class="inline-flex items-center gap-2.5 px-4 py-2 rounded-full bg-white/[0.04] border border-white/[0.08] backdrop-blur-md">
                            <span class="relative flex h-2 w-2">
                                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                                <span class="relative inline-flex rounded-full h-2 w-2 bg-sky-400"></span>
                            </span>
                            <span class="text-slate-400 text-[11px] font-semibold tracking-[0.2em] uppercase">Launching Soon</span>
                        </span>
                    </div>

                    <!-- Title -->
                    <div class="reveal-text reveal-d2">
                        <h1 class="font-display font-black tracking-tight leading-[1.02]" style="font-size: clamp(2.6rem, 5.5vw, 5rem);">
                            <span class="text-white">ForgeForth </span><span class="bg-gradient-to-r from-sky-400 via-cyan-300 to-indigo-400 bg-clip-text text-transparent">Africa</span>
                        </h1>
                    </div>

                    <!-- Separator -->
                    <div class="reveal-text reveal-d3">
                        <div class="w-16 h-[2px] bg-gradient-to-r from-sky-500/60 to-transparent rounded-full"></div>
                    </div>

                    <!-- Tagline -->
                    <div class="reveal-text reveal-d3">
                        <p class="text-slate-300/90 font-medium tracking-tight max-w-lg" style="font-size: clamp(1rem, 1.8vw, 1.3rem); line-height: 1.5;">
                            Forging Africa's Future Through Talents.
                        </p>
                    </div>


                    <!-- Copy -->
                    <div class="reveal-text reveal-d4">
                        <p class="text-slate-500 text-sm leading-relaxed max-w-xl">
                            Africa's AI-powered talent infrastructure is on the way. We're building something
                            extraordinary &mdash; connecting every kind of talent across every industry with
                            global opportunities that recognise real skills, not just paper credentials.
                        </p>
                    </div>

                    <!-- Iconic quote -->
                    <div class="reveal-text reveal-d5">
                        <p class="text-slate-500/70 text-xs italic pl-4 border-l border-sky-500/20">&ldquo;There is power beyond a poor r&eacute;sum&eacute;.&rdquo;</p>
                    </div>

                    <!-- CTAs -->
                    <div class="reveal-text reveal-d5 pt-1">
                        <div class="inline-flex items-center gap-2 px-2 py-2 rounded-2xl bg-transparent border border-white/[0.06] backdrop-blur-sm">
                            <button onclick="openWaitlistModal()"
                                    class="group inline-flex items-center gap-2.5 px-5 py-2.5 rounded-xl
                                           text-xs font-medium tracking-wide
                                           bg-white/[0.05] border border-white/[0.1]
                                           text-slate-300
                                           hover:bg-white/[0.1] hover:border-white/[0.18] hover:text-white
                                           hover:-translate-y-0.5 active:translate-y-0
                                           transition-all duration-300">
                                <svg class="w-3.5 h-3.5 flex-shrink-0 text-sky-400 group-hover:text-sky-300 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"/></svg>
                                <span>Get Early Access</span>
                            </button>
                            <div class="w-px h-6 bg-white/[0.06]"></div>
                            <button onclick="openContactModal()"
                                    class="group inline-flex items-center gap-2.5 px-5 py-2.5 rounded-xl
                                           text-xs font-medium tracking-wide
                                           bg-white/[0.05] border border-white/[0.1]
                                           text-slate-300
                                           hover:bg-white/[0.1] hover:border-white/[0.18] hover:text-white
                                           hover:-translate-y-0.5 active:translate-y-0
                                           transition-all duration-300">
                                <svg class="w-3.5 h-3.5 flex-shrink-0 text-sky-400 group-hover:text-sky-300 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                                <span>Contact Us</span>
                            </button>
                        </div>
                    </div>

                </div>

                <!-- RIGHT : 5 cols — Orbit system -->
                <div class="lg:col-span-5 flex items-center justify-center relative">
                    <div class="reveal-text reveal-d5 relative flex items-center justify-center scale-[0.6] sm:scale-75 lg:scale-100 origin-center">
                        <div class="orbit-system relative flex items-center justify-center">
                            <div class="orbit-ring orbit-ring-1">
                                <div class="orbit-dot bg-sky-400" style="animation: dot-pulse 2s ease-in-out infinite; color: #38bdf8;"></div>
                                <div class="orbit-dot-2 bg-sky-300" style="animation: dot-pulse 2s ease-in-out infinite 0.8s; color: #7dd3fc;"></div>
                            </div>
                            <div class="orbit-ring orbit-ring-2">
                                <div class="orbit-dot bg-violet-400" style="animation: dot-pulse 2.5s ease-in-out infinite 0.4s; color: #a78bfa;"></div>
                                <div class="orbit-dot-3 bg-violet-300" style="animation: dot-pulse 2.5s ease-in-out infinite 1.2s; color: #c4b5fd;"></div>
                            </div>
                            <div class="orbit-ring orbit-ring-3">
                                <div class="orbit-dot bg-indigo-400" style="animation: dot-pulse 3s ease-in-out infinite 0.6s; color: #818cf8;"></div>
                            </div>
                            <div class="orbit-ring orbit-ring-4"></div>
                            <div class="orb-center absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center justify-center text-center px-8 border border-white/[0.06] shadow-[0_0_60px_rgba(56,189,248,0.06),0_0_120px_rgba(99,102,241,0.04)]">
                                <p class="font-display font-bold text-white leading-snug tracking-tight text-[0.85rem] sm:text-[1.1rem] lg:text-[1.35rem]">We promise you,</p>
                                <p class="font-display font-black leading-snug tracking-tight text-[1rem] sm:text-[1.25rem] lg:text-[1.55rem] mt-1 bg-gradient-to-r from-sky-300 via-cyan-200 to-indigo-400 bg-clip-text text-transparent">something big</p>
                                <p class="font-display font-bold text-white leading-snug tracking-tight text-[0.85rem] sm:text-[1.1rem] lg:text-[1.35rem] mt-0.5">is coming.</p>
                                <div class="w-8 sm:w-10 h-px mx-auto mt-3 sm:mt-4 mb-2 sm:mb-3 bg-gradient-to-r from-transparent via-sky-400/30 to-transparent"></div>
                                <p class="text-slate-400 text-[10px] sm:text-xs font-medium tracking-wide leading-relaxed">Are you ready to<br>transform Africa?</p>
                            </div>
                        </div>
                    </div>
                </div>

            </div>

        </div>
    </main>


    <!-- Footer -->
    <footer class="relative z-10 pb-2 pt-1 text-center flex-shrink-0">
        <p class="text-slate-700 text-[11px] tracking-wide">&copy; <?php echo $year; ?> ForgeForth Africa &middot; Created by <a href="https://synavuetechnologies.com" target="_blank" rel="noopener noreferrer" class="text-slate-500 hover:text-slate-300 transition-colors duration-200">SynaVue Technologies</a></p>
    </footer>

    <!-- ══════════ WAITLIST MODAL ══════════ -->
    <div id="waitlist-modal" class="fixed inset-0 z-[9999] hidden items-center justify-center p-4 opacity-0 transition-opacity duration-500">
        <div class="absolute inset-0 bg-black/75 backdrop-blur-lg"></div>
        <div class="absolute inset-0 pointer-events-none overflow-hidden">
            <div class="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-700/20 rounded-full blur-3xl"></div>
            <div class="absolute bottom-1/4 right-1/4 w-96 h-96 bg-pink-700/15 rounded-full blur-3xl"></div>
        </div>
        <div id="modal-content" class="relative w-full max-w-4xl max-h-[94vh] overflow-y-auto hide-scroll transform-gpu scale-75 opacity-0 transition-all duration-500" style="transform-style:preserve-3d;">
            <div class="relative rounded-3xl overflow-hidden flex flex-col shadow-[0_40px_100px_rgba(0,0,0,0.7),0_0_0_1px_rgba(255,255,255,0.07)]">

                <!-- TOP BANNER -->
                <div class="relative px-8 pt-7 pb-6 border-b border-white/[0.06]" style="background: linear-gradient(135deg, #1a0933 0%, #130826 50%, #0d1424 100%);">
                    <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-purple-500 via-pink-400 to-indigo-500"></div>
                    <div class="absolute right-0 top-0 h-full w-64 bg-gradient-to-l from-purple-600/10 to-transparent pointer-events-none"></div>
                    <button onclick="closeWaitlistModal()" class="absolute top-4 right-4 z-20 w-8 h-8 flex items-center justify-center rounded-lg bg-white/[0.08] border border-white/[0.15] hover:bg-red-500/70 hover:border-red-400/50 hover:rotate-90 transition-all duration-300">
                        <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>
                    </button>
                    <div class="flex items-center gap-4 relative z-10">
                        <div class="w-11 h-11 rounded-2xl flex-shrink-0 bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center shadow-[0_0_20px_rgba(139,92,246,0.5)]">
                            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                        </div>
                        <div>
                            <div class="flex items-center gap-2 mb-0.5">
                                <span class="text-white font-bold text-base">ForgeForth Africa</span>
                                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-500/20 border border-purple-400/30 text-purple-300 text-[10px] font-semibold uppercase tracking-widest">
                                    <span class="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse inline-block"></span> Early Access
                                </span>
                            </div>
                            <p class="text-slate-400 text-xs">Join Africa's skills-first talent platform &mdash; free, always.</p>
                        </div>
                    </div>
                </div>

                <!-- MODAL BODY -->
                <div class="bg-[#0d1424] px-8 py-6">
                    <div id="modal-success-message" class="hidden text-center py-6 px-4">
                        <div class="w-12 h-12 mx-auto mb-4 rounded-full bg-emerald-500/10 border border-emerald-400/20 flex items-center justify-center">
                            <svg class="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                        </div>
                        <h3 class="font-semibold text-base text-white mb-1.5">You're In</h3>
                        <p class="text-slate-400 text-xs max-w-xs mx-auto leading-relaxed mb-1">Your space in <span class="text-white font-medium">ForgeForth Africa</span> has been reserved.</p>
                        <p class="text-slate-600 text-[11px]">We'll reach out with next steps soon.</p>
                        <button onclick="closeWaitlistModal()" class="mt-4 px-4 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.08] text-slate-400 text-[11px] font-medium hover:bg-white/[0.1] hover:text-white transition-all">Close</button>
                    </div>

                    <form id="modal-waitlist-form">
                        <div id="modal-grid" class="grid gap-6 relative" style="grid-template-columns: repeat(2, minmax(0, 1fr));">
                            <div class="absolute top-0 bottom-0 w-px bg-white/[0.05] pointer-events-none" style="left:50%"></div>
                            <div id="divider-23" class="absolute top-0 bottom-0 w-px bg-white/[0.05] pointer-events-none" style="left:66.666%;display:none;"></div>

                            <!-- LEFT COL -->
                            <div class="space-y-4 pr-3">
                                <div>
                                    <p class="text-slate-400 text-[10px] font-semibold uppercase tracking-widest mb-2">I'm looking for *</p>
                                    <div class="grid grid-cols-2 gap-2">
                                        <label class="cursor-pointer"><input type="checkbox" name="opportunity_type" value="volunteer" class="peer sr-only"><div class="opp-pill flex items-center gap-2 px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-slate-400 hover:bg-white/[0.08] hover:border-white/[0.15] transition-all duration-200 select-none"><span class="text-base leading-none flex-shrink-0">&#x1F91D;</span><span class="opp-label text-xs font-semibold">Volunteer</span></div></label>
                                        <label class="cursor-pointer"><input type="checkbox" name="opportunity_type" value="internship" class="peer sr-only"><div class="opp-pill flex items-center gap-2 px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-slate-400 hover:bg-white/[0.08] hover:border-white/[0.15] transition-all duration-200 select-none"><span class="text-base leading-none flex-shrink-0">&#x1F393;</span><span class="opp-label text-xs font-semibold">Internship</span></div></label>
                                        <label class="cursor-pointer"><input type="checkbox" name="opportunity_type" value="job" class="peer sr-only"><div class="opp-pill flex items-center gap-2 px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-slate-400 hover:bg-white/[0.08] hover:border-white/[0.15] transition-all duration-200 select-none"><span class="text-base leading-none flex-shrink-0">&#x1F4BC;</span><span class="opp-label text-xs font-semibold">Job</span></div></label>
                                        <label class="cursor-pointer"><input type="checkbox" name="opportunity_type" value="skillup" class="peer sr-only"><div class="opp-pill flex items-center gap-2 px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-slate-400 hover:bg-white/[0.08] hover:border-white/[0.15] transition-all duration-200 select-none"><span class="text-base leading-none flex-shrink-0">&#x1F4C8;</span><span class="opp-label text-xs font-semibold">SkillUp</span></div></label>
                                    </div>
                                </div>
                                <div class="grid grid-cols-2 gap-3">
                                    <div><label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">First *</label><input type="text" name="first_name" required placeholder="First name" class="w-full px-3 py-2.5 rounded-xl bg-white/[0.05] border border-white/[0.07] text-white placeholder-slate-600 text-xs focus:outline-none focus:border-purple-400/60 focus:bg-white/[0.08] transition-all duration-200"/></div>
                                    <div><label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">Last *</label><input type="text" name="last_name" required placeholder="Last name" class="w-full px-3 py-2.5 rounded-xl bg-white/[0.05] border border-white/[0.07] text-white placeholder-slate-600 text-xs focus:outline-none focus:border-purple-400/60 focus:bg-white/[0.08] transition-all duration-200"/></div>
                                </div>
                                <div><label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">Email *</label><div class="relative"><svg class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-600 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg><input type="email" name="email" required placeholder="you@example.com" class="w-full pl-9 pr-3 py-2.5 rounded-xl bg-white/[0.05] border border-white/[0.07] text-white placeholder-slate-600 text-xs focus:outline-none focus:border-purple-400/60 focus:bg-white/[0.08] transition-all duration-200"/></div></div>
                                <div><label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">Phone <span class="text-slate-700 normal-case tracking-normal font-normal">- optional</span></label><div class="relative"><svg class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-600 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg><input type="tel" name="phone" placeholder="+27 000 000 0000" class="w-full pl-9 pr-3 py-2.5 rounded-xl bg-white/[0.05] border border-white/[0.07] text-white placeholder-slate-600 text-xs focus:outline-none focus:border-purple-400/60 focus:bg-white/[0.08] transition-all duration-200"/></div></div>
                                <div><label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">Country *</label><select name="country" required class="w-full px-3 py-2.5 rounded-xl bg-white/[0.05] border border-white/[0.07] text-slate-300 text-xs focus:outline-none focus:border-purple-400/60 transition-all duration-200 [&>option]:bg-[#0d1424] [&>option]:text-white"><option value="">Select country</option><option>Nigeria</option><option>Kenya</option><option>South Africa</option><option>Ghana</option><option>Egypt</option><option>Ethiopia</option><option>Tanzania</option><option>Uganda</option><option>Rwanda</option><option>Other African Country</option></select></div>
                                <div><label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">How did you hear about us?</label><select name="referral_source" class="w-full px-3 py-2.5 rounded-xl bg-white/[0.05] border border-white/[0.07] text-slate-300 text-xs focus:outline-none focus:border-purple-400/60 transition-all duration-200 [&>option]:bg-[#0d1424] [&>option]:text-white"><option value="">Select one</option><option value="social_media">Social Media</option><option value="friend">Friend / Colleague</option><option value="google">Google Search</option><option value="linkedin">LinkedIn</option><option value="event">Event / Meetup</option><option value="news">News / Article</option><option value="other">Other</option></select></div>
                            </div>

                            <!-- RIGHT COL -->
                            <div class="space-y-4 pl-3">
                                <div>
                                    <div class="flex items-center justify-between mb-1"><p class="text-slate-400 text-[10px] font-semibold uppercase tracking-widest">Your Skills *</p><span id="skills-count" class="text-[10px] text-purple-300 font-semibold px-2 py-0.5 rounded-full bg-purple-500/15 border border-purple-400/25" style="display:none;"></span></div>
                                    <p class="text-slate-600 text-[10px] mb-2">Tap to select, pick all that apply</p>
                                    <div id="skills-hidden-inputs"></div>
                                    <div class="flex flex-wrap gap-1.5 max-h-[190px] overflow-y-auto hide-scroll">
                                        <button type="button" data-skill="Software Dev" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Software Dev</button>
                                        <button type="button" data-skill="Data Science" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Data Science</button>
                                        <button type="button" data-skill="AI / ML" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">AI / ML</button>
                                        <button type="button" data-skill="Cybersecurity" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Cybersecurity</button>
                                        <button type="button" data-skill="Cloud / DevOps" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Cloud / DevOps</button>
                                        <button type="button" data-skill="Design / UX" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Design / UX</button>
                                        <button type="button" data-skill="Product Mgmt" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Product Mgmt</button>
                                        <button type="button" data-skill="Marketing" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Marketing</button>
                                        <button type="button" data-skill="Finance" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Finance</button>
                                        <button type="button" data-skill="Accounting" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Accounting</button>
                                        <button type="button" data-skill="Healthcare" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Healthcare</button>
                                        <button type="button" data-skill="Nursing" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Nursing</button>
                                        <button type="button" data-skill="Teaching" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Teaching</button>
                                        <button type="button" data-skill="Legal" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Legal</button>
                                        <button type="button" data-skill="HR" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">HR</button>
                                        <button type="button" data-skill="Engineering" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Engineering</button>
                                        <button type="button" data-skill="Agriculture" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Agriculture</button>
                                        <button type="button" data-skill="Media" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Media</button>
                                        <button type="button" data-skill="Customer Service" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Customer Service</button>
                                        <button type="button" data-skill="Operations" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Operations</button>
                                        <button type="button" data-skill="Sales" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Sales</button>
                                        <button type="button" data-skill="Research" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Research</button>
                                        <button type="button" data-skill="Architecture" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Architecture</button>
                                        <button type="button" data-skill="Logistics" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Logistics</button>
                                        <button type="button" data-skill="Other" class="skill-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-purple-400/50 hover:text-slate-200 hover:bg-purple-500/10 transition-all duration-150 select-none">Other</button>
                                    </div>
                                    <div id="skill-other-wrap" style="display:none;" class="mt-2"><input type="text" id="skill-other-input" placeholder="Describe your skill..." class="w-full px-3 py-2 rounded-lg bg-purple-500/10 border border-purple-400/30 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-purple-400/60 transition-all duration-200"/></div>
                                </div>
                                <div class="h-px bg-white/[0.05] mt-2"></div>
                                <div class="pt-1">
                                    <div class="flex items-center justify-between mb-1"><p class="text-slate-400 text-[10px] font-semibold uppercase tracking-widest">Preferred Fields *</p><span id="fields-count" class="text-[10px] text-pink-300 font-semibold px-2 py-0.5 rounded-full bg-pink-500/15 border border-pink-400/25" style="display:none;"></span></div>
                                    <p class="text-slate-600 text-[10px] mb-2">Tap to select, pick all that apply</p>
                                    <div id="fields-hidden-inputs"></div>
                                    <div class="flex flex-wrap gap-1.5 max-h-[130px] overflow-y-auto hide-scroll">
                                        <button type="button" data-field="technology" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Technology</button>
                                        <button type="button" data-field="healthcare" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Healthcare</button>
                                        <button type="button" data-field="education" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Education</button>
                                        <button type="button" data-field="finance" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Finance</button>
                                        <button type="button" data-field="marketing" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Marketing</button>
                                        <button type="button" data-field="design" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Design</button>
                                        <button type="button" data-field="engineering" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Engineering</button>
                                        <button type="button" data-field="legal" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Legal</button>
                                        <button type="button" data-field="hr" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Human Resources</button>
                                        <button type="button" data-field="operations" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Operations</button>
                                        <button type="button" data-field="agriculture" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Agriculture</button>
                                        <button type="button" data-field="media" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Media</button>
                                        <button type="button" data-field="research" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Research</button>
                                        <button type="button" data-field="hospitality" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Hospitality</button>
                                        <button type="button" data-field="manufacturing" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Manufacturing</button>
                                        <button type="button" data-field="other" class="field-pill px-2.5 py-1 rounded-lg text-[10px] font-medium bg-white/[0.04] border border-white/[0.07] text-slate-500 hover:border-pink-400/50 hover:text-slate-200 hover:bg-pink-500/10 transition-all duration-150 select-none">Other</button>
                                    </div>
                                    <div id="field-other-wrap" style="display:none;" class="mt-2"><input type="text" id="field-other-input" placeholder="Describe your preferred field..." class="w-full px-3 py-2 rounded-lg bg-pink-500/10 border border-pink-400/30 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-pink-400/60 transition-all duration-200"/></div>
                                </div>
                            </div>

                            <!-- THIRD COL (selections) -->
                            <div id="modal-col-3" class="pl-4" style="display:none;">
                                <div class="sticky top-0 rounded-2xl bg-white/[0.03] border border-white/[0.06] p-4">
                                    <div class="flex items-center gap-2 mb-4">
                                        <div class="w-5 h-5 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center flex-shrink-0"><svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg></div>
                                        <p class="text-white text-xs font-semibold">Your Selections</p>
                                    </div>
                                    <div id="col3-skills-wrap" class="mb-3" style="display:none;"><p class="text-purple-400 text-[10px] font-semibold uppercase tracking-widest mb-2">Skills</p><div id="col3-skills" class="flex flex-col gap-1.5"></div></div>
                                    <div id="col3-fields-wrap" style="display:none;"><p class="text-pink-400 text-[10px] font-semibold uppercase tracking-widest mb-2 mt-3">Fields</p><div id="col3-fields" class="flex flex-col gap-1.5"></div></div>
                                    <p id="col3-empty" class="text-slate-700 text-[11px] italic text-center py-4">Nothing selected yet...</p>
                                </div>
                            </div>
                        </div>

                        <!-- Form footer -->
                        <div class="flex items-center justify-between mt-6 pt-5 border-t border-white/[0.05]">
                            <p class="text-slate-600 text-[10px] flex items-center gap-1.5"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>Secure &amp; private. No spam, ever.</p>
                            <button type="submit" id="modal-submit-btn" class="group relative flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-pink-600 text-white font-semibold text-xs tracking-widest uppercase hover:opacity-90 hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 shadow-[0_4px_16px_rgba(139,92,246,0.35)] disabled:opacity-40 disabled:cursor-not-allowed overflow-hidden">
                                <span class="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-500 pointer-events-none"></span>
                                <svg class="relative w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
                                <span id="modal-btn-text" class="relative">Join Waitlist</span>
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <!-- ══════════ CONTACT US MODAL ══════════ -->
    <div id="contact-modal" class="fixed inset-0 z-[9999] hidden items-center justify-center p-4 opacity-0 transition-opacity duration-500">
        <div class="absolute inset-0 bg-black/70 backdrop-blur-lg"></div>
        <!-- Ambient blobs -->
        <div class="absolute inset-0 pointer-events-none overflow-hidden">
            <div class="absolute top-1/3 left-1/5 w-80 h-80 bg-sky-700/15 rounded-full blur-3xl"></div>
            <div class="absolute bottom-1/4 right-1/4 w-72 h-72 bg-indigo-700/12 rounded-full blur-3xl"></div>
        </div>

        <div id="contact-modal-content" class="relative w-full max-w-lg transform-gpu scale-75 opacity-0 transition-all duration-500" style="transform-style:preserve-3d;">
            <div class="relative rounded-2xl overflow-hidden shadow-[0_32px_80px_rgba(0,0,0,0.65),0_0_0_1px_rgba(255,255,255,0.06)]"
                 style="background: linear-gradient(145deg, rgba(15,25,50,0.92) 0%, rgba(10,16,34,0.95) 100%); backdrop-filter: blur(24px);">

                <!-- Accent top line -->
                <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-sky-500 via-cyan-400 to-indigo-500"></div>

                <!-- Close button -->
                <button onclick="closeContactModal()" class="absolute top-4 right-4 z-20 w-8 h-8 flex items-center justify-center rounded-lg bg-white/[0.06] border border-white/[0.1] hover:bg-red-500/60 hover:border-red-400/40 hover:rotate-90 transition-all duration-300">
                    <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>
                </button>

                <!-- Header -->
                <div class="px-7 pt-6 pb-5 border-b border-white/[0.05]">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl flex-shrink-0 bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center shadow-[0_0_18px_rgba(56,189,248,0.35)]">
                            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                        </div>
                        <div>
                            <h3 class="text-white font-bold text-base">Get in Touch</h3>
                            <p class="text-slate-500 text-xs mt-0.5">We'd love to hear from you</p>
                        </div>
                    </div>
                </div>

                <!-- Body -->
                <div class="px-7 py-5 space-y-4">

                    <!-- Form fields -->
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">Full Name *</label>
                            <input type="text" id="contact-name" required placeholder="Your full name"
                                   class="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-white placeholder-slate-600 text-xs focus:outline-none focus:border-sky-400/50 focus:bg-white/[0.07] transition-all duration-200"/>
                        </div>
                        <div>
                            <label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">Phone</label>
                            <input type="tel" id="contact-phone" placeholder="+27 000 000 0000"
                                   class="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-white placeholder-slate-600 text-xs focus:outline-none focus:border-sky-400/50 focus:bg-white/[0.07] transition-all duration-200"/>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">Email *</label>
                            <input type="email" id="contact-email" required placeholder="you@example.com"
                                   class="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-white placeholder-slate-600 text-xs focus:outline-none focus:border-sky-400/50 focus:bg-white/[0.07] transition-all duration-200"/>
                        </div>
                        <div>
                            <label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">Country</label>
                            <select id="contact-country"
                                    class="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-slate-400 text-xs focus:outline-none focus:border-sky-400/50 transition-all duration-200 [&>option]:bg-[#0d1424] [&>option]:text-white">
                                <option value="">Select country</option>
                                <option>Nigeria</option><option>Kenya</option><option>South Africa</option><option>Ghana</option><option>Egypt</option><option>Ethiopia</option><option>Tanzania</option><option>Uganda</option><option>Rwanda</option><option>Other</option>
                            </select>
                        </div>
                    </div>

                    <div>
                        <label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">Message *</label>
                        <textarea id="contact-message" required rows="3" placeholder="How can we help you?"
                                  class="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-white placeholder-slate-600 text-xs focus:outline-none focus:border-sky-400/50 focus:bg-white/[0.07] transition-all duration-200 resize-none hide-scroll"></textarea>
                    </div>

                    <!-- Divider -->
                    <div class="flex items-center gap-3 pt-1">
                        <div class="flex-1 h-px bg-white/[0.05]"></div>
                        <span class="text-slate-600 text-[10px] font-semibold uppercase tracking-widest">Reach us via</span>
                        <div class="flex-1 h-px bg-white/[0.05]"></div>
                    </div>

                    <!-- 4 Action Buttons — 2x2 grid -->
                    <div class="grid grid-cols-2 gap-2.5">

                        <!-- WhatsApp -->
                        <button type="button" onclick="contactViaWhatsApp()"
                                class="group relative flex items-center gap-2.5 px-4 py-3 rounded-xl
                                       bg-emerald-500/[0.06] border border-emerald-400/[0.12]
                                       hover:bg-emerald-500/[0.14] hover:border-emerald-400/[0.3]
                                       hover:-translate-y-0.5 active:translate-y-0
                                       transition-all duration-250 overflow-hidden"
                                style="backdrop-filter:blur(8px);">
                            <div class="absolute inset-0 bg-gradient-to-br from-emerald-500/[0.04] to-transparent pointer-events-none"></div>
                            <div class="relative w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-400/20 flex items-center justify-center flex-shrink-0 group-hover:shadow-[0_0_12px_rgba(16,185,129,0.25)] transition-shadow duration-300">
                                <svg class="w-4 h-4 text-emerald-400" fill="currentColor" viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
                            </div>
                            <div class="relative">
                                <span class="block text-emerald-300/90 text-xs font-semibold">WhatsApp</span>
                                <span class="block text-slate-600 text-[10px]">Chat with us</span>
                            </div>
                        </button>

                        <!-- Email -->
                        <button type="button" onclick="contactViaEmail()"
                                class="group relative flex items-center gap-2.5 px-4 py-3 rounded-xl
                                       bg-sky-500/[0.06] border border-sky-400/[0.12]
                                       hover:bg-sky-500/[0.14] hover:border-sky-400/[0.3]
                                       hover:-translate-y-0.5 active:translate-y-0
                                       transition-all duration-250 overflow-hidden"
                                style="backdrop-filter:blur(8px);">
                            <div class="absolute inset-0 bg-gradient-to-br from-sky-500/[0.04] to-transparent pointer-events-none"></div>
                            <div class="relative w-8 h-8 rounded-lg bg-sky-500/15 border border-sky-400/20 flex items-center justify-center flex-shrink-0 group-hover:shadow-[0_0_12px_rgba(14,165,233,0.25)] transition-shadow duration-300">
                                <svg class="w-4 h-4 text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                            </div>
                            <div class="relative">
                                <span class="block text-sky-300/90 text-xs font-semibold">Email</span>
                                <span class="block text-slate-600 text-[10px]">Send an email</span>
                            </div>
                        </button>

                        <!-- Call -->
                        <button type="button" onclick="contactViaCall()"
                                class="group relative flex items-center gap-2.5 px-4 py-3 rounded-xl
                                       bg-violet-500/[0.06] border border-violet-400/[0.12]
                                       hover:bg-violet-500/[0.14] hover:border-violet-400/[0.3]
                                       hover:-translate-y-0.5 active:translate-y-0
                                       transition-all duration-250 overflow-hidden"
                                style="backdrop-filter:blur(8px);">
                            <div class="absolute inset-0 bg-gradient-to-br from-violet-500/[0.04] to-transparent pointer-events-none"></div>
                            <div class="relative w-8 h-8 rounded-lg bg-violet-500/15 border border-violet-400/20 flex items-center justify-center flex-shrink-0 group-hover:shadow-[0_0_12px_rgba(139,92,246,0.25)] transition-shadow duration-300">
                                <svg class="w-4 h-4 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>
                            </div>
                            <div class="relative">
                                <span class="block text-violet-300/90 text-xs font-semibold">Call</span>
                                <span class="block text-slate-600 text-[10px]">Speak directly</span>
                            </div>
                        </button>

                        <!-- Direct Message -->
                        <button type="button" onclick="contactViaDirectMessage()"
                                class="group relative flex items-center gap-2.5 px-4 py-3 rounded-xl
                                       bg-amber-500/[0.06] border border-amber-400/[0.12]
                                       hover:bg-amber-500/[0.14] hover:border-amber-400/[0.3]
                                       hover:-translate-y-0.5 active:translate-y-0
                                       transition-all duration-250 overflow-hidden"
                                style="backdrop-filter:blur(8px);">
                            <div class="absolute inset-0 bg-gradient-to-br from-amber-500/[0.04] to-transparent pointer-events-none"></div>
                            <div class="relative w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-400/20 flex items-center justify-center flex-shrink-0 group-hover:shadow-[0_0_12px_rgba(245,158,11,0.25)] transition-shadow duration-300">
                                <svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg>
                            </div>
                            <div class="relative">
                                <span class="block text-amber-300/90 text-xs font-semibold">Direct Message</span>
                                <span class="block text-slate-600 text-[10px]">Send instantly</span>
                            </div>
                        </button>
                    </div>
                </div>

                <!-- Footer -->
                <div class="px-7 py-3 border-t border-white/[0.04]">
                    <p class="text-slate-700 text-[10px] flex items-center justify-center gap-1.5">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
                        Your information is secure and private
                    </p>
                </div>
            </div>

            <!-- Success overlay (shown after direct message) -->
            <div id="contact-success" class="absolute inset-0 z-30 hidden items-center justify-center rounded-2xl"
                 style="background: rgba(10,16,30,0.95); backdrop-filter: blur(20px);">
                <div class="text-center px-6">
                    <div class="w-12 h-12 mx-auto mb-4 rounded-full bg-sky-500/10 border border-sky-400/20 flex items-center justify-center">
                        <svg class="w-6 h-6 text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                    </div>
                    <h3 class="font-semibold text-base text-white mb-1.5">Message Sent</h3>
                    <p class="text-slate-400 text-xs max-w-xs mx-auto leading-relaxed mb-1">Thank you for reaching out.</p>
                    <p class="text-slate-600 text-[11px]">Our team will get back to you shortly.</p>
                    <button onclick="closeContactModal()" class="mt-4 px-4 py-1.5 rounded-lg bg-white/[0.05] border border-white/[0.08] text-slate-400 text-[11px] font-medium hover:bg-white/[0.1] hover:text-white transition-all">Close</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ══════════ ALL JS — INLINE ══════════ -->
    <script>
    /* ================================================================
       WAITLIST MODAL  (inlined from waitlist-modal.js)
       ================================================================ */
    (function() {
        'use strict';
        const modal = document.getElementById('waitlist-modal');
        const modalContent = document.getElementById('modal-content');
        const modalForm = document.getElementById('modal-waitlist-form');
        const modalSuccessMessage = document.getElementById('modal-success-message');
        const modalSubmitBtn = document.getElementById('modal-submit-btn');
        const modalBtnText = document.getElementById('modal-btn-text');

        // ── Col-3 helpers ─────────────────────────
        function col3Update() {
            const col3=document.getElementById('modal-col-3'), grid=document.getElementById('modal-grid'), div23=document.getElementById('divider-23'), empty=document.getElementById('col3-empty'), skillWrap=document.getElementById('col3-skills-wrap'), fieldWrap=document.getElementById('col3-fields-wrap'), skillList=document.getElementById('col3-skills'), fieldList=document.getElementById('col3-fields');
            if(!col3||!grid) return;
            const hasSkills=skillList&&skillList.children.length>0, hasFields=fieldList&&fieldList.children.length>0, hasAny=hasSkills||hasFields;
            col3.style.display=hasAny?'block':'none';
            grid.style.gridTemplateColumns=hasAny?'repeat(3,minmax(0,1fr))':'repeat(2,minmax(0,1fr))';
            if(div23) div23.style.display=hasAny?'block':'none';
            if(skillWrap) skillWrap.style.display=hasSkills?'block':'none';
            if(fieldWrap) fieldWrap.style.display=hasFields?'block':'none';
            if(empty) empty.style.display=hasAny?'none':'block';
        }
        function col3AddTag(listId,val,label,accent,onRemove){
            const list=document.getElementById(listId); if(!list) return;
            const tag=document.createElement('div');
            tag.id='col3-tag-'+listId+'-'+val.replace(/\s+/g,'_');
            tag.className='flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all duration-150';
            tag.style.cssText='background:'+accent+'22;border:1px solid '+accent+'55;color:'+accent+';';
            tag.innerHTML='<span class="col3-tag-label leading-none truncate">'+label+'</span><button type="button" class="flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center opacity-60 hover:opacity-100 transition-opacity" style="background:'+accent+'33;" data-remove="'+val+'"><svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M6 18L18 6M6 6l12 12"/></svg></button>';
            tag.querySelector('[data-remove]').addEventListener('click',()=>onRemove(val));
            list.appendChild(tag); col3Update();
        }
        function col3RemoveTag(listId,val){
            const tag=document.getElementById('col3-tag-'+listId+'-'+val.replace(/\s+/g,'_'));
            if(tag) tag.remove(); col3Update();
        }

        // ── Opp pills ────────────────────────────
        function initOppPills(){
            document.querySelectorAll('.opp-pill').forEach(div=>{
                const input=div.previousElementSibling; if(!input) return;
                const ac='opp-active-'+input.value;
                div.addEventListener('click',(e)=>{ e.preventDefault(); input.checked=!input.checked; input.checked?div.classList.add(ac):div.classList.remove(ac); });
            });
        }

        // ── Skill / Field pill toggle ────────────
        function initPills(sel,hiddenId,inputName,activeClass,counterId,col3ListId,accent,otherWrapId,otherInputId){
            const pills=document.querySelectorAll(sel), container=document.getElementById(hiddenId);
            const counter=counterId?document.getElementById(counterId):null;
            const otherWrap=otherWrapId?document.getElementById(otherWrapId):null;
            const otherInput=otherInputId?document.getElementById(otherInputId):null;
            if(!pills.length||!container) return;
            function updateCounter(){ if(!counter) return; const n=container.querySelectorAll('input').length; counter.textContent=n+' selected'; counter.style.display=n>0?'inline':'none'; }
            if(otherInput){ otherInput.addEventListener('input',()=>{ const typed=otherInput.value.trim()||'Other'; const h=container.querySelector('input[data-other="1"]'); if(h) h.value=typed; const tl=document.querySelector('#col3-tag-'+col3ListId+'-Other .col3-tag-label'); if(tl) tl.textContent=typed; }); }
            function deselect(val){
                const isO=val.toLowerCase()==='other';
                pills.forEach(p=>{ if((p.dataset.skill||p.dataset.field)===val) p.classList.remove('active-pill'); });
                if(isO){ const h=container.querySelector('input[data-other="1"]'); if(h) h.remove(); if(otherWrap) otherWrap.style.display='none'; if(otherInput) otherInput.value=''; } else { const h=container.querySelector('input[value="'+val+'"]'); if(h) h.remove(); }
                col3RemoveTag(col3ListId,val); updateCounter();
            }
            pills.forEach(pill=>{
                pill.addEventListener('click',()=>{
                    const val=pill.dataset.skill||pill.dataset.field, label=pill.textContent.trim(), isO=val.toLowerCase()==='other';
                    if(pill.classList.contains('active-pill')){ deselect(val); } else {
                        pill.classList.add('active-pill');
                        if(isO){ if(otherWrap){otherWrap.style.display='block'; if(otherInput) setTimeout(()=>otherInput.focus(),50);} const inp=document.createElement('input'); inp.type='hidden'; inp.name=inputName; inp.value='Other'; inp.setAttribute('data-other','1'); container.appendChild(inp); }
                        else { const inp=document.createElement('input'); inp.type='hidden'; inp.name=inputName; inp.value=val; container.appendChild(inp); }
                        col3AddTag(col3ListId,val,label,accent,(rv)=>deselect(rv)); updateCounter();
                    }
                });
            });
        }

        // ── Open / Close ─────────────────────────
        window.openWaitlistModal=function(){
            modal.classList.remove('hidden'); modal.classList.add('flex');
            if(!modal.dataset.pillsInit){ initOppPills(); initPills('.skill-pill','skills-hidden-inputs','skills','active-pill','skills-count','col3-skills','#a78bfa','skill-other-wrap','skill-other-input'); initPills('.field-pill','fields-hidden-inputs','preferred_field','active-pill','fields-count','col3-fields','#f472b6','field-other-wrap','field-other-input'); modal.dataset.pillsInit='1'; }
            setTimeout(()=>{ modal.classList.remove('opacity-0'); modalContent.classList.remove('scale-75','opacity-0'); modalContent.classList.add('scale-100','opacity-100'); },10);
            document.body.style.overflow='hidden';
        };
        window.closeWaitlistModal=function(){
            modalContent.classList.remove('scale-100','opacity-100'); modalContent.classList.add('scale-75','opacity-0'); modal.classList.add('opacity-0');
            setTimeout(()=>{
                modal.classList.add('hidden'); modal.classList.remove('flex');
                if(modalForm){ modalForm.reset(); modalForm.classList.remove('hidden'); if(modalSuccessMessage) modalSuccessMessage.classList.add('hidden');
                    document.querySelectorAll('.skill-pill.active-pill,.field-pill.active-pill').forEach(p=>p.classList.remove('active-pill'));
                    document.querySelectorAll('.opp-pill').forEach(div=>{ const inp=div.previousElementSibling; if(inp) inp.checked=false; div.classList.remove('opp-active-volunteer','opp-active-internship','opp-active-job','opp-active-skillup'); });
                    ['col3-skills','col3-fields'].forEach(id=>{ const el=document.getElementById(id); if(el) el.innerHTML=''; });
                    const c3=document.getElementById('modal-col-3'),gr=document.getElementById('modal-grid'),d23=document.getElementById('divider-23');
                    if(c3) c3.style.display='none'; if(gr) gr.style.gridTemplateColumns='repeat(2,minmax(0,1fr))'; if(d23) d23.style.display='none';
                    ['col3-skills-wrap','col3-fields-wrap'].forEach(id=>{ const el=document.getElementById(id); if(el) el.style.display='none'; });
                    const emp=document.getElementById('col3-empty'); if(emp) emp.style.display='block';
                    ['skills-hidden-inputs','fields-hidden-inputs'].forEach(id=>{ const el=document.getElementById(id); if(el) el.innerHTML=''; });
                    ['skills-count','fields-count'].forEach(id=>{ const el=document.getElementById(id); if(el) el.style.display='none'; });
                }
            },500);
            document.body.style.overflow='';
        };

        // ── Form submit ──────────────────────────
        document.addEventListener('DOMContentLoaded',function(){
            document.querySelectorAll('a[href*="waitlist"],a[href*="#waitlist"]').forEach(link=>{ link.addEventListener('click',function(e){ e.preventDefault(); openWaitlistModal(); }); });
            if(modalForm){ modalForm.addEventListener('submit',async function(e){
                e.preventDefault();
                const oppCbs=modalForm.querySelectorAll('input[name="opportunity_type"]:checked');
                if(!oppCbs.length){ ffToast('Please select at least one opportunity type','error'); return; }
                const skillInputs=document.querySelectorAll('#skills-hidden-inputs input');
                const fieldInputs=document.querySelectorAll('#fields-hidden-inputs input');
                if(!skillInputs.length){ ffToast('Please select at least one skill','error'); return; }
                if(!fieldInputs.length){ ffToast('Please select at least one preferred field','error'); return; }
                modalSubmitBtn.disabled=true; modalBtnText.textContent='Processing...'; modalSubmitBtn.classList.add('opacity-75','cursor-not-allowed');
                const fd=new FormData(modalForm), data={};
                const ot=[]; oppCbs.forEach(cb=>ot.push(cb.value)); data.opportunity_types=ot;
                const sk=[]; skillInputs.forEach(i=>sk.push(i.value)); data.skills=sk.join(', ');
                const fl=[]; fieldInputs.forEach(i=>fl.push(i.value)); data.preferred_field=fl.join(', ');
                for(let[k,v]of fd.entries()){ if(!['opportunity_type','skills','preferred_field'].includes(k)) data[k]=v; }
                data.user_type='talent';
                try{
                    // POST to self (?action=waitlist) — fully standalone
                    const baseUrl=window.location.href.split('?')[0].split('#')[0];
                    const res=await fetch(baseUrl+'?action=waitlist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
                    const result=await res.json();
                    if(res.ok){ modalForm.reset(); modalForm.classList.add('hidden'); modalSuccessMessage.classList.remove('hidden'); createConfetti(); setTimeout(()=>closeWaitlistModal(),8000); }
                    else throw new Error(result.detail||'Something went wrong');
                }catch(err){ console.error(err); ffToast(err.message||'Something went wrong','error'); modalSubmitBtn.disabled=false; modalBtnText.textContent='Join Waitlist'; modalSubmitBtn.classList.remove('opacity-75','cursor-not-allowed'); }
            }); }
        });

        // ── Confetti ─────────────────────────────
        function createConfetti(){
            const colors=['#9333ea','#ec4899','#f59e0b','#10b981','#3b82f6'];
            for(let i=0;i<50;i++){ setTimeout(()=>{
                const c=document.createElement('div');
                c.style.cssText='position:fixed;left:'+Math.random()*100+'%;top:-10px;width:'+(Math.random()*10+5)+'px;height:'+(Math.random()*10+5)+'px;background:'+colors[Math.floor(Math.random()*colors.length)]+';opacity:'+(Math.random()+0.5)+';z-index:10000;pointer-events:none;border-radius:'+(Math.random()>.5?'50%':'0')+';transform:rotate('+Math.random()*360+'deg)';
                document.body.appendChild(c);
                c.animate([{transform:'translate(0,0) rotate(0deg)',opacity:1},{transform:'translate('+(Math.random()*200-100)+'px,'+(window.innerHeight+20)+'px) rotate('+Math.random()*720+'deg)',opacity:0}],{duration:Math.random()*2000+2000,easing:'cubic-bezier(0.25,0.46,0.45,0.94)'}).onfinish=()=>c.remove();
            },i*30); }
        }

        // ── 3D tilt ──────────────────────────────
        if(modalContent){
            modalContent.addEventListener('mousemove',function(e){ const r=this.getBoundingClientRect(); this.style.transform='perspective(1000px) rotateX('+((e.clientY-r.top)-r.height/2)/50+'deg) rotateY('+(r.width/2-(e.clientX-r.left))/50+'deg)'; });
            modalContent.addEventListener('mouseleave',function(){ this.style.transform='perspective(1000px) rotateX(0deg) rotateY(0deg)'; });
        }
    })();

    /* ================================================================
       CONTACT MODAL
       ================================================================ */
    (function(){
        'use strict';
        const modal = document.getElementById('contact-modal');
        const content = document.getElementById('contact-modal-content');
        const success = document.getElementById('contact-success');

        function getFormData(){
            return {
                name: (document.getElementById('contact-name').value||'').trim(),
                phone: (document.getElementById('contact-phone').value||'').trim(),
                email: (document.getElementById('contact-email').value||'').trim(),
                country: (document.getElementById('contact-country').value||'').trim(),
                message: (document.getElementById('contact-message').value||'').trim()
            };
        }

        function validate(requireMessage){
            const d = getFormData();
            if(!d.name){ alert('Please enter your name.'); return null; }
            if(!d.email){ alert('Please enter your email.'); return null; }
            if(requireMessage && !d.message){ alert('Please enter a message.'); return null; }
            return d;
        }

        function getTimestamp(){
            return new Date().toLocaleString('en-ZA', { dateStyle:'medium', timeStyle:'short', timeZone:'Africa/Johannesburg' });
        }

        // Open / Close
        window.openContactModal = function(){
            modal.classList.remove('hidden'); modal.classList.add('flex');
            setTimeout(function(){
                modal.classList.remove('opacity-0');
                content.classList.remove('scale-75','opacity-0');
                content.classList.add('scale-100','opacity-100');
            }, 10);
            document.body.style.overflow = 'hidden';
        };

        window.closeContactModal = function(){
            content.classList.remove('scale-100','opacity-100');
            content.classList.add('scale-75','opacity-0');
            modal.classList.add('opacity-0');
            setTimeout(function(){
                modal.classList.add('hidden'); modal.classList.remove('flex');
                // Reset
                document.getElementById('contact-name').value = '';
                document.getElementById('contact-phone').value = '';
                document.getElementById('contact-email').value = '';
                document.getElementById('contact-country').value = '';
                document.getElementById('contact-message').value = '';
                if(success){ success.classList.add('hidden'); success.classList.remove('flex'); }
            }, 500);
            document.body.style.overflow = '';
        };

        // WhatsApp
        window.contactViaWhatsApp = function(){
            var d = validate(true); if(!d) return;
            var ts = getTimestamp();
            var text = 'Hello, my name is ' + d.name + '\n' + d.message + '\n' + ts;
            var url = 'https://wa.me/27692973425?text=' + encodeURIComponent(text);
            window.open(url, '_blank');
        };

        // Email
        window.contactViaEmail = function(){
            var d = validate(true); if(!d) return;
            var subject = 'Enquiry from ' + d.name + ' - ForgeForth Africa';
            var body = 'Hello ForgeForth Africa,\n\n' + d.message + '\n\nName: ' + d.name + '\nEmail: ' + d.email + (d.phone ? '\nPhone: ' + d.phone : '') + (d.country ? '\nCountry: ' + d.country : '') + '\nSent: ' + getTimestamp();
            var mailto = 'mailto:contact@forgeforthafrica.com?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
            window.location.href = mailto;
        };

        // Call
        window.contactViaCall = function(){
            window.location.href = 'tel:+27692973425';
        };

        // Direct Message
        window.contactViaDirectMessage = function(){
            var d = validate(true); if(!d) return;
            var btn = document.querySelector('[onclick="contactViaDirectMessage()"]');
            if(btn){
                btn.style.opacity = '0.5';
                btn.style.pointerEvents = 'none';
            }
            var payload = {
                name: d.name,
                email: d.email,
                phone: d.phone,
                country: d.country,
                message: d.message,
                channel: 'direct'
            };
            // Build URL relative to current script (handles both /index.php and / paths)
            var baseUrl = window.location.href.split('?')[0].split('#')[0];
            fetch(baseUrl + '?action=contact', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(function(r){
                if(!r.ok) return r.json().then(function(e){ throw new Error(e.detail || 'Server error'); });
                return r.json();
            })
            .then(function(data){
                // Auto-empty the form immediately on success
                document.getElementById('contact-name').value = '';
                document.getElementById('contact-phone').value = '';
                document.getElementById('contact-email').value = '';
                document.getElementById('contact-country').value = '';
                document.getElementById('contact-message').value = '';
                if(success){
                    success.classList.remove('hidden');
                    success.classList.add('flex');
                }
                setTimeout(function(){ closeContactModal(); }, 6000);
            })
            .catch(function(err){
                console.error('Contact save error:', err);
                ffToast('Failed to send message', 'error');
            })
            .finally(function(){
                if(btn){ btn.style.opacity = ''; btn.style.pointerEvents = ''; }
            });
        };

        // 3D tilt
        if(content){
            content.addEventListener('mousemove', function(e){
                var r = this.getBoundingClientRect();
                var rotX = ((e.clientY - r.top) - r.height/2) / 80;
                var rotY = (r.width/2 - (e.clientX - r.left)) / 80;
                this.style.transform = 'perspective(1200px) rotateX(' + rotX + 'deg) rotateY(' + rotY + 'deg)';
            });
            content.addEventListener('mouseleave', function(){
                this.style.transform = 'perspective(1200px) rotateX(0deg) rotateY(0deg)';
            });
        }
    })();

    /* ================================================================
       ANIMATED MESH BACKGROUND
       ================================================================ */
    (function(){
        const canvas=document.getElementById('mesh-canvas'), ctx=canvas.getContext('2d');
        let w,h,dots=[]; const N=70, MD=160;
        function resize(){ w=canvas.width=window.innerWidth; h=canvas.height=window.innerHeight; }
        window.addEventListener('resize',resize); resize();
        for(let i=0;i<N;i++) dots.push({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-0.5)*0.35,vy:(Math.random()-0.5)*0.35,r:Math.random()*1.5+0.5});
        function draw(){
            ctx.clearRect(0,0,w,h);
            for(const d of dots){ d.x+=d.vx; d.y+=d.vy; if(d.x<0||d.x>w) d.vx*=-1; if(d.y<0||d.y>h) d.vy*=-1; }
            for(let i=0;i<dots.length;i++) for(let j=i+1;j<dots.length;j++){ const dx=dots[i].x-dots[j].x,dy=dots[i].y-dots[j].y,dist=Math.sqrt(dx*dx+dy*dy); if(dist<MD){ ctx.strokeStyle='rgba(56,189,248,'+(1-dist/MD)*0.15+')'; ctx.lineWidth=0.5; ctx.beginPath(); ctx.moveTo(dots[i].x,dots[i].y); ctx.lineTo(dots[j].x,dots[j].y); ctx.stroke(); } }
            for(const d of dots){ ctx.fillStyle='rgba(148,163,184,0.25)'; ctx.beginPath(); ctx.arc(d.x,d.y,d.r,0,Math.PI*2); ctx.fill(); }
            requestAnimationFrame(draw);
        }
        draw();
    })();

    /* ================================================================
       COUNTER ANIMATION
       ================================================================ */
    document.querySelectorAll('[data-count]').forEach(el=>{
        const target=parseInt(el.dataset.count,10); let cur=0; const step=Math.ceil(target/40);
        const iv=setInterval(()=>{ cur+=step; if(cur>=target){cur=target;clearInterval(iv);} el.textContent=cur; },35);
    });

    /* ================================================================
       SILENT HEALTH CHECK  (polls self → ?action=health)
       ================================================================ */
    (function(){
        let redirecting=false;
        function check(){
            if(redirecting) return;
            fetch(window.location.href.split('?')[0].split('#')[0]+'?action=health',{method:'GET',cache:'no-cache',headers:{'Cache-Control':'no-cache'}})
                .then(r=>{ if(r.ok) return r.json(); throw 0; })
                .then(d=>{ if(d&&d.status==='healthy'){ redirecting=true; document.body.style.transition='opacity 0.6s ease-out'; document.body.style.opacity='0'; setTimeout(()=>{window.location.href='/';},600); } })
                .catch(()=>{});
        }
        check(); setInterval(check,3000);
    })();
    </script>

    <!-- Global Toast Notification -->
    <div id="ff-toast" class="fixed bottom-5 left-1/2 -translate-x-1/2 z-[99999] hidden pointer-events-none">
        <div id="ff-toast-inner" class="flex items-center gap-2.5 px-4 py-2.5 rounded-xl shadow-[0_8px_32px_rgba(0,0,0,0.5)] border border-white/[0.07] translate-y-4 opacity-0 transition-all duration-300"
             style="background:rgba(10,16,30,0.92);backdrop-filter:blur(16px)">
            <div id="ff-toast-icon" class="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"></div>
            <p id="ff-toast-text" class="text-[11px] font-medium"></p>
        </div>
    </div>
    <script>
    function ffToast(msg,type){
        var t=document.getElementById('ff-toast'),i=document.getElementById('ff-toast-inner'),
            ic=document.getElementById('ff-toast-icon'),tx=document.getElementById('ff-toast-text');
        var c={
            success:{bg:'bg-emerald-500/15 border border-emerald-400/20',tx:'text-emerald-400',sv:'<svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>'},
            error:{bg:'bg-red-500/15 border border-red-400/20',tx:'text-red-400',sv:'<svg class="w-3.5 h-3.5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>'}
        };
        var s=c[type]||c.success;
        ic.className='w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 '+s.bg;
        ic.innerHTML=s.sv; tx.className='text-[11px] font-medium '+s.tx; tx.textContent=msg;
        t.classList.remove('hidden');
        setTimeout(function(){i.classList.remove('translate-y-4','opacity-0');},10);
        setTimeout(function(){i.classList.add('translate-y-4','opacity-0');setTimeout(function(){t.classList.add('hidden');},300);},4000);
    }
    </script>
</body>
</html>

