<?php
/**
 * ForgeForth Africa — Admin Dashboard
 * ====================================
 * Standalone PHP file to view all messages and registrations.
 * Reads from the same SQLite databases as index.php.
 *
 * Route: /view
 *
 * Features:
 *   - View all early-access registrations
 *   - View all contact messages
 *   - Export to PDF or Excel (CSV)
 *   - Mark messages as read
 *   - Delete records
 *   - Basic auth protection
 *   - Same dark glassmorphic theme
 */

session_start();

// ─── No caching ──────────────────────────────────────
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');

// ─── Base dir (parent of /view) ──────────────────────
$base_dir = dirname(__DIR__);

// ─── Config ──────────────────────────────────────────
$config_file = $base_dir . '/config.json';
$config = file_exists($config_file)
    ? (json_decode(file_get_contents($config_file), true) ?: [])
    : [];

// ─── Database path ───────────────────────────────────
$db_dir = $base_dir . '/data';
if (!is_dir($db_dir)) {
    mkdir($db_dir, 0755, true);
}

// ─── Database helpers ────────────────────────────────
function get_earlyaccess_db() {
    global $db_dir;
    $db_path = $db_dir . '/earlyaccess.db';
    if (!file_exists($db_path)) return null;
    $db = new SQLite3($db_path);
    $db->busyTimeout(5000);
    $db->exec('PRAGMA journal_mode=WAL');
    return $db;
}

function get_messages_db() {
    global $db_dir;
    $db_path = $db_dir . '/messages.db';
    $db = new SQLite3($db_path);
    $db->busyTimeout(5000);
    $db->exec('PRAGMA journal_mode=WAL');
    $db->exec('PRAGMA foreign_keys=ON');

    // Ensure messages table exists
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

function clean($value) {
    if (!is_string($value)) return '';
    return trim(strip_tags($value));
}

/**
 * Authenticate user against the users table in messages.db.
 * Returns the user row array on success, or false on failure.
 */
function authenticate_user($username, $password) {
    $db = get_messages_db();
    if (!$db) return false;

    $stmt = $db->prepare('SELECT * FROM users WHERE username = :u AND is_active = 1');
    $stmt->bindValue(':u', trim($username), SQLITE3_TEXT);
    $result = $stmt->execute();
    $user = $result->fetchArray(SQLITE3_ASSOC);

    if (!$user) {
        $db->close();
        return false;
    }

    if (!password_verify($password, $user['password_hash'])) {
        $db->close();
        return false;
    }

    // Update last_login timestamp
    $db->exec("UPDATE users SET last_login = datetime('now') WHERE id = " . (int)$user['id']);
    $db->close();

    return $user;
}

// ─── Auth check ──────────────────────────────────────
$is_logged_in = isset($_SESSION['ff_admin_auth']) && $_SESSION['ff_admin_auth'] === true
                && isset($_SESSION['ff_admin_user']);

// Handle login
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action']) && $_POST['action'] === 'login') {
    $user = isset($_POST['username']) ? trim($_POST['username']) : '';
    $pass = isset($_POST['password']) ? $_POST['password'] : '';

    $auth_user = authenticate_user($user, $pass);
    if ($auth_user) {
        $_SESSION['ff_admin_auth'] = true;
        $_SESSION['ff_admin_user'] = $auth_user['username'];
        $_SESSION['ff_admin_name'] = $auth_user['display_name'] ?: $auth_user['username'];
        $_SESSION['ff_admin_role'] = $auth_user['role'];
        $is_logged_in = true;
    } else {
        $login_error = 'Invalid username or password';
    }
}

// Handle logout
if (isset($_GET['action']) && $_GET['action'] === 'logout') {
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $p = session_get_cookie_params();
        setcookie(session_name(), '', time() - 42000, $p['path'], $p['domain'], $p['secure'], $p['httponly']);
    }
    session_destroy();
    header('Location: /view');
    exit;
}

// ─── API Actions (require auth) ──────────────────────
if ($is_logged_in) {

    // Export registrations as CSV
    if (isset($_GET['export']) && $_GET['export'] === 'registrations_csv') {
        $db = get_earlyaccess_db();
        if ($db) {
            header('Content-Type: text/csv; charset=utf-8');
            header('Content-Disposition: attachment; filename=forgeforth_registrations_' . date('Y-m-d_His') . '.csv');
            $out = fopen('php://output', 'w');
            fputcsv($out, ['ID', 'First Name', 'Last Name', 'Email', 'Phone', 'Country', 'Type', 'Opportunities', 'Skills', 'Preferred Field', 'Referral', 'Registered At', 'Confirmed', 'IP Address']);
            $results = $db->query('SELECT * FROM registrants ORDER BY created_at DESC');
            while ($row = $results->fetchArray(SQLITE3_ASSOC)) {
                fputcsv($out, [
                    $row['id'], $row['first_name'], $row['last_name'], $row['email'],
                    $row['phone'], $row['country'], $row['user_type'], $row['opportunity_types'],
                    $row['skills'], $row['preferred_field'], $row['referral_source'],
                    $row['created_at'], $row['is_confirmed'] ? 'Yes' : 'No', $row['ip_address']
                ]);
            }
            fclose($out);
            $db->close();
        }
        exit;
    }

    // Export messages as CSV
    if (isset($_GET['export']) && $_GET['export'] === 'messages_csv') {
        $db = get_messages_db();
        if ($db) {
            header('Content-Type: text/csv; charset=utf-8');
            header('Content-Disposition: attachment; filename=forgeforth_messages_' . date('Y-m-d_His') . '.csv');
            $out = fopen('php://output', 'w');
            fputcsv($out, ['ID', 'Full Name', 'Email', 'Phone', 'Country', 'Message', 'Channel', 'Sent At', 'Read', 'Replied', 'IP Address']);
            $results = $db->query('SELECT * FROM messages ORDER BY created_at DESC');
            while ($row = $results->fetchArray(SQLITE3_ASSOC)) {
                fputcsv($out, [
                    $row['id'], $row['full_name'], $row['email'], $row['phone'],
                    $row['country'], $row['message'], $row['channel'],
                    $row['created_at'], $row['is_read'] ? 'Yes' : 'No',
                    $row['is_replied'] ? 'Yes' : 'No', $row['ip_address']
                ]);
            }
            fclose($out);
            $db->close();
        }
        exit;
    }

    // AJAX: Toggle read status
    if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_GET['api']) && $_GET['api'] === 'toggle_read') {
        header('Content-Type: application/json');
        $body = json_decode(file_get_contents('php://input'), true);
        $id = isset($body['id']) ? (int)$body['id'] : 0;
        if ($id > 0) {
            $db = get_messages_db();
            if ($db) {
                $db->exec('UPDATE messages SET is_read = CASE WHEN is_read = 1 THEN 0 ELSE 1 END WHERE id = ' . $id);
                $db->close();
                echo json_encode(['status' => 'ok']);
                exit;
            }
        }
        http_response_code(400);
        echo json_encode(['detail' => 'Invalid request']);
        exit;
    }

    // AJAX: Delete registration
    if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_GET['api']) && $_GET['api'] === 'delete_registration') {
        header('Content-Type: application/json');
        $body = json_decode(file_get_contents('php://input'), true);
        $id = isset($body['id']) ? (int)$body['id'] : 0;
        if ($id > 0) {
            $db = get_earlyaccess_db();
            if ($db) {
                $db->exec('DELETE FROM registrants WHERE id = ' . $id);
                $db->close();
                echo json_encode(['status' => 'ok']);
                exit;
            }
        }
        http_response_code(400);
        echo json_encode(['detail' => 'Invalid request']);
        exit;
    }

    // AJAX: Delete message
    if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_GET['api']) && $_GET['api'] === 'delete_message') {
        header('Content-Type: application/json');
        $body = json_decode(file_get_contents('php://input'), true);
        $id = isset($body['id']) ? (int)$body['id'] : 0;
        if ($id > 0) {
            $db = get_messages_db();
            if ($db) {
                $db->exec('DELETE FROM messages WHERE id = ' . $id);
                $db->close();
                echo json_encode(['status' => 'ok']);
                exit;
            }
        }
        http_response_code(400);
        echo json_encode(['detail' => 'Invalid request']);
        exit;
    }

    // AJAX: Get stats
    if (isset($_GET['api']) && $_GET['api'] === 'stats') {
        header('Content-Type: application/json');
        $stats = ['registrations' => 0, 'messages' => 0, 'unread' => 0];
        $db = get_earlyaccess_db();
        if ($db) { $stats['registrations'] = (int)$db->querySingle('SELECT COUNT(*) FROM registrants'); $db->close(); }
        $db = get_messages_db();
        if ($db) {
            $stats['messages'] = (int)$db->querySingle('SELECT COUNT(*) FROM messages');
            $stats['unread'] = (int)$db->querySingle('SELECT COUNT(*) FROM messages WHERE is_read = 0');
            $db->close();
        }
        echo json_encode($stats);
        exit;
    }
}

