# Security Configuration

## Database Credentials

**IMPORTANT**: Never commit real database credentials to version control!

### Setup

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your actual credentials:
```bash
nano .env  # or your preferred editor
```

3. Load environment variables before running SLM:
```bash
source .env
uv run slm submit job.sh
```

### Environment Variables

Required variables:
- `SLM_DB_HOST` - MySQL server hostname
- `SLM_DB_USER` - Database username
- `SLM_DB_PASSWORD` - Database password (strong password recommended)
- `SLM_DB_NAME` - Database name

Optional variables:
- `SLM_DB_PORT` - MySQL port (default: 3306)
- `SLM_API_URL` - API service URL (default: http://10.11.100.251:9008)

### Security Best Practices

1. **Never** commit `.env` file (it's in `.gitignore`)
2. Use strong passwords for database accounts
3. Restrict database user privileges (only necessary permissions)
4. Rotate passwords regularly
5. Use different credentials for development/production

### Local Development

For local development, create a `.env.local` file:
```bash
cp .env.example .env.local
# Edit .env.local with local database credentials
source .env.local
```

`.env.local` is also in `.gitignore` for safety.
