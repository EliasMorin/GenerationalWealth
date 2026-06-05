#!/bin/bash
#
# Nginx setup script for GenerationalWealth application
# This script configures Nginx to reverse proxy to the Flask application
#

set -euo pipefail

# Configuration variables
DOMAIN="generationalwealth.duckdns.org"
APP_PORT=5000
NGINX_SITE_AVAILABLE="/etc/nginx/sites-available/$DOMAIN"
NGINX_SITE_ENABLED="/etc/nginx/sites-enabled/$DOMAIN"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    log_error "Please run this script with sudo:"
    log_error "sudo $0"
    exit 1
fi

log_info "Starting Nginx setup for $DOMAIN"

# Check if the application is running on the expected port
if ! ss -tlnp | grep -q ":$APP_PORT "; then
    log_warn "No process listening on port $APP_PORT"
    log_warn "Make sure your Flask application is running:"
    log_warn "  cd /path/to/GenerationalWealth"
    log_warn "  source venv/bin/activate"
    log_warn "  python3 run.py"
    # Don't exit - Nginx config can still be applied
fi

# Backup existing configuration if it exists
if [ -L "$NGINX_SITE_ENABLED" ] || [ -f "$NGINX_SITE_ENABLED" ]; then
    log_info "Backing up existing Nginx configuration..."
    cp "$NGINX_SITE_ENABLED" "${NGINX_SITE_ENABLED}.backup.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
fi

# Create sites-available directory if it doesn't exist
mkdir -p /etc/nginx/sites-available

# Create the Nginx configuration
log_info "Creating Nginx configuration for $DOMAIN"
cat > "$NGINX_SITE_AVAILABLE" << EOF
server {
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
}

server {
    if (\$host = $DOMAIN) {
        return 301 https://\$host\$request_uri;
    } # managed by Certbot

    listen 80;
    server_name $DOMAIN;
    return 404; # managed by Certbot
}
EOF

# Create symbolic link from sites-available to sites-enabled
log_info "Enabling site in Nginx..."
ln -sf "$NGINX_SITE_AVAILABLE" "$NGINX_SITE_ENABLED"

# Test Nginx configuration
log_info "Testing Nginx configuration..."
if nginx -t; then
    log_info "Nginx configuration test PASSED"
else
    log_error "Nginx configuration test FAILED"
    log_error "Please check the configuration above"
    exit 1
fi

# Reload Nginx to apply changes
log_info "Reloading Nginx..."
if systemctl reload nginx; then
    log_info "Nginx reloaded successfully"
else
    log_warn "Failed to reload Nginx with systemctl, trying service command..."
    if service nginx reload; then
        log_info "Nginx reloaded successfully via service command"
    else
        log_error "Failed to reload Nginx"
        exit 1
    fi
fi

# Final verification
log_info "Verifying Nginx is active..."
if systemctl is-active --quiet nginx; then
    log_info "Nginx is running and active"
else
    log_warn "Nginx does not appear to be active. Please check:"
    log_warn "  systemctl status nginx"
    log_warn "  journalctl -u nginx"
fi

log_info "Nginx setup completed successfully!"
log_info ""
log_info "Your application should now be accessible at:"
log_info "  https://$DOMAIN"
log_info ""
log_info "To test the configuration:"
log_info "  curl -I https://$DOMAIN"
log_info "  curl -I https://$DOMAIN/api/claude/status"
log_info ""
log_info "Remember to keep your Flask application running:"
log_info "  python3 run.py"