<?php
/**
 * ei_proxy.php — Proxy para Envíos Internacionales API
 * Subir a HostGator en: public_html/ei_proxy.php
 * URL resultante: https://tudominio.com/ei_proxy.php
 *
 * Seguridad: solo acepta requests con el header X-Proxy-Key correcto
 */

// ── CLAVE SECRETA — cámbiala y ponla igual en Render ──────────────
define('PROXY_KEY', 'PaqLlegue_EI_2026_xK9mZ');

// ── Verificar clave ────────────────────────────────────────────────
$key = $_SERVER['HTTP_X_PROXY_KEY'] ?? '';
if ($key !== PROXY_KEY) {
    http_response_code(403);
    echo json_encode(['error' => 'Acceso denegado']);
    exit;
}

// ── Leer request ───────────────────────────────────────────────────
$method   = $_SERVER['REQUEST_METHOD'];
$endpoint = $_GET['endpoint'] ?? '';   // ej: /oauth/token  o  /quotations
$body     = file_get_contents('php://input');
$ei_base  = 'https://app.enviosinternacionales.com/api/v1';
$url      = $ei_base . $endpoint;

if (!$endpoint) {
    http_response_code(400);
    echo json_encode(['error' => 'Falta ?endpoint=']);
    exit;
}

// ── Reenviar a EI ──────────────────────────────────────────────────
$headers_in = [];
foreach (getallheaders() as $k => $v) {
    $kl = strtolower($k);
    if (in_array($kl, ['content-type', 'authorization', 'accept'])) {
        $headers_in[] = "$k: $v";
    }
}

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_CUSTOMREQUEST  => $method,
    CURLOPT_HTTPHEADER     => $headers_in,
    CURLOPT_POSTFIELDS     => $body ?: null,
    CURLOPT_TIMEOUT        => 45,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_SSL_VERIFYPEER => true,
    CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
]);

$resp    = curl_exec($ch);
$code    = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$ct      = curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
$err     = curl_error($ch);
curl_close($ch);

if ($err) {
    http_response_code(502);
    echo json_encode(['error' => "cURL: $err"]);
    exit;
}

// ── Devolver respuesta de EI tal cual ─────────────────────────────
http_response_code($code);
header('Content-Type: ' . ($ct ?: 'application/json'));
echo $resp;