// ─── Fetch data for page render ──────────────────────
$registrations = [];
$messages = [];
$stats = ['registrations' => 0, 'messages' => 0, 'unread' => 0];

if ($is_logged_in) {
    $db = get_earlyaccess_db();
    if ($db) {
        $results = $db->query('SELECT * FROM registrants ORDER BY created_at DESC');
        while ($row = $results->fetchArray(SQLITE3_ASSOC)) {
            $registrations[] = $row;
        }
        $stats['registrations'] = count($registrations);
        $db->close();
    }

    $db = get_messages_db();
    if ($db) {
        $results = $db->query('SELECT * FROM messages ORDER BY created_at DESC');
        while ($row = $results->fetchArray(SQLITE3_ASSOC)) {
            $messages[] = $row;
        }
        $stats['messages'] = count($messages);
        $stats['unread'] = 0;
        foreach ($messages as $m) { if (!$m['is_read']) $stats['unread']++; }
        $db->close();
    }
}

// ─── Render ──────────────────────────────────────────
header('Content-Type: text/html; charset=UTF-8');
$year = date('Y');
$admin_name = htmlspecialchars($_SESSION['ff_admin_name'] ?? 'Admin');
$admin_role = htmlspecialchars($_SESSION['ff_admin_role'] ?? 'admin');
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard - ForgeForth Africa</title>
    <meta name="robots" content="noindex, nofollow">
    <link rel="icon" type="image/x-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#x1F6E1;</text></svg>">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>tailwind.config={theme:{extend:{fontFamily:{display:['Inter','sans-serif']}}}}</script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js"></script>
    <style>
        *,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Inter',sans-serif;background:#060b16;color:#e2e8f0;min-height:100vh;overflow:hidden}
        .no-scroll::-webkit-scrollbar{display:none} .no-scroll{scrollbar-width:none}
        .glass{background:rgba(10,16,30,0.65);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.05)}
        .row-hover:hover{background:rgba(255,255,255,0.025)}
        .msg-unread{border-left:2px solid #38bdf8} .msg-read{border-left:2px solid transparent;opacity:.65}
        .nav-item{transition:all .2s ease} .nav-item:hover{background:rgba(255,255,255,0.04)}
        .nav-active{background:rgba(56,189,248,0.08)!important;color:#7dd3fc!important;border-right:2px solid #38bdf8}
        @keyframes fade-up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
        .anim{animation:fade-up .4s ease-out forwards}
        @keyframes slide-in{from{transform:translateX(-100%)}to{transform:translateX(0)}}
        .sidebar-open{animation:slide-in .25s ease-out forwards}
    </style>
</head>
<body>

<?php if (!$is_logged_in): ?>
<!-- ══════════════════════════════════════════
     LOGIN
     ══════════════════════════════════════════ -->
<div class="min-h-screen flex items-center justify-center p-4">
    <div class="fixed inset-0 bg-[#060b16]"></div>
    <div class="fixed top-1/4 left-1/3 w-96 h-96 bg-sky-600/[0.03] rounded-full blur-3xl"></div>
    <div class="fixed bottom-1/3 right-1/4 w-80 h-80 bg-indigo-600/[0.04] rounded-full blur-3xl"></div>

    <div class="relative z-10 w-full max-w-sm anim">
        <div class="glass rounded-2xl overflow-hidden shadow-[0_24px_80px_rgba(0,0,0,0.6)]">
            <div class="h-px bg-gradient-to-r from-sky-500 via-cyan-400 to-indigo-500"></div>
            <div class="p-8">
                <div class="flex items-center gap-3 mb-8">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center shadow-[0_0_20px_rgba(56,189,248,0.2)]">
                        <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
                    </div>
                    <div>
                        <h1 class="text-white font-bold text-sm">ForgeForth Africa</h1>
                        <p class="text-slate-500 text-[11px]">Admin Dashboard</p>
                    </div>
                </div>
                <?php if (isset($login_error)): ?>
                <div class="mb-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-400/20 text-red-400 text-xs"><?php echo htmlspecialchars($login_error); ?></div>
                <?php endif; ?>
                <form method="POST" class="space-y-4">
                    <input type="hidden" name="action" value="login">
                    <div>
                        <label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">Username</label>
                        <input type="text" name="username" required autofocus class="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-white placeholder-slate-600 text-xs focus:outline-none focus:border-sky-400/40 transition-all" placeholder="Enter username">
                    </div>
                    <div>
                        <label class="block text-slate-500 text-[10px] font-semibold uppercase tracking-widest mb-1.5">Password</label>
                        <input type="password" name="password" required class="w-full px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.07] text-white placeholder-slate-600 text-xs focus:outline-none focus:border-sky-400/40 transition-all" placeholder="Enter password">
                    </div>
                    <button type="submit" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 text-white text-xs font-semibold tracking-wide uppercase hover:opacity-90 transition-all shadow-[0_4px_16px_rgba(56,189,248,0.2)]">Sign In</button>
                </form>
                <p class="text-center text-slate-700 text-[10px] mt-6">Authorized personnel only</p>
            </div>
        </div>
    </div>
</div>

<?php else: ?>
<!-- ══════════════════════════════════════════
     SIDEBAR + MAIN LAYOUT
     ══════════════════════════════════════════ -->
<div class="flex h-screen overflow-hidden">

    <!-- ─── Mobile overlay ─── -->
    <div id="sidebar-overlay" class="fixed inset-0 bg-black/60 z-40 hidden lg:hidden" onclick="toggleSidebar()"></div>

    <!-- ─── Sidebar ─── -->
    <aside id="sidebar" class="fixed lg:static inset-y-0 left-0 z-50 w-56 flex flex-col border-r border-white/[0.05] -translate-x-full lg:translate-x-0 transition-transform duration-200"
           style="background:rgba(8,12,24,0.95);backdrop-filter:blur(24px)">

        <!-- Brand -->
        <div class="px-5 pt-5 pb-4 border-b border-white/[0.04]">
            <div class="flex items-center gap-2.5">
                <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
                    <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                </div>
                <div class="min-w-0">
                    <p class="text-white font-bold text-xs truncate">ForgeForth Africa</p>
                    <p class="text-slate-600 text-[9px]">Admin Panel</p>
                </div>
            </div>
        </div>

        <!-- Nav -->
        <nav class="flex-1 px-3 py-4 space-y-1 overflow-y-auto no-scroll">
            <p class="px-2 mb-2 text-slate-600 text-[9px] font-semibold uppercase tracking-widest">Data</p>

            <button onclick="switchTab('registrations')" id="nav-registrations"
                    class="nav-item nav-active w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[11px] font-medium text-slate-400">
                <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                <span class="flex-1 text-left">Registrations</span>
                <span class="px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 text-[9px] font-bold"><?php echo $stats['registrations']; ?></span>
            </button>

            <button onclick="switchTab('messages')" id="nav-messages"
                    class="nav-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[11px] font-medium text-slate-400">
                <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                <span class="flex-1 text-left">Messages</span>
                <?php if ($stats['unread'] > 0): ?>
                <span class="px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-400 text-[9px] font-bold"><?php echo $stats['unread']; ?></span>
                <?php else: ?>
                <span class="px-1.5 py-0.5 rounded-full bg-sky-500/10 text-sky-400/70 text-[9px] font-bold"><?php echo $stats['messages']; ?></span>
                <?php endif; ?>
            </button>

            <div class="pt-4 pb-1"><p class="px-2 text-slate-600 text-[9px] font-semibold uppercase tracking-widest">Export</p></div>

            <button onclick="exportPDF()" class="nav-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[11px] font-medium text-slate-400">
                <svg class="w-4 h-4 flex-shrink-0 text-red-400/70" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>
                <span class="flex-1 text-left">Export PDF</span>
            </button>

            <button onclick="exportCSV()" class="nav-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[11px] font-medium text-slate-400">
                <svg class="w-4 h-4 flex-shrink-0 text-emerald-400/70" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                <span class="flex-1 text-left">Export CSV</span>
            </button>
        </nav>

        <!-- Sidebar footer — user + logout -->
        <div class="px-3 pb-4 pt-2 border-t border-white/[0.04] space-y-2">
            <a href="../" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[11px] font-medium text-slate-500 no-underline">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M10 19l-7-7m0 0l7-7m-7 7h18"/></svg>
                Back to Site
            </a>
            <div class="flex items-center gap-2.5 px-3 py-2">
                <div class="w-7 h-7 rounded-full bg-gradient-to-br from-sky-500 to-indigo-500 flex items-center justify-center flex-shrink-0">
                    <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
                </div>
                <div class="min-w-0 flex-1">
                    <p class="text-white text-[11px] font-medium truncate"><?php echo $admin_name; ?></p>
                    <p class="text-slate-600 text-[9px] capitalize"><?php echo $admin_role; ?></p>
                </div>
            </div>
            <a href="?action=logout" class="nav-item flex items-center gap-2.5 px-3 py-2 rounded-lg text-[11px] font-medium text-red-400/80 no-underline hover:text-red-400 hover:bg-red-500/[0.06]">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
                Logout
            </a>
        </div>
    </aside>

    <!-- ─── Main content ─── -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">

        <!-- Top bar (mobile hamburger + page title) -->
        <header class="flex items-center gap-3 px-4 sm:px-6 py-3 border-b border-white/[0.04] flex-shrink-0" style="background:rgba(8,12,24,0.7);backdrop-filter:blur(12px)">
            <button onclick="toggleSidebar()" class="lg:hidden w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.07] flex items-center justify-center text-slate-400 hover:text-white transition-colors">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
            </button>
            <div class="flex-1 min-w-0">
                <h1 id="page-title" class="text-white font-semibold text-sm">Registrations</h1>
                <p id="page-subtitle" class="text-slate-600 text-[10px]"><?php echo $stats['registrations']; ?> early access signups</p>
            </div>
            <!-- Quick stats -->
            <div class="hidden sm:flex items-center gap-4">
                <div class="text-center">
                    <p class="text-white font-bold text-lg leading-none"><?php echo $stats['registrations']; ?></p>
                    <p class="text-slate-600 text-[9px] mt-0.5">Signups</p>
                </div>
                <div class="w-px h-8 bg-white/[0.06]"></div>
                <div class="text-center">
                    <p class="text-white font-bold text-lg leading-none"><?php echo $stats['messages']; ?></p>
                    <p class="text-slate-600 text-[9px] mt-0.5">Messages</p>
                </div>
                <div class="w-px h-8 bg-white/[0.06]"></div>
                <div class="text-center">
                    <p class="text-amber-400 font-bold text-lg leading-none"><?php echo $stats['unread']; ?></p>
                    <p class="text-slate-600 text-[9px] mt-0.5">Unread</p>
                </div>
            </div>
        </header>

        <!-- Scrollable content -->
        <main class="flex-1 overflow-y-auto p-4 sm:p-6 no-scroll">

            <!-- ═══ Registrations Panel ═══ -->
            <div id="panel-registrations" class="anim">
                <?php if (empty($registrations)): ?>
                <div class="glass rounded-xl p-16 text-center">
                    <div class="w-14 h-14 mx-auto mb-4 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center">
                        <svg class="w-7 h-7 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                    </div>
                    <p class="text-slate-500 text-sm">No registrations yet</p>
                    <p class="text-slate-700 text-xs mt-1">Early access signups will appear here</p>
                </div>
                <?php else: ?>
                <div class="glass rounded-xl overflow-hidden">
                    <div class="overflow-x-auto no-scroll">
                        <table class="w-full text-xs">
                            <thead>
                                <tr class="border-b border-white/[0.06]">
                                    <th class="text-left px-4 py-3 text-slate-500 font-semibold text-[10px] uppercase tracking-widest">#</th>
                                    <th class="text-left px-4 py-3 text-slate-500 font-semibold text-[10px] uppercase tracking-widest">Name</th>
                                    <th class="text-left px-4 py-3 text-slate-500 font-semibold text-[10px] uppercase tracking-widest">Email</th>
                                    <th class="text-left px-4 py-3 text-slate-500 font-semibold text-[10px] uppercase tracking-widest">Phone</th>
                                    <th class="text-left px-4 py-3 text-slate-500 font-semibold text-[10px] uppercase tracking-widest">Country</th>
                                    <th class="text-left px-4 py-3 text-slate-500 font-semibold text-[10px] uppercase tracking-widest">Looking For</th>
                                    <th class="text-left px-4 py-3 text-slate-500 font-semibold text-[10px] uppercase tracking-widest">Skills</th>
                                    <th class="text-left px-4 py-3 text-slate-500 font-semibold text-[10px] uppercase tracking-widest">Field</th>
                                    <th class="text-left px-4 py-3 text-slate-500 font-semibold text-[10px] uppercase tracking-widest">Date</th>
                                    <th class="text-left px-4 py-3 text-slate-500 font-semibold text-[10px] uppercase tracking-widest"></th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php foreach ($registrations as $r): ?>
                                <tr id="reg-row-<?php echo $r['id']; ?>" class="row-hover border-b border-white/[0.03] transition-colors cursor-pointer"
                                    data-reg="<?php echo htmlspecialchars(json_encode([
                                        'id' => $r['id'],
                                        'first_name' => $r['first_name'],
                                        'last_name' => $r['last_name'],
                                        'email' => $r['email'],
                                        'phone' => $r['phone'],
                                        'country' => $r['country'],
                                        'user_type' => $r['user_type'] ?? 'talent',
                                        'opportunity_types' => $r['opportunity_types'],
                                        'skills' => $r['skills'],
                                        'preferred_field' => $r['preferred_field'],
                                        'referral_source' => $r['referral_source'] ?? '',
                                        'is_confirmed' => (int)($r['is_confirmed'] ?? 0),
                                        'created_at' => $r['created_at']
                                    ]), ENT_QUOTES); ?>"
                                    onclick="openRegistration(this)">
                                    <td class="px-4 py-3 text-slate-600"><?php echo $r['id']; ?></td>
                                    <td class="px-4 py-3 text-white font-medium whitespace-nowrap"><?php echo htmlspecialchars($r['first_name'].' '.$r['last_name']); ?></td>
                                    <td class="px-4 py-3 text-sky-400"><?php echo htmlspecialchars($r['email']); ?></td>
                                    <td class="px-4 py-3 text-slate-400"><?php echo htmlspecialchars($r['phone']); ?></td>
                                    <td class="px-4 py-3 text-slate-400"><?php echo htmlspecialchars($r['country']); ?></td>
                                    <td class="px-4 py-3"><?php
                                        $opps = array_filter(array_map('trim', explode(',', $r['opportunity_types'])));
                                        $oColors = ['volunteer'=>'emerald','internship'=>'sky','job'=>'amber','skillup'=>'violet'];
                                        foreach ($opps as $opp):
                                            $oc = isset($oColors[strtolower($opp)]) ? $oColors[strtolower($opp)] : 'slate';
                                    ?><span class="inline-block px-1.5 py-0.5 rounded text-[9px] font-semibold bg-<?php echo $oc;?>-500/15 text-<?php echo $oc;?>-400 mr-0.5 mb-0.5"><?php echo htmlspecialchars($opp);?></span><?php endforeach; ?></td>
                                    <td class="px-4 py-3 text-slate-400 max-w-[140px] truncate" title="<?php echo htmlspecialchars($r['skills']); ?>"><?php echo htmlspecialchars($r['skills']); ?></td>
                                    <td class="px-4 py-3 text-slate-400 max-w-[110px] truncate" title="<?php echo htmlspecialchars($r['preferred_field']); ?>"><?php echo htmlspecialchars($r['preferred_field']); ?></td>
                                    <td class="px-4 py-3 text-slate-600 whitespace-nowrap"><?php echo date('M j, Y H:i', strtotime($r['created_at'])); ?></td>
                                    <td class="px-4 py-3">
                                        <button onclick="event.stopPropagation();deleteRegistration(<?php echo $r['id']; ?>)" class="w-7 h-7 rounded-lg bg-red-500/10 border border-red-400/15 text-red-400 hover:bg-red-500/20 transition-all flex items-center justify-center" title="Delete">
                                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                                        </button>
                                    </td>
                                </tr>
                                <?php endforeach; ?>
                            </tbody>
                        </table>
                    </div>
                </div>
                <?php endif; ?>
            </div>

            <!-- ═══ Messages Panel ═══ -->
            <div id="panel-messages" class="hidden anim">
                <?php if (empty($messages)): ?>
                <div class="glass rounded-xl p-16 text-center">
                    <div class="w-14 h-14 mx-auto mb-4 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center">
                        <svg class="w-7 h-7 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                    </div>
                    <p class="text-slate-500 text-sm">No messages yet</p>
                    <p class="text-slate-700 text-xs mt-1">Contact form submissions will appear here</p>
                </div>
                <?php else: ?>
                <div class="space-y-2">
                    <?php foreach ($messages as $m): ?>
                    <div id="msg-row-<?php echo $m['id']; ?>" class="glass rounded-xl p-4 <?php echo $m['is_read']?'msg-read':'msg-unread'; ?> transition-all duration-300 cursor-pointer hover:border-white/[0.1]"
                         data-msg="<?php echo htmlspecialchars(json_encode([
                             'id' => $m['id'],
                             'full_name' => $m['full_name'],
                             'email' => $m['email'],
                             'phone' => $m['phone'],
                             'country' => $m['country'],
                             'message' => $m['message'],
                             'channel' => $m['channel'],
                             'created_at' => $m['created_at'],
                             'is_read' => (int)$m['is_read']
                         ]), ENT_QUOTES); ?>"
                         onclick="openMessage(this)">
                        <div class="flex items-start gap-3">
                            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-sky-500/20 to-indigo-500/20 border border-white/[0.06] flex items-center justify-center flex-shrink-0 mt-0.5">
                                <span class="text-white font-bold text-[10px]"><?php echo strtoupper(substr($m['full_name'],0,1)); ?></span>
                            </div>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2 mb-1">
                                    <h3 class="text-white font-semibold text-xs"><?php echo htmlspecialchars($m['full_name']); ?></h3>
                                    <?php if (!$m['is_read']): ?><span class="px-1.5 py-0.5 rounded-full bg-sky-500/15 text-sky-400 text-[8px] font-bold uppercase">New</span><?php endif; ?>
                                    <span class="text-slate-700 text-[10px] ml-auto flex-shrink-0"><?php echo date('M j, H:i', strtotime($m['created_at'])); ?></span>
                                </div>
                                <div class="flex items-center gap-3 mb-2 text-[10px] text-slate-500">
                                    <span><?php echo htmlspecialchars($m['email']); ?></span>
                                    <?php if($m['phone']):?><span><?php echo htmlspecialchars($m['phone']);?></span><?php endif;?>
                                    <?php if($m['country']):?><span><?php echo htmlspecialchars($m['country']);?></span><?php endif;?>
                                </div>
                                <p class="text-slate-300 text-[11px] leading-relaxed"><?php echo nl2br(htmlspecialchars($m['message'])); ?></p>
                            </div>
                            <div class="flex flex-col gap-1 flex-shrink-0">
                                <button onclick="event.stopPropagation();toggleRead(<?php echo $m['id'];?>)" class="w-7 h-7 rounded-lg transition-all flex items-center justify-center <?php echo $m['is_read']?'bg-white/[0.03] border border-white/[0.06] text-slate-500 hover:text-sky-400':'bg-sky-500/10 border border-sky-400/20 text-sky-400 hover:bg-sky-500/20';?>" title="<?php echo $m['is_read']?'Mark unread':'Mark read';?>">
                                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="<?php echo $m['is_read']?'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z':'M5 13l4 4L19 7';?>"/></svg>
                                </button>
                                <button onclick="event.stopPropagation();deleteMessage(<?php echo $m['id'];?>)" class="w-7 h-7 rounded-lg bg-red-500/10 border border-red-400/15 text-red-400 hover:bg-red-500/20 transition-all flex items-center justify-center" title="Delete">
                                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                                </button>
                            </div>
                        </div>
                    </div>
                    <?php endforeach; ?>
                </div>
                <?php endif; ?>
            </div>

        </main>
    </div>
