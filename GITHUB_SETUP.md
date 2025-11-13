# GitHub Setup Instructions

## Repository Status

✅ Git initialized
✅ Files staged
✅ Initial commit created

## Next Steps: Connect to GitHub

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `DNStracking` (or your preferred name)
3. Description: "Marketing tracking system with UTM parameter capture and MongoDB storage"
4. Choose: **Private** (recommended) or Public
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"

### Step 2: Connect Local Repository to GitHub

After creating the repository, GitHub will show you commands. Use these:

```bash
# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/DNStracking.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

### Step 3: Authentication

If prompted for authentication:
- **Personal Access Token**: Use a GitHub Personal Access Token (not password)
- Create one at: https://github.com/settings/tokens
- Select scopes: `repo` (full control of private repositories)

## Alternative: Using SSH

If you prefer SSH:

```bash
git remote add origin git@github.com:YOUR_USERNAME/DNStracking.git
git push -u origin main
```

## What's Included in Repository

✅ All source code (src/)
✅ Flask application (app.py)
✅ Templates (templates/)
✅ Configuration files (data/)
✅ Scripts (scripts/)
✅ Documentation (README.md, etc.)
✅ .gitignore (protects .env, venv/, etc.)

## What's NOT Included (Protected by .gitignore)

❌ `.env` file (contains MongoDB password - keep this secret!)
❌ `venv/` directory (virtual environment)
❌ `__pycache__/` directories
❌ Database files
❌ Log files

## Important: Before Pushing

1. **Verify .env is NOT tracked:**
   ```bash
   git status
   ```
   You should NOT see `.env` in the list

2. **If .env appears, remove it:**
   ```bash
   git rm --cached .env
   git commit -m "Remove .env from tracking"
   ```

## After Pushing

Your repository will be available at:
```
https://github.com/YOUR_USERNAME/DNStracking
```

## Security Note

**NEVER commit your `.env` file!** It contains:
- MongoDB Atlas connection string with password
- Other sensitive configuration

The `.gitignore` file should protect this, but always verify before pushing.

