# IP Address Configuration Guide

This guide explains how to configure your application to capture real client IP addresses instead of just `127.0.0.1`.

## Current Issue

Your audit logs show:

```
Activity: api_access | IP: 127.0.0.1
Activity: login_success | User: 1a203ccda4 | IP: 127.0.0.1
```

This happens because the application is either:

1. Running locally (development)
2. Behind a proxy/load balancer that doesn't forward real IPs
3. Missing proper IP extraction configuration

## Solutions

### 1. For Local Development Testing

To test with different IP addresses locally, you can:

```bash
# Run the test script
cd backend
pipenv run python test_ip_extraction.py
```

Or manually send requests with headers:

```bash
curl -H "X-Forwarded-For: 203.0.113.195" http://127.0.0.1:8001/v1.0/analytics/test/health
curl -H "X-Real-IP: 198.51.100.42" http://127.0.0.1:8001/v1.0/analytics/test/health
```

### 2. For Production with Nginx

Configure nginx to forward real client IPs:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. For Production with Apache

Configure Apache to forward real client IPs:

```apache
<VirtualHost *:80>
    ServerName your-domain.com

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8001/
    ProxyPassReverse / http://127.0.0.1:8001/

    # Forward real IP
    ProxyAddHeaders On
    RemoteIPHeader X-Forwarded-For
</VirtualHost>
```

### 4. For Cloudflare

If using Cloudflare, the application automatically checks for `CF-Connecting-IP` header.

### 5. For AWS Application Load Balancer

AWS ALB automatically adds `X-Forwarded-For` headers. No additional configuration needed.

### 6. For Docker Deployment

If running in Docker, make sure to:

```yaml
# docker-compose.yml
version: "3.8"
services:
  app:
    build: .
    ports:
      - "8001:8001"
    environment:
      - FORWARDED_ALLOW_IPS=* # Allow all IPs to send forwarded headers
```

## Middleware Configuration

The application now includes `IPAddressMiddleware` that automatically extracts IPs from:

1. `X-Forwarded-For` (most common)
2. `X-Real-IP` (nginx)
3. `X-Client-IP`
4. `CF-Connecting-IP` (Cloudflare)
5. `Forwarded` (RFC 7239)
6. Direct client IP (fallback)

## Testing IP Extraction

### Method 1: Use the test endpoint

```bash
curl http://127.0.0.1:8001/v1.0/analytics/test/health
```

### Method 2: Test with custom headers

```bash
curl -H "X-Forwarded-For: 203.0.113.195" http://127.0.0.1:8001/v1.0/analytics/test/health
```

### Method 3: Run the test script

```bash
cd backend
pipenv run python test_ip_extraction.py
```

## Expected Results

After configuration, your audit logs should show real IPs:

```
Activity: api_access | IP: 203.0.113.195
Activity: login_success | User: 1a203ccda4 | IP: 203.0.113.195
```

## Security Considerations

1. **Trusted Proxies**: Configure `trusted_proxies` in the middleware to only accept forwarded headers from known proxy IPs
2. **Header Validation**: The middleware validates IP format to prevent injection
3. **Priority Order**: Headers are checked in priority order to get the most reliable IP

## Troubleshooting

### Still seeing 127.0.0.1?

1. Check if your reverse proxy is configured correctly
2. Verify headers are being sent: `curl -v http://your-domain.com/v1.0/analytics/test/health`
3. Check middleware configuration in `main.py`
4. Review proxy logs to ensure headers are being forwarded

### Getting wrong IPs?

1. Adjust the `trusted_proxies` configuration
2. Check the header priority order in the middleware
3. Verify your proxy isn't adding extra headers

### Need custom headers?

Modify `middleware/ip_middleware.py` to add support for your specific headers.

## Configuration Examples

### For Development

```python
# main.py
app.add_middleware(
    IPAddressMiddleware,
    trusted_proxies=['127.0.0.1', '::1', '192.168.0.0/16']
)
```

### For Production

```python
# main.py
app.add_middleware(
    IPAddressMiddleware,
    trusted_proxies=['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']  # Your proxy IPs
)
```

### For Cloudflare

```python
# main.py
app.add_middleware(
    IPAddressMiddleware,
    trusted_proxies=[]  # Cloudflare IPs (add specific ranges if needed)
)
```