</div>

<!-- ══════ Registration Detail Modal ══════ -->
<div id="reg-modal" class="fixed inset-0 z-[9998] hidden">
    <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" onclick="closeRegModal()"></div>
    <div class="absolute inset-0 flex items-center justify-center p-4 pointer-events-none">
        <div id="reg-modal-card" class="relative w-full max-w-md pointer-events-auto rounded-2xl overflow-hidden shadow-[0_30px_80px_rgba(0,0,0,0.6)] transform scale-95 opacity-0 transition-all duration-300"
             style="background:rgba(10,16,30,0.88);backdrop-filter:blur(28px);border:1px solid rgba(255,255,255,0.07)">
            <div class="h-px bg-gradient-to-r from-emerald-500 via-sky-400 to-indigo-500"></div>

            <button onclick="closeRegModal()" class="absolute top-4 right-4 w-7 h-7 rounded-lg bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/[0.1] transition-all z-10">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>

            <div class="p-6 max-h-[85vh] overflow-y-auto no-scroll">
                <!-- Header -->
                <div class="flex items-center gap-3 mb-5">
                    <div class="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-500/25 to-sky-500/25 border border-white/[0.08] flex items-center justify-center flex-shrink-0">
                        <span class="text-white font-bold text-sm" id="rm-initial">A</span>
                    </div>
                    <div class="min-w-0 flex-1">
                        <h2 id="rm-name" class="text-white font-semibold text-sm"></h2>
                        <p id="rm-date" class="text-slate-600 text-[10px]"></p>
                    </div>
                    <span id="rm-type" class="px-2 py-0.5 rounded-md text-[9px] font-semibold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-400/15">Talent</span>
                </div>

                <!-- Contact row -->
                <div class="flex flex-wrap gap-x-5 gap-y-1.5 mb-5">
                    <div class="flex items-center gap-1.5">
                        <svg class="w-3.5 h-3.5 text-sky-400/60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                        <a id="rm-email" href="#" class="text-sky-400 text-[11px] hover:underline"></a>
                    </div>
                    <div id="rm-phone-wrap" class="flex items-center gap-1.5 hidden">
                        <svg class="w-3.5 h-3.5 text-emerald-400/60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>
                        <a id="rm-phone" href="#" class="text-emerald-400 text-[11px] hover:underline"></a>
                    </div>
                    <div id="rm-country-wrap" class="flex items-center gap-1.5 hidden">
                        <svg class="w-3.5 h-3.5 text-amber-400/60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                        <span id="rm-country" class="text-slate-400 text-[11px]"></span>
                    </div>
                </div>

                <div class="h-px bg-white/[0.05] mb-5"></div>

                <!-- Details grid -->
                <div class="space-y-4">
                    <!-- Looking for -->
                    <div>
                        <p class="text-slate-600 text-[9px] font-semibold uppercase tracking-widest mb-2">Looking For</p>
                        <div id="rm-opps" class="flex flex-wrap gap-1.5"></div>
                    </div>
                    <!-- Skills -->
                    <div id="rm-skills-wrap">
                        <p class="text-slate-600 text-[9px] font-semibold uppercase tracking-widest mb-2">Skills</p>
                        <div id="rm-skills" class="flex flex-wrap gap-1.5"></div>
                    </div>
                    <!-- Preferred Field -->
                    <div id="rm-field-wrap">
                        <p class="text-slate-600 text-[9px] font-semibold uppercase tracking-widest mb-2">Preferred Field</p>
                        <div id="rm-fields" class="flex flex-wrap gap-1.5"></div>
                    </div>
                    <!-- Referral -->
                    <div id="rm-referral-wrap" class="hidden">
                        <p class="text-slate-600 text-[9px] font-semibold uppercase tracking-widest mb-1.5">Referral Source</p>
                        <p id="rm-referral" class="text-slate-400 text-[11px]"></p>
                    </div>
                    </div>
                </div>

                <!-- Footer actions -->
                <div class="flex items-center gap-2 mt-6 pt-4 border-t border-white/[0.05]">
                    <button onclick="rmReplyEmail()" class="flex-1 py-2 rounded-xl text-[11px] font-semibold transition-all bg-sky-500/10 border border-sky-400/15 text-sky-400 hover:bg-sky-500/20">Email</button>
                    <button onclick="rmDelete()" class="flex-1 py-2 rounded-xl text-[11px] font-semibold transition-all bg-red-500/10 border border-red-400/15 text-red-400 hover:bg-red-500/20">Delete</button>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- ══════ Message Detail Modal ══════ -->
