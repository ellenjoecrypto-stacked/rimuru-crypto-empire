# Security Policy

## Supported Versions

We take security seriously. The following versions are currently supported with security updates:

| Version | Supported          | Notes                           |
| ------- | ------------------ | ------------------------------- |
| 1.0.x   | :white_check_mark: | Current stable release          |
| < 1.0   | :x:                | Legacy versions, please upgrade |

## Security Features

### Credential Protection
- **AES-256-GCM Encryption**: All API keys and sensitive credentials are encrypted at rest
- **Secure Vault**: Encrypted credential storage with audit logging
- **Environment Variables**: Never commit secrets to the repository
- **2FA Support**: Two-factor authentication integration for supported exchanges

### API Security
- **Rate Limiting**: Protection against brute force and DDoS attacks
- **Input Validation**: Strict validation using Pydantic models
- **CORS Configuration**: Properly configured cross-origin resource sharing
- **Authentication**: JWT-based authentication with secure token handling

### Container Security
- **Non-root Containers**: All Docker containers run as non-root users
- **Network Isolation**: Services communicate over isolated Docker networks
- **Volume Permissions**: Restricted file system access
- **Minimal Images**: Using Alpine-based images to reduce attack surface

### Dependency Security
- **Regular Updates**: Dependencies are kept up-to-date with security patches
- **Vulnerability Scanning**: Automated scanning with pip-audit and npm audit
- **Pin Versions**: Specific versions pinned to prevent supply chain attacks

## Best Practices for Users

### API Key Management
1. **NEVER enable withdrawal permissions** on exchange API keys
2. **Use IP whitelisting** on your exchange accounts
3. **Rotate API keys** every 90 days minimum
4. **Store vault password** securely (password manager recommended)
5. **Enable 2FA** on all exchange accounts

### Deployment Security
1. **Use HTTPS** for all production deployments
2. **Configure firewall** to restrict access to necessary ports only
3. **Regular backups** of database and configuration
4. **Monitor logs** for suspicious activity
5. **Keep system updated** with latest security patches

### Trading Safety
1. **Start with paper trading** before using real funds
2. **Set strict loss limits** and respect them
3. **Never trade more** than you can afford to lose
4. **Review bot configuration** regularly
5. **Use emergency stop** feature when needed

## Reporting a Vulnerability

We appreciate responsible disclosure of security vulnerabilities.

### How to Report

**Please DO NOT report security vulnerabilities through public GitHub issues.**

Instead, please report security vulnerabilities by:

1. **Email**: Send details to the repository maintainer (check GitHub profile)
2. **GitHub Security Advisory**: Use the "Security" tab → "Report a vulnerability"

### What to Include

- **Description**: Clear description of the vulnerability
- **Impact**: Potential impact and severity assessment
- **Reproduction**: Step-by-step instructions to reproduce
- **Environment**: Version numbers, OS, configuration details
- **Suggestions**: Possible fix or mitigation (if known)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity
  - Critical: 1-3 days
  - High: 1-2 weeks
  - Medium: 2-4 weeks
  - Low: Next release cycle

### Disclosure Policy

- We will coordinate disclosure timing with the reporter
- Security advisories will be published after fixes are released
- Credit will be given to reporters (unless anonymity is requested)

## Security Checklist for Developers

Before deploying changes:

- [ ] All dependencies updated to latest secure versions
- [ ] No hardcoded credentials or secrets in code
- [ ] Input validation implemented for all user inputs
- [ ] Authentication/authorization checks in place
- [ ] Error messages don't leak sensitive information
- [ ] Logging doesn't include sensitive data
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (proper output encoding)
- [ ] CSRF protection enabled
- [ ] Rate limiting configured
- [ ] Security headers set correctly
- [ ] Dependencies scanned for vulnerabilities

## Known Security Considerations

### Trading Risks
- **Market Volatility**: Cryptocurrency markets are highly volatile
- **Exchange Risk**: Third-party exchange security is outside our control
- **API Reliability**: Exchange API downtime can affect trading operations
- **Smart Contract Risk**: DeFi integrations carry smart contract risks

### Technical Limitations
- **No guarantees**: Software provided "as is" without warranties
- **Testing**: Thoroughly test in paper trading mode before live trading
- **Monitoring**: Active monitoring required during trading operations
- **Backup**: Always maintain secure backups of configuration and data

## Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Docker Security Best Practices](https://docs.docker.com/develop/security-best-practices/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

---

**Last Updated**: 2026-02-17

For questions about this security policy, please contact the project maintainers.