<div id="msg-modal" class="fixed inset-0 z-[9998] hidden">
    <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" onclick="closeMessageModal()"></div>
    <div class="absolute inset-0 flex items-center justify-center p-4 pointer-events-none">
        <div id="msg-modal-card" class="relative w-full max-w-lg pointer-events-auto rounded-2xl overflow-hidden shadow-[0_30px_80px_rgba(0,0,0,0.6)] transform scale-95 opacity-0 transition-all duration-300"
             style="background:rgba(10,16,30,0.88);backdrop-filter:blur(28px);border:1px solid rgba(255,255,255,0.07)">
            <!-- Accent line -->
            <div class="h-px bg-gradient-to-r from-sky-500 via-cyan-400 to-indigo-500"></div>

            <!-- Close button -->
            <button onclick="closeMessageModal()" class="absolute top-4 right-4 w-7 h-7 rounded-lg bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/[0.1] transition-all z-10">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>

            <div class="p-6">
                <!-- Header -->
                <div class="flex items-center gap-3 mb-5">
                    <div id="mm-avatar" class="w-10 h-10 rounded-full bg-gradient-to-br from-sky-500/25 to-indigo-500/25 border border-white/[0.08] flex items-center justify-center flex-shrink-0">
                        <span class="text-white font-bold text-sm" id="mm-initial">A</span>
                    </div>
                    <div class="min-w-0 flex-1">
                        <h2 id="mm-name" class="text-white font-semibold text-sm"></h2>
                        <p id="mm-date" class="text-slate-600 text-[10px]"></p>
                    </div>
                    <span id="mm-channel" class="px-2 py-0.5 rounded-md text-[9px] font-semibold uppercase tracking-wider bg-white/[0.04] text-slate-500 border border-white/[0.06]"></span>
                </div>

                <!-- Contact info -->
                <div class="flex flex-wrap gap-x-5 gap-y-1.5 mb-5">
                    <div id="mm-email-wrap" class="flex items-center gap-1.5">
                        <svg class="w-3.5 h-3.5 text-sky-400/60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                        <a id="mm-email" href="#" class="text-sky-400 text-[11px] hover:underline"></a>
                    </div>
                    <div id="mm-phone-wrap" class="flex items-center gap-1.5 hidden">
                        <svg class="w-3.5 h-3.5 text-emerald-400/60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>
                        <a id="mm-phone" href="#" class="text-emerald-400 text-[11px] hover:underline"></a>
                    </div>
                    <div id="mm-country-wrap" class="flex items-center gap-1.5 hidden">
                        <svg class="w-3.5 h-3.5 text-amber-400/60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                        <span id="mm-country" class="text-slate-400 text-[11px]"></span>
                    </div>
                </div>

                <!-- Divider -->
                <div class="h-px bg-white/[0.05] mb-5"></div>

                <!-- Message body -->
                <div class="max-h-60 overflow-y-auto no-scroll pr-1">
                    <p id="mm-body" class="text-slate-300 text-xs leading-relaxed whitespace-pre-wrap"></p>
                </div>

                <!-- Footer actions -->
                <div class="flex items-center gap-2 mt-6 pt-4 border-t border-white/[0.05]">
                    <button id="mm-toggle-read" onclick="mmToggleRead()" class="flex-1 py-2 rounded-xl text-[11px] font-semibold transition-all bg-sky-500/10 border border-sky-400/15 text-sky-400 hover:bg-sky-500/20">Mark as read</button>
                    <button id="mm-delete" onclick="mmDelete()" class="flex-1 py-2 rounded-xl text-[11px] font-semibold transition-all bg-red-500/10 border border-red-400/15 text-red-400 hover:bg-red-500/20">Delete</button>
                    <button onclick="mmReplyEmail()" class="flex-1 py-2 rounded-xl text-[11px] font-semibold transition-all bg-emerald-500/10 border border-emerald-400/15 text-emerald-400 hover:bg-emerald-500/20">Reply via Email</button>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Toast -->
<div id="toast" class="fixed bottom-5 right-5 z-[9999] hidden">
    <div id="toast-inner" class="flex items-center gap-3 px-4 py-2.5 rounded-xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] border border-white/[0.07] translate-y-4 opacity-0 transition-all duration-300" style="background:rgba(10,16,30,0.92);backdrop-filter:blur(16px)">
        <div id="toast-icon" class="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"></div>
        <p id="toast-text" class="text-xs font-medium"></p>
    </div>
</div>

<script>
/* ── Sidebar toggle (mobile) ─────────────── */
function toggleSidebar(){
    var s=document.getElementById('sidebar'),o=document.getElementById('sidebar-overlay');
    var open=s.classList.contains('-translate-x-full');
    s.classList.toggle('-translate-x-full',!open);
    if(open){s.classList.add('sidebar-open');o.classList.remove('hidden');}
    else{s.classList.remove('sidebar-open');o.classList.add('hidden');}
}

/* ── Tab / panel switching ────────────────── */
var currentTab='registrations';
function switchTab(tab){
    currentTab=tab;
    document.getElementById('panel-registrations').classList.toggle('hidden',tab!=='registrations');
    document.getElementById('panel-messages').classList.toggle('hidden',tab!=='messages');
    document.querySelectorAll('.nav-item').forEach(function(b){b.classList.remove('nav-active');});
    var nb=document.getElementById('nav-'+tab); if(nb) nb.classList.add('nav-active');
    var t=document.getElementById('page-title'),s=document.getElementById('page-subtitle');
    if(tab==='registrations'){t.textContent='Registrations';s.textContent='<?php echo $stats["registrations"];?> early access signups';}
    else{t.textContent='Messages';s.textContent='<?php echo $stats["messages"];?> contact submissions (<?php echo $stats["unread"];?> unread)';}
    /* close mobile sidebar */
    if(window.innerWidth<1024){var sb=document.getElementById('sidebar');if(!sb.classList.contains('-translate-x-full')){toggleSidebar();}}
}

/* ── Toast ─────────────────────────────────── */
function showToast(msg,type){
    var t=document.getElementById('toast'),i=document.getElementById('toast-inner'),ic=document.getElementById('toast-icon'),tx=document.getElementById('toast-text');
    var c={success:{bg:'bg-emerald-500/15',bd:'border-emerald-400/20',tx:'text-emerald-400',sv:'<svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>'},error:{bg:'bg-red-500/15',bd:'border-red-400/20',tx:'text-red-400',sv:'<svg class="w-3.5 h-3.5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>'},info:{bg:'bg-sky-500/15',bd:'border-sky-400/20',tx:'text-sky-400',sv:'<svg class="w-3.5 h-3.5 text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'}};
    var s=c[type]||c.info;
    ic.className='w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 '+s.bg+' border '+s.bd;
    ic.innerHTML=s.sv; tx.className='text-xs font-medium '+s.tx; tx.textContent=msg;
    t.classList.remove('hidden');
    setTimeout(function(){i.classList.remove('translate-y-4','opacity-0');},10);
    setTimeout(function(){i.classList.add('translate-y-4','opacity-0');setTimeout(function(){t.classList.add('hidden');},300);},3500);
}

/* ── Toggle read ──────────────────────────── */
function toggleRead(id){
    var u=window.location.href.split('?')[0].split('#')[0];
    fetch(u+'?api=toggle_read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})})
    .then(function(r){return r.json();}).then(function(d){
        if(d.status==='ok'){var row=document.getElementById('msg-row-'+id);if(row){var wasU=row.classList.contains('msg-unread');row.classList.toggle('msg-unread');row.classList.toggle('msg-read');showToast(wasU?'Marked as read':'Marked as unread','success');}}
    }).catch(function(){showToast('Failed to update','error');});
}

/* ── Delete ────────────────────────────────── */
function deleteRegistration(id){
    if(!confirm('Delete this registration?'))return;
    var u=window.location.href.split('?')[0].split('#')[0];
    fetch(u+'?api=delete_registration',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})})
    .then(function(r){return r.json();}).then(function(d){if(d.status==='ok'){var row=document.getElementById('reg-row-'+id);if(row){row.style.cssText='opacity:0;transform:translateX(-20px);transition:all .3s';setTimeout(function(){row.remove();},300);}showToast('Registration deleted','success');}})
    .catch(function(){showToast('Failed to delete','error');});
}
function deleteMessage(id){
    if(!confirm('Delete this message?'))return;
    var u=window.location.href.split('?')[0].split('#')[0];
    fetch(u+'?api=delete_message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})})
    .then(function(r){return r.json();}).then(function(d){if(d.status==='ok'){var row=document.getElementById('msg-row-'+id);if(row){row.style.cssText='opacity:0;transform:translateX(-20px);transition:all .3s';setTimeout(function(){row.remove();},300);}showToast('Message deleted','success');}})
    .catch(function(){showToast('Failed to delete','error');});
}

/* ── Export CSV ────────────────────────────── */
function exportCSV(){
    var t=currentTab==='messages'?'messages_csv':'registrations_csv';
    window.location.href='/view?export='+t;
    showToast('Downloading '+currentTab+' as CSV...','info');
}

/* ── Export PDF ────────────────────────────── */
function exportPDF(){
    var jsPDF=window.jspdf.jsPDF,doc=new jsPDF({orientation:'landscape'});
    var now=new Date().toLocaleString('en-ZA',{dateStyle:'medium',timeStyle:'short'});
    doc.setFontSize(16);doc.setTextColor(15,76,129);doc.text('ForgeForth Africa',14,15);
    doc.setFontSize(10);doc.setTextColor(100);
    doc.text(currentTab==='messages'?'Contact Messages Report':'Early Access Registrations Report',14,22);
    doc.text('Generated: '+now,14,28);
    if(currentTab==='registrations'){
        var rows=[],tbl=document.querySelector('#panel-registrations table');
        if(tbl){tbl.querySelectorAll('tbody tr').forEach(function(tr){var c=tr.querySelectorAll('td');if(c.length>=9)rows.push([c[0].textContent.trim(),c[1].textContent.trim(),c[2].textContent.trim(),c[3].textContent.trim(),c[4].textContent.trim(),c[5].textContent.trim(),c[6].textContent.trim(),c[7].textContent.trim(),c[8].textContent.trim()]);});}
        doc.autoTable({startY:34,head:[['#','Name','Email','Phone','Country','Looking For','Skills','Field','Date']],body:rows,styles:{fontSize:7,cellPadding:2},headStyles:{fillColor:[15,76,129],textColor:[255,255,255],fontSize:7},alternateRowStyles:{fillColor:[245,247,250]},columnStyles:{6:{cellWidth:40},7:{cellWidth:30}}});
    }else{
        var rows=[];document.querySelectorAll('#panel-messages [id^="msg-row-"]').forEach(function(card){
            var nm=card.querySelector('h3')?card.querySelector('h3').textContent.trim():'';
            var info=card.querySelectorAll('.text-\\[10px\\]');var em='',ph='',co='',dt='';
            info.forEach(function(s){var t=s.textContent.trim();if(t.indexOf('@')>-1)em=t;else if(t.indexOf('+')===0)ph=t;else if(/[A-Z][a-z]+ \d/.test(t))dt=t;else if(t.length>1)co=t;});
            var mg=card.querySelector('.text-slate-300,.text-\\[11px\\].leading-relaxed')?card.querySelector('.text-slate-300,.text-\\[11px\\].leading-relaxed').textContent.trim():'';
            rows.push([nm,em,ph,co,mg.substring(0,100),dt]);
        });
        doc.autoTable({startY:34,head:[['Name','Email','Phone','Country','Message','Date']],body:rows,styles:{fontSize:7,cellPadding:2},headStyles:{fillColor:[15,76,129],textColor:[255,255,255],fontSize:7},alternateRowStyles:{fillColor:[245,247,250]},columnStyles:{4:{cellWidth:80}}});
    }
    var fn='forgeforth_'+currentTab+'_'+new Date().toISOString().slice(0,10)+'.pdf';
    doc.save(fn);showToast('PDF downloaded: '+fn,'success');
}

/* ── Registration Detail Modal ────────────── */
var rmCurrent=null;
function openRegistration(el){
    var d=JSON.parse(el.getAttribute('data-reg'));
    rmCurrent=d;
    document.getElementById('rm-initial').textContent=(d.first_name||'A').charAt(0).toUpperCase();
    document.getElementById('rm-name').textContent=(d.first_name+' '+d.last_name).trim();
    document.getElementById('rm-date').textContent='Registered '+new Date(d.created_at).toLocaleString('en-ZA',{dateStyle:'medium',timeStyle:'short'});
    document.getElementById('rm-type').textContent=d.user_type||'talent';
    document.getElementById('rm-email').textContent=d.email;
    document.getElementById('rm-email').href='mailto:'+d.email;
    if(d.phone){document.getElementById('rm-phone').textContent=d.phone;document.getElementById('rm-phone').href='tel:'+d.phone.replace(/\s/g,'');document.getElementById('rm-phone-wrap').classList.remove('hidden');}
    else{document.getElementById('rm-phone-wrap').classList.add('hidden');}
    if(d.country){document.getElementById('rm-country').textContent=d.country;document.getElementById('rm-country-wrap').classList.remove('hidden');}
    else{document.getElementById('rm-country-wrap').classList.add('hidden');}
    /* Opportunity pills */
    var oppsEl=document.getElementById('rm-opps');oppsEl.innerHTML='';
    var oc={'volunteer':'emerald','internship':'sky','job':'amber','skillup':'violet'};
    (d.opportunity_types||'').split(',').map(function(s){return s.trim();}).filter(Boolean).forEach(function(o){
        var c=oc[o.toLowerCase()]||'slate';
        oppsEl.innerHTML+='<span class="px-2 py-1 rounded-lg text-[10px] font-semibold bg-'+c+'-500/15 text-'+c+'-400 border border-'+c+'-400/15">'+o+'</span>';
    });
    /* Skills pills */
    var skEl=document.getElementById('rm-skills');skEl.innerHTML='';
    var skWrap=document.getElementById('rm-skills-wrap');
    var skills=(d.skills||'').split(',').map(function(s){return s.trim();}).filter(Boolean);
    if(skills.length){skWrap.style.display='';skills.forEach(function(s){skEl.innerHTML+='<span class="px-2 py-1 rounded-lg text-[10px] font-medium bg-violet-500/10 text-violet-400 border border-violet-400/10">'+s+'</span>';});}
    else{skWrap.style.display='none';}
    /* Fields pills */
    var flEl=document.getElementById('rm-fields');flEl.innerHTML='';
    var flWrap=document.getElementById('rm-field-wrap');
    var fields=(d.preferred_field||'').split(',').map(function(s){return s.trim();}).filter(Boolean);
    if(fields.length){flWrap.style.display='';fields.forEach(function(f){flEl.innerHTML+='<span class="px-2 py-1 rounded-lg text-[10px] font-medium bg-pink-500/10 text-pink-400 border border-pink-400/10">'+f+'</span>';});}
    else{flWrap.style.display='none';}
    /* Referral */
    if(d.referral_source){document.getElementById('rm-referral').textContent=d.referral_source;document.getElementById('rm-referral-wrap').classList.remove('hidden');}
    else{document.getElementById('rm-referral-wrap').classList.add('hidden');}
    /* Show */
    var modal=document.getElementById('reg-modal'),card=document.getElementById('reg-modal-card');
    modal.classList.remove('hidden');document.body.style.overflow='hidden';
    setTimeout(function(){card.classList.remove('scale-95','opacity-0');card.classList.add('scale-100','opacity-100');},10);
}
function closeRegModal(){
    var card=document.getElementById('reg-modal-card');
    card.classList.remove('scale-100','opacity-100');card.classList.add('scale-95','opacity-0');
    setTimeout(function(){document.getElementById('reg-modal').classList.add('hidden');document.body.style.overflow='';},250);
    rmCurrent=null;
}
function rmDelete(){
    if(!rmCurrent)return;
    deleteRegistration(rmCurrent.id);
    closeRegModal();
}
function rmReplyEmail(){
    if(!rmCurrent)return;
    var name=(rmCurrent.first_name+' '+rmCurrent.last_name).trim();
    var subject=encodeURIComponent('Welcome to ForgeForth Africa');
    var body=encodeURIComponent('Hi '+name+',\n\nThank you for your early access registration at ForgeForth Africa.\n\n');
    window.open('mailto:'+rmCurrent.email+'?subject='+subject+'&body='+body,'_blank');
}

/* ── Message Detail Modal ─────────────────── */
var mmCurrent=null;
function openMessage(el){
    var data=JSON.parse(el.getAttribute('data-msg'));
    mmCurrent=data;
    document.getElementById('mm-initial').textContent=data.full_name.charAt(0).toUpperCase();
    document.getElementById('mm-name').textContent=data.full_name;
    document.getElementById('mm-date').textContent=new Date(data.created_at).toLocaleString('en-ZA',{dateStyle:'medium',timeStyle:'short'});
    document.getElementById('mm-channel').textContent=data.channel||'direct';
    document.getElementById('mm-email').textContent=data.email;
    document.getElementById('mm-email').href='mailto:'+data.email;
    if(data.phone){document.getElementById('mm-phone').textContent=data.phone;document.getElementById('mm-phone').href='tel:'+data.phone.replace(/\s/g,'');document.getElementById('mm-phone-wrap').classList.remove('hidden');}
    else{document.getElementById('mm-phone-wrap').classList.add('hidden');}
    if(data.country){document.getElementById('mm-country').textContent=data.country;document.getElementById('mm-country-wrap').classList.remove('hidden');}
    else{document.getElementById('mm-country-wrap').classList.add('hidden');}
    document.getElementById('mm-body').textContent=data.message;
    /* Update read/unread button label */
    var readBtn=document.getElementById('mm-toggle-read');
    var row=document.getElementById('msg-row-'+data.id);
    var isUnread=row&&row.classList.contains('msg-unread');
    readBtn.textContent=isUnread?'Mark as read':'Mark as unread';
    /* Show modal with animation */
    var modal=document.getElementById('msg-modal');
    var card=document.getElementById('msg-modal-card');
    modal.classList.remove('hidden');
    document.body.style.overflow='hidden';
    setTimeout(function(){card.classList.remove('scale-95','opacity-0');card.classList.add('scale-100','opacity-100');},10);
    /* Auto-mark as read if unread */
    if(isUnread){
        toggleRead(data.id);
        data.is_read=1;
        readBtn.textContent='Mark as unread';
    }
}
function closeMessageModal(){
    var card=document.getElementById('msg-modal-card');
    card.classList.remove('scale-100','opacity-100');
    card.classList.add('scale-95','opacity-0');
    setTimeout(function(){document.getElementById('msg-modal').classList.add('hidden');document.body.style.overflow='';},250);
    mmCurrent=null;
}
function mmToggleRead(){
    if(!mmCurrent)return;
    toggleRead(mmCurrent.id);
    var readBtn=document.getElementById('mm-toggle-read');
    var row=document.getElementById('msg-row-'+mmCurrent.id);
    setTimeout(function(){
        var isNowUnread=row&&row.classList.contains('msg-unread');
        readBtn.textContent=isNowUnread?'Mark as read':'Mark as unread';
    },200);
}
function mmDelete(){
    if(!mmCurrent)return;
    deleteMessage(mmCurrent.id);
    closeMessageModal();
}
function mmReplyEmail(){
    if(!mmCurrent)return;
    var subject=encodeURIComponent('Re: Your message to ForgeForth Africa');
    var body=encodeURIComponent('Hi '+mmCurrent.full_name+',\n\nThank you for reaching out to ForgeForth Africa.\n\n---\nOriginal message:\n'+mmCurrent.message+'\n');
    window.open('mailto:'+mmCurrent.email+'?subject='+subject+'&body='+body,'_blank');
}
/* Close on Escape key */
document.addEventListener('keydown',function(e){if(e.key==='Escape'){if(mmCurrent)closeMessageModal();if(rmCurrent)closeRegModal();}});
</script>
<?php endif; ?>

</body>
</html>

